from enum import Enum


class TestRun:

    def __init__(self,
                 run_id,
                 title,
                 test_groups,
                 started_time,
                 finished_time):
        """
        :type run_id: str
        :type title: str
        :type test_groups: list[TestGroup]
        :type started_time: long|None
        :type finished_time: long|None
        """
        self.run_id = run_id
        self.title = title
        self.test_groups = test_groups
        self.started_time = started_time
        self.finished_time = finished_time


class TestGroup:

    def __init__(self,
                 path,
                 test_cases):
        """
        :type path: str|None
        :type test_cases: list[TestCase]
        """
        self.path = path
        self.test_cases = test_cases


class TestCase:

    def __init__(self,
                 status,
                 started_by,
                 finished_by,
                 started_time,
                 finished_time,
                 duration,
                 attributes):
        """
        :type status: TestCaseStatus
        :type started_by: str|None
        :type finished_by: str|None
        :type started_time: long|None
        :type finished_time: long|None
        :type duration: long|None
        :type attributes: dict
        """
        self.status = status
        self.started_by = started_by
        self.started_time = started_time
        self.finished_by = finished_by
        self.finished_time = finished_time
        self.duration = duration
        self.attributes = attributes


class TestCaseStatus(Enum):
    CREATED = 1
    STARTED = 2
    SKIPPED = 3
    PASSED = 4
    BROKEN = 5
    FAILED = 6
    KNOWN_BUG = 7
    UNSUPPORTED = 8


class TestPalmDefinition:

    def __init__(self,
                 title: str,
                 values: [str]):
        self.title = title
        self.values = values
