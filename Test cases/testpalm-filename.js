/**
 * Линтер на правильные имена *.testpalm.yml файлов
 */
const files = process.argv.slice(2);
const badFiles = [];

files.forEach((filename) => {
    if (!/\.(common|desktop|deskpad|touch|touch-phone|touch-pad)\.testpalm\.yml|\.testpalm\.steps\.yml/.test(filename)) {
        badFiles.push(filename);
    }
});

if (badFiles.length) {
    console.error('Невалидное имя тестового сценария(шагов). Имя должно оканчиваться на *.{common,desktop,deskpad,touch,touch-phone,touch-pad}.testpalm.yml или *.testpalm.steps.yml:');
    badFiles.forEach((badFilename) => console.error(` * ${badFilename}`));
    console.error();

    process.exitCode = 1;
}
