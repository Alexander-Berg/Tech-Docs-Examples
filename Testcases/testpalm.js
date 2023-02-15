const { execSync } = require('child_process');
const { branch } = require('./vcs');

const VERSION_REGEXP = /(v(\d+\.)?(\d+\.)?(\d+))/;

// Эта функция позволяет получить название для проекта в testpalm формата turbo-v9_999_9
// Версию релиза мы достаем из навзвании ветки
function getProjectId() {
    const projectId = ['turbo'];
    const match = branch.match(VERSION_REGEXP) || [];
    const suffix = match[0];
    if (suffix) {
        projectId.push(suffix.split('.').join('_'));
    }
    return projectId.join('-');
}

function main() {
    const dest = getProjectId();

    if (dest !== 'turbo') {
        // Клонируем основной проект turbo в testpalm в проект с новым названием
        const cloneCMD = [
            'npx testpalm clone',
            'turbo',
            dest
        ];
        execSync(cloneCMD.join(' '));

        const buildCMD = 'npm run build:ci';
        execSync(buildCMD);

        const syncCMD = [
            'npx palmsync synchronize',
            '-p',
            dest
        ];
        execSync(syncCMD.join(' '));
    }

    const runSuiteCMD = [
        'npx testpalm-suite-runner',
        '.config/assessors/release.tsr.json',
        `--project-id=${dest}`,
    ];

    execSync(runSuiteCMD.join(' '));
}

main();
