import TestpalmApi from '@yandex-int/testpalm-api';

export default function createTestpalmApiMock(fn: Function) {
    return {
        getTestSuite: fn(),
        addTestRun: fn(),
    } as unknown as TestpalmApi;
}
