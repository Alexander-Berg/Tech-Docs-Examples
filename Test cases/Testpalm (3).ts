import Client, {TestCaseStatus, TestCase as TestCaseFull} from '@yandex-int/testpalm-api'

interface TestpalmConstructorParams {
  token: string
  project: string
  browsers: string[]
}

interface TestSkip {
  skipReason: string
  browsers: string[]
}

type TestCase = Pick<TestCaseFull, 'id' | 'status' | 'name' | 'properties'>

export class Testpalm {
  private _skipsMap = new Map<string, TestSkip>()
  private _client: Client
  private _browsers: string[]
  private _project: string

  constructor({token, project, browsers}: TestpalmConstructorParams) {
    this._project = project
    this._browsers = browsers
    this._client = new Client(token)
  }

  private _getTestKey(test: TestCase): string {
    return `[${this._project}-${test.id}] ${test.name}`
  }

  private _getTestCaseUrl(testId: number) {
    return `https://testpalm.yandex-team.ru/testcase/${this._project}-${testId}`
  }

  async fetchSkips(): Promise<void> {
    const testCases = await this._client.getTestCases(this._project, {
      include: ['id', 'status', 'name', 'properties'],
      expression: JSON.stringify({key: 'isAutotest', type: 'EQ', value: true})
    })

    testCases.forEach((testCase) => {
      if (testCase.status === TestCaseStatus.NEEDSREPAIR) {
        this._skipsMap.set(this._getTestKey(testCase), {
          skipReason: `Skipped with testpalm. ${TestCaseStatus.NEEDSREPAIR}. ${this._getTestCaseUrl(testCase.id)}`,
          browsers: this._browsers
        })

        return
      }

      const skip = testCase.properties.find((property) => property.key === 'skip')
      if (!skip) {
        return
      }

      const skippedBrowsers = skip.value.split(',')
      if (skippedBrowsers.length) {
        this._skipsMap.set(this._getTestKey(testCase), {
          skipReason: `Skipped with testpalm. ${this._getTestCaseUrl(testCase.id)}`,
          browsers: skippedBrowsers
        })
      }
    })
  }

  /**
   * @returns Skip reason or false
   */
  isSkipped(testTitle: string, browserId: string): false | string {
    const testSkip = this._skipsMap.get(testTitle)
    if (!testSkip || !testSkip.browsers.includes(browserId)) {
      return false
    }

    return testSkip.skipReason
  }
}
