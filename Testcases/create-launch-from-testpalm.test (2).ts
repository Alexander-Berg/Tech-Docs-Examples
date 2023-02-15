import debugFactory, { IDebugger } from 'debug';
import request from 'supertest';
import TestPalmApiClient from '@yandex-int/testpalm-api';

import createApp from '../src/app';
import LaunchApiService from '../src/lib/api/launch/launch';
import TestpalmApiService from '../src/lib/api/testpalm/testpalm';
import BookingApiService from '../src/lib/api/booking';

import createDBMock, { TestDB } from './helpers/test-db';
import createTestpalmApiMock from './helpers/testpalm-api';
import createBookingApiServiceMock from './helpers/booking-api';

describe('POST /api/v1/launch/create-from-testpalm', () => {
    let debug: IDebugger;
    let db: TestDB;
    let launchApi: LaunchApiService;
    let testpalmApi: TestpalmApiService;
    let bookingApi: BookingApiService;
    let testpalmApiClientMock: TestPalmApiClient;

    beforeEach(async() => {
        debug = debugFactory('test');
        db = createDBMock();

        await db.initialize();

        launchApi = new LaunchApiService({ debug, db });

        testpalmApiClientMock = createTestpalmApiMock(jest.fn);

        testpalmApi = new TestpalmApiService({
            debug,
            testpalmApi: testpalmApiClientMock,
        });

        bookingApi = createBookingApiServiceMock(jest.fn);
    });

    afterEach(async() => {
        await db.flushDB();
        await db.close();
    });

    it('should return 303 with Location header', () => {
        testpalmApiClientMock.getTestSuite = jest.fn().mockResolvedValue({ id: 1, properties: [] });
        const app = createApp({ launchApi, testpalmApi, bookingApi });

        const payload = [
            'title=test-title',
            'project=serp-js',
            'author=robot-serp-bot',
            'type=testsuite',
            `content=${JSON.stringify({ testSuiteId: 'fake-testsuite-id' })}`,
        ].join('&');

        return request(app)
            .post('/api/v1/launch/create-from-testpalm')
            .set('Content-Type', 'application/x-www-form-urlencoded')
            .send(payload)
            .expect(303)
            .expect('Location', /\/client\/launch/);
    });

    it('should return 406 when payload are invalid', async() => {
        const app = createApp({ launchApi, testpalmApi, bookingApi });

        const payload = [
            'title=test-title',
            'project=serp-js',
            'author=robot-serp-bot',
            'type=testplan',
            `content=${JSON.stringify({ testSuiteId: 'fake-testsuite-id' })}`,
        ].join('&');

        const response = await request(app)
            .post('/api/v1/launch/create-from-testpalm')
            .set('Content-Type', 'application/x-www-form-urlencoded')
            .send(payload)
            .expect('Content-Type', /json/)
            .expect(406);

        const actual = response.body;

        expect(typeof actual).not.toBeNull();
        expect(typeof actual).toBe('object');

        return response;
    });

    it('should return 406 when unknown type presented', async() => {
        const app = createApp({ launchApi, testpalmApi, bookingApi });

        const payload = [
            'title=test-title',
            'project=serp-js',
            'author=robot-serp-bot',
            'type=unknown-type',
            `content=${JSON.stringify({ testsuiteId: 'fake-testsuite-id' })}`,
        ].join('&');

        const response = await request(app)
            .post('/api/v1/launch/create-from-testpalm')
            .set('Content-Type', 'application/x-www-form-urlencoded')
            .send(payload)
            .expect('Content-Type', /json/)
            .expect(406);

        const actual = response.body;

        expect(typeof actual).not.toBeNull();
        expect(typeof actual).toBe('object');

        return response;
    });
});
