param(
    [Parameter(Mandatory=$true)][string]$CaseDir,
    [Parameter(Mandatory=$true)][string]$RscriptPath,
    [string]$InputOverride = '',
    [string]$OutputOverride = '',
    [string]$Models = ''
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$case = Join-Path $root $CaseDir
$inputFile = if ($InputOverride) { $InputOverride } else { Join-Path $root 'model_input.csv' }
$parts = $CaseDir -split [regex]::Escape([string][IO.Path]::DirectorySeparatorChar)
if ($parts.Count -ne 4) { throw 'CaseDir must be Objective/Scope/Target/FeatureSet.' }
$objective = [int]($parts[0] -replace '^Objective ', '')
$scope = $parts[1].ToLowerInvariant()
$feature = switch ($parts[3]) { 'IV' {'iv'} 'IV+CV' {'iv_cv'} 'IV+CV+NES' {'iv_cv_nes'} default {throw 'Unknown feature set'} }
$outcome = if ($objective -le 3) { $parts[2] } elseif ($objective -eq 4) { 'fearfail_2015_2022' } else { 'EXIT_ENT_harmonized' }
$outputDir = if ($OutputOverride) { $OutputOverride } else { Join-Path $case 'rerun_output' }
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
Remove-Item -LiteralPath (Join-Path $outputDir 'pipeline_complete.txt') -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $outputDir 'rerun_failed.txt') -ErrorAction SilentlyContinue
if (-not (Test-Path -LiteralPath (Join-Path $case 'run.R') -PathType Leaf)) {
    Set-Content -LiteralPath (Join-Path $outputDir 'rerun_failed.txt') -Value 'Case R launcher missing.'
    throw "Case R launcher missing: $case"
}
if (-not (Test-Path -LiteralPath $inputFile -PathType Leaf)) {
    Set-Content -LiteralPath (Join-Path $outputDir 'rerun_failed.txt') -Value 'Prepared input missing.'
    throw 'Run prepare_data.do first.'
}
if (-not (Test-Path -LiteralPath $RscriptPath -PathType Leaf)) {
    Set-Content -LiteralPath (Join-Path $outputDir 'rerun_failed.txt') -Value 'Rscript.exe missing.'
    throw "Rscript.exe not found: $RscriptPath"
}
$argsForR = @("--input=$inputFile","--output=$outputDir","--project=$root",
              "--objective=$objective","--scope=$scope","--feature_set=$feature","--outcome=$outcome","--resume=true")
if ($Models) { $argsForR += "--models=$Models" }
if ($feature -eq 'iv_cv_nes') {
    $baseDir = Join-Path (Split-Path -Parent $case) 'IV+CV\rerun_output'
    $casePath = Join-Path $baseDir ("objective_${objective}\${scope}\iv_cv\${outcome}")
    $argsForR += "--baseline_case=$casePath"
    $argsForR += "--baseline_performance=$(Join-Path $baseDir 'all_performance.csv')"
}
& $RscriptPath (Join-Path $case 'run.R') @argsForR 2>&1 |
    Tee-Object -FilePath (Join-Path $case 'rerun_console.log')
if ($LASTEXITCODE -ne 0) {
    Set-Content -LiteralPath (Join-Path $outputDir 'rerun_failed.txt') -Value 'R analysis failed; inspect rerun_console.log.'
    throw "R analysis failed; see $case\rerun_console.log"
}
if (-not (Test-Path -LiteralPath (Join-Path $outputDir 'pipeline_complete.txt'))) {
    Set-Content -LiteralPath (Join-Path $outputDir 'rerun_failed.txt') -Value 'R did not create pipeline_complete.txt.'
    throw 'R finished without the expected completion marker.'
}
Write-Output "Completed $CaseDir"
