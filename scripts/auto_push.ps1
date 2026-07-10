Param(
    [string]$RepoPath = (Get-Location).Path,
    [int]$DebounceMs = 3000
)

Set-Location $RepoPath
Write-Host "Watching $RepoPath for changes. Debounce: $DebounceMs ms. Press Ctrl+C to stop."

$timer = $null

$runPush = {
    Write-Host "Changes detected. Running git add/commit/push..."
    & git add -A
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    # try to commit; ignore if no changes
    $commitOutput = & git commit -m "Auto update $time" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "No commit created or commit failed: $commitOutput"
    } else {
        Write-Host "Commit created. Pushing to remote..."
        & git push
        if ($LASTEXITCODE -eq 0) { Write-Host "Push succeeded." } else { Write-Host "Push failed. Check credentials and remote." }
    }
}

$scheduleDebounce = {
    param($ms)
    if ($timer) { $timer.Stop(); $timer.Dispose() }
    $timer = New-Object System.Timers.Timer $ms
    $timer.AutoReset = $false
    Register-ObjectEvent $timer Elapsed -Action { & $runPush } | Out-Null
    $timer.Start()
}

$action = {
    # on any change event, schedule a debounce timer
    & $scheduleDebounce $DebounceMs
}

$fsw = New-Object System.IO.FileSystemWatcher $RepoPath, '*.*'
$fsw.IncludeSubdirectories = $true
$fsw.NotifyFilter = [IO.NotifyFilters]'FileName, LastWrite, DirectoryName'

Register-ObjectEvent $fsw Created -Action $action | Out-Null
Register-ObjectEvent $fsw Changed -Action $action | Out-Null
Register-ObjectEvent $fsw Deleted -Action $action | Out-Null
Register-ObjectEvent $fsw Renamed -Action $action | Out-Null

try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    if ($timer) { $timer.Dispose() }
}
