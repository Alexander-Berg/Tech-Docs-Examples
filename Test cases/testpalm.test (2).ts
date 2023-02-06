import debugFactory, { IDebugger } from 'debug';
import TestpalmApi from '@yandex-int/testpalm-api';

import { LaunchTypes, Launch, LaunchStatuses, LaunchId } from '../../../models/Launch';
import TestpalmApiService, {
    LaunchAlreadyStartedError,
    LaunchTypeNotImplementedError,
    TestPalmTestSuiteFetchError,
    TestPalmTestRunCreationError,
    TestPalmTestCasesFetchError,
    TestPalmProjectFetchError,
} from './testpalm';

function createLaunch(launch: Partial<Launch> = {}): Launch {
    return {
        _id: 'fake-id' as unknown as LaunchId,
        title: 'test-title',
        project: 'test-project',
        author: 'robot',
        type: LaunchTypes.testsuite,
        content: {
            testsuiteId: 'fake-test-suite',
        },
        status: LaunchStatuses.draft,
        platform: 'desktop',
        tags: [],
        properties: [],
        environments: [],
        testRunIds: [],
        bookingId: 123,
        createdAt: 1,
        updatedAt: 1,

        ...launch as Launch,
    };
}

function createTestpalmApi() {
    return {
        getTestSuite: jest.fn().mockImplementation((_, id: string) => Promise.resolve({
            id,
            filter: { expression: {} },
        })),
        addTestRun: jest.fn().mockResolvedValue(([{ id: '123' }, { id: '321' }])),
        getTestCasesWithPost: jest.fn().mockResolvedValue(([{ id: '111' }, { id: '222' }])),
        getProject: jest.fn().mockResolvedValue({ id: 'serp-js', title: 'serp js' }),
    } as unknown as TestpalmApi;
}

describe('TestpalmApiService', () => {
    let debug: IDebugger;

    beforeEach(() => {
        debug = debugFactory('test');
    });

    describe('.createRunFromLaunch', () => {
        it('should return array of created test-runs', async() => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch();
            const runnerConfig = {
                title: 'United',
                runnerId: 'bulkcurl',
            };

            const expected = [{ id: '123' }, { id: '321' }];

            const actual = await api.createRunFromLaunch(launch, runnerConfig);

            expect(Array.isArray(actual)).toBe(true);
            expect(actual).toEqual(expected);
        });

        it('should create run with correctly filled fields', async() => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch({
                environments: ['Chrome_80'],
                tags: ['serp-js'],
                properties: [
                    { key: 'platform', value: 'tv' },
                    { key: 'hitman_booking_id', value: '333' },
                    { key: 'custom_prop', value: 'special value' },
                ],
            });

            const runnerConfig = {
                title: 'United',
                runnerId: 'bulkcurl',
            };

            const expected = {
                testSuite: { id: 'fake-test-suite', filter: { expression: {} }, properties: [] },
                title: 'test-title',
                tags: ['serp-js'],
                properties: [
                    { key: 'custom_prop', value: 'special value' },
                    { key: 'crowdtest_runner_launch_id', value: 'fake-id' },
                    { key: 'responsible_user', value: 'robot' },
                    { key: 'platform', value: 'desktop' },
                    { key: 'hitman_booking_id', value: '123' },
                ],
                participants: ['robot'],
                environments: [
                    { title: 'Chrome_80', description: '' },
                ],
                runnerConfig: {
                    title: 'United',
                    runnerId: 'bulkcurl',
                },
            };

            await api.createRunFromLaunch(launch, runnerConfig);

            expect(testpalmApi.addTestRun).toHaveBeenCalledTimes(1);
            expect(testpalmApi.addTestRun).toHaveBeenCalledWith('test-project', expected);
        });

        it('should create run without booking field if it has a null value', async() => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });

            const runnerConfig = {
                title: 'United',
                runnerId: 'bulkcurl',
            };

            const launch = createLaunch({
                bookingId: null,
            });

            await api.createRunFromLaunch(launch, runnerConfig);

            expect(testpalmApi.addTestRun).toHaveBeenCalledTimes(1);
            expect(testpalmApi.addTestRun).toHaveBeenCalledWith('test-project', expect.objectContaining({
                properties: expect.not.arrayContaining([
                    { key: 'hitman_booking_id', value: expect.anything() },
                ]),
            }));
        });

        it('should build special test-suite for launch with "expression" type', async() => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch({
                environments: ['Chrome_80'],
                tags: ['serp-js'],
                type: LaunchTypes.expression,
                content: {
                    expression: '{"type": "NEQ", "value": "null", "key": "attributes.5cb05f1db5d1e20028a8487a"}',
                },
            });

            const runnerConfig = {
                title: 'United',
                runnerId: 'bulkcurl',
            };

            const expected = {
                testSuite: {
                    $new: true,
                    filter: {
                        expression: { type: 'NEQ', value: 'null', key: 'attributes.5cb05f1db5d1e20028a8487a' },
                    },
                    ignoreSuiteOrder: true,
                    groups: [],
                    orders: [],
                },
                title: 'test-title',
                tags: ['serp-js'],
                properties: [
                    { key: 'crowdtest_runner_launch_id', value: 'fake-id' },
                    { key: 'responsible_user', value: 'robot' },
                    { key: 'platform', value: 'desktop' },
                    { key: 'hitman_booking_id', value: '123' },
                ],
                participants: ['robot'],
                environments: [
                    { title: 'Chrome_80', description: '' },
                ],
                runnerConfig: {
                    title: 'United',
                    runnerId: 'bulkcurl',
                },
            };

            await api.createRunFromLaunch(launch, runnerConfig);

            expect(testpalmApi.addTestRun).toHaveBeenCalledTimes(1);
            expect(testpalmApi.addTestRun).toHaveBeenCalledWith('test-project', expected);
        });

        it('should throw LaunchAlreadyStartedError when attempting to start already started launch', () => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch({ status: LaunchStatuses.started, testRunIds: ['123'] });

            const runnerConfig = {
                title: 'United',
                runnerId: 'bulkcurl',
            };

            const actual = api.createRunFromLaunch(launch, runnerConfig);

            expect(actual).rejects.toThrow(LaunchAlreadyStartedError);
        });

        it('should throw LaunchTypeNotImplementedError when attempting to create run with unsupported launch type', () => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch({ type: LaunchTypes.testplan });

            const runnerConfig = {
                title: 'United',
                runnerId: 'bulkcurl',
            };

            const actual = api.createRunFromLaunch(launch, runnerConfig);

            expect(actual).rejects.toThrow(LaunchTypeNotImplementedError);
        });

        it('should throw TestPalmTestSuiteFetchError when failed to fetch testsuite', () => {
            const testpalmApi = createTestpalmApi();
            testpalmApi.getTestSuite = jest.fn().mockImplementation(() => Promise.reject(new Error('network error')));
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch();

            const runnerConfig = {
                title: 'United',
                runnerId: 'bulkcurl',
            };

            const actual = api.createRunFromLaunch(launch, runnerConfig);

            expect(actual).rejects.toThrow(TestPalmTestSuiteFetchError);
        });

        it('should throw TestPalmTestRunCreationError when failed to create test-run', () => {
            const testpalmApi = createTestpalmApi();
            testpalmApi.addTestRun = jest.fn().mockImplementation(() => Promise.reject(new Error('network error')));
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch();

            const runnerConfig = {
                title: 'United',
                runnerId: 'bulkcurl',
            };

            const actual = api.createRunFromLaunch(launch, runnerConfig);

            expect(actual).rejects.toThrow(TestPalmTestRunCreationError);
        });
    });

    describe('.getTestcasesForLaunch', () => {
        it('should return array of test-cases', async() => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch();

            const expected = [{ id: '111' }, { id: '222' }];

            const actual = await api.getTestcasesForLaunch(launch, { include: ['id'] });

            expect(Array.isArray(actual)).toBe(true);
            expect(actual).toEqual(expected);
        });

        it('should fetch testsuite for launch with type === "testsuite"', async() => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch();

            await api.getTestcasesForLaunch(launch, { include: ['id'] });

            expect(testpalmApi.getTestSuite).toHaveBeenCalled();
            expect(testpalmApi.getTestSuite).toHaveBeenCalledWith('test-project', 'fake-test-suite');
        });

        it('should fetch test-cases with passed filter', async() => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch({ type: LaunchTypes.expression, content: { expression: 'some-expression' } });

            const expected = {
                include: ['id'],
                expression: 'some-expression',
            };

            await api.getTestcasesForLaunch(launch, { include: ['id'] });

            expect(testpalmApi.getTestCasesWithPost).toHaveBeenCalled();
            expect(testpalmApi.getTestCasesWithPost).toHaveBeenCalledWith('test-project', expected);
        });

        it('should throw LaunchTypeNotImplementedError when attempting to fetch test-cases with unsupported launch type', () => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch({ type: LaunchTypes.testplan });

            const actual = api.getTestcasesForLaunch(launch);

            return expect(actual).rejects.toThrow(LaunchTypeNotImplementedError);
        });

        it('should throw TestPalmTestCasesFetchError when failed to fetch test-cases', () => {
            const testpalmApi = createTestpalmApi();
            testpalmApi.getTestCasesWithPost = jest.fn().mockRejectedValue(new Error('network error'));

            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch();

            const actual = api.getTestcasesForLaunch(launch);

            return expect(actual).rejects.toThrow(TestPalmTestCasesFetchError);
        });

        it('should throw TestPalmTestCasesFetchError when failed to fetch test-suite', () => {
            const testpalmApi = createTestpalmApi();
            testpalmApi.getTestSuite = jest.fn().mockImplementation(() => Promise.reject(new Error('network error')));

            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch();

            const actual = api.getTestcasesForLaunch(launch);

            return expect(actual).rejects.toThrow(TestPalmTestCasesFetchError);
        });
    });

    describe('.findPlatformInTestSuiteProperties', () => {
        it('should return null if platform property is not presented', () => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });

            const properties = [{ key: 'not a platform', value: 'value' }];

            const expected = null;

            const actual = api.findPlatformInTestSuiteProperties(properties);

            expect(actual).toEqual(expected);
        });

        it('should return null if platform property presented but has invalid value', () => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });

            const properties = [{ key: 'platform', value: 'smarttv' }];

            const expected = null;

            const actual = api.findPlatformInTestSuiteProperties(properties);

            expect(actual).toEqual(expected);
        });

        it('should return platform when property presented with valid value', () => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });

            const properties = [{ key: 'platform', value: 'desktop' }];

            const expected = 'desktop';

            const actual = api.findPlatformInTestSuiteProperties(properties);

            expect(actual).toEqual(expected);
        });
    });

    describe('.getTestPalmProjectForLaunch', () => {
        it('should return project', async() => {
            const testpalmApi = createTestpalmApi();
            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch();

            const expected = { id: 'serp-js', title: 'serp js' };

            const actual = await api.getTestPalmProjectForLaunch(launch);

            expect(actual).toEqual(expected);
        });

        it('should throw TestPalmProjectFetchError when failed to fetch error', () => {
            const testpalmApi = createTestpalmApi();
            testpalmApi.getProject = jest.fn().mockRejectedValue(new Error('network error'));

            const api = new TestpalmApiService({ debug, testpalmApi });
            const launch = createLaunch();

            const actual = api.getTestPalmProjectForLaunch(launch);

            return expect(actual).rejects.toThrow(TestPalmProjectFetchError);
        });
    });
});
