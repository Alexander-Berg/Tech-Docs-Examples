import { IDebugger } from 'debug';
import ExtendableError from 'es6-error';
import TestpalmApi, {
    Project,
    TestRunSuite,
    TestRunCreation,
    TestRunRunnerConfigCreation as RunnerConfig,
    Filter,
    TestCase,
    TestRunParameter,
    TestSuiteProperty,
} from '@yandex-int/testpalm-api';

import {
    Launch,
    LaunchStatuses,
    LaunchTypes,
    LaunchFromTestSuite,
    LaunchFromExpression,
    LaunchPlatform,
    LaunchProperty,
} from '../../../models/Launch';

export type Dependencies = {
    debug: IDebugger;
    testpalmApi: TestpalmApi;
};

const CROWDTEST_RUNNER_ID_PROPERTY_NAME = 'crowdtest_runner_launch_id';
const BOOKING_ID_PROPERTY_NAME = 'hitman_booking_id';
const RESPONSIBLE_USER_PROPERTY_NAME = 'responsible_user';
const PLATFORM_PROPERTY_NAME = 'platform';
const SPECIAL_PROPERTIES_NAMES = new Set([
    CROWDTEST_RUNNER_ID_PROPERTY_NAME,
    BOOKING_ID_PROPERTY_NAME,
    RESPONSIBLE_USER_PROPERTY_NAME,
    PLATFORM_PROPERTY_NAME,
]);
const ALLOWED_PLATFORMS = new Set<LaunchPlatform>(['desktop', 'pad', 'touch', 'searchapp', 'tv']);

export class LaunchAlreadyStartedError extends ExtendableError {
    testRunIds: string[];

    constructor(launch: Launch) {
        super(`launch "${launch._id}" already started, test-runs ids: ${launch.testRunIds.join(', ')}`);

        this.testRunIds = launch.testRunIds;
    }
}

export class LaunchTypeNotImplementedError extends ExtendableError {
    constructor(type: string) {
        super(`cannot create run from launch with type ${type}: not implemented`);
    }
}

export class TestPalmTestSuiteFetchError extends ExtendableError {
    constructor(error: Error) {
        super(`cannot fetch test-suite: ${error}`);
    }
}

export class TestPalmTestRunCreationError extends ExtendableError {
    constructor(error: Error) {
        super(`cannot create run from launch: ${error}`);
    }
}

export class TestPalmTestCasesFetchError extends ExtendableError {
    constructor(error: Error) {
        super(`cannot fetch test-cases: ${error}`);
    }
}

export class TestPalmProjectFetchError extends ExtendableError {
    constructor(project: string, error: Error) {
        super(`cannot fetch project "${project}" from TestPalm: ${error}`);
    }
}

export default class TestpalmApiService {
    constructor(private readonly _deps: Dependencies) {}

    async createRunFromLaunch(launch: Launch, runnerConfig: RunnerConfig) {
        if (launch.status === LaunchStatuses.started) {
            throw new LaunchAlreadyStartedError(launch);
        }

        const runBody = await this._buildRunFromLaunch(launch, runnerConfig);

        try {
            return await this._deps.testpalmApi.addTestRun(launch.project, runBody);
        } catch (error) {
            const creationError = new TestPalmTestRunCreationError(error);

            this._deps.debug(`${creationError.message}, %o`, error);

            throw creationError;
        }
    }

    protected async _buildRunFromLaunch(launch: Launch, runnerConfig: RunnerConfig): Promise<TestRunCreation> {
        const commonRun = this._buildCommonTestRunFromLaunch(launch, runnerConfig);

        switch (launch.type) {
            case LaunchTypes.testsuite: return {
                ...commonRun,
                testSuite: await this._fetchTestSuiteFromLaunchForTestRun(launch),
            };
            case LaunchTypes.expression: return {
                ...commonRun,
                testSuite: this._buildTestSuiteWithExpression(launch),
            };
        }

        throw new LaunchTypeNotImplementedError(launch.type);
    }

    private _buildCommonTestRunFromLaunch(launch: Launch, runnerConfig: RunnerConfig) {
        return {
            title: launch.title,
            tags: launch.tags,
            participants: [launch.author],
            environments: this._buildEnvironments(launch),
            properties: this._buildProperties(launch),
            runnerConfig,
        };
    }

    private _buildEnvironments(launch: Launch) {
        return launch.environments.map(env => ({ title: env, description: '' }));
    }

    private _buildProperties(launch: Launch): TestRunParameter[] {
        const properties = [
            ...this._filterSpecialProperties(launch.properties),

            { key: CROWDTEST_RUNNER_ID_PROPERTY_NAME, value: `${launch._id}` },
            { key: RESPONSIBLE_USER_PROPERTY_NAME, value: launch.author },
            { key: PLATFORM_PROPERTY_NAME, value: `${launch.platform}` },
        ];

        /**
         * Изначально предполагалось, что сервис будет работать только с обычной бронью, но со временем потребовалось
         * использовать регулярную бронь, которая указывается в отдельном поле.
         *
         * Нужно почистить после FEI-19362.
         */
        if (launch.bookingId !== null) {
            properties.push({ key: BOOKING_ID_PROPERTY_NAME, value: `${launch.bookingId}` });
        }

        return properties;
    }

    private _filterSpecialProperties(properties: LaunchProperty[]): LaunchProperty[] {
        return properties.filter(prop => !SPECIAL_PROPERTIES_NAMES.has(prop.key));
    }

    private async _fetchTestSuiteFromLaunchForTestRun(launch: LaunchFromTestSuite): Promise<TestRunSuite> {
        const testSuite = await this.fetchTestSuiteFromLaunch(launch);

        /**
         * Обнуляем, так как иногда приходят невалидные свойства,
         * из-за которых падает создание тест-рана.
         *
         * @see TESTPALM-2635
         *
         * @TODO выпилить после починки в TestPalm
         */
        testSuite.properties = [];

        return testSuite;
    }

    async fetchTestSuiteFromLaunch(launch: LaunchFromTestSuite): Promise<TestRunSuite> {
        try {
            return await this._deps.testpalmApi.getTestSuite(launch.project, launch.content.testsuiteId);
        } catch (error) {
            const fetchError = new TestPalmTestSuiteFetchError(error);

            this._deps.debug(fetchError.message);

            throw fetchError;
        }
    }

    private _buildTestSuiteWithExpression(launch: LaunchFromExpression): TestRunSuite {
        const filter = {
            expression: JSON.parse(launch.content.expression),
        };

        return {
            /**
             * Хак, с помощью которого TestPalm понимает, что тест-сьют не настоящий,
             * нужно использовать тест-кейсы из фильтра, указанного в переданном тест-сьюте.
             */
            $new: true,
            ignoreSuiteOrder: true,
            filter,
            groups: [],
            orders: [],
        } as unknown as TestRunSuite;
    }

    async getTestcasesForLaunch(launch: Launch, query: Filter<TestCase> = {}) {
        try {
            switch (launch.type) {
                case LaunchTypes.testsuite: return await this._getTestcasesFromLaunchByTestsuite(launch, query);
                case LaunchTypes.expression: return await this._getTestcasesFromLaunchByExpression(launch, query);
            }
        } catch (error) {
            const fetchError = new TestPalmTestCasesFetchError(error);

            this._deps.debug(`${fetchError.message}, %o`, error);

            throw fetchError;
        }

        throw new LaunchTypeNotImplementedError(launch.type);
    }

    private async _getTestcasesFromLaunchByTestsuite(launch: LaunchFromTestSuite, query: Filter<TestCase> = {}) {
        const testsuite = await this.fetchTestSuiteFromLaunch(launch);

        const expression = JSON.stringify(testsuite.filter?.expression);

        const filter = { ...query, expression };

        /**
         * @todo заменить на `getTestCases` после TESTPALM-2773
         * @see INFRADUTY-11437
         */
        return await this._deps.testpalmApi.getTestCasesWithPost(launch.project, filter);
    }

    private async _getTestcasesFromLaunchByExpression(launch: LaunchFromExpression, query: Filter<TestCase> = {}) {
        const filter = { ...query, expression: launch.content.expression };

        /**
         * @todo заменить на `getTestCases` после TESTPALM-2773
         * @see INFRADUTY-11437
         */
        return await this._deps.testpalmApi.getTestCasesWithPost(launch.project, filter);
    }

    findPlatformInTestSuiteProperties(properties: TestSuiteProperty[]): LaunchPlatform | null {
        const platformProperty = properties.find(this._isPlatformProperty);

        if (!platformProperty) return null;

        return platformProperty.value as LaunchPlatform;
    }

    private _isPlatformProperty(property: TestSuiteProperty): boolean {
        return property.key === PLATFORM_PROPERTY_NAME && ALLOWED_PLATFORMS.has(property.value as LaunchPlatform);
    }

    async getTestPalmProjectForLaunch(launch: Launch): Promise<Project> {
        const project = launch.project;

        this._deps.debug(`fetching project "${project}"`);

        try {
            return await this._deps.testpalmApi.getProject(project);
        } catch (error) {
            const fetchError = new TestPalmProjectFetchError(project, error);

            this._deps.debug(fetchError.message);

            throw fetchError;
        }
    }
}
