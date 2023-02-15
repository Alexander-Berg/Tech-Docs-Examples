import { Request, Response, NextFunction } from 'express';

import CreateLaunchController, { Dependencies as CreateLaunchDependencies } from './create-launch';
import { Launch } from '../../../models';

import * as errors from '../../errors';

export type Dependencies = CreateLaunchDependencies & {
    redirectUrlTemplate: string;
};

const REDIRECT_HTTP_STATUS_CODE = 303;

export default class CreateLaunchFromTestpalmController extends CreateLaunchController<Dependencies> {
    static path = '/api/v1/launch/create-from-testpalm';

    getParseBodyMiddleware() {
        return this._parseBodyMiddleware.bind(this);
    }

    protected _parseBodyMiddleware(req: Request, _res: Response, next: NextFunction) {
        const debug = this._getDebugWithTrace(req);
        /**
         * Запрос приходит с типом application/x-www-form-urlencoded,
         * при этом content представляет собой строку с json.
         * Поля на верхнем уровне парсятся корректно, но в поле content
         * получается строка с json.
         * Проверяем руками, что поле content непустое, а затем пытаемся
         * его распарсить самостоятельно, чтобы затем передать в валидатор.
         */
        if (req.body && req.body.content && typeof req.body.content === 'string') {
            try {
                req.body.content = JSON.parse(req.body.content);
            } catch (error) {
                const errorMessage = `failed to parse content: ${error}`;

                debug(errorMessage);

                return next(new errors.InvalidPayloadError(errorMessage));
            }
        }

        next();
    }

    protected _sendResponse(launch: Launch, res: Response) {
        const redirectUrl = this._renderRedirectUrl(launch);

        return res.redirect(REDIRECT_HTTP_STATUS_CODE, redirectUrl);
    }

    private _renderRedirectUrl(launch: Launch) {
        return this._deps.redirectUrlTemplate.replace(':id', launch._id.toHexString());
    }
}
