import json
import logging
import os
from collections import Counter
from datetime import datetime, timedelta

import requests
from retrying import retry

from set_secret import set_secret

FORMAT = '%(asctime)s:%(levelname)s:%(name)s:%(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)

AUTOTEST_FILTER = {
    "type": "AND",
    "left": {
        "type": "IN",
        "key": "modifiedBy",
        "value": [
            "robot-aqua-testpers"
        ]
    },
    "right": {
        "type": "AND",
        "left": {
            "type": "IN",
            "key": "runTestCase.status",
            "value": [
                "PASSED",
                "BROKEN",
                "FAILED",
            ]
        },
        "right": {
            "type": "EQ_CS",
            "key": "type",
            "value": "IN_RUN_UPDATED"
        }
    }
}

AUTOTEST_FILTER_SKIPPED = {
    "type": "AND",
    "left": {
        "type": "IN",
        "key": "modifiedBy",
        "value": [
            "robot-aqua-testpers"
        ]
    },
    "right": {
        "type": "AND",
        "left": {
            "type": "IN",
            "key": "runTestCase.status",
            "value": [
                "SKIPPED"
            ]
        },
        "right": {
            "type": "EQ_CS",
            "key": "type",
            "value": "IN_RUN_UPDATED"
        }
    }
}


class TestCase:
    def __init__(self, id, estimated_time):
        self.id = id
        self.estimated_time = estimated_time

    def __repr__(self):
        return f'{{id: {self.id}, estimated_time: {self.estimated_time}}}'


class TestPalm:

    def __init__(self, testpalm_project):
        self.testpalm_project = testpalm_project
        self.host = 'https://testpalm-api.yandex-team.ru'
        self.headers_testpalm = {'Authorization': f'OAuth {os.environ["TESTPALM_OAUTH"]}',
                                 'Content-Type': 'application/json'}
        self.definitions = self.request_testpalm_definitions()
        self.bro_index = 0

    @retry(stop_max_attempt_number=5)
    def request_testpalm_definitions(self):
        r = requests.get(
            f'{self.host}/definition/{self.testpalm_project}',
            headers=self.headers_testpalm,
            verify=False,
            timeout=5,
        )
        if r.status_code != 200:
            logging.info(r.text)
        return r.json()

    def get_definition(self, definition_from_settings):
        for definition in self.definitions:
            if definition['title'] == definition_from_settings:
                return definition

    def get_attribute_key(self, attribute_name):
        if attribute_name in ['isAutotest', 'status']:
            return attribute_name
        return 'attributes.' + self.get_definition(attribute_name)['id']

    def count_cases_by_filter(self, cases_filter):
        return len(self.request_testpalm_cases_by_filter(cases_filter))

    @staticmethod
    def get_cases_for_run(cases):
        run_case_ids = []
        for i in range(len(cases)):
            if cases[i].get('estimatedTime', 0) == 0:
                case_time = 120
                logging.info("not timed!")
            else:
                case_time = cases[i]["estimatedTime"] / 1000
            run_case_ids.append(TestCase(cases[i]["id"], case_time))
            # logging.info(run_case_ids[i])
        return run_case_ids

    @retry(stop_max_attempt_number=3)
    def request_testpalm_cases_by_filter(self, cases_filter):
        print(cases_filter)
        r = requests.get(
            f'{self.host}/testcases/{self.testpalm_project}/',
            headers=self.headers_testpalm,
            params={
                'include': 'id,history',
                'expression': str(cases_filter).replace("'", '"')
            },
            verify=False,
            timeout=120,
        )
        if r.status_code != 200:
            logging.info(r.text)

        return json.loads(r.text)

    @retry(stop_max_attempt_number=10)
    def get_eventslog_for_case(self, case):
        data = []
        r = requests.get(
            f'{self.host}/eventslog/{self.testpalm_project}',
            headers=self.headers_testpalm,
            params={
                'testcaseId': case['id'],
                'expression': str(AUTOTEST_FILTER).replace("'", '"'),
                "limit": 100,
                'include': 'runTestCase.status,modifiedBy,lastModifiedTime'
            },
            verify=False,
            timeout=5,
        ).json()
        skipped = requests.get(
            f'{self.host}/eventslog/{self.testpalm_project}',
            headers=self.headers_testpalm,
            params={
                'testcaseId': case['id'],
                'expression': str(AUTOTEST_FILTER_SKIPPED).replace("'", '"'),
                "limit": 50,
                'include': 'testRunTitle,lastModifiedTime'
            },
            verify=False,
            timeout=5,
        ).json()
        statuses = list(filter(lambda x: x.get('modifiedBy', '') == 'robot-aqua-testpers', r))
        for status in statuses:
            data.append({
                'status': status['runTestCase']['status'],
                'time': status['lastModifiedTime']
            })
        if len(statuses) == 0:
            return {
                'stat': {"PASSED": 0,
                         "BROKEN": 0,
                         "FAILED": 0},
                'lastModified': 0,
                'isIgnoredTemporary': self.is_ignored_temporary_today(skipped)
            }
        print(case['id'])
        print(data)
        return {
            'stat': Counter(list([x['status'] for x in data])),
            'lastModified': max([x['time'] for x in data]),
            'isIgnoredTemporary': self.is_ignored_temporary_today(skipped)
        }

    @retry(stop_max_attempt_number=5)
    def change_tag_in_case_attribute(self, ids, attribute, tag, mode):
        """
        :param ids: список id кейсов
        :param attribute: ключ, в котором мы что-то меняем
        :param tag: тег, который мы добавляем/удалем из ключа
        :param mode: если 0 - удаление, если 1 - добавление
        :return: ничего
        """
        print(f'mode: {mode}, tag: {tag}')
        cases_to_patch = []
        if len(ids) == 0:
            print('no cases to change')
            return
        attribute_to_add = self.get_attribute_key(attribute).split('.')[1]
        cases = self.get_cases(ids).json()
        for case in cases:
            if 'attributes' not in case:
                print(f'========CASE HAVE NO ATTRIBUTES AT ALL========{case["id"]}')
                case['attributes'] = {}
            case_attribute = case['attributes']
            if attribute_to_add not in case_attribute:
                print(f'========CASE HAVE NO ATTRIBUTE========{case["id"]}')
                case_attribute[attribute_to_add] = []
            if mode:
                case_attribute[attribute_to_add].append(tag)
            else:
                case_attribute[attribute_to_add].remove(tag)
            # print(case_attribute)
            cases_to_patch.append({
                'id': case['id'],
                'attributes': case_attribute
            })
        r = requests.patch(
            f'{self.host}/testcases/{self.testpalm_project}/bulk',
            headers=self.headers_testpalm,
            data=json.dumps(cases_to_patch),
            verify=False,
            timeout=20,
        )
        print(r.json())

    @staticmethod
    def is_ignored_temporary_today(events):
        for event in events:
            if datetime.fromtimestamp(int(event.get('lastModifiedTime', 0)) /
                                      1000) > datetime.now() - timedelta(days=2):
                if (event.get('testRunTitle', '').find('Смоук') == -1) & \
                        (event.get('testRunTitle', '').find('Smoke') == -1):
                    return 1
        return 0

    @retry(stop_max_attempt_number=3)
    def get_case(self, id):
        case = requests.get(
            f'{self.host}/testcases/{self.testpalm_project}/',
            headers=self.headers_testpalm,
            params={
                'id': str(id),
                'include': 'attributes',
            },
            verify=False,
            timeout=120,
        )
        return case

    @retry(stop_max_attempt_number=3)
    def get_cases(self, id):
        case = requests.get(
            f'{self.host}/testcases/{self.testpalm_project}/',
            headers=self.headers_testpalm,
            params={
                'id': id,
                'include': 'id,attributes',
            },
            verify=False,
            timeout=120,
        )
        return case


if __name__ == '__main__':
    set_secret.set_secrets()
    testpalm = TestPalm('mail-liza')
    # cases = testpalm.get_cases(['1554', '1436'])
    # print(cases.json())
