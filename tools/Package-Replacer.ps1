param(
    [string]$Version = '0.4.6-preview',
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'release')
)

$ErrorActionPreference = 'Stop'
$project = (Split-Path -Parent $PSScriptRoot)
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
$releaseName = "RE4R-Character-Replacer-$Version"
$stage = Join-Path $output $releaseName
$zip = Join-Path $output ($releaseName + '.zip')

function Copy-RequiredFile([string]$RelativePath) {
    $source = Join-Path $project $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Required release file is missing: $RelativePath"
    }
    $destination = Join-Path $stage $RelativePath
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

function Copy-FilteredTree([string]$Source, [string]$Destination, [string[]]$ExcludedDirectories, [string[]]$ExcludedFiles) {
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Required dependency directory is missing: $Source"
    }
    foreach ($file in Get-ChildItem -LiteralPath $Source -Recurse -Force -File) {
        $relative = $file.FullName.Substring($Source.TrimEnd('\').Length).TrimStart('\')
        $parts = $relative -split '[\\/]'
        if ($parts | Where-Object { $ExcludedDirectories -contains $_ -or $_ -like '*_updater' }) { continue }
        if ($ExcludedFiles -contains $file.Name -or $file.Extension -in @('.pyc', '.pyo')) { continue }
        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    }
}

New-Item -ItemType Directory -Path $output -Force | Out-Null
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
New-Item -ItemType Directory -Path $stage -Force | Out-Null

$coreFiles = @(
    'Start-Replacer.cmd', 'Start-Replacer.ps1', 'Configure-Paths.cmd', 'RELEASE_README.md',
    'LICENSE-NOTICE.md', 'THIRD_PARTY_NOTICES.md',
    'replacer_app\server.py', 'replacer_app\pipeline.py', 'replacer_app\game_resources.py',
    'replacer_app\fluffy_package.py', 'replacer_app\doctor.py', 'replacer_app\runtime_paths.py',
    'scripts\create_pose_alignment_workspace.py', 'scripts\refresh_pose_preview.py',
    'scripts\build_character_mod.py', 'scripts\prepare_character_profiles.py',
    'scripts\align_humanoid.py', 'scripts\humanoid_bones.py',
    'scripts\regularize_skin_weights.py', 'scripts\dds_fallback.py',
    'scripts\material_contract.py', 'scripts\character_motion_audit.py'
)
foreach ($file in $coreFiles) { Copy-RequiredFile $file }
Copy-FilteredTree (Join-Path $project 'replacer_app\web') (Join-Path $stage 'replacer_app\web') @('__pycache__') @()

$meshEditor = Join-Path $project 'tools\RE-Mesh-Editor'
Copy-FilteredTree $meshEditor (Join-Path $stage 'tools\RE-Mesh-Editor') @('.git', '__pycache__') @('.git', 'testMPLYPlot.py')
Copy-Item -LiteralPath (Join-Path $meshEditor 'LICENSE.GPL') -Destination (Join-Path $stage 'COPYING') -Force

$mmdTools = Join-Path $project 'vendor\blender_mmd_tools'
Copy-FilteredTree $mmdTools (Join-Path $stage 'vendor\blender_mmd_tools') @('.git', '.github', '__pycache__', 'samples', 'tests') @('.git')

$pakOutput = Join-Path $stage 'tools\replacer_pak'
New-Item -ItemType Directory -Path $pakOutput -Force | Out-Null
& dotnet publish (Join-Path $project 'tools\replacer_pak\ReplacerPak.csproj') -c Release -r win-x64 --self-contained true -p:PublishSingleFile=false -p:DebugType=None -p:DebugSymbols=false -o $pakOutput
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $pakOutput 'ReplacerPak.exe'))) {
    throw 'Failed to publish the self-contained PAK helper.'
}
$nativeZstd = Join-Path $pakOutput 'libzstd.dll'
if (-not (Test-Path -LiteralPath $nativeZstd -PathType Leaf)) {
    throw 'Failed to package the native ZSTD dependency: tools\replacer_pak\libzstd.dll'
}

$launcherOutput = Join-Path $output 'launcher-publish'
if (Test-Path -LiteralPath $launcherOutput) { Remove-Item -LiteralPath $launcherOutput -Recurse -Force }
& dotnet publish (Join-Path $project 'tools\replacer_launcher\ReplacerLauncher.csproj') -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=None -p:DebugSymbols=false -o $launcherOutput
$launcherExe = Join-Path $launcherOutput 'RE4RCharacterReplacer.exe'
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $launcherExe)) {
    throw 'Failed to publish the self-contained Windows launcher.'
}
Copy-Item -LiteralPath $launcherExe -Destination (Join-Path $stage 'RE4RCharacterReplacer.exe') -Force

$catalog = Join-Path $project 'data\RE4_STM_Character.list'
if (-not (Test-Path -LiteralPath $catalog -PathType Leaf)) { throw "Character resource catalog is missing: $catalog" }
$dataDirectory = Join-Path $stage 'data'
New-Item -ItemType Directory -Path $dataDirectory -Force | Out-Null
$resources = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($line in Get-Content -LiteralPath $catalog -Encoding UTF8) {
    $path = $line.Trim().Replace('\', '/').ToLowerInvariant()
    if ($path) { [void]$resources.Add($path) }
}
$resourceFile = Join-Path $dataDirectory 'RE4_STM_Character.list'
[System.IO.File]::WriteAllLines($resourceFile, ([string[]]$resources | Sort-Object), [System.Text.UTF8Encoding]::new($false))

$metadata = [ordered]@{
    name = 'RE4R Character Replacer Generator'
    version = $Version
    channel = 'preview'
    platform = 'windows-x64'
    packagedAtUtc = [DateTime]::UtcNow.ToString('o')
    containsModels = $false
    containsExtractedGameAssets = $false
    fullRegressionTargets = @('leon', 'ashley')
    experimentalTargets = @('ada', 'luis', 'wesker', 'merchant')
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stage 'release.json') -Encoding UTF8

$forbiddenExtensions = @('.blend', '.pmx', '.pmd', '.fbx', '.pak', '.mesh', '.mdf2', '.tex')
$forbiddenFiles = Get-ChildItem -LiteralPath $stage -Recurse -File | Where-Object {
    $lower = $_.Name.ToLowerInvariant()
    $forbiddenExtensions | Where-Object { $lower.EndsWith($_) -or $lower.Contains($_ + '.') }
}
if ($forbiddenFiles) { throw ('Forbidden model/game files entered release: ' + ($forbiddenFiles.FullName -join ', ')) }
$absoluteLeaks = Get-ChildItem -LiteralPath $stage -Recurse -File | Where-Object { $_.Length -lt 5MB } | Select-String -SimpleMatch 'D:\work_console' -List
if ($absoluteLeaks) { throw ('Development path entered release: ' + ($absoluteLeaks.Path -join ', ')) }

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($zip, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in Get-ChildItem -LiteralPath $stage -Recurse -File) {
        $relative = $file.FullName.Substring($stage.TrimEnd('\').Length).TrimStart('\').Replace('\', '/')
        $entryName = "$releaseName/$relative"
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, $entryName, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally {
    $archive.Dispose()
}

$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
$files = @(Get-ChildItem -LiteralPath $stage -Recurse -File)
$manifest = [ordered]@{
    archive = [System.IO.Path]::GetFileName($zip)
    sha256 = $hash
    bytes = (Get-Item -LiteralPath $zip).Length
    files = $files.Count
    unpackedBytes = ($files | Measure-Object -Property Length -Sum).Sum
    resourcePaths = $resources.Count
    singleRoot = $releaseName
}
$manifestPath = Join-Path $output ($releaseName + '.manifest.json')
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output ($manifest | ConvertTo-Json -Compress)
