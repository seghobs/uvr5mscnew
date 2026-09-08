const { spawn } = require('child_process');
const fs = require('fs');

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

openBrowser().catch(() => {});
