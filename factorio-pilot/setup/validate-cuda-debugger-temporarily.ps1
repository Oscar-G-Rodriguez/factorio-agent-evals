$ErrorActionPreference = 'Stop'
$taskRoot = 'C:\Users\osci2\Documents\Codex\2026-10-05\igni'
$taskStatus = Join-Path $taskRoot 'work\cuda-debugger-validation-status.json'
$taskRegistry = 'HKLM:\SOFTWARE\NVIDIA Corporation\GPUDebugger'
$taskName = 'EnableInterface'
$taskHadKey = Test-Path -LiteralPath $taskRegistry
$taskHadValue = $false
$taskChanged = $false
$taskResult = @{status='starting'; user_authorized=$true; started_utc=[DateTime]::UtcNow.ToString('o')}
try {
    if ($taskHadKey) {
        $taskKey = Get-Item -LiteralPath $taskRegistry
        $taskHadValue = $taskKey.GetValueNames() -contains $taskName
        if ($taskHadValue) {
            $taskPrevious = $taskKey.GetValue($taskName)
            $taskPreviousKind = $taskKey.GetValueKind($taskName)
        }
    }
    @{path=$taskRegistry; name=$taskName; key_existed=$taskHadKey; value_existed=$taskHadValue;
      previous_value=if($taskHadValue){$taskPrevious}else{$null};
      previous_kind=if($taskHadValue){[string]$taskPreviousKind}else{$null}} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRoot 'work\cuda-debugger-approved-previous.json') -Encoding UTF8
    if (-not $taskHadKey) { New-Item -Path $taskRegistry -Force | Out-Null }
    $taskChanged = $true
    New-ItemProperty -LiteralPath $taskRegistry -Name $taskName -PropertyType DWord -Value 1 -Force | Out-Null
    $taskResult.status='running_sanitizers'
    $taskResult.enabled_value=Get-ItemPropertyValue -LiteralPath $taskRegistry -Name $taskName
    $taskResult | ConvertTo-Json | Set-Content -LiteralPath $taskStatus -Encoding UTF8
    & wsl.exe -d Ubuntu-24.04 -u osci2 -- bash /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/setup/run-rmsnorm-sanitizers.sh *>&1 |
        Out-File -LiteralPath (Join-Path $taskRoot 'work\approved-rmsnorm-sanitizers.log') -Encoding utf8
    $taskResult.sanitizer_exit_code=$LASTEXITCODE
    $taskResult.status=if($LASTEXITCODE -eq 0){'sanitizers_passed'}else{'sanitizers_failed'}
} catch {
    $taskResult.status='failed'
    $taskResult.error=$_.Exception.Message
} finally {
    try {
        if ($taskChanged) {
            if ($taskHadValue) {
                New-ItemProperty -LiteralPath $taskRegistry -Name $taskName -PropertyType $taskPreviousKind -Value $taskPrevious -Force | Out-Null
            } else {
                Remove-ItemProperty -LiteralPath $taskRegistry -Name $taskName -ErrorAction SilentlyContinue
            }
            if (-not $taskHadKey -and (Test-Path -LiteralPath $taskRegistry)) {
                $taskAfter = Get-Item -LiteralPath $taskRegistry
                if ($taskAfter.GetValueNames().Count -eq 0 -and $taskAfter.GetSubKeyNames().Count -eq 0) {
                    Remove-Item -LiteralPath $taskRegistry
                }
            }
        }
        $taskRestored = if ($taskHadValue) {
            $taskAfter = Get-Item -LiteralPath $taskRegistry
            $taskAfter.GetValue($taskName) -eq $taskPrevious -and $taskAfter.GetValueKind($taskName) -eq $taskPreviousKind
        } else {
            -not (Test-Path -LiteralPath $taskRegistry) -or -not ((Get-Item -LiteralPath $taskRegistry).GetValueNames() -contains $taskName)
        }
        $taskResult.registry_restored=$taskRestored
    } catch {
        $taskResult.registry_restored=$false
        $taskResult.restore_error=$_.Exception.Message
    }
    $taskResult.finished_utc=[DateTime]::UtcNow.ToString('o')
    $taskResult | ConvertTo-Json | Set-Content -LiteralPath $taskStatus -Encoding UTF8
}
