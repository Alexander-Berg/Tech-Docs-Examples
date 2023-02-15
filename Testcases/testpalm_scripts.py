import urllib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
from helpers import days_between_today_and_ts, unique
from constants import MAX_NOT_FINISHED_DAYS, MAX_UNUSED_CASE_DAYS, Team, OAUTH_TOKEN_TESTPALM, \
    TestPalmMessages, Exceptions, IGNORED_VERSIONS, TestPalmSubjects, MAX_DAYS_IN_STATUS_DRAFT_ON_REVIEW_NEEDS_CHANGES
from tp_api_client.tp_api_client import TestPalmClient, Projects, Fields, Operators, CaseStatus, RunStatus, \
    VersionStatus, Action
from mail_sender import MailSender
import logging

logger = logging.getLogger('testpalm_logger')
logging.basicConfig(format=u'%(asctime)s [%(levelname)s] %(module)s: %(message)s', level=logging.INFO)


@dataclass
class Component:
    ios = 'iOS'
    android = 'Android'


class TestPalmScripts:
    def __init__(self, project: str, component: str, client) -> None:
        self.__project = project
        self.__client = client
        self.__component = component

    def get_recipient_by_component(self) -> List[str]:
        if self.__component == Component.ios:
            team = Team.qa_ios
        elif self.__component == Component.android:
            team = Team.qa_android
        else:
            raise ValueError(Exceptions.unknown_component)
        return [recipient + '@yandex-team.ru' for recipient in team]

    def filter_expression_with_current_component(self, filter_expression: Dict[str, str]) -> str:
        component_attr_id: str = f"attributes.{self.__client.get_attributes_id_by_title(project=self.__project)['Components']}"
        return str({
            "type": "AND",
            "right": {"type": Operators.eq, "key": component_attr_id, "value": self.__component},
            "left": filter_expression
        }).replace("'", '"')

    def create_filter_by_attribute(self, attr_name: str, attr_value: str) -> str:
        attr_by_id = self.__client.get_attributes_id_by_title(project=self.__project)
        attr_id = attr_by_id[attr_name]
        filter_expression = urllib.parse.quote(str({
            "type": Operators.eq,
            "key": f'attributes.{attr_id}',
            "value": attr_value
        }).replace("'", '"'))
        return filter_expression

    def send_message_about_long_time_opened_versions(self, statuses: List[str] = None) -> None:
        def all_runs_finished(version_title: str) -> bool:
            def is_only_one_specified_elem_in_list(elem_list: list, elem: str) -> bool:
                return len(elem_list) == 1 and elem in elem_list

            testruns_statuses = self.__client.get_testruns(project=self.__project,
                                                           include='status',
                                                           expression=str({
                                                               "type": Operators.eq,
                                                               "key": Fields.version,
                                                               "value": version_title
                                                           }).replace("'", '"'))

            unique_testrun_statuses = unique(list(map(lambda testrun: testrun["status"], testruns_statuses)))

            return is_only_one_specified_elem_in_list(unique_testrun_statuses, RunStatus.finished)

        def get_long_time_opened_versions() -> List[Dict[str, Any]]:
            versions = self.__client.get_versions(project=self.__project, statuses=statuses)
            versions = list(filter(lambda version:
                                   days_between_today_and_ts(version["startedTime"]) > MAX_NOT_FINISHED_DAYS and
                                   version['title'] not in IGNORED_VERSIONS, versions))

            return list(map(lambda version: {
                "title": version["title"],
                "started": days_between_today_and_ts(version["startedTime"]),
                "createdBy": version["createdBy"],
                "allTestRunsAreFinished": all_runs_finished(version["title"])
            }, versions))

        def prepare_message(data: List[Dict[str, Any]]) -> str:
            messages = ""
            for version in data:
                runs_status = 'Да' if version["allTestRunsAreFinished"] else 'Нет'
                messages += TestPalmMessages.long_time_opened_version.format(self.__project, version['title'],
                                                                             version['title'], version['started'],
                                                                             runs_status)
            return TestPalmMessages.long_time_opened_versions.format(self.__project, messages)

        long_time_opened_versions = get_long_time_opened_versions()

        if len(long_time_opened_versions) == 0:
            return

        message = prepare_message(data=long_time_opened_versions)
        mail_sender = MailSender(recipient_list=self.get_recipient_by_component(),
                                 subject=TestPalmSubjects.long_time_opened_version.format(self.__project),
                                 header=TestPalmMessages.header,
                                 body=message)
        mail_sender.send()

    def send_message_about_unused_cases(self) -> None:
        attr_name = 'Reminder'

        def get_unused_cases() -> Optional[Dict[str, Any]]:
            cases = self.__client.get_testcases(project=self.__project,
                                                include='stats,id',
                                                expression=self.filter_expression_with_current_component({
                                                    "type": Operators.eq,
                                                    "key": Fields.status,
                                                    "value": CaseStatus.actual}))
            case_id_to_case_last_run = list(map(lambda case: {
                "id": case["id"],
                "last_run_days_ago": days_between_today_and_ts(ts=case["stats"]["latestRunTime"])
            }, cases))
            unused_cases = list(filter(lambda x: x["last_run_days_ago"] > MAX_UNUSED_CASE_DAYS, case_id_to_case_last_run))

            if len(unused_cases) == 0:
                return

            case_ids = list(map(lambda case: case["id"], unused_cases))
            tag = f'unused_cases_{int(datetime.now().timestamp())}'
            self.__client.update_testcases_attribute_value(project=self.__project, case_ids=case_ids, action=Action.add,
                                                           attr_name=attr_name, attr_values=[tag])
            return {
                "unused_cases": unused_cases,
                "attr_name": attr_name,
                "attr_value": tag,
                "case_ids": case_ids
            }

        def prepare_message(filter_expression: str) -> str:
            message = TestPalmMessages.unused_cases.format(self.__project, self.__project, filter_expression)
            return message

        unused_cases = get_unused_cases()

        if unused_cases is None:
            return

        filter_expression = self.create_filter_by_attribute(attr_name=unused_cases["attr_name"],
                                                            attr_value=unused_cases["attr_value"])
        message = prepare_message(filter_expression)
        mail_sender = MailSender(recipient_list=self.get_recipient_by_component(),
                                 subject=TestPalmSubjects.unused_cases.format(self.__project),
                                 header=TestPalmMessages.header,
                                 body=message)
        mail_sender.send()

    def send_message_about_cases_in_status_on_review_draft_needs_change(self):
        attr_name = 'Reminder'

        def get_testcases_ids(status: str):
            cases = self.__client.get_testcases(project=self.__project,
                                                include='id,createdTime',
                                                expression=self.filter_expression_with_current_component({
                                                    "type": Operators.eq,
                                                    "key": Fields.status,
                                                    "value": status}))
            case_ids = list(map(lambda case: case['id'], filter(lambda case: case['createdTime'] > MAX_DAYS_IN_STATUS_DRAFT_ON_REVIEW_NEEDS_CHANGES, cases)))
            return case_ids

        def add_tag_to_testcases(case_ids: List[int]) -> Dict[str, str]:
            tag = f'{status}_cases_{int(datetime.now().timestamp())}'
            self.__client.update_testcases_attribute_value(project=self.__project, case_ids=case_ids, action=Action.add,
                                                           attr_name=attr_name, attr_values=[tag])
            return {
                "attr_name": attr_name,
                "attr_value": tag
            }

        statuses = [CaseStatus.on_review, CaseStatus.draft, CaseStatus.needs_changes]
        message = ""

        for status in statuses:
            case_ids = get_testcases_ids(status)
            if len(case_ids) > 0:
                tag = add_tag_to_testcases(case_ids)
                filter_expression = self.create_filter_by_attribute(attr_name=tag["attr_name"],
                                                                    attr_value=tag["attr_value"])
                message += TestPalmMessages.case_with_status.format(status.capitalize(),
                                                                    self.__project,
                                                                    filter_expression)
        if message == "":
            return

        mail_sender = MailSender(recipient_list=self.get_recipient_by_component(),
                                 subject=TestPalmSubjects.cases_with_status.format(self.__project, ', '.join(statuses)),
                                 header=TestPalmMessages.header,
                                 body=TestPalmMessages.cases_with_status.format(self.__project, ', '.join(statuses), message))
        mail_sender.send()


if __name__ == '__main__':
    components = [Component.ios, Component.android]
    for component in components:
        scripts = TestPalmScripts(project=Projects.mobilemail, component=component, client=TestPalmClient(auth=OAUTH_TOKEN_TESTPALM))
        scripts.send_message_about_cases_in_status_on_review_draft_needs_change()
        scripts.send_message_about_long_time_opened_versions(statuses=[VersionStatus.started])
        scripts.send_message_about_unused_cases()
