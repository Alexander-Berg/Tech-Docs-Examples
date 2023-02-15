import math
import os
from typing import Dict
import csv

from tp_api_client.tp_api_client import TestPalmClient

OAUTH_TOKEN_TESTPALM = os.environ['OAUTH_TOKEN_TESTPALM']

PROJECT: str = 'mobilemail'

version_name_to_overlap: Dict[str, int] = {
    'android_acceptance': 3,
    'android_bl_prod': 1,
    'android_bl_beta': 1,
    'android_update': 3,
}

version_name_to_suite_id: Dict[str, str] = {
    'android_acceptance': '5da6dc460d441f1e03472043',
    'android_bl_prod': '5f297c90b9a54406dde9d19e',
    'android_bl_beta': '616d84d5627a5200221437ee',
    'android_update': '5e7e220e396e4d1e0c3332c3',
}


def get_estimate_time_for_version(suite_estimate_time_min: float, overlap: int) -> float:
    runs_number = math.ceil(suite_estimate_time_min / 10)
    prepare_time_min, k = 5, 1.5
    return round(((suite_estimate_time_min * overlap + runs_number * prepare_time_min * overlap) * k) / 60, 2)


def read_csv(filename: str, project: str = PROJECT):
    with open(filename) as fp:
        return [row for row in csv.reader(fp, delimiter=";", quotechar='"') if row[0] == project]


def get_suite_et_from_cases_et(cases_et_list) -> float:
    return sum(cases_et_list) / 1000 / 60


if __name__ == '__main__':
    new_et_data = read_csv('et.csv')
    client = TestPalmClient(auth=OAUTH_TOKEN_TESTPALM)

    old_total_et, new_total_et = 0, 0

    for version, overlap in version_name_to_overlap.items():
        testcases_from_suite = client.get_testcases_from_suite(project=PROJECT,
                                                               suite_id=version_name_to_suite_id[version])

        old_case_id_to_et = {testcase['id']: testcase['estimatedTime'] for testcase in testcases_from_suite}
        old_testsuite_et = get_suite_et_from_cases_et(old_case_id_to_et.values())
        new_case_id_to_et = old_case_id_to_et.copy()

        for data in new_et_data[1:]:
            case_id = int(data[1])
            new_et = float(data[3].replace(',', '.'))
            if case_id in new_case_id_to_et:
                new_case_id_to_et[case_id] = new_et

        new_testsuite_et = get_suite_et_from_cases_et(new_case_id_to_et.values())

        old_et_for_version = get_estimate_time_for_version(old_testsuite_et, overlap)
        new_et_for_version = get_estimate_time_for_version(new_testsuite_et, overlap)

        old_total_et += old_et_for_version * 5
        new_total_et += new_et_for_version * 5

        print(f'Версия `{version}`\n'
              f'Используется: {old_et_for_version} ч/ч\n'
              f'Станет необходимо: {new_et_for_version} ч/ч\n\n')

    print(f'На регулярные брони в месяц используется: {old_total_et} ч/ч\n'
          f'Станет необходимо: {new_total_et} ч/ч\n'
          f'Разница: {round(((new_total_et - old_total_et) / old_total_et) * 100, 1)} %')
