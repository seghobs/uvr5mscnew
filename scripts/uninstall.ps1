param([switch]$ListOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'uninstall-functions.ps1')
$setupLock = $null
try {
    $root = Assert-ProjectRoot (Join-Path $PSScriptRoot '..')
    # Leave the directory before removing it; no helper or log is copied elsewhere.
    Set-Location -LiteralPath $env:SystemRoot
    Write-Host 'UVR5 Next Studio - TAM KALDIRMA' -ForegroundColor Red
    Write-Host "Silinecek klasor: $root"
    Write-Host 'Python ortami, modeller, kutuphaneler, sesler, projeler, kaynak kodu ve .git DAHIL silinir.'
    Write-Host 'Kurulum/kaldirma betikleri de silinir. Bu islem geri alinamaz.'
    Write-Host 'Ortak sistem Python/Node, baska uygulamalar ve sahipligi belirsiz ortak onbellekler korunur.'
    if ($ListOnly) { exit 0 }
    if ((Read-Host 'Devam etmek icin SIL yazin; iptal icin Enter').Trim() -cne 'SIL') {
        Write-Host 'Iptal edildi. Hicbir dosya silinmedi.'; exit 0
    }
    $runtime = Join-Path $root '.runtime'
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    $setupLock = [IO.File]::Open((Join-Path $runtime 'setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    [IO.File]::WriteAllText((Join-Path $runtime 'uninstalling'), 'uninstalling')
    Write-Host '[1/3] Bu projeye ait islemler durduruluyor...'
    Stop-ProjectProcesses $root
    Write-Host '[2/3] Projeye ait Conda kayitlari ve kisayollar temizleniyor...'
    Remove-CondaReferences (Join-Path $env:USERPROFILE '.conda\environments.txt') $root
    Remove-ProjectRegistryEntries $root
    Remove-ProjectShortcuts $root
    $setupLock.Dispose(); $setupLock = $null
    Write-Host '[3/3] Proje ve kurulum dosyalari siliniyor...'
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try { Remove-ProjectTree $root $root; break }
        catch { if ($attempt -eq 3) { throw }; Start-Sleep -Seconds 2 }
    }
    if (Test-Path -LiteralPath $root) { throw 'Proje klasorunde kalan dosyalar var.' }
    Write-Host 'KALDIRILDI. Proje klasoru ve projeye ozel kurulum verileri silindi.' -ForegroundColor Green
    [void](Read-Host 'Pencereyi kapatmak icin Enter')
} catch {
    Write-Host "KALDIRMA TAMAMLANAMADI: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Basariyla silindigi dogrulanamayan dosyalar kalmis olabilir. Acik terminalleri/dosyalari kapatip kontrol edin.'
    [void](Read-Host 'Pencereyi kapatmak icin Enter')
    exit 1
} finally { if ($setupLock) { $setupLock.Dispose() } }
