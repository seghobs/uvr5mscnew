const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {claimBrowserOpen}=require('../frontend/scripts/open-browser.js');
test('overlapping launchers may open only once for the same running frontend',()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'uvr-browser-test-'));
  try {
    assert.equal(claimBrowserOpen('100:123.456',folder),true);
    assert.equal(claimBrowserOpen('100:123.456',folder),false);
    assert.equal(claimBrowserOpen('100:123.456',folder),false);
    assert.equal(claimBrowserOpen('200:125.456',folder),true);
    assert.equal(claimBrowserOpen('100:200.456',folder),true,'reused PID with new start time is a new server');
  } finally {
    const relative=path.relative(fs.realpathSync(os.tmpdir()),fs.realpathSync(folder));
    assert(relative.startsWith('uvr-browser-test-')&&!relative.includes(path.sep));
    fs.rmSync(folder,{recursive:true,force:true});
  }
});
