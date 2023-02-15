# coding=utf-8
import requests
import json
import sys
import datetime
from core.utils.internal.yql_worker import YqlWorker


def get_response_json(session, url):
    temp = session.get(url, verify=False)
    return temp.json()


def write_result(output_file_name, res):
    with open(output_file_name, 'w') as f:
        json.dump(res, f)


def get_last_test_run_date(marker):
    yql_client = YqlWorker(yql_token)
    query_b2b = """SELECT `creation_timestamp` FROM hahn.`home/market/users/serookiy/b2b_crm_testruns`"""
    query_b2c = """SELECT `creation_timestamp` FROM hahn.`home/market/users/serookiy/b2c_crm_testruns`"""
    if marker == 'b2b':
        test_runs_history_df = yql_client.run_query(query_b2b)
    elif marker == 'b2c':
        test_runs_history_df = yql_client.run_query(query_b2c)
    else:
        res = 0
        return res
    res = test_runs_history_df.nlargest(1, 'creation_timestamp')
    res = res.get('creation_timestamp').to_list()
    try:
        res = res[0]
    except IndexError:
        res = 0
    return res


def get_test_run_stat(js_data, js_suite_data):
    tags_list = js_data['tags']
    tags_string = ''
    for tag in tags_list:
        tags_string += str(tag) + ' '
    temp_duration_automated_cases = 0
    temp_duration_manual_cases = 0
    passed_test_cases = 0
    failed_test_cases = 0
    skipped_test_cases = 0
    automated_test_cases = 0
    test_cases_count = 0
    participants_counter = {}
    for group in js_data['testGroups']:
        for case in group['testCases']:
            test_cases_count += 1
            try:
                if case['status'] == 'PASSED':
                    passed_test_cases += 1
                elif case['status'] == 'FAILED':
                    failed_test_cases += 1
                elif case['status'] == 'SKIPPED':
                    skipped_test_cases += 1
                if case['testCase']['status'] == 'AUTOMATED':
                    temp_duration_automated_cases += case['testCase']['stats']['avgRunDuration']
                    automated_test_cases += 1
                elif case['status'] == 'PASSED' or case['status'] == 'FAILED':
                    if case['finishedBy'] not in participants_counter:
                        participants_counter[case['finishedBy']] = 1
                    else:
                        participants_counter[case['finishedBy']] += 1
                    temp_duration_manual_cases += case["duration"]
            except KeyError:
                continue
    for case in js_suite_data:
        if case['status'] == 'AUTOMATED':
            temp_duration_automated_cases += case['stats']['avgRunDuration']
            automated_test_cases += 1
            test_cases_count += 1
    res_df = {'creation_date': datetime.datetime.fromtimestamp(js_data['createdTime'] / 1000).isoformat(),
              'creation_timestamp': js_data['createdTime'],
              'test_run_duration': js_data['executionTime']/1000/60,
              'author': js_data['createdBy'], 'tags': tags_string,
              "test_case_count": test_cases_count,
              "automated_test_cases_duration_avg": temp_duration_automated_cases,
              "manual_test_cases_duration_avg": temp_duration_manual_cases,
              "passed_test_cases": passed_test_cases,
              "failed_test_cases": failed_test_cases,
              "skipped_test_cases": skipped_test_cases,
              "automated_test_cases": automated_test_cases}
    res_participants = []
    for tester in participants_counter:
        res_participants.append({"creation_timestamp": res_df['creation_timestamp'],
                                 "tester": tester,
                                 "number_of_cases": participants_counter[tester]
                                 })
    return res_df, res_participants


# Отфильтровать id тех ранов, которые должны попасть в обработку
# (завершенные с тегом sanity + только новые, если скрипт запускается из нирваны)
# Поскольку сейчас настройка строгая под тег sanity, то раны suitecrm отсеиваются.
def filter_relevant_ids(runs_overviews, mode, last_test_run_date):
    relevant_runs_ids = []

    for run in runs_overviews:
        if run['status'] == 'FINISHED' and 'sanity' in run['tags']:
            if mode == 1 and run['createdTime'] <= last_test_run_date:
                continue
            relevant_runs_ids.append(run['id'])

    return relevant_runs_ids


# Параметры запуска скрипта
test_palm_token = sys.argv[1]
output_b2b_runs_filename = sys.argv[2]
output_b2c_runs_filename = sys.argv[3]
regress_participants_filename = sys.argv[6]

# Ручки к api тестпалма, включающие в себя ссылки на сьюты, содержащие все кейсы регресса, в т.ч. автоматизированные
b2b_crm_testsuite_url = 'https://testpalm-api.yandex-team.ru/testcases/sugarcrm/suite/5ecb9f76e1ff18a2987686a4'
b2c_crm_testsuite_url = 'https://testpalm-api.yandex-team.ru/testcases/ocrm/suite/5f8e89ce2266e50011bcf83c'

# Ручки для получения общей информации о всех ранах (отдают только id рана, дату создания, статус и теги)
b2b_crm_testruns_overviews_url = 'https://testpalm-api.yandex-team.ru/testrun/sugarcrm?include=id%2CcreatedTime%2Cstatus%2Ctags'
b2c_crm_testruns_overviews_url = 'https://testpalm-api.yandex-team.ru/testrun/ocrm?include=id%2CcreatedTime%2Cstatus%2Ctags'

# Если есть токен yql - предполагается, что запуск производится из нирваны.
# В таком случае нужно вытянуть из тестпалма и обработать только те раны,
# которых ещё нет в таблице в YT.
# Если токена нет - предполагается, что запуск производится из IDE и нужно вытянуть
# все раны и сформировать на их основе файл.
try:
    yql_token = sys.argv[5]
    mode = 1
except IndexError:
    mode = 2

# Base url для запросов в api
b2b_crm_testruns_urls = 'https://testpalm-api.yandex-team.ru/testrun/sugarcrm/'
b2c_crm_testruns_urls = 'https://testpalm-api.yandex-team.ru/testrun/ocrm/'

# Авторизация в тестпалме
test_palm_session = requests.Session()
test_palm_session.headers.update({'Authorization': 'OAuth {}'.format(test_palm_token)})

# Информация из сьютов для подсчета процента автоматизации
b2bcrm_suite_runs = get_response_json(test_palm_session, b2b_crm_testsuite_url)
b2ccrm_suite_runs = get_response_json(test_palm_session, b2c_crm_testsuite_url)

# Переменные вывода
output_df_b2b = []
output_df_b2c = []
output_participants = []

# Получить короткую сводку (id, дата создания, статус, теги) всех ранов в проекте
b2b_crm_suite_runs_overviews = get_response_json(test_palm_session, b2b_crm_testruns_overviews_url)
b2c_crm_suite_runs_overviews = get_response_json(test_palm_session, b2c_crm_testruns_overviews_url)

# Выбрать id тех ранов, которые нужно обработать
b2b_crm_runs_relevant_ids = filter_relevant_ids(
    b2b_crm_suite_runs_overviews, mode, get_last_test_run_date('b2b') if mode == 1 else None)
b2c_crm_runs_relevant_ids = filter_relevant_ids(
    b2c_crm_suite_runs_overviews, mode, get_last_test_run_date('b2c') if mode == 1 else None)

# Для каждого id постучаться в api, получить подробную инфу по рану и обработать ее
for run_id in b2b_crm_runs_relevant_ids:
    # Постучаться
    run = get_response_json(test_palm_session, b2b_crm_testruns_urls + run_id)
    # Обработать
    result, participants = get_test_run_stat(run, b2bcrm_suite_runs)
# Записать в результаты
    output_df_b2b.append(result)
write_result(output_b2b_runs_filename, output_df_b2b)

for run_id in b2c_crm_runs_relevant_ids:
    # Постучаться
    run = get_response_json(test_palm_session, b2c_crm_testruns_urls + run_id)
    # Обработать
    result, participants = get_test_run_stat(run, b2ccrm_suite_runs)
# Записать в результаты
    output_df_b2c.append(result)
    for tester_line in participants:
        output_participants.append(tester_line)
write_result(output_b2c_runs_filename, output_df_b2c)
write_result(regress_participants_filename, output_participants)

