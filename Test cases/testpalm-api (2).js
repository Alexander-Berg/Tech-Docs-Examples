const debuglog = require('util').debuglog('hermione-testpalm-reporter');

const got = require('got');
const FormData = require('form-data');
const PromiseQueue = require('promise-queue');

const pkg = require('../package');

const defaultConfig = {
    apiHost: 'https://testpalm.yandex-team.ru',
    requestOptions: {
        timeout: 5000,
        rejectUnauthorized: false,
        headers: {
            'User-Agent': `hermione-testpalm-reporter v${pkg.version} (https://github.yandex-team.ru/toolbox/hermione-testpalm-reporter)`,
        },
    },
};

class TestpalmApi {
    /**
     * @param {Object} config
     */
    constructor(config) {
        this._config = Object.assign(
            {},
            defaultConfig,
            config,
            {
                requestOptions: Object.assign({}, defaultConfig.requestOptions, config.requestOptions),
            },
        );

        this._queue = new PromiseQueue(1, Infinity);

        debuglog('create TestPalm API', this._config);
    }

    /**
     * @param {String} runId
     * @returns {Promise<Object>}
     */
    getTestRun(runId) {
        return this._request(`/api/testrun/${this._config.project}/${runId}`);
    }

    /**
     * @param {String} runId
     * @param {String} uuid
     * @param {String} status
     * @returns {Promise<Object>}
     */
    setTestCaseStatus(runId, uuid, status) {
        return this._request(`/api/testrun/${this._config.project}/${runId}/${uuid}/${status}`, {
            method: 'POST',
            body: {},
        });
    }

    /**
     * @param {String} runId
     * @param {String} uuid
     * @param {String} text
     * @returns {Promise<Object>}
     */
    addTestCaseComment(runId, uuid, text) {
        return this._request(`/api/runtestcase/${this._config.project}/${runId}/${uuid}/comments`, {
            method: 'POST',
            body: { text },
        });
    }

    /**
     * Загружает скриншот в TestPalm attachments
     *
     * @param {String} testCaseId
     * @param {String} base64
     * @returns {Promise<String>}
     * @private
     */
    uploadScreenshot(testCaseId, base64) {
        debuglog('Uploading screenshot...');

        const name = [
            'hermione',
            'testpalm',
            'reporter',
            this._config.project,
            testCaseId,
            `${new Date().toISOString()}.png`,
        ].join('-');

        const buffer = Buffer.from(base64, 'base64');
        const form = new FormData();
        form.append('file', buffer, name);
        form.append('fileDetail', JSON.stringify({
            fileName: name,
            size: buffer.length,
            type: 'image/png',
        }));
        form.append('size', buffer.length);

        return this
            ._request(`/api/testcases/${this._config.project}/${testCaseId}/attachment`, {
                method: 'POST',
                body: form,
                json: false,
            })
            .then(response => {
                const data = JSON.parse(response);

                debuglog(`Screenshot uploaded. URL: https://testpalm.yandex-team.ru${data.url}`);

                return data;
            });
    }

    /**
     * @param {String} url
     * @param {Object} [options]
     * @returns {Promise}
     */
    _request(url, options) {
        options = Object.assign(
            {
                method: 'GET',
                json: true,
            },
            options,
        );

        options.headers = Object.assign(
            {
                Authorization: `OAuth ${this._config.token}`,
            },
            options.headers,
        );

        url = `${this._config.apiHost}${url}`;

        debuglog(`${options.method} ${url}`, options);

        // Все запросы должны быть последовательные, чтобы гарантировать правильный порадок комментариев
        return this._queue
            .add(() => got(url, options))
            .then(res => res.body)
            .then(body => {
                // Отравляем не больше одного запроса за 1s
                return new Promise(resolve => {
                    setTimeout(() => resolve(body), 1000);
                });
            });
    }
}

module.exports = TestpalmApi;
