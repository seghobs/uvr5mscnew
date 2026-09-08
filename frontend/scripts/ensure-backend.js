const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.resolve(__dirname, '..', '..');
const apiScript = path.join(rootDir, 'api_modern.py');

// ANSI TrueColor & High-Contrast Cyberpunk Palette
const c = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  italic: '\x1b[3m',
  underline: '\x1b[4m',

  cyan: '\x1b[36m',
  brightCyan: '\x1b[96m',
  purple: '\x1b[35m',
  brightPurple: '\x1b[95m',
  gold: '\x1b[33m',
  brightYellow: '\x1b[93m',
  green: '\x1b[32m',
  brightGreen: '\x1b[92m',
  blue: '\x1b[34m',
  brightBlue: '\x1b[94m',
  rose: '\x1b[91m',
  gray: '\x1b[90m',
  white: '\x1b[97m',
};

function printBanner() {
  console.clear();
  console.log(`
${c.brightPurple} ╔══════════════════════════════════════════════════════════════════════════════╗
 ║                                                                              ║
 ║   ${c.brightCyan}██╗   ██╗██╗   ██╗██████╗ ███████╗    ███╗   ██╗███████╗██╗  ██╗████████╗${c.brightPurple}  ║
 ║   ${c.brightCyan}██║   ██║██║   ██║██╔══██╗██╔════╝    ████╗  ██║██╔════╝╚██╗██╔╝╚══██╔══╝${c.brightPurple}  ║
 ║   ${c.brightCyan}██║   ██║██║   ██║██████╔╝███████╗    ██╔██╗ ██║█████╗   ╚███╔╝    ██║   ${c.brightPurple}  ║
 ║   ${c.brightCyan}██║   ██║╚██╗ ██╔╝██╔══██╗╚════██║    ██║╚██╗██║██╔══╝   ██╔██╗    ██║   ${c.brightPurple}  ║
 ║   ${c.brightCyan}╚██████╔╝ ╚████╔╝ ██║  ██║███████║    ██║ ╚████║███████╗██╔╝ ██╗   ██║   ${c.brightPurple}  ║
 ║    ${c.brightCyan}╚═════╝   ╚═══╝  ╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝   ╚═╝   ${c.brightPurple}  ║
 ║                                                                              ║
 ║      ${c.gold}⚡ ULTRA VOCAL REMOVER 5 ${c.gray}•${c.brightYellow} NEXT.JS STUDIO PRO EDITION (v1.8.4) ${c.gold}⚡${c.brightPurple}        ║
 ║      ${c.white}✨ ${c.dim}BS-Roformer 1297 • MDX23C HQ • VR-Arch • Demucs • Whisper AI Studio${c.reset}${c.brightPurple}    ║
 ╚══════════════════════════════════════════════════════════════════════════════╝${c.reset}
`);
}

function printServices(pythonPath) {
  const pyDisplay = pythonPath.length > 38 ? '...' + pythonPath.slice(-35) : pythonPath;
  console.log(`${c.brightCyan} ┌── 🎛️  SİSTEM VE SERVİS MATRİSİ ──────────────────────────────────────────────┐
 │                                                                              │
 │  ${c.brightGreen}●${c.white} BACKEND    ${c.gray}➜${c.brightCyan}  http://127.0.0.1:8000     ${c.dim}[ FastAPI • Python ASGI • ${pyDisplay} ]${c.brightCyan}
 │  ${c.brightPurple}●${c.white} FRONTEND   ${c.gray}➜${c.brightPurple}  http://localhost:3000     ${c.dim}[ Next.js 16 • React 19 • Turbopack Core ]${c.brightCyan}
 │  ${c.gold}●${c.white} AI ENGINE  ${c.gray}➜${c.gold}  PyTorch 2.x • CUDA / DirectML • ONNX Runtime Engine${c.brightCyan}     │
 │  ${c.rose}●${c.white} SUITE      ${c.gray}➜${c.white}  1080p Karaoke Video • De-Reverb • De-Bleed • Pitch/Tempo${c.brightCyan}      │
 │  ${c.brightBlue}●${c.white} TARAYICI   ${c.gray}➜${c.brightGreen}  Google Chrome (Otomatik Başlatıcı Devrede)${c.brightCyan}                    │
 │                                                                              │
 └──────────────────────────────────────────────────────────────────────────────┘${c.reset}

${c.gray} ┌── 💡 HIZLI KISAYOLLAR & İPUÇLARI ────────────────────────────────────────────┐
 │  ${c.white}[Ctrl + C]${c.gray} Sunucuyu Durdur   ${c.white}•${c.gray}   ${c.white}[F5 / Ctrl + R]${c.gray} Sayfayı Yenile                │
 │  ${c.brightYellow}✨ Tavsiye:${c.gray} %100 Temiz Vokal için ${c.brightCyan}BS-Roformer-Viperx-1297${c.gray} Modelini Kullanın! │
 └──────────────────────────────────────────────────────────────────────────────┘${c.reset}
`);
}

// Find python executable (prefer pythonw.exe on Windows for 100% silent windowless execution)
function getPythonExe() {
  const candidates = [
    path.join(rootDir, 'env', 'pythonw.exe'),
    path.join(rootDir, 'env', 'Scripts', 'pythonw.exe'),
    path.join(rootDir, 'env', 'python.exe'),
    path.join(rootDir, 'env', 'Scripts', 'python.exe'),
    path.join(rootDir, '..', 'env', 'pythonw.exe'),
    path.join(rootDir, '..', 'env', 'python.exe'),
    'pythonw',
    'python',
    'python3',
  ];

  for (const candidate of candidates) {
    if (path.isAbsolute(candidate) && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return 'pythonw';
}

async function checkBackendHealth() {
  try {
    const res = await fetch('http://127.0.0.1:8000/models', { signal: AbortSignal.timeout(1500) });
    return res.ok;
  } catch {
    return false;
  }
}

function killPort8000IfStale() {
  try {
    if (process.platform === 'win32') {
      const output = execSync('netstat -ano | findstr :8000 | findstr LISTENING', { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] });
      const lines = output.trim().split('\n');
      for (const line of lines) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && !isNaN(Number(pid))) {
          console.log(`  ${c.gold}🧹 8000 portundaki eski işlem temizleniyor (PID: ${pid})...${c.reset}`);
          try {
            execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore' });
          } catch {}
        }
      }
    }
  } catch {}
}

function launchBackend(pythonExe) {
  killPort8000IfStale();

  if (process.platform === 'win32') {
    try {
      const psCmd = `Start-Process -FilePath "${pythonExe}" -ArgumentList "${apiScript}" -WorkingDirectory "${rootDir}" -WindowStyle Hidden`;
      execSync(`powershell -NoProfile -NonInteractive -Command "${psCmd}"`, {
        stdio: 'ignore',
        windowsHide: true,
      });
      return;
    } catch {}
  }

  const child = spawn(pythonExe, [apiScript], {
    cwd: rootDir,
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  });

  child.unref();
}

function spawnBrowserWatcher() {
  const browserScript = path.join(__dirname, 'open-browser.js');
  const watcher = spawn(process.execPath, [browserScript], {
    cwd: __dirname,
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  });
  watcher.unref();
}

async function main() {
  const pythonExe = getPythonExe();
  printBanner();
  printServices(pythonExe);

  const isAlreadyRunning = await checkBackendHealth();
  if (isAlreadyRunning) {
    console.log(`  ${c.brightGreen}✔ [FASTAPI]${c.white} Backend servisi 100% aktif ve yanıt veriyor! ${c.dim}(Port :8000)${c.reset}`);
    spawnBrowserWatcher();
    console.log(`  ${c.brightCyan}🚀 [NEXT.JS]${c.white} Studio UI derleniyor, Chrome otomatik başlatılacak...\n${c.reset}`);
    return;
  }

  launchBackend(pythonExe);

  const spinners = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
  let spinIdx = 0;
  const maxAttempts = 40; // 20 seconds max

  for (let i = 0; i < maxAttempts; i++) {
    const sym = spinners[spinIdx % spinners.length];
    spinIdx++;
    const progressBlocks = '■'.repeat(Math.min(20, Math.floor((i / 15) * 20))).padEnd(20, '─');
    process.stdout.write(`\r  ${c.brightYellow}${sym}${c.gold} [FASTAPI] AI Modelleri & PyTorch Yükleniyor [${c.brightCyan}${progressBlocks}${c.gold}] (${(i * 0.5).toFixed(1)}s)${c.reset}   `);
    
    await new Promise((r) => setTimeout(r, 500));
    const ready = await checkBackendHealth();
    if (ready) {
      process.stdout.write(`\r  ${c.brightGreen}✔ [FASTAPI]${c.white} Backend & AI Çekirdeği 100% Hazır! [${c.brightGreen}${'■'.repeat(20)}${c.white}] ${c.dim}(Port :8000)${c.reset}      \n`);
      spawnBrowserWatcher();
      console.log(`  ${c.brightCyan}🚀 [NEXT.JS]${c.white} Studio UI derleniyor, Chrome otomatik başlatılacak...\n${c.reset}`);
      return;
    }
  }

  spawnBrowserWatcher();
  console.log(`\n  ${c.gold}⚠️ [UYARI] Backend başlangıcı gecikti, Next.js başlatılıyor...${c.reset}\n`);
}

main().catch((err) => {
  console.error('[Hata] Backend kontrolü başarısız:', err);
});
