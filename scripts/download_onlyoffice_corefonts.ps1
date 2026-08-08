param(
    [string]$Destination = (Join-Path $PSScriptRoot '..\assets\onlyoffice-corefonts')
)

$ErrorActionPreference = 'Stop'
$fileNames = @(
    'andale32.exe',
    'arial32.exe',
    'arialb32.exe',
    'comic32.exe',
    'courie32.exe',
    'georgi32.exe',
    'impact32.exe',
    'times32.exe',
    'trebuc32.exe',
    'verdan32.exe',
    'webdin32.exe',
    'wd97vwr32.exe'
)
$baseUri = 'https://downloads.sourceforge.net/project/corefonts/the%20fonts/final'

$destinationPath = [System.IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -Path $destinationPath | Out-Null

foreach ($fileName in $fileNames) {
    $outputPath = Join-Path $destinationPath $fileName
    $temporaryPath = "$outputPath.partial"
    $uri = "$baseUri/$fileName"

    if ((Test-Path $outputPath) -and (Get-Item $outputPath).Length -gt 0) {
        Write-Host "Using existing $fileName"
        continue
    }

    Remove-Item -Force -ErrorAction SilentlyContinue $temporaryPath
    Write-Host "Downloading $fileName"
    & curl.exe --fail --location --retry 3 --output $temporaryPath $uri
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $temporaryPath) -or (Get-Item $temporaryPath).Length -lt 1024) {
        Remove-Item -Force -ErrorAction SilentlyContinue $temporaryPath
        throw "Download failed: $fileName"
    }

    Move-Item -Force $temporaryPath $outputPath
}

Write-Host "Core-font cache is ready: $destinationPath"