const fs = require('fs');
const path = require('path');
const {promisify} = require('util');

const TestpalmClient = require('@yandex-int/testpalm-api').default;
const {flatten} = require('lodash');

const fsReadFile = promisify(fs.readFile);
const fsWriteFile = promisify(fs.writeFile);

const REPORT_DIR_PATH = 'txt_reports';
const TESTPALM_IDS_REPORT_PATH = path.join(process.cwd(), `${REPORT_DIR_PATH}/testpalm_ids_report`);
const DIFFECTOR_PAGES_REPORT_PATH = path.join(process.cwd(), `${REPORT_DIR_PATH}/diffector_pages`);

const PROJECT_ID = 'vendor_auto';
const VENDORS_PAGE_ATTRIBUTE = 'attributes.59c3d790ac9801d3a4c5af39';
const DEFAULT_EXPRESSION = {
    type: 'IN',
    key: VENDORS_PAGE_ATTRIBUTE,
    value: '',
};

const testpalmClient = new TestpalmClient(process.env.TESTPALM_OAUTH_API_TOKEN, {
    retryPostMethod: true,
    retryCount: 3,
});

/* eslint-disable-next-line no-console */
const log = data => console.log(String(data));

const testPalmRequest = async filter => {
    try {
        const testcases = await testpalmClient.getTestCasesWithPost(PROJECT_ID, {
            include: ['id', 'attributes'],
            expression: filter,
        });

        log(`Found ${testcases.length} testcases`);

        return testcases.map(testcase => testcase.id);
    } catch (error) {
        //  TestPalm иногда возвращает 503 по непонятным причинам, даже когда все работает
        if (error.statusCode !== 503) {
            throw new Error(error);
        }

        return [];
    }
};

const getTestcases = async () => {
    const pagesList = await fsReadFile(DIFFECTOR_PAGES_REPORT_PATH, 'utf8');

    if (!pagesList) {
        return Promise.resolve([]);
    }

    const pages = pagesList.split(',');
    const filter = {
        ...DEFAULT_EXPRESSION,
        value: pages,
    };
    const filterFormatted = JSON.stringify(filter);

    return testPalmRequest(filterFormatted);
};

getTestcases()
    .then(async testcases => {
        if (!fs.existsSync(REPORT_DIR_PATH)) {
            fs.mkdirSync(REPORT_DIR_PATH);
        }

        if (!testcases.length) {
            await fsWriteFile(TESTPALM_IDS_REPORT_PATH, '')
                .then(() => {
                    log('No TestPalm cases found');
                });
            return;
        }

        const testcaseIds = flatten(testcases)
            .join('|');
        const formatedTestcaseIds = `${PROJECT_ID}-(${testcaseIds})`;

        await fsWriteFile(TESTPALM_IDS_REPORT_PATH, formatedTestcaseIds)
            .then(() => {
                log(`TestPalm case IDS successfully written to file ${TESTPALM_IDS_REPORT_PATH}`);
            });
    })
    .catch(error => {
        console.error(error);
    });
