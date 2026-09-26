<#
.SYNOPSIS
    Control Better Map - installer.

.DESCRIPTION
    Converts the improved map textures to DDS and places them as loose files
    for the Loose Files Loader framework mod (registrator2000).

    Prerequisites:
      1. Control installed (Steam/Epic/GOG)
      2. Loose Files Loader installed (Nexus Mods: control/mods/4)
      3. Python 3.9+ with Pillow + numpy

    Usage:
      .\install.ps1                     # auto-detect game, DXT5, better variant
      .\install.ps1 -Variant labeled    # labeled map variant
      .\install.ps1 -Format bgra8       # lossless (bigger files)
      .\install.ps1 -GameDir "D:\Games\Control"
#>
param(
    [ValidateSet('better', 'labeled')]
    [string]$Variant = 'better',
    [ValidateSet('dxt5', 'dxt1', 'bgra8')]
    [string]$Format = 'dxt5',
    [string]$GameDir = '',
    [switch]$SkipConvert
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Improved = Join-Path $Root 'maps\improved'
$Ready = Join-Path $Root 'maps\mod\ready'

function Find-GameDir {
    $candidates = @(
        "$env:ProgramFiles(x86)\Steam\steamapps\common\Control",
        "$env:ProgramFiles\Steam\steamapps\common\Control",
        "$env:ProgramFiles\Epic Games\Control",
        "$env:ProgramFiles(x86)\Epic Games\Control",
        'D:\SteamLibrary\steamapps\common\Control',
        'D:\Epic Games\Control',
        'E:\SteamLibrary\steamapps\common\Control',
        'E:\Epic Games\Control'
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    return $null
}

function Test-LooseFilesLoader {
    param([string]$GameDir)
    $dlls = Get-ChildItem -Path $GameDir -Filter '*.dll' -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'loose|loader|mod' }
    return $dlls
}

Write-Host '=== Control Better Map installer ===' -ForegroundColor Cyan

# 1. game dir
if (-not $GameDir) { $GameDir = Find-GameDir }
if (-not $GameDir -or -not (Test-Path -LiteralPath $GameDir)) {
    Write-Host 'ERROR: Control install not found.' -ForegroundColor Red
    Write-Host 'Pass -GameDir "path\to\Control"'
    exit 1
}
Write-Host "Game dir : $GameDir"

# 2. loose files loader check
$loader = Test-LooseFilesLoader $GameDir
if (-not $loader) {
    Write-Host 'WARNING: Loose Files Loader not detected.' -ForegroundColor Yellow
    Write-Host '  Download it from Nexus Mods (Control > Loose Files Loader, mod id 4)'
    Write-Host '  and install it before this mod will take effect.'
} else {
    Write-Host "Loader   : $($loader.Name -join ', ')"
}

# 3. convert
if (-not $SkipConvert) {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { Write-Host 'ERROR: python not found on PATH.' -ForegroundColor Red; exit 1 }
    New-Item -ItemType Directory -Force -Path $Ready | Out-Null
    $sectors = @('executive','research','maintenance','containment','foundation','investigations','quarry','unmapped')
    foreach ($s in $sectors) {
        $png = Join-Path $Improved "$s`_$Variant.png"
        if (-not (Test-Path -LiteralPath $png)) { continue }
        $dds = Join-Path $Ready "$s`_$Variant.dds"
        Write-Host "  convert $s ($Variant, $Format)..." -ForegroundColor Gray
        & python (Join-Path $Root 'tools\make_dds.py') $png $dds --format $Format
        if ($LASTEXITCODE -ne 0) { Write-Host "  FAILED $s" -ForegroundColor Red }
    }
    Write-Host "Converted textures -> $Ready" -ForegroundColor Green
}

# 4. placement
$dataDir = Join-Path $GameDir 'data'
if (Test-Path -LiteralPath $dataDir) {
    $dest = Join-Path $dataDir 'better_map'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $Ready '*') -Destination $dest -Force
    Write-Host "Placed loose files -> $dest" -ForegroundColor Green
    Write-Host ''
    Write-Host 'IMPORTANT: loose files must mirror the EXACT paths inside the game archives.' -ForegroundColor Yellow
    Write-Host 'Run:  python tools\extract_map_textures.py --game-dir "<game dir>"' -ForegroundColor Yellow
    Write-Host 'Then move the .tex files into the matching subfolders under data\better_map\.' -ForegroundColor Yellow
} else {
    Write-Host "No data\ folder found under $GameDir - loose files placed in $Ready" -ForegroundColor Yellow
    Write-Host 'Copy them into <game>\data\ mirroring the archive paths (see README).'
}

Write-Host ''
Write-Host 'Done. Launch Control and open the map.' -ForegroundColor Green