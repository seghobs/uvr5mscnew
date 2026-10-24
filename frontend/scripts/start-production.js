// Keep the production server and its output in the invoking terminal.
const { spawn, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const root = path.resolve(__dirname, '../..');
const python = path.join(root, 'env', process.platform === 'win32' ? 'python.exe' : 'bin/python');

function run(command, args, cwd = root) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', windowsHide: false });
  if (result.error) throw result.error;
  return result.status;
}

function main() {
  const existing = run(python, [path.join(root, 'service_control.py'), 'frontend-check']);
  if (existing !== 0 && existing !== 10) return existing || 1;
  if (existing !== 10) {
    const build = run(python, [path.join(root, 'studio_build.py'), 'ensure']);
    if (build !== 0) return build || 1;
  }
  const watch = run(python, [path.join(root, 'studio_build.py'), 'watch']);
  if (watch !== 0) return watch || 1;
  const backend = run(process.execPath, [path.join(__dirname, 'ensure-backend.js'), '--no-browser', '--quiet']);
  if (backend !== 0) return backend || 1;
  if (existing === 10) {
    run(python, [path.join(root, 'service_control.py'), 'frontend-focus']);
    const browser = spawn(process.execPath, [path.join(__dirname, 'open-browser.js')], { stdio: 'ignore', windowsHide: false });
    browser.unref();
    return 0;
  }
  const manifest = JSON.parse(fs.readFileSync(path.join(root, '.runtime/frontend-build.json'), 'utf8'));
  const server = spawn(process.execPath, [require.resolve('next/dist/bin/next'), 'start', '-p', '3000'], { cwd: path.join(root, 'frontend'), stdio: 'inherit', env: {...process.env, UVR_NEXT_DIST: manifest.dist} });
  server.once('error', error => { console.error(error.message); process.exitCode = 1; });
  server.once('exit', code => { process.exitCode = code === null ? 1 : code; });
  // The watcher opens the browser only after production responds successfully.
  const browser = spawn(process.execPath, [path.join(__dirname, 'open-browser.js')], { stdio: 'ignore', windowsHide: false });
  browser.unref();
}

try { const code = main(); if (code !== undefined) process.exitCode = code; }
catch (error) { console.error(error.message); process.exitCode = 1; }
