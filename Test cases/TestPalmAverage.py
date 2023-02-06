# -*- coding: utf-8 -*-
import datetime
import json
import logging
import os

import numpy
import requests
import urllib3
import yaml

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(
    format='%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', level=logging.INFO)
scriptPath = os.path.dirname(os.path.abspath(__file__) + '/SupportQueueMonitoring')
yaconfig = yaml.load(open(os.path.dirname(scriptPath) + '/config.yaml'))
dateLimit = yaconfig['dateLimit']


def is_assessor_version(version):
    if 'As' in version:
        return True


def is_autotest(testrun):
    return testrun['launcherInfo']['external'] == "True"


# from 01.08.2018
def is_last_quarter(created_date):
    if created_date >= dateLimit:
        return True
    return False


def is_not_empty(testruns):
    if not testruns:
        return False
    return True


def is_finished(single_run):
    if single_run['status'] == 'FINISHED':
        return True
    return False


# Для асессоров считаем время начала первого рана и время окончания последнего, берем среднее по версии
# Среднее время разбора бага от асессора: 20 минут
def assessor_failed_data():
    url = 'https://testpalm.yandex-team.ru:443/api/version/' + parentId
    req_headers = {'TestPalm-Api-Token': yaconfig['AUTH_TP'], 'Content-Type': 'application/json'}
    all_versions = requests.get(url, headers=req_headers).json()
    versions = list()
    assessor_failed = dict()

    for single_version in all_versions:
        if is_last_quarter(single_version['finishedTime']) and is_not_empty(single_version['suites']) \
                and is_assessor_version(single_version['title']) and 'Win' in single_version['title']:
            versions.append(single_version['title'])
        else:
            continue

    for assessor_version in versions:
        url = 'https://testpalm.yandex-team.ru:443/api/version/' + parentId + '/overview/' + assessor_version
        req_headers = {'TestPalm-Api-Token': yaconfig['AUTH_TP'], 'Content-Type': 'application/json'}
        response = requests.get(url, headers=req_headers)
        runs = response.json()
        start_time = list()
        finish_time = list()
        version_failed = dict()
        failed = 0
        # runMap = dict()

        for single_run in runs['testruns']:
            if is_finished(single_run) and 'testSuite' in single_run and 'id' in single_run['testSuite'] \
                    and single_run['testSuite']['id'] in assessor_testplan:
                execution_time = int(single_run['executionTime'])
                finished_time = int(single_run['finishedTime'])
                # Использовать для очередей, где в одной версии может быть несколько запусков
                #         title = single_run['title']
                #         print('ass run %s' % title)
                #
                #         if not runMap.get(title):
                #             runMap[title] = single_run
                #             continue
                #         else:
                #             execution_time = int(single_run['executionTime'])
                #             time_from_json = int(single_run['finishedTime']) / 1000
                #             current_time = int(runMap[title]['finishedTime']) / 1000
                #             if execution_time > 0:
                #                 if time_from_json > current_time:
                #                     runMap[title] = single_run
                #                 continue
                #             continue
                #     else:
                #         print('skip ass run %s' % single_run['title'])
                #         continue
                #
                # for single_run in runMap.values():

                if execution_time > 0 and finished_time > 0:
                    start = round(single_run['startedTime'] / 1000 / 60)
                    fin = round(single_run['finishedTime'] / 1000 / 60)

                    failed_tc = int(single_run['resolution']['counter']['failed'])
                    broken_tc = int(single_run['resolution']['counter']['broken'])
                    knownbug_tc = int(single_run['resolution']['counter']['knownbug'])
                    skipped_tc = int(single_run['resolution']['counter']['skipped'])
                    total_tc = int(single_run['resolution']['counter']['total'])

                    if 'failed_tc' in tc_list:
                        failed += failed_tc
                    if 'broken_tc' in tc_list:
                        failed += broken_tc
                    if 'knownbug_tc' in tc_list:
                        failed += knownbug_tc
                    if 'skipped_tc' in tc_list and skipped_tc != total_tc:
                        failed += skipped_tc

                    if start > 0 and fin > 0:
                        start_time.append(start)
                        finish_time.append(fin)
                    else:
                        continue
                else:
                    continue

        if start_time and finish_time:
            time_from_json = int(runs['version']['finishedTime']) / 1000  # ALERT ЗАМЕНА нужно finished
            date = datetime.date.fromtimestamp(time_from_json)
            month = str(date - datetime.timedelta(days=(date.day - 1)))

            ver_title = runs['version']['title']
        else:
            continue

        failed = failed * parce_time_case
        if failed > parce_time_max:
            version_failed[ver_title] = parce_time_max
        else:
            version_failed[ver_title] = failed

        if month in assessor_failed:
            assessor_failed[month].update(version_failed)
        else:
            assessor_failed[month] = version_failed

    # Рассчитываем среднее время, затраченное на разбор багов от асессоров, по месяцам
    failed_dict = dict()
    for month in assessor_failed:
        failed_average_time = list()
        for key in assessor_failed[month]:
            failed_average_time.append(assessor_failed[month][key])
        failed_dict[month] = failed_average_time

    assessor_failed_average = dict()
    for month in failed_dict:
        assessor_failed_average[month] = int(numpy.mean(failed_dict[month]))

    return assessor_failed_average


# Для ручного считаем время начала первого рана и время окончания последнего, берем среднее по версии
def manual_data():
    url = 'https://testpalm.yandex-team.ru:443/api/version/' + parentId
    req_headers = {'TestPalm-Api-Token': yaconfig['AUTH_TP'], 'Content-Type': 'application/json'}
    all_versions = requests.get(url, headers=req_headers).json()
    versions = list()
    manual = dict()

    for single_version in all_versions:
        if is_last_quarter(single_version['finishedTime']) and is_not_empty(single_version['suites']) \
                and not is_assessor_version(single_version['title']) and 'Win' in single_version['title']:
            versions.append(single_version['title'])
        else:
            continue

    for manual_version in versions:
        url = 'https://testpalm.yandex-team.ru:443/api/version/' + parentId + '/overview/' + manual_version
        req_headers = {'TestPalm-Api-Token': yaconfig['AUTH_TP'], 'Content-Type': 'application/json'}
        response = requests.get(url, headers=req_headers)
        runs = response.json()
        start_time = list()
        finish_time = list()
        version = dict()
        exec_time = 0

        for single_run in runs['testruns']:
            if is_last_quarter(single_run['startedTime']) \
                    and 'testSuite' in single_run and 'id' in single_run['testSuite'] \
                    and single_run['testSuite']['id'] in manual_testplan:
                start = round(single_run['startedTime'] / 1000 / 60)
                fin = round(single_run['finishedTime'] / 1000 / 60)
                execution = round(single_run['executionTime']) / 1000 / 60

                if execution > 0 and fin > 0:
                    exec_time += execution
                    if start > 0 and fin > 0:
                        start_time.append(start)
                        finish_time.append(fin)
                    else:
                        continue
            else:
                continue

        if start_time and finish_time:
            time_from_json = int(runs['version']['finishedTime']) / 1000
            date = datetime.date.fromtimestamp(time_from_json)
            fin_date = str(date - datetime.timedelta(days=(date.day - 1)))

            ver_start = round(runs['version']['startedTime'] / 1000 / 60)
            ver_fin = round(runs['version']['finishedTime'] / 1000 / 60)
            duration = ver_fin - ver_start

            runtime = min(duration, exec_time)
            # print('original runtime %s' % runtime)

            if runtime >= man_max:
                version_run_time = man_max
            else:
                version_run_time = runtime
            ver_title = runs['version']['title']

        else:
            continue

        if version_run_time == 0:
            logging.info('Skip empty version %s' % ver_title)
            continue
        else:
            version[ver_title] = version_run_time
            # print('manual %s' % version)

        if fin_date in manual:
            manual[fin_date].update(version)
        else:
            manual[fin_date] = version

    # Расчитываем среднее время рана асессоров по месяцам
    manual_dict = dict()
    for fin_date in manual:
        manual_average_time = list()
        for key in manual[fin_date]:
            manual_average_time.append(manual[fin_date][key])
        manual_dict[fin_date] = manual_average_time

    manual_average = dict()
    for fin_date in manual_dict:
        manual_average[fin_date] = int(numpy.mean(manual_dict[fin_date]))

    return manual_average


def create_data(assessor, manual):
    #dates = ['2019-03-01']
    dates = ['2018-08-01', '2018-09-01', '2018-10-01', '2018-11-01', '2018-12-01', '2019-01-01', '2019-02-01',  '2019-03-01']

    for date in dates:
        if date in manual:
            continue
        else:
            manual[date] = 0

    for date in dates:
        if date in assessor:
            continue
        else:
            assessor[date] = 0

    data = [
        {
            'fielddate': date,
            'queue': parentId,
            'assessor_failed': assessor[date],
            'manual': manual[date],
        }
        for date in dates
    ]

    logging.info(' Data is ready %s' % data)

    # r = requests.post(
    #     'https://upload.stat.yandex-team.ru/_api/report/data',
    #     headers={'Authorization': 'OAuth %s' % yaconfig['AUTH_STAT']},
    #     data={
    #         'name': 'Mail/Others/regression',
    #         'scale': 'm',
    #         'data': json.dumps({'values': data})
    #     }
    # )
    # logging.info(' Stat response: %s' % r.text)

    return data


all_queues = yaconfig['parentId']
for queue_data in all_queues:
    for parentId in queue_data:
        queue_params = queue_data[parentId]
        assessor_testplan = queue_params['assessor_testplan']
        manual_testplan = queue_params['manual_testplan']
        as_max = int(queue_params['as_max'])
        man_max = int(queue_params['man_max'])
        tc_list = queue_params['tc_list']
        parce_time_case = queue_params['parce_time_case']
        parce_time_max = queue_params['parce_time_max']

        create_data(assessor_failed_data(), manual_data())
