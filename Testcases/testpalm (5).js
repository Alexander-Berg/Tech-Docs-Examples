#!/usr/bin/env node

const fs = require('fs');
const {join} = require('path');
const rp = require('request-promise');

const TESTPALM_STATUS = 'data/testpalm.json';
const PACKAGES = 'data/packages.json';
const SUITES = 'data/suites.json';
const BEHAVIORS = 'data/behaviors.json';

async function main() {
    const [reportDir] = process.argv.slice(2);

    if (!fs.existsSync(reportDir)) throw Error('Report directory?');

    const url = 'https://testpalm-api.yandex-team.ru/testcases/marketmbi?include=id,status,stats,bugs';
    const {TESTPALM_OAUTH_API_TOKEN: TOKEN} = process.env;
    const tests = await rp({
        url,
        headers: {
            accept: 'application/json',
            Authorization: `OAuth ${TOKEN}`,
        },
        rejectUnauthorized: false, // InternalCA
        json: true,
    });
    const statuses = tests
        .filter(({status}) => status && status !== 'ARCHIVED')
        .map(({id, stats = {}, bugs = []}) => ({
            id,
            status: stats.latestRunStatus,
            ts: stats.latestRunTime,
            bugs: bugs.filter(bug => bug && !bug.isResolved).map(bug => bug.id),
        }));

    fs.writeFileSync(join(reportDir, TESTPALM_STATUS), JSON.stringify(statuses, null, 1));

    // patch packages newFailed

    const statusMap = new Map(statuses.map(x => [`marketmbi-${x.id}`, x]));
    const uidMap = new Map();
    const packages = JSON.parse(fs.readFileSync(join(reportDir, PACKAGES), 'utf8'));
    const suites = JSON.parse(fs.readFileSync(join(reportDir, SUITES), 'utf8'));
    const behaviors = JSON.parse(fs.readFileSync(join(reportDir, BEHAVIORS), 'utf8'));
    let newFailed = 0;

    function walk(node) {
        const {children, name, status, uid} = node;

        if (status && !/^(passed|skipped)$/i.test(status)) {
            const tp = statusMap.get(name);

            if (tp && tp.status === 'PASSED') {
                uidMap.set(uid, tp);
                node.newFailed = true;
                ++newFailed;
            }
        } else if (children) {
            children.forEach(x => walk(x));
        }
    }

    function walkUid(node) {
        const {children, uid} = node;

        if (uidMap.get(uid)) {
            node.newFailed = true;
        } else if (children) {
            children.forEach(x => walkUid(x));
        }
    }

    walk(packages);
    walkUid(suites);
    walkUid(behaviors);

    console.warn(`New failed: ${newFailed}`);

    if (newFailed > 0) {
        fs.writeFileSync(join(reportDir, PACKAGES), JSON.stringify(packages, null, 1));
        fs.writeFileSync(join(reportDir, SUITES), JSON.stringify(suites, null, 1));
        fs.writeFileSync(join(reportDir, BEHAVIORS), JSON.stringify(behaviors, null, 1));
    }
}

main().catch(err => {
    console.error(err.message);
    process.exit(1);
});
