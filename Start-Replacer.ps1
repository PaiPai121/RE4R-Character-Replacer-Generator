param([switch]$Configure)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$configPath = Join-Path $PSScriptRoot 'replacer-paths.json'
$saved = $null
if (Test-Path -LiteralPath $configPath -PathType Leaf) {
    try {
        $saved = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        Write-Warning 'replacer-paths.json could not be read; paths will be configured again.'
    }
}

function Normalize-PathInput([string]$Value, [string]$ChildName = '') {
    if (-not $Value) { return $null }
    $clean = [Environment]::ExpandEnvironmentVariables($Value.Trim().Trim('"').Trim("'"))
    if ($ChildName -and (Test-Path -LiteralPath $clean -PathType Container)) {
        $clean = Join-Path $clean $ChildName
    }
    try { return [IO.Path]::GetFullPath($clean) } catch { return $clean }
}

function Test-Blender([string]$Path) {
    return $Path -and (Test-Path -LiteralPath $Path -PathType Leaf) -and
        ([IO.Path]::GetFileName($Path) -ieq 'blender.exe')
}

function Test-Game([string]$Path) {
    return $Path -and (Test-Path -LiteralPath (Join-Path $Path 're_chunk_000.pak') -PathType Leaf)
}

$candidates = @()
if ($env:REPLACER_BLENDER) { $candidates += (Normalize-PathInput $env:REPLACER_BLENDER 'blender.exe') }
if ($saved -and $saved.blender) { $candidates += (Normalize-PathInput ([string]$saved.blender) 'blender.exe') }
$command = Get-Command blender -ErrorAction SilentlyContinue
if ($command) { $candidates += $command.Source }
$candidates += Get-ChildItem -Path "$env:ProgramFiles\Blender Foundation\Blender *\blender.exe" -File -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName
foreach ($drive in 'C:','D:','E:','F:','G:') {
    $candidates += "$drive\SteamLibrary\steamapps\common\Blender\blender.exe"
    $candidates += "$drive\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
}
$blender = $candidates | Where-Object { Test-Blender $_ } | Select-Object -First 1

if ($Configure -or -not $blender) {
    Write-Host ''
    Write-Host 'Blender was not found automatically, or manual configuration was requested.'
    Write-Host 'Paste blender.exe, paste the Blender folder, or drag blender.exe into this window.'
    $label = if ($blender) { "Blender path [$blender]" } else { 'Blender path' }
    $answer = Read-Host $label
    if ($answer) { $blender = Normalize-PathInput $answer 'blender.exe' }
    if (-not (Test-Blender $blender)) {
        throw 'The selected Blender path is invalid. Expected an existing blender.exe.'
    }
}

$gameCandidates = @()
if ($env:RE4_GAME_DIR) { $gameCandidates += (Normalize-PathInput $env:RE4_GAME_DIR) }
if ($saved -and $saved.game) { $gameCandidates += (Normalize-PathInput ([string]$saved.game)) }
foreach ($drive in 'C:','D:','E:','F:','G:') {
    $gameCandidates += "$drive\SteamLibrary\steamapps\common\RESIDENT EVIL 4  BIOHAZARD RE4"
    $gameCandidates += "$drive\Program Files (x86)\Steam\steamapps\common\RESIDENT EVIL 4  BIOHAZARD RE4"
}
$game = $gameCandidates | Where-Object { Test-Game $_ } | Select-Object -First 1

if ($Configure -or -not $game) {
    Write-Host ''
    Write-Host 'Paste the Resident Evil 4 game folder that contains re_chunk_000.pak.'
    $label = if ($game) { "Game path [$game]" } else { 'Game path (Enter to choose it later in the web page)' }
    $answer = Read-Host $label
    if ($answer) {
        $candidate = Normalize-PathInput $answer
        if (-not (Test-Game $candidate)) {
            throw 'The selected game folder is invalid. It must contain re_chunk_000.pak.'
        }
        $game = $candidate
    }
}

$configuration = [ordered]@{ blender = $blender }
if ($game) { $configuration.game = $game }
$configuration | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
Write-Host "Saved paths: $configPath"

if ($Configure) {
    Write-Host 'Configuration complete. Run Start-Replacer.cmd to start the tool.'
    exit 0
}

$env:REPLACER_BLENDER = $blender
if ($game) { $env:RE4_GAME_DIR = $game }
if (-not $env:REPLACER_BUILD_ROOT -and $env:LOCALAPPDATA) {
    $env:REPLACER_BUILD_ROOT = Join-Path $env:LOCALAPPDATA 'RE4R-Replacer\jobs'
}
$bundledMmd = Join-Path $PSScriptRoot 'vendor\blender_mmd_tools'
if (-not $env:REPLACER_MMD_TOOLS -and (Test-Path -LiteralPath (Join-Path $bundledMmd 'mmd_tools\__init__.py'))) {
    $env:REPLACER_MMD_TOOLS = $bundledMmd
}
& $blender --background --python-exit-code 1 --python replacer_app/doctor.py
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed. See the paths above.' }
$setBrowserDefault = -not $env:REPLACER_OPEN_BROWSER
if ($setBrowserDefault) { $env:REPLACER_OPEN_BROWSER = '1' }
try {
    & $blender --background --python-exit-code 1 --python replacer_app/server.py
} finally {
    if ($setBrowserDefault) { Remove-Item Env:REPLACER_OPEN_BROWSER -ErrorAction SilentlyContinue }
}
