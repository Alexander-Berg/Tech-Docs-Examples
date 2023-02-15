import {
    ITestDefinition,
    ITestPalmExpression,
    TTestPalmFilterExpression,
} from './types';

export class TestPalmFilterParser {
    private definitions: ITestDefinition[];

    constructor(definitions: ITestDefinition[]) {
        this.definitions = definitions;
    }

    parse(filterString: string): TTestPalmFilterExpression | undefined {
        if (!filterString) {
            return undefined;
        }

        const parts = filterString.split('&');

        return this.parseFilterParts(parts);
    }

    private parseFilterParts(parts: string[]): TTestPalmFilterExpression {
        if (parts.length === 1) {
            return this.parseExpression(parts[0]);
        } else if (parts.length === 2) {
            return {
                type: 'AND',
                left: this.parseExpression(parts[0]),
                right: this.parseExpression(parts[1]),
            };
        }

        const center = Math.ceil(parts.length / 2);

        return {
            type: 'AND',
            left: this.parseFilterParts(parts.slice(0, center)),
            right: this.parseFilterParts(parts.slice(center, parts.length)),
        };
    }

    private parseExpression(expression: string): ITestPalmExpression {
        const parts = expression.split('=');
        const valueParts = parts[1].split(',');

        const definition = this.definitions.find(d => d.title === parts[0]);
        const key = definition ? `attributes.${definition.id}` : parts[0];

        if (valueParts.length > 1) {
            return {
                type: 'IN',
                key,
                value: valueParts,
            };
        }

        return {
            type: 'EQ',
            key,
            value: valueParts[0],
        };
    }
}
