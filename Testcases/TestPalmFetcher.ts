import https from 'https';
import axios, {AxiosInstance} from 'axios';
import {stringify} from 'query-string';

import {TESTPALM_API_URL} from './constants';

import {IUrlQuery} from 'utilities/url/types';

export class TestPalmFetcher {
    private oAuthToken: string;

    private axiosInstance: AxiosInstance;

    constructor(oAuthToken: string) {
        this.oAuthToken = oAuthToken;
        this.axiosInstance = axios.create({
            httpsAgent: new https.Agent({
                rejectUnauthorized: false,
            }),
            headers: {
                Authorization: `OAuth ${this.oAuthToken}`,
            },
        });
    }

    async fetch<TResponse>(url: string, query?: IUrlQuery): Promise<TResponse> {
        const queryPart = query ? `?${stringify(query)}` : '';

        const response = await this.axiosInstance.get<TResponse>(
            `${TESTPALM_API_URL}${url}${queryPart}`,
        );

        return response.data;
    }
}
