import os
import requests
import json

from lib.util.requtil import intercept_response_error
from lib.util import timeutil
import lib.integration.testpalm as tp


def fetch_test_run(project_id, test_run_id):
    """
    :type project_id: str
    :type test_run_id: str
    :rtype: dict
    """
    url = '{api_endpoint}/testrun/{project_id}/{run_id}'.format(
        api_endpoint=__get_api_endpoint(),
        project_id=project_id,
        run_id=test_run_id
    )
    headers = __build_headers()
    response = requests.get(url=url, headers=headers)
    response = intercept_response_error(response)
    return json.loads(response.text)


def fetch_test_cases_by_features(project_id, platform, features):
    """
    :type project_id: str
    :type platform: str
    :type features: list[str]
    :rtype: dict
    """
    expression = tp.expression(
        tp.condition_all(
            [
                tp.condition_eq(key='attributes.5a0577ac9793a44a4f377cb5', value='RegressApps'),  # Run type
                tp.condition_eq(key='attributes.5a6b08459107fc97a9b008b7', value=platform),  # Platform Type
                tp.condition_in(key='attributes.5a057a299793a44a4f377cea', value=features)  # Functionality
            ]
        )
    )
    url = '{api_endpoint}/testcases/{project_id}?' \
          '&expression={expression}'\
        .format(
            api_endpoint=__get_api_endpoint(),
            project_id=project_id,
            expression=expression
        )
    headers = __build_headers()
    response = requests.get(url=url, headers=headers)
    response = intercept_response_error(response)
    return response.content
    # return json.loads(response.text)


def fetch_test_runs_with_participant(project_id, participants, days):
    """
    :type project_id: str
    :type participants: list[str]
    :type days: int
    :rtype: dict
    """
    since_ms = timeutil.current_millis() - timeutil.days_in_millis(days)
    title_and_time_filter = tp.condition_all([
        tp.condition_gt(key='createdTime', value=since_ms),
        tp.condition_not_contain(key='title', value='asessor')
    ])
    expression = tp.expression(
        tp.condition_all([
            title_and_time_filter,
            tp.condition_any(
                list(map(lambda p: tp.condition_contain(key='participants', value=p), participants))
            )
        ]) if participants else title_and_time_filter
    )
    url = '{api_endpoint}/testrun/{project_id}?' \
          '&createdTimeSort=desc' \
          '&expression={expression}'\
        .format(
            api_endpoint=__get_api_endpoint(),
            project_id=project_id,
            expression=expression
        )
    headers = __build_headers()
    response = requests.get(url=url, headers=headers)
    response = intercept_response_error(response)
    return json.loads(response.text)


def fetch_definitions(project_id: str, definitions: [str]):
    expression = tp.expression(
        tp.condition_any(
            list(map(
                lambda definition: tp.condition_eq(key='title', value=definition),
                definitions
            ))
        )
    )
    url = '{api_endpoint}/definition/{project_id}?' \
          '&expression={expression}'\
        .format(
            api_endpoint=__get_api_endpoint(),
            project_id=project_id,
            expression=expression
        )
    headers = __build_headers()
    response = requests.get(url=url, headers=headers)
    response = intercept_response_error(response)
    return json.loads(response.text)


def __build_headers():
    return {
        'Authorization': 'OAuth {}'.format(__get_token()),
        'Content-Type': 'application/json'
    }


def __get_api_endpoint():
    return 'https://testpalm-api.yandex-team.ru'


def __get_token():
    return os.environ['TEST_PALM_TOKEN']
