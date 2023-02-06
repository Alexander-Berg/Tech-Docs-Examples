package ru.yandex.market.tsum.pipelines.apps.jobs.coverage;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import ru.yandex.startrek.client.Links;

class TestpalmHelper {

    private static final Logger log = LogManager.getLogger(CheckTestCoverageForFeatureJob.class);
    private static final String TESTPALM_ST_APP_NAME = "TestPalm";

    private final Links links;

    TestpalmHelper(Links links) {
        this.links = links;
    }

    int getLinkedTestCasesCount(String ticketKey) {
        return (int) links
            .getRemote(ticketKey)
            .filter(remoteLink -> TESTPALM_ST_APP_NAME.equals(remoteLink.getObject().getApplication().getName()))
            .stream()
            .peek(remoteLink -> log.info("Found test case {}", remoteLink.getObject().getSelf()))
            .count();
    }
}
