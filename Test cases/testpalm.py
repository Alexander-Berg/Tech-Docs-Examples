import copy
import json
import logging
import os
import re
import sys
import uuid
from enum import Enum
from typing import List

import requests
from retrying import retry

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.split(dir_path)[0])

from assessors.project_configs import start_cases, finish_cases, tag_for_environment
import utils.testpalm_filter_convertor as filter_converter

FORMAT = '%(asctime)s:%(levelname)s:%(name)s:%(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)


class TestCase:
    def __init__(self, id, estimated_time):
        self.id = id
        self.estimated_time = estimated_time

    def __repr__(self):
        return f'{{id: {self.id}, estimated_time: {self.estimated_time}}}'


class RunCreationMode(Enum):
    FULL_COVERAGE = 0
    ONE_BRO_PER_SUITE = 1
    TWO_BRO_PER_SUITE = 2
    GET_FROM_CONFIG = 3


class TestPalm:
    SUITE_JSON_FOR_API = {
        'title': '',  # название сьюта
        'version': '',  # имя версии в пальме, с которой слинкуем ран
        'environments': [{
            'title': '',  # название окружения, в котором будет проходиться сьют
            'description': '',  # название окружения, в котором будет проходиться сьют
            'default': False}],
        'testGroups': [{  # наполнение сьюта. Либо testSuite: string либо testCases: {}
            'path': [],
            'defaultOrder': True,
            'testCases': []
        }],
        'runnerConfig': None,
        'status': 'CREATED',
        'tags': []
    }

    TEST_CASE_JSON_FOR_API = {  # пихаем в suite.testGroups[i].testCases
        'testCase': {
            'id': '',  # id кейса
            'status': 'ACTUAL'
        },
        'status': 'CREATED'
    }

    TRACKER_VERSION_JSON_FOR_API = {
        'groupId': 'MAILEXP',
        'isClosed': False,
        'trackerId': 'Startrek',
        'versionId': '',
        'url': 'https://st.yandex-team.ru/MAILEXP/filter?fixVersions='
    }

    TRACKER_ISSUE_JSON_FOR_API = {
        'groupId': 'MAILEXP',
        'trackerId': 'Startrek',
        'id': '',
    }

    def __init__(self, testpalm_project):
        self.testpalm_project = testpalm_project
        self.host = 'https://testpalm-api.yandex-team.ru'
        self.headers_testpalm = {'Authorization': f'OAuth {os.environ["TESTPALM_OAUTH"]}',
                                 'Content-Type': 'application/json'}
        self.definitions = self.request_testpalm_definitions()
        self.bro_index = 0
        self.run_creation_mode = RunCreationMode.FULL_COVERAGE
        self.start_cases = start_cases.get(testpalm_project, [])
        self.finish_cases = finish_cases.get(testpalm_project, [])

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

    def create_version_tp(self, version_name, stand='', requester=''):
        url = f'{self.host}/version/{self.testpalm_project}'
        data = {
            'id': f'{version_name}',
            'description': f'stand: {stand}\nversion: {self.parse_version(version_name)}.*\ninterested: olga-ganchikova, {requester}'
        }
        # TODO: https://st.yandex-team.ru/TESTPALM-2594
        # if startreck_version:
        #     tracker_version = copy.deepcopy(self.TRACKER_VERSION_JSON_FOR_API)
        #     tracker_version['versionId'] = str(startreck_version)
        #     tracker_version['url'] = tracker_version['url'] + str(startreck_version)
        #     data['trackerVersion'] = tracker_version
        raw_data = json.dumps(data, ensure_ascii=False, separators=(',', ': ')).encode('utf-8')
        requests.post(url, headers=self.headers_testpalm, verify=False, data=raw_data)

    def get_attribute_key(self, attribute_name):
        if attribute_name in ['isAutotest', 'status']:
            return attribute_name
        return 'attributes.' + self.get_definition(attribute_name)['id']

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

    def count_cases_by_filter(self, cases_filter):
        return len(self.request_testpalm_cases_by_filter(cases_filter))

    def build_testpalm_filter(self, text_filter):
        return filter_converter.convert_filter(self, text_filter)

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

    @retry(stop_max_attempt_number=10)
    def request_testpalm_cases_by_suite(self, suite_id):
        cases = []
        r = requests.get(
            f'{self.host}/testcases/{self.testpalm_project}/suite/{suite_id}?include=id,estimatedTime',
            headers=self.headers_testpalm,
            verify=False
        )
        for case in r.json():
            cases.append(TestCase(case['id'], case.get('estimatedTime', 120000)))
        return cases

    @retry(stop_max_attempt_number=10)
    def request_testpalm_cases_by_filter(self, cases_filter):
        r = requests.get(
            f'{self.host}/testcases/{self.testpalm_project}',
            headers=self.headers_testpalm,
            params={
                'include': 'id,estimatedTime,attributes',
                'expression': cases_filter
            },
            verify=False,
            timeout=5,
        )
        if r.status_code != 200:
            logging.info(r.text)

        return self.get_cases_for_run(json.loads(r.text))

    def create_runs_with_time_limit(self, cases: List[TestCase], environment, testpalm_version):
        cases_to_run = []
        suite_time = 0
        run_num = 0
        left_cases_timing = 0
        correction = 0
        sum_suit_time = 0
        for case in cases:
            left_cases_timing += int(case.estimated_time)
        logging.info("Estimated time for all run is " + str(left_cases_timing / 60) + " min")
        if left_cases_timing // 2400 >= 2:
            time_for_suite = 2400
        else:
            time_for_suite = left_cases_timing
        for case in cases:
            cases_to_run.append(case)
            suite_time += int(case.estimated_time)
            left_cases_timing -= int(case.estimated_time)
            if suite_time >= time_for_suite - correction:
                self.create_run_from_cases(cases_to_run, environment, testpalm_version)
                run_num += 1
                sum_suit_time += suite_time
                logging.info("Run time: {} min".format((int(suite_time) // 60)))
                logging.info("Time left: {} min".format(int(left_cases_timing) // 60))
                cases_to_run = []
                suite_time = 0
                logging.info("")
                if left_cases_timing < 3600:
                    if left_cases_timing < 1800:
                        correction = time_for_suite - left_cases_timing
                    else:
                        correction = time_for_suite - left_cases_timing
        if len(cases_to_run) > 1:
            self.create_run_from_cases(cases_to_run, environment, testpalm_version)
            run_num += 1
            sum_suit_time += suite_time
        logging.info("")
        logging.info("Number of runs: {}".format(run_num))
        logging.info("Total time: {} hours".format(int(sum_suit_time) // 3600))

    @retry(wait_fixed=5000, stop_max_attempt_number=3)
    def create_run_from_cases(self, cases, environment, testpalm_version='', task_key=''):
        logging.info("Run creation...")
        logging.info(f'Running in {self.run_creation_mode.name} {self.run_creation_mode.value} regime')

        cases = list(map(lambda x: x.id, cases))
        # удаляем старт и финиш кейсы и потом возвращаем их в правильный порядок
        cases = list(set(cases) - set(self.start_cases) - set(self.finish_cases))
        cases = self.start_cases + cases + self.finish_cases

        if self.run_creation_mode.value != 0:
            bros = []
            for i in range(0, self.run_creation_mode.value):
                bros.append(environment[self.bro_index % len(environment)])
                self.bro_index += 1
            environment = bros
        for version_of_env in environment:
            data = copy.deepcopy(self.SUITE_JSON_FOR_API)
            data['title'] = f'Suite for {version_of_env} {uuid.uuid4()}'
            data['version'] = testpalm_version
            data['environments'][0]['title'] = version_of_env
            data['environments'][0]['description'] = version_of_env

            if self.testpalm_project in tag_for_environment:
                if version_of_env in tag_for_environment[self.testpalm_project]:
                    data['tags'].append(tag_for_environment[self.testpalm_project][version_of_env])

            for case in cases:
                case_json = copy.deepcopy(self.TEST_CASE_JSON_FOR_API)
                case_json['testCase']['id'] = case
                # noinspection PyUnresolvedReferences
                data["testGroups"][0]["testCases"].append(case_json)
            data["testGroups"][0]["defaultOrder"] = False

            if task_key:
                issue_json = copy.deepcopy(self.TRACKER_ISSUE_JSON_FOR_API)
                issue_json['id'] = task_key
                data['parentIssue'] = issue_json

            logging.info(data)
            raw_body = json.dumps(data, ensure_ascii=False, separators=(',', ': ')).encode('utf-8')
            url = f'{self.host}/testrun/{self.testpalm_project}/create?includeOnlyExisted=True'
            r = requests.post(
                url,
                headers=self.headers_testpalm,
                verify=False,
                data=raw_body
            )

    def set_run_creation_mode(self, mode: RunCreationMode):
        """
        Устанавливает режим создания ранов. Есть два режима RunCreationMode:
        * FULL_COVERAGE: каждый собранный сьют проходится во всех окружениях
        * ONE_BRO_PER_SUITE: каждый собранный сьют проходится в одном окружении.
        По умолчанию работаем в режиме FULL_COVERAGE.
        """
        self.run_creation_mode = mode

    @staticmethod
    def parse_version(condition):
        versions = re.findall('[0-9]+[.\-_][0-9]+|pr-[0-9]+|liza-[0-9]+', condition)
        version = f'{versions[0]}' if len(versions) > 0 else ''
        if re.match('[0-9]+[\-_][0-9]+', version):
            version = version.replace('-', '.').replace('_', '.')
        return version

    def set_start_cases(self, cases):
        self.start_cases[self.testpalm_project] = cases

    def set_finish_cases(self, cases):
        self.finish_cases[self.testpalm_project] = cases

    def make_runs_from_filter(self, filter, environment, testpalm_version):
        """Создаёт раны по фильтру с лимитом по времени"""
        cases = self.request_testpalm_cases_by_filter(filter)
        self.create_runs_with_time_limit(cases, environment, testpalm_version)

    def make_runs_from_suites(self, suites_ids, environment, testpalm_version, task_key=''):
        """Создаёт раны из сьютов as is"""
        for suite_id in suites_ids:
            cases = self.request_testpalm_cases_by_suite(suite_id)
            self.create_run_from_cases(cases, environment, testpalm_version, task_key=task_key)
