import { Collection } from 'mongodb';
import debugFactory, { IDebugger } from 'debug';
import { Request, Response } from 'express';

import LaunchApiService, { Dependencies as LaunchApiServiceDependencies } from '../../../lib/api/launch';
import TestpalmApiService from '../../../lib/api/testpalm';
import CreateLaunchFromTestpalmController from './create-launch-from-testpalm';
import * as errors from '../../errors';

import { getMockedDBClass, createCollectionStub } from '../../../../test/helpers/mocked-db';
import createTestpalmApiMock from '../../../../test/helpers/testpalm-api';

function createDbMock(collection: Partial<Collection> = {}) {
    const collectionStub = createCollectionStub(jest.fn);
    const MockedDB = getMockedDBClass({ ...collectionStub, ...collection });

    return new MockedDB();
}

function createLaunchApiServiceMock(deps: Partial<LaunchApiServiceDependencies> = {}) {
    const debug = debugFactory('test');

    return new LaunchApiService({ debug, db: createDbMock(), ...deps });
}

function createTestpalmApiServiceMock() {
    const debug = debugFactory('test');
    const testpalmApi = createTestpalmApiMock(jest.fn);

    return new TestpalmApiService({ debug, testpalmApi });
}

function getPayload(type = 'testsuite') {
    const contentByType: Record<string, Record<string, string>> = {
        testsuite: {
            testsuiteId: 'fake-testsuite-id',
        },
        testplan: {
            testplanId: 'fake-testplan-id',
        },
        testcases: {
            expression: 'fake expression',
        },
    };

    return {
        title: 'test-launch',
        project: 'test-project',
        author: 'robot',
        type,
        content: contentByType[type],
    };
}

function getMockedResponse() {
    return {
        status: jest.fn().mockReturnThis(),
        json: jest.fn().mockReturnThis(),
        end: jest.fn(),
        redirect: jest.fn(),
    } as unknown as Response;
}

describe('CreateLaunchFromTestpalmController', () => {
    let debug: IDebugger;

    beforeEach(() => {
        debug = debugFactory('test');
    });

    describe('.getParseBodyMiddleware', () => {
        it('should return function', () => {
            const launchApi = createLaunchApiServiceMock();
            const testpalmApi = createTestpalmApiServiceMock();
            const controller = new CreateLaunchFromTestpalmController({ debug, launchApi, testpalmApi, redirectUrlTemplate: '/client/:id' });

            const expected = 'function';

            const actual = controller.getParseBodyMiddleware();

            expect(typeof actual).toBe(expected);
        });

        it('should correctly work when content presented as string', () => {
            const launchApi = createLaunchApiServiceMock();
            const testpalmApi = createTestpalmApiServiceMock();
            const controller = new CreateLaunchFromTestpalmController({ debug, launchApi, testpalmApi, redirectUrlTemplate: '/client/:id' });

            const payload = getPayload();
            const body = { ...payload, content: JSON.stringify(payload.content) };

            const next = jest.fn();

            const middleware = controller.getParseBodyMiddleware();

            middleware({ body } as Request, {} as Response, next);

            expect(next).toHaveBeenCalled();
            expect(next).toHaveBeenCalledWith();
        });

        it('should return InvalidPayloadError when cannot parse payload', () => {
            const launchApi = createLaunchApiServiceMock();
            const testpalmApi = createTestpalmApiServiceMock();
            const controller = new CreateLaunchFromTestpalmController({ debug, launchApi, testpalmApi, redirectUrlTemplate: '/client/:id' });

            const payload = getPayload();
            const body = { ...payload, content: 'wrong payload' };

            const next = jest.fn();
            const response = getMockedResponse();
            const expected = new errors.InvalidPayloadError(
                'failed to parse content: SyntaxError: Unexpected token w in JSON at position 0',
            );

            const middleware = controller.getParseBodyMiddleware();

            middleware({ body } as Request, response, next);

            expect(next).toHaveBeenCalledWith(expected);
        });
    });

    describe('.getHandler', () => {
        it('should return function', () => {
            const launchApi = createLaunchApiServiceMock();
            const testpalmApi = createTestpalmApiServiceMock();
            const controller = new CreateLaunchFromTestpalmController({ debug, launchApi, testpalmApi, redirectUrlTemplate: '/client/:id' });

            const expected = 'function';

            const actual = controller.getHandler();

            expect(typeof actual).toBe(expected);
        });

        it('should return 303 when launch successfully created', async() => {
            const id = { toHexString() { return 'fake-id' } };
            const insertOneMock = jest.fn().mockResolvedValue({ insertedId: id });
            const db = createDbMock({ insertOne: insertOneMock });
            const launchApi = createLaunchApiServiceMock({ db });
            const testpalmApi = createTestpalmApiServiceMock();

            testpalmApi.fetchTestSuiteFromLaunch = jest.fn().mockResolvedValue({ id: 1, properties: [] });

            const controller = new CreateLaunchFromTestpalmController({ debug, launchApi, testpalmApi, redirectUrlTemplate: '/client/:id' });
            const handler = controller.getHandler();

            const request = { body: getPayload('testsuite') } as Request;
            const response = getMockedResponse();

            await handler(request, response);

            expect(response.redirect).toHaveBeenCalledWith(303, '/client/fake-id');
        });
    });
});
