# -*- coding: utf-8 -*-
import json
import logging
import os
import re
import smtplib
import sys
import urllib
from collections import defaultdict
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from retrying import retry

import filters

sys.path.append(str(Path(__file__).parent.parent.parent))
from set_secret import set_secret

set_secret.set_secrets()

testpalm_host = 'https://testpalm-api.yandex-team.ru/'
testpalm = 'https://testpalm.yandex-team.ru/'
headers_testpalm = {'Authorization': f'OAuth {os.environ["TESTPALM_OAUTH"]}',
                    'Content-Type': 'application/json'}
subj = 'Кейсам не хватает разметки'
fromaddr = 'testoviy-test111@yandex.ru'
mypass = 'Testoviy1'
toaddr = ['mail-qa-duty@yandex-team.ru']

projects = {
    'mail-touch': {
        'automation': '58eba70b88955049314bf7d4',
        'key_to_remove': 'Кандидат в автоматизацию',
        'features': '582c40f3c6123313214de3d6',
        'feature_priority': '5d66cac646af84e7088d5781',
        'regress_level': '60e70a5b22220a0022296bd5'
    },
    'mail-liza': {
        'automation': '5c5453a66acd3d903a10fba9',
        'key_to_remove': 'Кандидат на автоматизацию',
        'features': '55a7b654e4b0de1599b0c517',
        'feature_priority': '5d5b2320f97f2449b408c4bf',
        'regress_level': '60e6f216380e220022a97d97'
    },
    'cal': {
        'automation': '5c9cc8d07c48e33b4a624932',
        'key_to_remove': 'Кандидат на автоматизацию',
        'features': '5822dfb1889550027e060679',
        'feature_priority': '5d6e2d543d42cbf92a6bef45',
        'regress_level': '60e70a2169d473002270ecd6'
    },
    'sender_main':
        {
            'features': '61c49f0dc4653000222f54e5',
            'feature_priority': '61c499ca0ee78400220cf452',
            'regress_level': '620bbc01e57fde0022b5fed4'
        }
}


def remove_automation_key(project):
    if 'automated_filter' in filters.projects[project].keys():
        # Получаем список id автоматизированных кейсом с ключов Кандидат в автоматизацию
        raw_data = json.dumps(filters.projects[project]['automated_filter'], ensure_ascii=False,
                              separators=(',', ': ')).encode(
            'utf-8')
        urlBody = urllib.parse.quote(raw_data)
        url = f'{testpalm_host}testcases/{project}?include=id&expression={urlBody}'
        cases = requests.get(url, headers=headers_testpalm).json()
        print(cases)
        logging.info(' Testpalm response: %s' % cases)

        # Получаем список ключей каждого кейса, удаляем из них значение Кандидат в автоматизацию
        for id in cases:
            url = f'{testpalm_host}testcases/{project}?include=attributes&id={id["id"]}'
            case = requests.get(url, headers=headers_testpalm).json()
            case[0]['attributes'][projects[project]['automation']].remove(projects[project]['key_to_remove'])

            data = {
                'id': id['id'],
                'attributes': case[0]['attributes']
            }
            print(id)
            raw_data = json.dumps(data, ensure_ascii=False, separators=(',', ': '))
            url = f'{testpalm_host}testcases/{project}'
            r = requests.patch(url, headers=headers_testpalm, data=raw_data.encode('utf8'))
            logging.info(' Testpalm response: %s' % r)


def check_automation_filled(project):
    if 'automation_empty_filter' in filters.projects[project].keys():
        # Получаем список id неавтоматизированных кейсов с незаполненным ключам Автоматизация
        raw_data = json.dumps(filters.projects[project]['automation_empty_filter'], ensure_ascii=False,
                              separators=(',', ': ')).encode('utf-8')
        urlBody = urllib.parse.quote(raw_data).replace('%22null%22', 'null')
        url = f'{testpalm_host}testcases/{project}?include=id&expression={urlBody}'
        cases = requests.get(url, headers=headers_testpalm).json()
        print(cases)
        logging.info(' Testpalm response: %s' % cases)
        if len(cases) != 0:
            authors = get_author(project, cases)
            for author in authors:
                cases_text = make_case_links(authors[author])
                text = 'У кейсов нужно заполнить поле автоматизация: <br>' + author + '<br>' + cases_text
            send_message(text)


def check_obligatory_keys(project):
    if 'missed_obligatory_keys_filter' in filters.projects[project].keys():
        raw_data = json.dumps(filters.projects[project]['missed_obligatory_keys_filter'], ensure_ascii=False,
                              separators=(',', ': ')).encode('utf-8')
        urlBody = urllib.parse.quote(raw_data).replace('%22null%22', 'null')
        url = f'{testpalm_host}testcases/{project}?include=id&expression={urlBody}'
        cases = requests.get(url, headers=headers_testpalm).json()
        print(cases)
        if len(cases) != 0:
            authors = get_author(project, cases)
            text = 'У кейсов не заполнено одно из полей: фича, логический кусок, приоритет кейса <br>'
            for author in authors:
                cases_text = make_case_links(authors[author])
                text = text + author + '<br>' + cases_text
            send_message(text)


def get_feature_priority(project):
    if 'cases_with_feature_priority' in filters.projects[project].keys():
        # Проходим по кейсам и выставляем поле Приоритет фичи в соответствии с названием фичи
        raw_data = json.dumps(filters.projects[project]['cases_with_feature_priority'], ensure_ascii=False,
                              separators=(',', ': ')).encode('utf-8')
        urlBody = urllib.parse.quote(raw_data).replace('%22null%22', 'null')
        url = f'{testpalm_host}testcases/{project}?include=id&expression={urlBody}'
        cases = requests.get(url, headers=headers_testpalm).json()
        for id in cases:
            url = f'{testpalm_host}testcases/{project}?include=attributes&id={id["id"]}'
            case = requests.get(url, headers=headers_testpalm).json()
            case_priorities = []
            priority = ''
            case_features = case[0]['attributes'][projects[project]['features']]
            for i in case_features:
                if re.search('\((.)\)', i) is not None:
                    if re.search('\((.)\)', i).group(1) in ['H', 'M', 'L', 'М']:  # русская и английская M
                        case_priorities.append(re.search('\((.)\)', i).group(1))
            if case_priorities:
                if 'H' in case_priorities:
                    priority = 'High'
                elif 'M' in case_priorities or 'М' in case_priorities:
                    priority = 'Medium'
                elif 'L' in case_priorities:
                    priority = 'Low'

            if projects[project]['feature_priority'] in case[0]['attributes']:
                if case[0]['attributes'][projects[project]['feature_priority']] != [priority]:
                    case[0]['attributes'][projects[project]['feature_priority']] = [priority]
                    data = {
                        'id': id['id'],
                        'attributes': case[0]['attributes']
                    }
                    raw_data = json.dumps(data, ensure_ascii=False, separators=(',', ': '))
                    url = f'{testpalm_host}testcases/{project}'
                    r = requests.patch(url, headers=headers_testpalm, data=raw_data.encode('utf8'))
                    logging.info(' Testpalm response: %s' % r)


@retry(stop_max_attempt_number=3, wait_fixed=10000)
def send_message(body):
    msg = MIMEMultipart()
    msg['From'] = fromaddr
    msg['To'] = ', '.join(toaddr)
    msg['Subject'] = project.upper() + ' ' + subj

    msg.attach(MIMEText(body, 'html', 'utf-8'))

    server = smtplib.SMTP_SSL('smtp.yandex.ru', 465, timeout=10)
    server.set_debuglevel(1)
    server.login(fromaddr, mypass)
    text = msg.as_string()
    server.sendmail(fromaddr, toaddr, text)
    server.quit()


def make_case_links(cases):
    cases_text = ''
    for case in cases:
        cases_text = cases_text + \
                     f'<a href=https://testpalm.yandex-team.ru/testcase/{project}-{case["id"]}>{case}</a><br>'
    return cases_text


def get_author(project, cases):
    authors = defaultdict(list)
    for id in cases:
        url = f'{testpalm_host}testcases/{project}?include=createdBy&id={id["id"]}'
        author = requests.get(url, headers=headers_testpalm).json()
        authors[author[0]["createdBy"]].append(id)
    return authors


def get_cases_with_problems(project):
    message = ''
    filters_dict = {'wrong_status_filter': f'Фильтр на кейсы, у которых некорректный статус.',
                    'automation_problem_filter': f'Фильтр на кейсы, у которых возможно нет вилки\долго не запускались.'}
    # 'asessors_need_actions': f'Фильтр на кейсы асессоров, которым можно поставить Actions.'}
    for key, value in filters_dict.items():
        if key in filters.projects[project].keys():
            raw_data = json.dumps(filters.projects[project][key], ensure_ascii=False,
                                  separators=(',', ': ')).encode('utf-8')
            urlBody = urllib.parse.quote(raw_data).replace('%22null%22', 'null')
            url = f'{testpalm_host}testcases/{project}?include=id&expression={urlBody}'
            cases = requests.get(url, headers=headers_testpalm).json()
            filter = f'{testpalm}{project}/testcases?filters={urlBody}'
            text = value
            if len(cases) != 0:
                message += f'<a href={filter}>{text}</a><br>'
    if message != '':
        send_message(message)


def get_regress_level(project):
    for level in ['AC', 'BL', 'Regress', 'Full regress', 'Once']:
        raw_data = json.dumps(filters.projects[project][level], ensure_ascii=False,
                              separators=(',', ': ')).encode('utf-8')
        urlBody = urllib.parse.quote(raw_data).replace('%22null%22', 'null')
        url = f'{testpalm_host}testcases/{project}?include=id&expression={urlBody}'
        cases = requests.get(url, headers=headers_testpalm).json()
        for id in cases:
            url = f'{testpalm_host}testcases/{project}?include=attributes&id={id["id"]}'
            case = requests.get(url, headers=headers_testpalm).json()
            if projects[project]['regress_level'] in case[0]['attributes']:
                case_level = case[0]['attributes'][projects[project]['regress_level']]
                if case_level != [level]:
                    case[0]['attributes'][projects[project]['regress_level']] = [level]
                    data = {
                        'id': id['id'],
                        'attributes': case[0]['attributes']
                    }
                    raw_data = json.dumps(data, ensure_ascii=False, separators=(',', ': '))
                    url = f'{testpalm_host}testcases/{project}'
                    r = requests.patch(url, headers=headers_testpalm, data=raw_data.encode('utf8'))
                    logging.info(' Testpalm response: %s' % r)
            else:
                case[0]['attributes'][projects[project]['regress_level']] = [level]
                data = {
                    'id': id['id'],
                    'attributes': case[0]['attributes']
                }
                raw_data = json.dumps(data, ensure_ascii=False, separators=(',', ': '))
                url = f'{testpalm_host}testcases/{project}'
                r = requests.patch(url, headers=headers_testpalm, data=raw_data.encode('utf8'))
                logging.info(' Testpalm response: %s' % r)


# Для тестирования лучше использовать тестовые кейсы и хардкодить id в коде.
# Например, https://testpalm.yandex-team.ru/testcase/mail-touch-1543
if __name__ == '__main__':
    for project in ['mail-touch', 'mail-liza', 'cal', 'sender_main']:
        remove_automation_key(project)
        get_feature_priority(project)
        get_regress_level(project)
        if datetime.now().isoweekday() == 4:
            check_automation_filled(project)
            check_obligatory_keys(project)
            get_cases_with_problems(project)
