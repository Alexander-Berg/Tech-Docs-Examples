#!/usr/bin/env node

const fs = require('fs');
const {join} = require('path');
const rp = require('request-promise');

const TESTPALM_STATUS = 'data/testpalm.json';
const PACKAGES = 'data/packages.json';
const SUITES = 'data/suites.json';
const BEHAVIORS = 'data/behaviors.json';

const SOX_ID = '56baf83b88955028cadd30e7';
const KADAVR_MARK = '\u24C0';

const project = process.env['hermione-allure_testpalm_project'] || 'marketmbi';
const hasCerts = Boolean(process.env.NODE_EXTRA_CA_CERTS);

async function main() {
    const [reportDir] = process.argv.slice(2);

    if (!fs.existsSync(reportDir)) throw Error('Report directory?');

    const params = `include=id,status,stats,bugs,tasks,attributes.${SOX_ID}`;
    const url = `https://testpalm-api.yandex-team.ru/testcases/${project}?${params}`;
    const {TESTPALM_OAUTH_API_TOKEN: TOKEN} = process.env;
    const runIssue = process.env['hermione-allure_testpalm_run_issue'];
    const tests = await rp({
        url,
        headers: {
            accept: 'application/json',
            Authorization: `OAuth ${TOKEN}`,
        },
        rejectUnauthorized: !hasCerts, // InternalCA
        json: true,
    });
    const statuses = tests
        // NOTICE sync with pipacth.js refreshTestpalm
        .map(({id, stats, bugs, tasks, attributes}) => ({
            id,
            status: stats && stats.latestRunStatus,
            ts: stats && stats.latestRunTime,
            bugs: (bugs || []).map(bug => bug.id),
            tasks: (tasks || []).map(task => task.id),
            isSOX: ((attributes || {})[SOX_ID] || [])[0] === 'yes',
        }));
    const report = {
        project,
        ts: Date.now(),
        runIssue,
        statuses,
    };

    try {
        const releaseName = process.env['hermione-allure_testpalm_run_version'];

        if (releaseName) {
            // eslint-disable-next-line @typescript-eslint/no-var-requires,global-require
            const {getVersionId} = require('../release-checker/issuesInRelease');

            report.versionId = await getVersionId(releaseName);
        }
    } catch (e) {
        console.error(e);
    }

    fs.writeFileSync(join(reportDir, TESTPALM_STATUS), JSON.stringify(report, null, 1));

    // patch packages newFailed

    const statusMap = new Map(statuses.map(x => [`${project}-${x.id}`, x]));
    const newFailedUidSet = new Set();
    const packages = JSON.parse(fs.readFileSync(join(reportDir, PACKAGES), 'utf8'));
    const suites = JSON.parse(fs.readFileSync(join(reportDir, SUITES), 'utf8'));
    const behaviors = JSON.parse(fs.readFileSync(join(reportDir, BEHAVIORS), 'utf8'));
    let newFailed = 0;

    function walk(node) {
        const {children, name, status, uid, parameters} = node;

        if (Array.isArray(parameters)) {
            if (parameters.includes('kadavr')) {
                node.name = `${name} ${KADAVR_MARK}`;
            }
            node.parameters = [];
        }
        if (status && !/^(passed|skipped)$/i.test(status)) {
            const tp = statusMap.get(name);

            if (tp && tp.status === 'PASSED') {
                newFailedUidSet.add(uid);
                node.newFailed = true;
                ++newFailed;
            }
        } else if (children) {
            children.forEach(x => walk(x));
        }
    }

    function walkUid(node) {
        const {name, children, uid, parameters} = node;

        if (Array.isArray(parameters)) {
            if (parameters.includes('kadavr')) {
                node.name = `${name} ${KADAVR_MARK}`;
            }
            node.parameters = [];
        }
        if (newFailedUidSet.has(uid)) {
            node.newFailed = true;
        } else if (children) {
            children.forEach(x => walkUid(x));
        }
    }

    walk(packages);
    walkUid(suites);
    walkUid(behaviors);

    console.warn(`New failed: ${newFailed}`);

    fs.writeFileSync(join(reportDir, PACKAGES), JSON.stringify(packages, null, 1));
    fs.writeFileSync(join(reportDir, SUITES), JSON.stringify(suites, null, 1));
    fs.writeFileSync(join(reportDir, BEHAVIORS), JSON.stringify(behaviors, null, 1));
}

main().catch(err => {
    console.error(err.message);
    process.exit(1);
});
