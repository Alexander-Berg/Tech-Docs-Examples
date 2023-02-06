import json
import urllib.parse


PROJECT_ID_BLUEMARKETAPPS = 'bluemarketapps'

ATTRIBUTE_RUN_TYPE = 'attributes.5a0577ac9793a44a4f377cb5'  # Run type
ATTRIBUTE_PLATFORM_TYPE = 'attributes.5a6b08459107fc97a9b008b7'  # Platform Type
ATTRIBUTE_FUNCTIONALITY = 'attributes.5a057a299793a44a4f377cea'  # Functionality

PLATFORM_TYPE_ANDROID = 'Android'
PLATFORM_TYPE_IOS = 'IOS'

RUN_TYPE_REGRESS_SHORT = 'Short-Regress'
RUN_TYPE_REGRESS_FULL = 'RegressApps'


def expression(expr: dict) -> str:
    """
    :type expr: dict
    :rtype: str
    """
    expression_string = json.dumps(expr, separators=(',', ':'))
    quoted_expression = urllib.parse.quote(expression_string)
    return quoted_expression


def condition_and(left: dict, right: dict) -> dict:
    return {
        'type': 'AND',
        'left': left,
        'right': right
    }


def condition_or(left: dict, right: dict) -> dict:
    return {
        'type': 'OR',
        'left': left,
        'right': right
    }


def condition_all(conditions: [dict]) -> dict:
    if len(conditions) == 1:
        return conditions[0]
    current = None
    for condition in conditions:
        if current:
            current = {
                'type': 'AND',
                'left': current,
                'right': condition
            }
        else:
            current = condition
    return current


def condition_any(conditions: [dict]) -> dict:
    if len(conditions) == 1:
        return conditions[0]
    current = None
    for condition in conditions:
        if current:
            current = {
                'type': 'OR',
                'left': current,
                'right': condition
            }
        else:
            current = condition
    return current


def condition_eq(key: str, value: str) -> dict:
    return {
        'type': 'EQ',
        'key': key,
        'value': value
    }


def condition_gt(key: str, value: str) -> dict:
    return {
        'type': 'GT',
        'key': key,
        'value': value
    }


def condition_in(key: str, value: [str]) -> dict:
    return {
        'type': 'IN',
        'key': key,
        'value': value
    }


def condition_contain(key: str, value: str) -> dict:
    return {
        'type': 'CONTAIN',
        'key': key,
        'value': value
    }


def condition_not_contain(key: str, value: str) -> dict:
    return {
        'type': 'NOT_CONTAIN',
        'key': key,
        'value': value
    }
