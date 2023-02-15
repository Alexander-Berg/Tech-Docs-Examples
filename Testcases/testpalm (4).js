'use strict';

const path = require('path');
const _ = require('lodash');
const Client = require('@yandex-int/testpalm-api').default;
const JsonStreamStringify = require('json-stream-stringify');

/**
 *  TestPalm error "Payload document size is larger than maximum of 16777216."
 *
 *  Размер документа считается после слияния с телами тест-кейсов неизвестного размера,
 *  поэтому размер кусочка выбирается наугад с большим запасом.
 */
const TESTPALM_CHUNK_SIZE = 500000;

/**
 * @param value any object
 * @returns {Promise<int>}
 */
function bigByteSize(value) {
    return new Promise((resolve => {
        let streamSize = 0;
        new JsonStreamStringify(value)
            .on('data', chunk => {
                streamSize += chunk.length;
            })
            .on('end', () => resolve(streamSize));
    }));
}

function byteSize(value) {
    return Buffer.byteLength(JSON.stringify(value));
}

module.exports = (action, command) => {
    if (!command.project) {
        throw new Error('Ginny: CLI option "project" must be defined');
    }

    if (!command.token) {
        throw new Error('Ginny: CLI option "token" must be defined');
    }

    switch (action) {
        case 'import_run':
            if (!command.run) {
                throw new Error('Ginny: CLI option "run" must be defined');
            }

            const run = require(path.resolve('.', command.run));
            const patch = global.process.env.GINNY_TESTPALM_RUN_PATCH;

            if (patch) {
                console.log(`Ginny: Applying path for test run: ${patch}`);

                _.merge(run, JSON.parse(patch));
            } else {
                console.log(`Ginny: No path for applying to test run`);
            }

            const runSizePromise = bigByteSize(run);

            console.log(`Ginny: Import TestPalm run`);

            const client = new Client(command.token, {
                retries: 0
            });

            return runSizePromise.then(runSize => {
                if (runSize > TESTPALM_CHUNK_SIZE) {
                    return exportRunInBatches({client, command});
                }
                else {
                    return exportRunInOneBatch({client, command});
                }
            });
    }

    throw new Error(`Ginny: Invalid argument ${command}`);
};

/**
 * @returns {Promise<undefined>}
 */
function exportRunInBatches({client, command}) {
    console.log(`Ginny: TestPalm run is above maximum size, exploding`);

    const baseDoc = _.omit(run, 'testGroups');
    const baseSizePromise = bigByteSize(baseDoc).then(size => size + 100);

    const groupBatchesPromise = baseSizePromise.then(baseSize => {
        const testGroups = run.testGroups;
        const groupBatches = [];
        let tail = 0;

        for (let i = 0, size = baseSize; i < testGroups.length; ++i) {
            size += byteSize(testGroups[i]) + 1;

            if (size > TESTPALM_CHUNK_SIZE && i > 0) {
                groupBatches.push(testGroups.slice(tail, i));

                size = baseSize;
                tail = i;
            }
        }

        if (tail < testGroups.length) {
            groupBatches.push(testGroups.slice(tail));
        }

        return groupBatches;
    });

                    const nextStep = (step) => {
                        let totalSteps;

                        const runPartPromise = groupBatchesPromise
                            .then(groupBatches => {
                                totalSteps = groupBatches.length;
                                const runPart = Object.assign({}, baseDoc, {
                                    title: `${baseDoc.title} (${step}/${totalSteps})`,
                                    testGroups: groupBatches[step - 1]
                                });

                console.log('Ginny: TestPalm addTestRun %d of %d', step, totalSteps);
                return runPart;
            });

        return runPartPromise
            .then(runPart => client.addTestRun(command.project, runPart))
            .then((body) => {
                console.log(`Ginny: Export ${step} result:\n`, body.id);

                if (step < totalSteps) {
                    return nextStep(step + 1);
                }

                global.process.exit(0);
            })
            .catch((error) => {
                console.error(error);

                if (error && error.response) {
                    console.error('Ginny: TestPalm error:\n', error.response.body);
                }

                global.process.exit(1);
            });
    };

    return nextStep(1);
}


/**
 * @returns {Promise<undefined>}
 */
function exportRunInOneBatch({client, command}) {
    return client
        .addTestRun(command.project, run)
        .then((body) => {
            console.log('Ginny: Export result:\n', body ? body.map((el) => el.id).join('\n') : []);

            global.process.exit(0);
        })
        .catch((error) => {
            console.error(error);

            if (error && error.response) {
                console.error('Ginny: TestPalm error:\n', error.response.body);
            }

            global.process.exit(1);
        });
}
