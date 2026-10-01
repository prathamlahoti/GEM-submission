param([Parameter(Mandatory=$true)][string]$RscriptPath)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$rscriptPath = $RscriptPath
$libraryPath = Join-Path $projectRoot '.r-lib'
$downloadPath = Join-Path $env:TEMP 'catboost-R-windows-x86_64-1.2.10.tgz'
$runtimePath = Join-Path $PSScriptRoot 'analysis\runtime'

if (-not (Test-Path -LiteralPath $rscriptPath -PathType Leaf)) {
    throw "Rscript.exe not found at $rscriptPath"
}
New-Item -ItemType Directory -Force -Path $libraryPath | Out-Null
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null

$libraryForR = $libraryPath.Replace('\', '/')
$cranScript = ".libPaths(c('$libraryForR', .libPaths())); pkgs <- c('data.table','glmnet','e1071','ranger','xgboost','bit64','remotes','R.utils'); missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)]; if (length(missing)) install.packages(missing, lib=.libPaths()[1], repos='https://cloud.r-project.org', type='binary')"
& $rscriptPath -e $cranScript
if ($LASTEXITCODE -ne 0) { throw 'CRAN package installation failed.' }

# CRAN's H2O build may lag the Java-compatible release used by this project.
$h2oScript = ".libPaths(c('$libraryForR', .libPaths())); if (!requireNamespace('h2o', quietly=TRUE) || as.character(packageVersion('h2o')) != '3.46.0.12') install.packages('h2o', repos='https://h2o-release.s3.amazonaws.com/h2o/rel-3.46.0/12/R', type='source', lib=.libPaths()[1])"
& $rscriptPath -e $h2oScript
if ($LASTEXITCODE -ne 0) { throw 'H2O installation failed.' }

$java8Path = Get-ChildItem -LiteralPath $runtimePath -Directory -Filter 'jdk8*' -ErrorAction SilentlyContinue |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'bin\java.exe') -PathType Leaf } |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $java8Path) {
    $javaZip = Join-Path $env:TEMP 'gem-jdk8.zip'
    $javaUrl = 'https://api.adoptium.net/v3/binary/latest/8/ga/windows/x64/jdk/hotspot/normal/eclipse'
    & curl.exe -L --ssl-no-revoke --fail --retry 5 --retry-all-errors --silent --show-error --output $javaZip $javaUrl
    if ($LASTEXITCODE -ne 0) { throw 'Portable Java 8 download failed.' }
    Expand-Archive -LiteralPath $javaZip -DestinationPath $runtimePath -Force
    Remove-Item -LiteralPath $javaZip
    $java8Path = Get-ChildItem -LiteralPath $runtimePath -Directory -Filter 'jdk8*' |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'bin\java.exe') -PathType Leaf } |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $java8Path) { throw 'Portable Java 8 was not found after extraction.' }
}

if (-not (Test-Path -LiteralPath (Join-Path $libraryPath 'catboost'))) {
    $catboostUrl = 'https://github.com/catboost/catboost/releases/download/v1.2.10/catboost-R-windows-x86_64-1.2.10.tgz'
    & curl.exe -L --ssl-no-revoke --fail --retry 5 --retry-all-errors --silent --show-error --output $downloadPath $catboostUrl
    if ($LASTEXITCODE -ne 0) { throw 'CatBoost download failed.' }
    $downloadForR = $downloadPath.Replace('\', '/')
    & $rscriptPath -e ".libPaths(c('$libraryForR', .libPaths())); remotes::install_local('$downloadForR', lib=.libPaths()[1], dependencies=FALSE, INSTALL_opts=c('--no-multiarch','--no-test-load'))"
    if ($LASTEXITCODE -ne 0) { throw 'CatBoost installation failed.' }
    Remove-Item -LiteralPath $downloadPath
}

Write-Output "R dependencies are installed in $libraryPath; portable Java is in $java8Path"
