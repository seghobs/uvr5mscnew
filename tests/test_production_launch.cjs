const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../frontend/scripts/start-production.js'), 'utf8');
function simulate(statuses) {
  const calls = [], process = { platform: 'win32', execPath: 'node.exe' };
  const req = name => name === 'child_process' ? {
    spawnSync(command, args, options) { calls.push(['sync', command, args, options]); return { status: statuses.shift() }; },
    spawn(command, args) { calls.push(['spawn', command, args]); return { once() {}, unref() {} }; },
  } : require(name);
  req.resolve = () => 'next/dist/bin/next';
  vm.runInNewContext(source, { require: req, __dirname: path.join(__dirname, '../frontend/scripts'), process, console });
  return { calls, process };
}
test('backend failure prevents production and browser startup', () => {
  const result = simulate([0, 1]);
  assert.equal(result.process.exitCode, 1);
  assert.equal(result.calls.filter(c => c[0] === 'spawn').length, 0);
});
test('occupied unrelated port prevents backend and frontend changes', () => {
  const result = simulate([1]);
  assert.equal(result.calls.length, 1);
});
test('owned server reused without another Next process', () => {
  const result = simulate([10, 0, 0]);
  assert.equal(result.process.exitCode, 0);
  assert.equal(result.calls.filter(c => c[0] === 'spawn').length, 1);
  assert.match(result.calls.at(-1)[2][0], /open-browser/);
});
test('backend ready before production and browser starts', () => {
  const result = simulate([0, 0]);
  assert.equal(result.calls[0][3].windowsHide, false);
  assert.equal(result.calls[1][3].windowsHide, false);
  assert.ok(result.calls[1][2].includes('--no-browser'));
  assert.equal(result.calls[2][2][1], 'start');
  assert.match(result.calls[3][2][0], /open-browser/);
});

test('launcher keeps the outer console open after shutdown or reuse',()=>{
  const batch=fs.readFileSync(path.join(__dirname,'../start.bat'),'utf8');
  const shutdown=batch.slice(batch.indexOf('call npm run start'),batch.indexOf(':already_running'));
  assert(!shutdown.includes('pause'));
  assert.match(shutdown,/exit \/b %uvr_exit_code%/);
  assert.match(batch,/cmd \/d \/k/);
  const reuse=batch.slice(batch.indexOf(':already_running'),batch.indexOf(':launch_failed'));
  assert.match(reuse,/call node scripts\\open-browser\.js/);
  assert.match(reuse,/exit \/b 0/);
  assert(!reuse.includes('pause'));
});
