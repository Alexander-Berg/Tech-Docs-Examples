import requests


class Auth:
    def __init__(self, login, token):
        self.__login = login
        self.__token = token

    @property
    def login(self):
        return self.__login

    @property
    def token(self):
        return self.__token


class TestPalmApi:
    def __init__(self, auth, host='https://testpalm-api.yandex-team.ru'):
        self.__auth = auth
        self.__host = host
        self.__headers = {
            'Authorization': 'OAuth {}'.format(self.__auth.token),
            'Content-Type': 'application/json'
        }

    @property
    def host(self):
        return self.__host

    def __make_req_internal(self, path, method, payload=None):
        method_name = str(method).upper()
        if method_name == 'GET':
            req = requests.get('{}{}'.format(self.__host, path), headers=self.__headers, verify = False)
        elif method_name == 'PUT':
            req = requests.put('{}{}'.format(self.__host, path), json=payload, headers=self.__headers, verify = False)
        elif method_name == 'POST':
            req = requests.post('{}{}'.format(self.__host, path), json=payload, headers=self.__headers, verify = False)
        elif method_name == 'DELETE':
            req = requests.delete('{}{}'.format(self.__host, path), headers=self.__headers, verify = False)
        elif method_name == 'PATCH':
            req = requests.patch('{}{}'.format(self.__host, path), json=payload, headers=self.__headers, verify = False)
        else:
            raise Exception('Method {} is not supported!'.format(method_name))
        # if req and req.status_code == requests.codes.ok:
        #     print 'method {} with path {} returned {}'.format(method_name, path, req.json())
        # noinspection PyBroadException
        try:
            res = req.json()
        except Exception:
            res = req.content
        return res

    def get_project(self, project_id):
        return self.__make_req_internal('/{}'.format(project_id), 'GET')

    def get_definition(self, project_id):
        return self.__make_req_internal('/definition/{}'.format(project_id), 'GET')

    def get_testcases_for_project(self, project_id, include_fields=None, exclude_fields=None, limit=None, skip=None, expression=None):
        params = {}
        if include_fields:
            params['include'] = ','.join(include_fields)
        if exclude_fields:
            params['exclude'] = ','.join(exclude_fields)
        if limit:
            params['limit'] = limit
        if skip:
            params['skip'] = skip
        if expression:
            params['expression'] = expression
        params_stringified = '&'.join(["{}={}".format(k, v) for k, v in params.items()])
        return self.__make_req_internal('/testcases/{}?{}'.format(project_id, params_stringified), 'GET')

    def get_testruns_for_project(self, project_id, include_fields=None, exclude_fields=None, limit=None, skip=None, expression=None):
        params = {}
        if include_fields:
            params['include'] = ','.join(include_fields)
        if exclude_fields:
            params['exclude'] = ','.join(exclude_fields)
        if limit:
            params['limit'] = limit
        if skip:
            params['skip'] = skip
        if expression:
            params['expression'] = expression
        params_stringified = '&'.join(["{}={}".format(k, v) for k, v in params.items()])
        return self.__make_req_internal('/testrun/{}?{}'.format(project_id, params_stringified), 'GET')

    def get_testrun(self, project_id, testrun_id, testcase_id):
        # /testrun/{projectId}/{testrunId}/{testcaseId}
        return self.__make_req_internal('/testrun/{project_id}/{testrun_id}/{testcase_id}'.format(
            project_id = project_id,
            testrun_id = testrun_id,
            testcase_id = testcase_id
        ), 'GET')

    def get_testrun_comments(self, project_id, testrun_id, testcase_id):
        # /testrun/{projectId}/{testrunId}/{testcaseId}
        return self.__make_req_internal('/testrun/{project_id}/{testrun_id}/{testcase_id}/comments'.format(
            project_id = project_id,
            testrun_id = testrun_id,
            testcase_id = testcase_id
        ), 'GET')

    def patch_testcases(self, project_id, testcases_update_dict):
        return self.__make_req_internal('/testcases/{}'.format(project_id), 'PATCH', payload=testcases_update_dict)

    def patch_testcases_bulk(self, project_id, new_testcases_array):
        return self.__make_req_internal('/testcases/{}/bulk'.format(project_id), 'PATCH', payload=new_testcases_array)



