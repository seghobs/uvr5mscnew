Set-StrictMode -Version Latest

function Test-InProject {
    param([string]$Path, [string]$Root)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    try {
        $full = [IO.Path]::GetFullPath($Path.Trim().Trim('"')).TrimEnd('\','/')
        $base = [IO.Path]::GetFullPath($Root).TrimEnd('\','/')
        return $full.Equals($base, [StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($base+'\', [StringComparison]::OrdinalIgnoreCase)
    } catch { return $false }
}

function Assert-ProjectRoot {
    param([string]$Root)
    $full = [IO.Path]::GetFullPath($Root).TrimEnd('\','/')
    $forbidden = @([IO.Path]::GetPathRoot($full), $env:USERPROFILE, $env:SystemRoot, $env:ProgramFiles,
        [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('MyDocuments'),
        [Environment]::GetFolderPath('LocalApplicationData'), [Environment]::GetFolderPath('ApplicationData'))
    foreach ($item in $forbidden) {
        if ($item -and $full.Equals($item.TrimEnd('\','/'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Sistem veya kullanici klasoru silinemez.' }
    }
    $directory = Get-Item -LiteralPath $full -Force
    if (-not $directory.PSIsContainer) { throw 'Proje klasoru bulunamadi.' }
    # Do not resolve a junction and accidentally uninstall its external target.
    $ancestor = $directory
    while ($ancestor) {
        if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Baglanti uzerinden kaldirma yapilamaz; asil proje klasorunu kullanin.' }
        $ancestor = $ancestor.Parent
    }
    if (-not (Test-Path -LiteralPath (Join-Path $full 'api_modern.py')) -or -not (Test-Path -LiteralPath (Join-Path $full 'start.bat'))) { throw 'UVR5 proje isaretleri eksik. Guvenli kaldirma durduruldu.' }
    $package = Get-Content -LiteralPath (Join-Path $full 'frontend\package.json') -Raw | ConvertFrom-Json
    if ($package.name -ne 'uvr5-ui-next') { throw 'Bu klasor UVR5 Next Studio degil.' }
    return $full
}

function Get-OwnedProcessIds {
    param([object[]]$Processes, [string]$Root, [int[]]$Excluded = @())
    $owned = New-Object 'System.Collections.Generic.HashSet[int]'
    $executables = @('python.exe','pythonw.exe','node.exe','ffmpeg.exe','ffprobe.exe','ffplay.exe','conda.exe','_conda.exe','mamba.exe','micromamba.exe','pip.exe','uvicorn.exe','ninja.exe')
    $rootPattern = '(?i)(?:^|[\s"''])'+[regex]::Escape($Root.TrimEnd('\','/'))+'[\\/]'
    foreach ($process in $Processes) {
        if ($process.ProcessId -in $Excluded) { continue }
        if ((Test-InProject $process.ExecutablePath $Root) -or ($process.Name -in $executables -and $process.CommandLine -match $rootPattern)) {
            [void]$owned.Add([int]$process.ProcessId)
        }
    }
    # Only relevant subprocesses; never kill an external browser or desktop app.
    do {
        $changed = $false
        foreach ($process in $Processes) {
            if ($process.ProcessId -in $Excluded) { continue }
            if ($process.Name -in ($executables+@('cmd.exe')) -and $owned.Contains([int]$process.ParentProcessId)) {
                if ($owned.Add([int]$process.ProcessId)) { $changed = $true }
            }
            # npm's cmd /c parent can otherwise keep the project as its current directory.
            if ($owned.Contains([int]$process.ProcessId)) {
                $parent = $Processes | Where-Object { $_.ProcessId -eq $process.ParentProcessId } | Select-Object -First 1
                if ($parent -and $parent.ProcessId -notin $Excluded -and $parent.Name -eq 'cmd.exe' -and $parent.CommandLine -match '(?i)/c\s+.*npm(?:\.cmd)?\s+(?:run\s+)?(?:dev|start)(?:\s|$)') {
                    if ($owned.Add([int]$parent.ProcessId)) { $changed = $true }
                }
            }
        }
    } while ($changed)
    return @($owned)
}

function Stop-ProjectProcesses {
    param([string]$Root)
    $snapshot = @(Get-CimInstance Win32_Process)
    $excluded = New-Object 'System.Collections.Generic.List[int]'
    $currentId = $PID
    while ($currentId -gt 0 -and -not $excluded.Contains($currentId)) {
        $excluded.Add($currentId)
        $entry = $snapshot | Where-Object { $_.ProcessId -eq $currentId } | Select-Object -First 1
        if (-not $entry) { break }; $currentId = [int]$entry.ParentProcessId
    }
    $ids = @(Get-OwnedProcessIds $snapshot $Root $excluded.ToArray())
    foreach ($processId in $ids) {
        $before = $snapshot | Where-Object { $_.ProcessId -eq $processId } | Select-Object -First 1
        $now = Get-CimInstance Win32_Process -Filter "ProcessId=$processId"
        if ($now -and $now.CreationDate -eq $before.CreationDate) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
    if ($ids.Count) { Start-Sleep -Seconds 2 }
    $remaining = @(Get-OwnedProcessIds @(Get-CimInstance Win32_Process) $Root $excluded.ToArray())
    if ($remaining.Count) { throw "Projeye ait islemler kapatilamadi: $($remaining -join ', '). Acik terminalleri kapatip yeniden deneyin." }
}

function Remove-CondaReferences {
    param([string]$File, [string]$Root)
    if (-not (Test-Path -LiteralPath $File)) { return }
    if ((Get-Item -LiteralPath $File -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Conda kayit dosyasi bir baglanti; otomatik degistirilmeyecek.' }
    $stream = [IO.File]::Open($File, 'Open', 'ReadWrite', 'None')
    try {
        $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::UTF8, $true, 1024, $true)
        try { $original = $reader.ReadToEnd() } finally { $reader.Dispose() }
        $lines = @($original -split '\r?\n')
        $kept = @($lines | Where-Object { -not (Test-InProject $_ $Root) })
        if ($kept.Count -ne $lines.Count) {
            $bytes = [Text.Encoding]::UTF8.GetBytes(($kept -join [Environment]::NewLine))
            $stream.Position = 0; $stream.SetLength(0); $stream.Write($bytes,0,$bytes.Length); $stream.Flush()
        }
    } finally { $stream.Dispose() }
}

function Remove-ProjectRegistryEntries {
    param([string]$Root)
    foreach ($base in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall','HKCU:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')) {
        if (-not (Test-Path -LiteralPath $base)) { continue }
        foreach ($key in Get-ChildItem -LiteralPath $base) {
            $value = Get-ItemProperty -LiteralPath $key.PSPath
            $location = $value.PSObject.Properties['InstallLocation']
            if ($location -and (Test-InProject $location.Value $Root)) {
                Remove-Item -LiteralPath $key.PSPath -Recurse -Force
            }
        }
    }
}

function Test-ProjectShortcut {
    param($Link, [string]$Root)
    if ((Test-InProject $Link.TargetPath $Root) -or (Test-InProject $Link.WorkingDirectory $Root)) { return $true }
    $launcher = [IO.Path]::GetFileName($Link.TargetPath)
    $pattern = '(?i)(?:^|[\s"''])'+[regex]::Escape($Root.TrimEnd('\','/'))+'[\\/]'
    return $launcher -in @('cmd.exe','powershell.exe','python.exe','pythonw.exe') -and $Link.Arguments -match $pattern
}

function Remove-ProjectShortcuts {
    param([string]$Root)
    $shell = New-Object -ComObject WScript.Shell
    try {
        $bases = @([Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('Desktop'))
        foreach ($base in $bases) {
            if (-not (Test-Path -LiteralPath $base)) { continue }
            $queue = New-Object 'System.Collections.Generic.Queue[string]'
            $queue.Enqueue($base)
            while ($queue.Count) {
                $folder = $queue.Dequeue()
                foreach ($file in Get-ChildItem -LiteralPath $folder -Force) {
                    if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
                    if ($file.PSIsContainer) {
                        # Traverse Start Menu folders, not arbitrary Desktop projects.
                        if ($base -eq $bases[0]) { $queue.Enqueue($file.FullName) }
                        continue
                    }
                    if ($file.Extension -ne '.lnk') { continue }
                    $link = $shell.CreateShortcut($file.FullName)
                    if (Test-ProjectShortcut $link $Root) {
                        Remove-Item -LiteralPath $file.FullName -Force
                        if ($folder -ne $base -and -not @(Get-ChildItem -LiteralPath $folder -Force).Count) { [IO.Directory]::Delete($folder) }
                    }
                    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($link)
                }
            }
        }
    } finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell) }
}

function Remove-ProjectTree {
    param([string]$Path, [string]$Root)
    if (-not (Test-InProject $Path $Root)) { throw "Proje disindaki yol reddedildi: $Path" }
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if (-not $item) { return }
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        # Delete the link itself, without enumerating the linked directory.
        if ($item.PSIsContainer) { [IO.Directory]::Delete($item.FullName) }
        else { [IO.File]::Delete($item.FullName) }
        return
    }
    if ($item.PSIsContainer) {
        foreach ($child in @(Get-ChildItem -LiteralPath $item.FullName -Force)) { Remove-ProjectTree $child.FullName $Root }
        $item.Attributes = $item.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)
        [IO.Directory]::Delete($item.FullName)
    } else { Remove-Item -LiteralPath $item.FullName -Force }
}
