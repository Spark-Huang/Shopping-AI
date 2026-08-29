param(
    [int]$RefreshSeconds = 5
)

$ErrorActionPreference = "SilentlyContinue"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

while ($true) {
    Clear-Host
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Codex Monitor - Shopping-AI" -ForegroundColor Cyan
    Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    Write-Host ""
    Write-Host "## Codex Process" -ForegroundColor Yellow
    $codex = Get-Process -Name "codex" -ErrorAction SilentlyContinue
    if ($codex) {
        $codex | ForEach-Object {
            $memMB = [math]::Round($_.WorkingSet64 / 1MB, 1)
            Write-Host "  PID: $($_.Id) | CPU: $($_.CPU) | Memory: ${memMB}MB" -ForegroundColor Green
        }
    } else {
        Write-Host "  [STOPPED] Codex not running" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "## Git Status" -ForegroundColor Yellow
    Push-Location $projectRoot
    $branch = git branch --show-current 2>$null
    $lastCommit = git log -1 --oneline 2>$null
    $status = git status --short 2>$null
    $changedCount = ($status | Measure-Object -Line).Lines
    Pop-Location

    Write-Host "  Branch: $branch" -ForegroundColor Green
    Write-Host "  Last Commit: $lastCommit"
    Write-Host "  Changed Files: $changedCount"
    if ($changedCount -gt 0) {
        Write-Host ""
        Write-Host "  Recent Changes:" -ForegroundColor Gray
        $status | Select-Object -First 10 | ForEach-Object {
            $color = "Gray"
            if ($_ -match '^M') { $color = "Yellow" }
            elseif ($_ -match '^\?\?') { $color = "Green" }
            Write-Host "    $_" -ForegroundColor $color
        }
    }

    Write-Host ""
    Write-Host "## Recent Files (last 1 min)" -ForegroundColor Yellow
    $since = (Get-Date).AddMinutes(1)
    $files = Get-ChildItem -Path $projectRoot -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -gt $since -and $_.Extension -notmatch '\.(log|db|pyc|png|jpg|jpeg|webp|gif|ico|svg|idx|bin|exe|dll)$' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 10
    if ($files) {
        $files | ForEach-Object {
            $rel = $_.FullName.Substring($projectRoot.Length + 1)
            $sizeKB = [math]::Round($_.Length / 1KB, 1)
            Write-Host "  $($_.LastWriteTime.ToString('HH:mm:ss')) | ${sizeKB}KB | $rel" -ForegroundColor Gray
        }
    } else {
        Write-Host "  (no recent changes)" -ForegroundColor Gray
    }

    Write-Host ""
    Write-Host "Press Ctrl+C to exit, auto-refresh in ${RefreshSeconds}s..." -ForegroundColor DarkGray
    Start-Sleep -Seconds $RefreshSeconds
}
