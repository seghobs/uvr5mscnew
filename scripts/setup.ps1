param([switch]$VerifyOnly, [switch]$SkipModels)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
$python = Join-Path $root 'env\python.exe'
$bootstrap = Join-Path $root 'tools\setup-runtime\miniforge'
$conda = Join-Path $bootstrap 'Scripts\conda.exe'
$installerUrl = 'https://github.com/conda-forge/miniforge/releases/download/26.7.2-0/Miniforge3-26.7.2-0-Windows-x86_64.exe'
$installerHash = '71cf9519087be74fa53021219ff292beb2fc05fa49e0bb6eb0e0b6b14fccbaab'
$env:PATH = "$root\tools\setup-runtime\ffmpeg\bin;$root\env;$root\env\Scripts;$root\env\Library\bin;$env:PATH"
$env:PYTHONUTF8 = '1'
$env:PYTHONNOUSERSITE = '1'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:CONDA_CHANNEL_PRIORITY = 'strict'
$env:CONDA_SUBDIR = 'win-64'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Invoke-Checked {
    param([string]$Exe, [string[]]$CommandArgs, [int]$Attempts = 1)
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        & $Exe @CommandArgs
        if ($LASTEXITCODE -eq 0) { return }
        if ($attempt -lt $Attempts) { Write-Host "Tekrar deneniyor ($attempt/$Attempts)..."; Start-Sleep -Seconds 3 }
    }
    throw "Komut basarisiz: $Exe (cikis kodu $LASTEXITCODE)."
}

function Test-Tool {
    param([string]$Name, [string[]]$CommandArgs)
    $tool = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $tool) { return $false }
    try { & $tool.Source @CommandArgs *> $null; return $LASTEXITCODE -eq 0 } catch { return $false }
}

function Install-Bootstrap {
    if (Test-Path -LiteralPath $conda) { return }
    $downloads = Join-Path $root 'tools\setup-runtime\downloads'
    New-Item -ItemType Directory -Path $downloads -Force | Out-Null
    $installer = Join-Path $downloads 'miniforge.exe'
    if (-not (Test-Path -LiteralPath $installer) -or (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $installerHash) {
        $downloaded = $false
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                Invoke-WebRequest -UseBasicParsing -Uri $installerUrl -OutFile "$installer.part" -TimeoutSec 600
                if ((Get-FileHash -LiteralPath "$installer.part" -Algorithm SHA256).Hash -ne $installerHash) { throw 'Indirilen dosyanin SHA256 dogrulamasi basarisiz.' }
                Move-Item -LiteralPath "$installer.part" -Destination $installer -Force
                $downloaded = $true; break
            } catch { if ($attempt -eq 3) { throw }; Start-Sleep -Seconds 3 }
        }
        if (-not $downloaded) { throw 'Kurulum araci indirilemedi.' }
    }
    # NSIS requires /D to be the final unquoted argument, including paths with spaces.
    $process = Start-Process -FilePath $installer -ArgumentList "/S /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /D=$bootstrap" -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $conda)) { throw 'Miniforge kurulumu tamamlanamadi. tools/setup-runtime konumunu ve gunlugu kontrol edin.' }
}

$transcript = $false
$lock = $null
try {
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { throw 'Bu kurulum Windows x64 icindir.' }
    if (-not (Test-Path -LiteralPath 'frontend\package-lock.json')) { throw 'Proje dosyalari eksik. GitHub ZIP dosyasini tamamen cikartin.' }
    New-Item -ItemType Directory -Path (Join-Path $root 'logs') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $root '.runtime') -Force | Out-Null
    $lock = [IO.File]::Open((Join-Path $root '.runtime\setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    Start-Transcript -Path (Join-Path $root 'logs\setup.log') -Append | Out-Null
    $transcript = $true
    Write-Host 'UVR5 Next Studio - Otomatik kurulum' -ForegroundColor Cyan
    if (-not $VerifyOnly) {
        $running = $null
        try { $running = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/service' -TimeoutSec 2 } catch {}
        if ($running -and $running.root -eq $root) { throw 'Uygulama acik. Once arayuzdeki Kapat dugmesiyle kapatin, sonra setup.bat dosyasini yeniden acin.' }
        $free = (Get-Item -LiteralPath $root).PSDrive.Free
        if ($free -and $free -lt 20GB) { throw 'Kurulum icin en az 20 GB bos alan ayirin. Model secimine gore daha fazlasi gerekebilir.' }
        Write-Host '[1/5] Python, Node.js ve FFmpeg kontrol ediliyor...'
        $hasPython = Test-Path -LiteralPath $python
        if ($hasPython) { Invoke-Checked $python @('-c', 'import sys; assert sys.version_info[:2] == (3,10)') }
        $nodeOK = Test-Tool 'node' @('scripts\check_frontend.cjs', '--node-only')
        $npmOK = Test-Tool 'npm.cmd' @('--version')
        $ffmpegOK = (Test-Tool 'ffmpeg' @('-version')) -and (Test-Tool 'ffprobe' @('-version'))
        if (-not $hasPython -or -not $nodeOK -or -not $npmOK) {
            Install-Bootstrap
            $verb = if ($hasPython) { 'install' } else { 'create' }
            Invoke-Checked $conda @($verb, '--yes', '--prefix', (Join-Path $root 'env'), '--override-channels', '-c', 'conda-forge', 'python=3.10', 'pip', 'nodejs=22', 'libsndfile') 3
        }
        if (-not $ffmpegOK) { Invoke-Checked $python @('scripts\setup_runtime.py', 'tools') 3 }
        Write-Host '[2/5] Ses ve yapay zeka paketleri kuruluyor...'
        Invoke-Checked $python @('scripts\setup_runtime.py', 'install') 2
        Write-Host '[3/5] Next.js bagimliliklari kuruluyor...'
        Push-Location -LiteralPath (Join-Path $root 'frontend')
        try {
            Invoke-Checked 'npm.cmd' @('ci', '--no-audit', '--no-fund') 3
            Invoke-Checked 'npm.cmd' @('run', 'build')
        } finally { Pop-Location }
        Write-Host '[4/5] Baslangic modelleri hazirlaniyor...'
        if (-not $SkipModels) { Invoke-Checked $python @('scripts\setup_runtime.py', 'models') 3 }
        else { Write-Host 'Model indirme atlandi (gelistirici secenegi).' }
    }
    Write-Host '[5/5] Kurulum dogrulaniyor...'
    if (-not (Test-Path -LiteralPath $python)) { throw 'env/python.exe bulunamadi.' }
    Invoke-Checked $python @('scripts\setup_runtime.py', 'verify')
    Invoke-Checked 'node' @('scripts\check_frontend.cjs')
    Invoke-Checked 'ffmpeg' @('-version')
    Invoke-Checked 'ffprobe' @('-version')
    Write-Host 'HAZIR. Uygulamayi acmak icin start.bat dosyasini kullanin.' -ForegroundColor Green
    Write-Host 'setup.bat uygulamayi baslatmaz. Diger modeller arayuzden indirilebilir.'
} catch {
    Write-Host "KURULUM TAMAMLANAMADI: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($transcript) { Stop-Transcript | Out-Null }
    if ($lock) { $lock.Dispose() }
}
