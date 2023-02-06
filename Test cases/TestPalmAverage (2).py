# -*- coding: utf-8 -*-
import json
import logging
import os
import time

import numpy
import requests
import urllib3
import yaml

from datetime import datetime, timedelta, date

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(
    format='%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', level=logging.INFO)
scriptPath = os.path.dirname(os.path.abspath(__file__) + '/SupportQueueMonitoring')
yaconfig = yaml.load(open(os.path.dirname(scriptPath) + '/config.yaml'))
dateLimit = yaconfig['dateLimit']
robots = yaconfig['robots']


def is_assessor_version(version):
    if 'asses' in version.lower() or 'ases' in version.lower() or 'acces' in version.lower() \
            or 'асес'.decode('utf-8') in version.lower():
        return True


def is_monitoring_version(version):
    if 'мониторинг'.decode('utf-8') in version.lower() or 'monitoring' in version.lower():
        return True


def use_for_autotests_computing(version):
    if independentAutotestVersion:
        if 'autotest' in version.lower():
            return True
        else:
            return False
    return not is_assessor_version(version) and not is_monitoring_version(version)


def created_by_robot(testrun):
    return testrun['createdBy'] in robots


def is_autotest(testrun):
    return testrun['launcherInfo']['external'] and created_by_robot(testrun)


def compute_finish_date(version_overview):
    version_finished_time = version_overview['version']["finishedTime"] / 1000

    last_run = max(version_overview['testruns'], key=lambda run: run['finishedTime'])
    testrun_finished_time = int(last_run['finishedTime']) / 1000

    version_date = date.fromtimestamp(version_finished_time)
    testrun_date = date.fromtimestamp(testrun_finished_time)
    if abs((version_date - testrun_date).days) > 7:
        return str(testrun_date - timedelta(days=(testrun_date.day - 1)))
    return str(version_date - timedelta(days=(version_date.day - 1)))


def cluster_runs(testruns):
    sorted_runs = sorted(testruns[:], key=lambda r: r['finishedTime'])
    cluster_set = []
    current_cluster = [sorted_runs[0]]
    for index in range(1, len(sorted_runs)):
        run = sorted_runs[index]
        if run['startedTime'] - current_cluster[len(current_cluster) - 1]['finishedTime'] < 120000:  # 3 минута
            current_cluster.append(run)
        else:
            cluster_set.append(current_cluster)
            current_cluster = [run]
    cluster_set.append(current_cluster)
    return cluster_set


def cluster_time(testrun):
    started_time = datetime.fromtimestamp(int(testrun['finishedTime']) / 1000)
    return started_time - timedelta(hours=started_time.time().hour % 12)


def cluster_date(testrun):
    started_time = datetime.fromtimestamp(int(testrun['finishedTime']) / 1000)
    return started_time - timedelta(hours=started_time.time().hour, minutes=started_time.time().minute,
                                    seconds=started_time.time().second, microseconds=started_time.time().microsecond)


def testrun_cluster_key(testrun):
    """
    Создаем ключ вида <testsuiteid | имя рана> - <год-месяц-день> что бы отличать раны по разным дням
    :param testrun: объект рана из версии
    :return: ключ по которому будет идентифицировать ран.
    """
    run_title = compute_run_title(testrun)

    return run_title + ' - ' + cluster_time(testrun).strftime('%Y-%m-%d')


def compute_run_title(testrun):
    if 'testSuite' in testrun:
        run_title = testrun['testSuite']['id']
    else:
        run_title = testrun['title']
    return run_title


def is_nightly_run(testrun):
    return cluster_time(testrun).hour == 0


def cluster_runs_by_titles(testruns):
    """
    Get test run clusters. Only latest test run on the night for specific test suite or test run name
    must be in cluster
    :param testruns: list of runs for specific version
    :return: run_map
    """
    run_map = {}
    for run in testruns:
        cluster_key = compute_run_title(run)
        if not run_map.get(cluster_key):
            run_map[cluster_key] = run
            continue
        else:
            run_time = int(run['finishedTime']) / 1000
            current_saved_time = int(run_map[cluster_key]['finishedTime']) / 1000
            if run_time > current_saved_time:
                run_map[cluster_key] = run
            continue
    return run_map


def cluster_by_date(testruns):
    """
    Return runs clustered by date
    :param testruns: list of runs for specific version
    :return: run_map: Map<date, [testrun]>
    """
    run_map = {}
    for run in testruns:
        cluster_key = testrun_cluster_key(run)
        if not run_map.get(cluster_key):
            run_map[cluster_key] = run
            continue
        else:
            run_time = int(run['finishedTime']) / 1000
            current_saved_time = int(run_map[cluster_key]['finishedTime']) / 1000
            if run_time > current_saved_time:
                run_map[cluster_key] = run
            continue
    return run_map


def clusterize_by_suite(testruns):
    run_map = {}
    for run in testruns:
        cluster_key = compute_run_title(run)
        if not run_map.get(cluster_key):
            run_map[cluster_key] = [run]
            continue
        else:
            run_map[cluster_key].append(run)
            continue
    return run_map


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
    #print(str(datetime.datetime.now()) + ' Start parsing TP for assessor failed data')
    url = 'https://testpalm.yandex-team.ru:443/api/version/' + parentId
    req_headers = {'TestPalm-Api-Token': yaconfig['AUTH_TP'], 'Content-Type': 'application/json'}
    all_versions = requests.get(url, headers=req_headers).json()
    versions = list()
    assessor_failed = dict()

    for single_version in all_versions:
        if is_last_quarter(single_version['finishedTime']) and is_assessor_version(single_version['title']) \
                and is_not_empty(single_version['suites']):
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

        for single_run in runs['testruns']:
            #if is_finished(single_run):
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
            time_from_json = int(runs['version']['finishedTime']) / 1000
            version_date = date.fromtimestamp(time_from_json)
            month = str(version_date - timedelta(days=(version_date.day - 1)))

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
    #print(str(datetime.datetime.now()) + ' Finish parsing TP for assessor failed data')
    #print(assessor_failed_average)
    return assessor_failed_average


# Для ручного считаем время начала первого рана и время окончания последнего, берем среднее по версии
def manual_data():
    #print(str(datetime.datetime.now()) + ' Start parsing TP for manual regression data')
    url = 'https://testpalm.yandex-team.ru:443/api/version/' + parentId
    req_headers = {'TestPalm-Api-Token': yaconfig['AUTH_TP'], 'Content-Type': 'application/json'}
    all_versions = requests.get(url, headers=req_headers).json()
    versions = list()
    manual = dict()

    for single_version in all_versions:
        if is_last_quarter(single_version['finishedTime']) and is_not_empty(single_version['suites']) \
                and not is_assessor_version(single_version['title']):
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
        print(runs['version']['title'])

        for single_run in runs['testruns']:
            if 'testSuite' in single_run and 'id' in single_run['testSuite'] \
                    and single_run['testSuite']['id'] in manual_testplan:
                start = round(single_run['startedTime'] / 1000 / 60)
                fin = round(single_run['finishedTime'] / 1000 / 60)
                execution = round(single_run['executionTime']) / 1000 / 60
                #print('run title %s' % single_run['title'])
                #print('run exec time %s' % execution)

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
            curr_date = date.fromtimestamp(time_from_json)
            fin_date = str(curr_date - timedelta(days=(curr_date.day - 1)))

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

    #print(manual_average)
    #print(str(datetime.datetime.now()) + ' Finish parsing TP for manual regression data')
    return manual_average


def autotest_data():
    url = 'https://testpalm.yandex-team.ru:443/api/version/' + parentId
    req_headers = {'TestPalm-Api-Token': yaconfig['AUTH_TP'], 'Content-Type': 'application/json'}
    all_versions = requests.get(url, headers=req_headers).json()
    versions = list()
    autotest = dict()
    autotest_failed = dict()

    for single_version in all_versions:
        if is_last_quarter(single_version['startedTime'])\
                and use_for_autotests_computing(single_version['title']):
            # and is_not_empty(single_version['suites']):
            # and not is_assessor_version(single_version['title']):
            versions.append(single_version['title'])
        else:
            continue

    for autotest_version in versions:
        url = 'https://testpalm.yandex-team.ru:443/api/version/' + parentId + '/overview/' + autotest_version
        req_headers = {'TestPalm-Api-Token': yaconfig['AUTH_TP'], 'Content-Type': 'application/json'}
        response = requests.get(url, headers=req_headers)
        version_overview = response.json()
        version_failed = dict()
        version = dict()
        fails_research_time = 0
        ver_title = version_overview['version']['title']

        autotest_runs = list(filter(lambda r: is_autotest(r), version_overview['testruns']))

        if len(autotest_runs) == 0:
            logging.info('Skip empty version %s' % ver_title)
            continue

        if cluster_by_suite:
            test_run_clusters = clusterize_by_suite(autotest_runs)
            summary_execution_time = 0
            for cluster in test_run_clusters.values():
                cluster_execution_time = 0
                for run in cluster:
                    run_execution_time = run['duration']
                    run_start_time = min(cluster, key=lambda r: r['startedTime'])['startedTime']
                    run_end_time = max(cluster, key=lambda r: r['finishedTime'])['finishedTime']
                    exec_time = min(run_end_time - run_start_time, run_execution_time)
                    cluster_execution_time += exec_time
                cluster_average_time = cluster_execution_time / len(cluster)
                summary_execution_time += cluster_average_time
            version_run_time = summary_execution_time / 1000 / 60  # minutes
        else:
            test_run_clusters = cluster_runs(autotest_runs)
            summary_execution_time = 0
            for cluster in test_run_clusters:
                cluster_execution_time = 0
                for run in cluster:
                    cluster_execution_time += run['duration']
                run_start_time = min(cluster, key=lambda r: r['startedTime'])['startedTime']
                cluster_end_time = max(cluster, key=lambda r: r['finishedTime'])['finishedTime']
                exec_time = min(cluster_end_time - run_start_time, cluster_execution_time)

                summary_execution_time += min(exec_time, cluster_execution_time)
            average_execution_time = summary_execution_time/1000/60 / len(test_run_clusters)
            version_run_time = average_execution_time  # minutes

        if cluster_by_suite:
            test_run_clusters = clusterize_by_suite(autotest_runs)
            fails = 0
            for cluster in test_run_clusters.values():
                cluster_fail = 0
                for run in cluster:
                    counters = run['resolution']['counter']
                    failed_cases = counters['failed'] + counters['broken'] + counters['knownbug']
                    if failed_cases <= counters['total'] / 2:
                        cluster_fail += failed_cases
                fails += (cluster_fail / len(cluster))
            fails_research_time = min(fails * research_multiplier, fails_research_limit)
        else:
            all_run_map = cluster_by_date(autotest_runs)
            cluster_fails = {}
            for run in all_run_map.values():
                counters = run['resolution']['counter']
                failed_cases = counters['failed'] + counters['broken'] + counters['knownbug']
                if failed_cases <= counters['total'] / 2:
                    date = cluster_date(run)
                    if cluster_fails.get(date) is None:
                        cluster_fails[date] = failed_cases
                    else:
                        cluster_fails[date] += failed_cases
            if len(cluster_fails.values()) != 0:
                fails_research_time = min(numpy.mean(list(cluster_fails.values())) * research_multiplier, fails_research_limit)
            else:
                fails_research_time = 0.0

        if version_run_time == 0:
            logging.info('Skip empty version %s' % ver_title)
            continue
        else:
            logging.info('Computed autotest time for %s: %s ' % (ver_title, str(version_run_time)))
            version[ver_title] = version_run_time

        fin_date = compute_finish_date(version_overview)
        if fin_date in autotest:
            autotest[fin_date].update(version)
        else:
            autotest[fin_date] = version
        version_failed[ver_title] = fails_research_time

        if fin_date in autotest_failed:
            autotest_failed[fin_date].update(version_failed)
        else:
            autotest_failed[fin_date] = version_failed

    # Расчитываем среднее время рана автотестов по месяцам
    autotest_dict = dict()
    for fin_date in autotest:
        autotest_average_time = list()
        for key in autotest[fin_date]:
            autotest_average_time.append(autotest[fin_date][key])
        autotest_dict[fin_date] = autotest_average_time

    autotest_average = dict()
    for fin_date in autotest_dict:
        autotest_average[fin_date] = int(numpy.mean(autotest_dict[fin_date]))
    # Рассчитываем среднее время, затраченное на разбор багов от автотестов , по месяцам
    failed_dict = dict()
    for month in autotest_failed:
        failed_average_time = list()
        for key in autotest_failed[month]:
            failed_average_time.append(autotest_failed[month][key])
        failed_dict[month] = failed_average_time

    assessor_failed_average = dict()
    for month in failed_dict:
        assessor_failed_average[month] = int(numpy.mean(failed_dict[month]))

    return autotest_average, assessor_failed_average


def create_data(assessor, manual, autotest, autotest_failed):
    #dates = ['2019-03-01']
    dates = ['2018-08-01', '2018-09-01', '2018-10-01', '2018-11-01', '2018-12-01', '2019-01-01', '2019-02-01', '2019-03-01']
    #dates = ['2019-01-01', '2019-02-01', '2019-03-01']

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
            'autotest': autotest[date],
            'autotest_failed': autotest_failed[date]
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

    #return data


all_queues = yaconfig['parentId']
for queue_data in all_queues:
    for parentId in queue_data:
        print('--------------------------------------')
        print(str(datetime.now()) + ' Run script for queue: ' + parentId)

        queue_params = queue_data[parentId]
        assessor_testplan = queue_params['assessor_testplan']
        manual_testplan = queue_params['manual_testplan']
        as_max = int(queue_params['as_max'])
        man_max = int(queue_params['man_max'])
        tc_list = queue_params['tc_list']
        parce_time_case = queue_params['parce_time_case']
        parce_time_max = queue_params['parce_time_max']
        fails_research_limit = queue_params['fails_research_limit']
        independentAutotestVersion = queue_params['independentAutotestVersion']
        cluster_by_suite = queue_params['clusterBySuite']
        research_multiplier = queue_params.get('researchMultiplier', 5)
        autotest_average, autotest_failed_average = autotest_data()
        # print("Autotest average", autotest_average)
        # print("Autotest failed research average", autotest_failed_average)

        create_data(assessor_failed_data(), manual_data(), autotest_average, autotest_failed_average)
