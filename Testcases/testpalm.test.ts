/* eslint-disable quote-props */
import 'mocha';
import _ from 'lodash';
import { expect } from 'chai';
import type { Test } from '../../../../src';
import {
    OperationType,
    TestpalmRenameQueueItem,
    Update,
} from '../../../../src/plugins/tide-renamer/types';
import {
    applyChanges,
    makeUpdateQueue,
} from '../../../../src/plugins/tide-renamer/renamer/testpalm';

describe('tide-renamer / renamer / testpalm', () => {
    describe('makeUpdateQueue', () => {
        const test = {
            type: 'integration',
            files: {
                testpalm: {
                    data: {
                        feature: 'Саджест',
                        experiment: 'Счетчики',
                        specs: {
                            Safeclick: {
                                'Проверка safeclick счетчика': ['item-1', 'item-2'],
                                'Проверка корректности sc': ['item-a-1'],
                            },
                            // prettier-ignore
                            'Основные': {
                                beforeEach: [],
                                'Тип взаимодействия': ['item-c-4'],
                                'Способ отправки': ['item-d-8', 'item-d-9', 'item-d-10'],
                                'Проверка вычисляемых полей': ['item-e-8', 'item-e-9'],
                            },
                        },
                    },
                },
            },
        };
        const data = test.files.testpalm.data;
        const constants = {
            TYPES: {
                INTEGRATION: 'integration',
            },
            hermione: {
                TITLE_KEYS: ['feature', 'type', 'experiment'],
            },
            testpalm: {
                SPECS_TYPE_KEYS: {
                    integration: 'specs',
                },
            },
        };

        let expectedQueue: Array<TestpalmRenameQueueItem> = _.sortBy(
            [
                {
                    object: data,
                    path: ['experiment'],
                    value: 'E-3',
                    priority: 999,
                    type: OperationType.RENAME_VALUE,
                },
                {
                    object: data,
                    path: ['feature'],
                    value: 'F-1',
                    priority: 999,
                    type: OperationType.RENAME_VALUE,
                },
                {
                    object: data,
                    path: ['specs', 'Основные', 'Тип взаимодействия'],
                    value: 'Type-5',
                    priority: 0,
                    type: OperationType.RENAME_KEY,
                },
            ],
            ['priority', 'value'],
        );
        // В тесте исключаем priority из сравнения, нам важно не конкретное значение, а порядок в очереди в целом
        expectedQueue = expectedQueue.map(
            (item) => _.pickBy(item, (value, key) => key !== 'priority') as TestpalmRenameQueueItem,
        );

        it('should return correct queue when the updates array contains objects', () => {
            const updates: Array<Update> = [
                {
                    from: { feature: 'Саджест', experiment: 'Счетчики' },
                    to: { feature: 'F-1', experiment: 'E-3' },
                },
                { from: 'Основные', to: 'Основные' },
                { from: 'Тип взаимодействия', to: 'Type-5' },
            ];

            let actualQueue = makeUpdateQueue(updates, test as unknown as Test, constants);
            actualQueue = _.sortBy(actualQueue, ['priority', 'value']);
            actualQueue = actualQueue.map(
                (item) =>
                    _.pickBy(item, (value, key) => key !== 'priority') as TestpalmRenameQueueItem,
            );

            expect(actualQueue.sort()).deep.equal(expectedQueue.sort());
        });

        it('should return correct queue when the updates array contains strings only', () => {
            const updates: Array<Update> = [
                { from: 'Саджест / Счетчики', to: 'F-1 / E-3' },
                { from: 'Основные', to: 'Основные' },
                { from: 'Тип взаимодействия', to: 'Type-5' },
            ];

            let actualQueue = makeUpdateQueue(updates, test as unknown as Test, constants);
            actualQueue = _.sortBy(actualQueue, ['priority', 'value']);
            actualQueue = actualQueue.map(
                (item) =>
                    _.pickBy(item, (value, key) => key !== 'priority') as TestpalmRenameQueueItem,
            );

            expect(actualQueue.sort()).deep.equal(expectedQueue.sort());
        });
    });

    describe('applyChanges', () => {
        it('should apply changes from the queue and preserve order of keys', () => {
            const test = {
                type: 'integration',
                files: {
                    testpalm: {
                        data: {
                            feature: 'Саджест',
                            experiment: 'Счетчики',
                            specs: {
                                Safeclick: {
                                    'Проверка safeclick счетчика': ['item-1', 'item-2'],
                                    'Проверка корректности sc': ['item-a-1'],
                                },
                                // prettier-ignore
                                'Основные': {
                                    beforeEach: [],
                                    'Тип взаимодействия': ['item-c-4'],
                                    'Способ отправки': ['item-d-8', 'item-d-9', 'item-d-10'],
                                    'Проверка вычисляемых полей': ['item-e-8', 'item-e-9'],
                                },
                            },
                        },
                    },
                },
            };
            const data = test.files.testpalm.data;
            const renameQueue: Array<TestpalmRenameQueueItem> = [
                {
                    object: data,
                    path: ['experiment'],
                    value: 'E-3',
                    priority: 999,
                    type: OperationType.RENAME_VALUE,
                },
                {
                    object: data,
                    path: ['feature'],
                    value: 'F-1',
                    priority: 999,
                    type: OperationType.RENAME_VALUE,
                },
                {
                    object: data,
                    path: ['specs', 'Основные', 'Тип взаимодействия'],
                    value: 'Type-5',
                    priority: 0,
                    type: OperationType.RENAME_KEY,
                },
            ];

            const changedTest = {
                type: 'integration',
                files: {
                    testpalm: {
                        data: {
                            feature: 'F-1',
                            experiment: 'E-3',
                            specs: {
                                Safeclick: {
                                    'Проверка safeclick счетчика': ['item-1', 'item-2'],
                                    'Проверка корректности sc': ['item-a-1'],
                                },
                                // prettier-ignore
                                'Основные': {
                                    beforeEach: [],
                                    'Type-5': ['item-c-4'],
                                    'Способ отправки': ['item-d-8', 'item-d-9', 'item-d-10'],
                                    'Проверка вычисляемых полей': ['item-e-8', 'item-e-9'],
                                },
                            },
                        },
                    },
                },
            };

            applyChanges(renameQueue);

            // переводим в json, чтобы убедиться, что порядок ключей не изменился
            expect(JSON.stringify(test)).equal(JSON.stringify(changedTest));
        });
    });
});
