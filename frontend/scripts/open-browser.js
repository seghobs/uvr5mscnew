const { spawn, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const root = path.resolve(__dirname, '../..');

function claimBrowserOpen(token, directory = path.join(root, '.runtime', 'browser-open')) {
  fs.mkdirSync(directory, { recursive: true });
  const marker = path.join(directory, crypto.createHash('sha256').update(token).digest('hex') + '.lock');
  try { const handle = fs.openSync(marker, 'wx'); fs.closeSync(handle); return true; }
  catch (error) { if (error.code === 'EEXIST') return false; throw error; }
}

function frontendToken() {
  const python = path.join(root, 'env', process.platform === 'win32' ? 'python.exe' : 'bin/python');
  const result = spawnSync(python, [path.join(root, 'service_control.py'), 'frontend-token'],
    { cwd: root, encoding: 'utf8', windowsHide: false });
  return result.status === 0 ? result.stdout.trim() : null;
}

const CHROME_PATHS = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  process.env.LOCALAPPDATA ? `${process.env.LOCALAPPDATA}\\Google\\Chrome\\Application\\chrome.exe` : null,
  process.env.PROGRAMFILES ? `${process.env.PROGRAMFILES}\\Google\\Chrome\\Application\\chrome.exe` : null,
].filter(Boolean);

function findChromeExe() {
  for (const p of CHROME_PATHS) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

async function checkFrontend() {
  for (const url of ['http://127.0.0.1:3000', 'http://localhost:3000']) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(1000) });
      if (res.status === 200 || res.status === 304 || res.status === 307) {
        return true;
      }
    } catch {}
  }
  return false;
}

async function openBrowser() {
  const maxAttempts = 120; // 60 seconds max
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 500));
    const isReady = await checkFrontend();
    if (isReady) {
      const token = frontendToken();
      if (!token) continue;
      if (!claimBrowserOpen(token)) return;
      if (process.platform === 'win32') {
        const chromeExe = findChromeExe();
        if (chromeExe) {
          const child = spawn(chromeExe, ['http://localhost:3000'], {
            detached: true,
            stdio: 'ignore',
            windowsHide: true,
          });
          child.unref();
        } else {
          const psCmd = `Start-Process 'http://localhost:3000'`;
          const child = spawn('powershell.exe', ['-NoProfile', '-WindowStyle', 'Hidden', '-Command', psCmd], {
            detached: true,
            stdio: 'ignore',
            windowsHide: true,
          });
          child.unref();
        }
      } else if (process.platform === 'darwin') {
        const opener = spawn('open', ['-a', 'Google Chrome', 'http://localhost:3000'], { detached: true, stdio: 'ignore' });
        opener.unref();
      } else {
        const opener = spawn('xdg-open', ['http://localhost:3000'], { detached: true, stdio: 'ignore' });
        opener.unref();
      }
      return;
    }
  }
}

module.exports = { claimBrowserOpen };
if (require.main === module) openBrowser().catch(() => {});
