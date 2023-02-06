/* eslint-disable no-console */

const {isEmpty, flatten} = require('ramda');
const {getPageId, getHtmlPageId, groupPages} = require('./utils');

const buildTestPalmQuery = pages => {
    const pagesQuery = pages
        .filter(Boolean)
        .map(page => `"PageId" = "${page}"`)
        .concat('"SOX" = "yes"')
        .join(' OR ');

    return `"Test-run type" = "Ручной регресс"
        AND isAutotest = false
        AND (status = "actual" OR status = "on review" OR status = "needs changes")
        AND (${pagesQuery})`;
};

const testpalmReporter = ({result}) => {
    const {client = [], html = []} = groupPages(Object.entries(result));
    const pageIds = flatten(
        client.map(([page]) => [...getPageId(page)]).concat(html.map(([page]) => [...getHtmlPageId(page)])),
    );

    if (!isEmpty(pageIds)) {
        console.log(/* \n */);
        console.log('Query:');
        console.log(buildTestPalmQuery([...new Set(pageIds)]));
    }
};

module.exports = testpalmReporter;
