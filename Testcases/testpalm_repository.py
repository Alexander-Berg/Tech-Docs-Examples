from lib.entity.testpalm import TestRun
from lib.entity.testpalm import TestGroup
from lib.entity.testpalm import TestCase
from lib.entity.testpalm import TestCaseStatus
from lib.entity.testpalm import TestPalmDefinition
from lib.integration import testpalm_client


PROJECT_ID = 'bluemarketapps'


def fetch_test_run(test_run_id):
    """
    :type test_run_id: str
    :rtype: TestRun
    """
    test_run_json = testpalm_client.fetch_test_run(project_id=PROJECT_ID, test_run_id=test_run_id)
    return __map_test_run(test_run_json)


def fetch_test_runs_with_participant(participants, days):
    """
    :type participants: list[str]
    :type days: int
    :rtype: list[TestRun]
    """
    test_runs_json = testpalm_client.fetch_test_runs_with_participant(
        project_id=PROJECT_ID,
        participants=participants,
        days=days
    )
    result = list(map(__map_test_run, test_runs_json))
    result.reverse()
    return result


def fetch_definitions(definitions: [str]) -> [TestPalmDefinition]:
    definition_jsons = testpalm_client.fetch_definitions(
        project_id=PROJECT_ID,
        definitions=definitions
    )
    return list(map(__map_test_palm_definition, definition_jsons))


def __map_test_run(test_run_json):
    """
    :type test_run_json: dict
    :rtype: TestRun
    """
    if 'startedTime' in test_run_json:
        started_time = test_run_json['startedTime']
    else:
        started_time = None
    if 'finishedTime' in test_run_json:
        finished_time = test_run_json['finishedTime']
    else:
        finished_time = None
    return TestRun(
        run_id=test_run_json['id'],
        title=test_run_json['title'],
        test_groups=list(map(__map_test_group, test_run_json['testGroups'])),
        started_time=started_time,
        finished_time=finished_time
    )


def __map_test_group(test_group_json):
    """
    :type test_group_json: dict
    :rtype: TestGroup
    """
    if 'path' in test_group_json:
        path_array = list(filter(lambda part: part, test_group_json['path']))
        path = "/".join(path_array)
    else:
        path = None
    return TestGroup(
        path=path,
        test_cases=list(map(__map_test_case, test_group_json['testCases']))
    )


def __map_test_case(test_case_json):
    """
    :type test_case_json: dict
    :rtype: TestCase
    """
    return TestCase(
        status=__map_test_case_status(test_case_json['status']),
        started_by=test_case_json['startedBy'],
        finished_by=test_case_json['finishedBy'],
        started_time=test_case_json['startedTime'],
        finished_time=test_case_json['finishedTime'],
        duration=test_case_json['duration'],
        attributes=test_case_json['testCase'].get('attributes', {})
    )


def __map_test_case_status(test_case_status):
    """
    :type test_case_status: str
    :rtype: TestCaseStatus
    """
    if test_case_status == 'CREATED':
        return TestCaseStatus.CREATED
    if test_case_status == 'STARTED':
        return TestCaseStatus.STARTED
    if test_case_status == 'SKIPPED':
        return TestCaseStatus.SKIPPED
    if test_case_status == 'PASSED':
        return TestCaseStatus.PASSED
    if test_case_status == 'BROKEN':
        return TestCaseStatus.BROKEN
    if test_case_status == 'FAILED':
        return TestCaseStatus.FAILED
    if test_case_status == 'KNOWNBUG':
        return TestCaseStatus.KNOWN_BUG
    return TestCaseStatus.UNSUPPORTED


def __map_test_palm_definition(definition_json: dict) -> TestPalmDefinition:
    return TestPalmDefinition(
        title=definition_json['title'],
        values=definition_json['values']
    )
