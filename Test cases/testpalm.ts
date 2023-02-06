import _ from 'lodash';
import type { Test, TestFile } from '../../..';
import { parseTitlePart } from './utils';
import { OperationType, StringObject, TestpalmRenameQueueItem, Update } from '../types';

/* Ставит в очередь переименование значений fromObject => toObject */
function makeValueUpdateQueue(
    fromObject,
    toObject: StringObject,
    constants,
): Array<TestpalmRenameQueueItem> {
    const keys = constants.hermione.TITLE_KEYS;
    const renameQueue: Array<TestpalmRenameQueueItem> = [];
    // Проверяем, что все ключи в старом объекте есть, на что заменить
    for (const key of keys) {
        if (fromObject[key] && !toObject[key]) {
            renameQueue.push({
                object: fromObject,
                path: [key],
                value: null,
                priority: 1000,
                type: OperationType.DELETE_KEY,
            });
        } else if (toObject[key]) {
            renameQueue.push({
                object: fromObject,
                path: [key],
                value: toObject[key],
                priority: 1000,
                type: OperationType.RENAME_VALUE,
            });
        }
    }
    return renameQueue;
}

/* Рекурсивно выполняет постановку обновлений ключей объекта в очередь.
 * root - корень дерева.
 * path - текущий рассматриваемый путь в дереве.
 * Такая структура обусловлена необходимостью сохранять порядок ключей: для этого нужно знать 2 уровня предков ключа */
function makeKeyUpdateQueue(
    root,
    path: Array<string>,
    updates: Array<Update>,
): Array<TestpalmRenameQueueItem> {
    if (!updates.length) return [];
    const renameQueue: Array<TestpalmRenameQueueItem> = [];
    for (const key of _.keys(_.get(root, path))) {
        if (updates[0].from !== key) continue;
        if (updates[0].to !== key) {
            renameQueue.push({
                object: root,
                path: [...path, key],
                value: updates[0].to as string,
                priority: updates.length,
                type: OperationType.RENAME_KEY,
            });
        }
        renameQueue.push(...makeKeyUpdateQueue(root, [...path, key], updates.slice(1)));
    }
    return renameQueue;
}

/* Возвращает очередь с обновлениями объекта в соответствии с аргументом updates */
function makeUpdateQueue(
    updates: Array<Update>,
    test: Test,
    constants,
): Array<TestpalmRenameQueueItem> {
    const data = (test.files.testpalm as TestFile).data;

    // Обработка корневых полей названия теста (feature, type, ...)
    const oldObject = _.pickBy(data, (value, key) => constants.hermione.TITLE_KEYS.includes(key));
    const fromObject = parseTitlePart(updates[0].from, oldObject, constants);
    const toObject = parseTitlePart(updates[0].to, oldObject, constants);

    if (!_.isEqual(oldObject, fromObject)) {
        return [];
    }

    const renameQueue: Array<TestpalmRenameQueueItem> = [];

    renameQueue.push(...makeValueUpdateQueue(data, toObject, constants));

    let rootKeyName: string;
    if (test.type === constants.TYPES.E2E) {
        rootKeyName = constants.testpalm.SPECS_TYPE_KEYS.e2e;
    } else {
        rootKeyName = constants.testpalm.SPECS_TYPE_KEYS.integration;
    }

    renameQueue.push(...makeKeyUpdateQueue(data, [rootKeyName], updates.slice(1)));
    return renameQueue;
}

/* Применяет изменения, хранящиеся в очереди. */
function applyChanges(queue: Array<TestpalmRenameQueueItem>): void {
    // Сортировка по приоритетам и исключение повторов
    const sortedQueue = _.uniqWith(_.sortBy(queue, ['priority']), _.isEqual);
    for (const item of sortedQueue) {
        // Редактирование ключа с сохранением порядка
        if (item.type === OperationType.RENAME_KEY) {
            const newObject = {};
            // Получение ключей, находящихся на одном уровне с тем, который хотим переименовать
            const siblings = _.get(item.object, item.path.slice(0, -1));
            for (const [siblingKey, siblingValue] of _.entries(siblings)) {
                if (siblingKey === item.path[item.path.length - 1]) {
                    newObject[item.value as string] = siblingValue;
                } else {
                    newObject[siblingKey] = siblingValue;
                }
            }
            // Находим узел двумя уровнями выше, чем ключ, который переименовываем, и применяем изменения
            _.get(item.object, item.path.slice(0, -2), item.object)[
                item.path[item.path.length - 2]
            ] = newObject;
        }
        // Редактирование значения
        if (item.type === OperationType.RENAME_VALUE) {
            // Получение узла по пути в объекте и замена его значения
            _.get(item.object, item.path.slice(0, -1), item.object)[
                item.path[item.path.length - 1]
            ] = item.value;
        }
        // Удаление ключа
        if (item.type === OperationType.DELETE_KEY) {
            delete _.get(item.object, item.path.slice(0, -1), item.object)[
                _.last(item.path) as string
            ];
        }
    }
}

export { makeUpdateQueue, applyChanges };
