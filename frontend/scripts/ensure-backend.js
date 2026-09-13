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
  printBanner();
  const pythonExe = getPythonExe().replace(/pythonw(?=\.exe$)/i, 'python');
  console.log('Yerel servis ve sürüm kontrol ediliyor…');
  const { spawnSync } = require('child_process');
  const result = spawnSync(pythonExe, [path.join(rootDir,'service_control.py'),'launch'], {cwd:rootDir,stdio:'inherit',windowsHide:true});
  if(result.error)throw result.error;
  if(result.status!==0)throw new Error('Sunucu hazırlanamadı; yukarıdaki açıklamayı kontrol edin.');
  spawnBrowserWatcher();
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
