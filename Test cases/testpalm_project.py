from tp_api_client.tp_api_client import TestPalmClient
from helpers import convert_filter
from constants import OAUTH_TOKEN_TESTPALM


class TestPalmProject:
    def __init__(self, project):
        self.__project_name = project
        self.__client = TestPalmClient(auth=OAUTH_TOKEN_TESTPALM)
        self.__definitions = self.__client.get_project_definitions(project=project)

    def project_name(self) -> str:
        return self.__project_name

    def __get_definition_id(self, name: str) -> str:
        definition_id = next((definition['id'] for definition in self.__definitions if definition['title'] == name), None)
        if definition_id is None:
            raise ValueError(f'There is no definition with name "{name}" in project "{self.__project_name}"')
        return definition_id

    def get_attribute_key(self, attribute_name):
        if attribute_name in ['isAutotest', 'status']:
            return attribute_name
        return f"attributes.{self.__get_definition_id(attribute_name)}"

    def count_cases_by_filter(self, cases_filter):
        return len(self.__request_testpalm_cases_by_filter(cases_filter))

    def __request_testpalm_cases_by_filter(self, expression):
        return self.__client.get_testcases(project=self.__project_name,
                                           include='id,isAutotest,attributes,status',
                                           expression=expression)

    def build_testpalm_filter(self, text_filter):
        return convert_filter(self, text_filter)
