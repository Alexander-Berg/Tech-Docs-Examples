const debuglog = require('util').debuglog('hermione-testpalm-filter');
const got = require('got');

const pkg = require('../package');

const defaultConfig = {
    apiHost: 'https://testpalm.yandex-team.ru',
    requestOptions: {
        timeout: 5000,
        rejectUnauthorized: false,
        headers: {
            'User-Agent': `hermione-testpalm-filter v${pkg.version} (https://github.yandex-team.ru/toolbox/hermione-testpalm-filter)`,
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

        return got(url, options).then(res => res.body);
    }
}

module.exports = TestpalmApi;
