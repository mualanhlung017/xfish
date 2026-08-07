[CmdletBinding()]
param(
    [ValidateSet('avx2')]
    [string]$Architecture = 'avx2',

    [string]$BuildDirectory = 'build/clangcl-avx2-pgo',

    [ValidateRange(1, 256)]
    [int]$Jobs = [Environment]::ProcessorCount,

    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$buildRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot $BuildDirectory))
$repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

if (-not $buildRoot.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "BuildDirectory must resolve inside the repository: $buildRoot"
}

if ($Clean -and (Test-Path -LiteralPath $buildRoot)) {
    Write-Host "Cleaning $buildRoot"
    Remove-Item -LiteralPath $buildRoot -Recurse -Force
}

function Find-ExistingTool {
    param(
        [Parameter(Mandatory)]
        [string]$DisplayName,

        [Parameter(Mandatory)]
        [string[]]$Candidates
    )

    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "$DisplayName was not found. Checked: $($Candidates -join ', ')"
}

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) {
    throw 'Visual Studio Installer (vswhere.exe) was not found.'
}

$vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    -property installationPath
if (-not $vsPath) {
    throw 'Visual Studio with the MSVC x64 tools and LLVM/Clang component was not found.'
}

$devCmd = Join-Path $vsPath 'Common7/Tools/VsDevCmd.bat'
$devCmdLine = "call `"$devCmd`" -no_logo -arch=x64 -host_arch=x64 >nul && set"
$devEnvironment = & $env:ComSpec /d /s /c $devCmdLine
if ($LASTEXITCODE -ne 0) {
    throw "VsDevCmd failed with exit code $LASTEXITCODE."
}

foreach ($line in $devEnvironment) {
    if ($line -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
    }
}

$pathClangCl = Get-Command clang-cl -ErrorAction SilentlyContinue
$clangClCandidates = @(
    (Join-Path $vsPath 'VC/Tools/Llvm/x64/bin/clang-cl.exe'),
    'C:/Program Files/LLVM/bin/clang-cl.exe'
)
if ($pathClangCl) {
    $clangClCandidates += $pathClangCl.Source
}
$clangCl = Find-ExistingTool -DisplayName 'clang-cl.exe' -Candidates $clangClCandidates
$profdata = Find-ExistingTool -DisplayName 'the matching llvm-profdata.exe' `
    -Candidates @((Join-Path (Split-Path -Parent $clangCl) 'llvm-profdata.exe'))

$pathCmake = Get-Command cmake -ErrorAction SilentlyContinue
$cmakeCandidates = @((Join-Path $vsPath 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'))
if ($pathCmake) {
    $cmakeCandidates = @($pathCmake.Source) + $cmakeCandidates
}
$cmake = Find-ExistingTool -DisplayName 'cmake.exe' -Candidates $cmakeCandidates

$pathNinja = Get-Command ninja -ErrorAction SilentlyContinue
$ninjaCandidates = @((Join-Path $vsPath 'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe'))
if ($pathNinja) {
    $ninjaCandidates = @($pathNinja.Source) + $ninjaCandidates
}
$ninja = Find-ExistingTool -DisplayName 'ninja.exe' -Candidates $ninjaCandidates
$clangClCmake = $clangCl.Replace('\', '/')
$ninjaCmake = $ninja.Replace('\', '/')
$network = Join-Path $repoRoot 'src/pikafish.nnue'
$networkUrl = 'https://github.com/official-pikafish/Networks/releases/download/master-net/pikafish.nnue'
$expectedNetworkSha256 = '3cd15292bf8c979884262f57fc723959fc0dea43b4d8d544f88db5ceb2479e24'

if (-not (Test-Path -LiteralPath $network)) {
    Write-Host "Downloading NNUE network from $networkUrl"
    Invoke-WebRequest -Uri $networkUrl -OutFile $network -UseBasicParsing
}
if ((Get-Item -LiteralPath $network).Length -lt 1MB) {
    throw "The downloaded NNUE network is unexpectedly small: $network"
}
$networkHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $network).Hash.ToLowerInvariant()
if ($networkHash -ne $expectedNetworkSha256) {
    throw "NNUE checksum mismatch. Expected $expectedNetworkSha256 but received $networkHash"
}

$generateDir = Join-Path $buildRoot 'generate'
$useDir = Join-Path $buildRoot 'use'
$profileDir = Join-Path $buildRoot 'profiles'
$artifactRoot = Join-Path $repoRoot 'artifacts'
$packageName = 'xfish-windows-x64-avx2-pgo'
$packageDir = Join-Path $artifactRoot $packageName
$zipPath = Join-Path $artifactRoot "$packageName.zip"

New-Item -ItemType Directory -Force -Path $generateDir, $useDir, $profileDir, $artifactRoot | Out-Null

function Invoke-Checked {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,

        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    Write-Host "> $FilePath $($Arguments -join ' ')"
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE."
    }
}

function Configure-Xfish {
    param(
        [Parameter(Mandatory)]
        [string]$OutputDirectory,

        [Parameter(Mandatory)]
        [ValidateSet('GENERATE', 'USE')]
        [string]$PgoStage,

        [string]$Profile = ''
    )

    $arguments = @(
        '-S', $repoRoot,
        '-B', $OutputDirectory,
        '-G', 'Ninja',
        '-DCMAKE_BUILD_TYPE=Release',
        "-DCMAKE_MAKE_PROGRAM=$ninjaCmake",
        "-DCMAKE_CXX_COMPILER=$clangClCmake",
        "-DXFISH_ARCH=$Architecture",
        "-DXFISH_PGO=$PgoStage",
        '-DXFISH_LTO=ON'
    )
    if ($Profile) {
        $arguments += "-DXFISH_PGO_PROFILE=$($Profile.Replace('\', '/'))"
    }
    Invoke-Checked -FilePath $cmake -Arguments $arguments
}

Write-Host '=== Stage 1/4: instrumented clang-cl AVX2 build ==='
Configure-Xfish -OutputDirectory $generateDir -PgoStage GENERATE
Invoke-Checked -FilePath $cmake -Arguments @('--build', $generateDir, '--parallel', "$Jobs")

$instrumentedExe = Join-Path $generateDir 'bin/xfish.exe'
if (-not (Test-Path -LiteralPath $instrumentedExe)) {
    throw "Instrumented executable was not produced: $instrumentedExe"
}

Write-Host '=== Stage 2/4: collect profile with the built-in benchmark ==='
Get-ChildItem -LiteralPath $profileDir -Filter '*.profraw' -File -ErrorAction SilentlyContinue |
    Remove-Item -Force
$oldProfileFile = $env:LLVM_PROFILE_FILE
$env:LLVM_PROFILE_FILE = Join-Path $profileDir 'xfish-%p.profraw'
try {
    $benchmarkStdout = Join-Path $buildRoot 'benchmark-pgo.stdout.txt'
    $benchmarkStderr = Join-Path $buildRoot 'benchmark-pgo.stderr.txt'
    $benchmark = Start-Process -FilePath $instrumentedExe -ArgumentList 'bench' `
        -WorkingDirectory (Join-Path $repoRoot 'src') -NoNewWindow -PassThru -Wait `
        -RedirectStandardOutput $benchmarkStdout -RedirectStandardError $benchmarkStderr
    Get-Content -LiteralPath $benchmarkStdout, $benchmarkStderr |
        Set-Content -LiteralPath (Join-Path $buildRoot 'benchmark-pgo.txt')
    Get-Content -LiteralPath $benchmarkStdout, $benchmarkStderr | Select-Object -Last 12
    if ($benchmark.ExitCode -ne 0) {
        throw "The PGO benchmark failed with exit code $($benchmark.ExitCode)."
    }
}
finally {
    $env:LLVM_PROFILE_FILE = $oldProfileFile
}

$rawProfiles = @(Get-ChildItem -LiteralPath $profileDir -Filter '*.profraw' -File)
if ($rawProfiles.Count -eq 0) {
    throw "No .profraw files were generated in $profileDir"
}

$mergedProfile = Join-Path $profileDir 'xfish.profdata'
$mergeArguments = @('merge', '-output', $mergedProfile) + @($rawProfiles.FullName)
Invoke-Checked -FilePath $profdata -Arguments $mergeArguments

Write-Host '=== Stage 3/4: optimized clang-cl AVX2 PGO build ==='
Configure-Xfish -OutputDirectory $useDir -PgoStage USE -Profile $mergedProfile
Invoke-Checked -FilePath $cmake -Arguments @('--build', $useDir, '--parallel', "$Jobs")

$finalExe = Join-Path $useDir 'bin/xfish.exe'
if (-not (Test-Path -LiteralPath $finalExe)) {
    throw "Final executable was not produced: $finalExe"
}

Write-Host '=== Stage 4/4: smoke test and package ==='
$smokeInput = Join-Path $buildRoot 'smoke-test.stdin.txt'
$smokeStdout = Join-Path $buildRoot 'smoke-test.stdout.txt'
$smokeStderr = Join-Path $buildRoot 'smoke-test.stderr.txt'
"uci`nquit" | Set-Content -LiteralPath $smokeInput -Encoding ascii
$smoke = Start-Process -FilePath $finalExe -WorkingDirectory (Join-Path $repoRoot 'src') `
    -NoNewWindow -PassThru -Wait -RedirectStandardInput $smokeInput `
    -RedirectStandardOutput $smokeStdout -RedirectStandardError $smokeStderr
Get-Content -LiteralPath $smokeStdout, $smokeStderr |
    Set-Content -LiteralPath (Join-Path $buildRoot 'smoke-test.txt')
Get-Content -LiteralPath $smokeStdout, $smokeStderr
if ($smoke.ExitCode -ne 0) {
    throw "The final smoke test failed with exit code $($smoke.ExitCode)."
}
if (-not (Select-String -LiteralPath $smokeStdout -Pattern '^uciok$' -Quiet)) {
    throw 'The final smoke test did not receive the UCI ready marker.'
}

$finalBenchmarkStdout = Join-Path $buildRoot 'benchmark-final.stdout.txt'
$finalBenchmarkStderr = Join-Path $buildRoot 'benchmark-final.stderr.txt'
$finalBenchmark = Start-Process -FilePath $finalExe -ArgumentList 'bench' `
    -WorkingDirectory (Join-Path $repoRoot 'src') -NoNewWindow -PassThru -Wait `
    -RedirectStandardOutput $finalBenchmarkStdout -RedirectStandardError $finalBenchmarkStderr
Get-Content -LiteralPath $finalBenchmarkStdout, $finalBenchmarkStderr |
    Set-Content -LiteralPath (Join-Path $buildRoot 'benchmark-final.txt')
$benchmarkSummary = @(Get-Content -LiteralPath $finalBenchmarkStdout, $finalBenchmarkStderr |
    Select-String -Pattern '^(Total time|Nodes searched|Nodes/second)')
$benchmarkSummary
if ($finalBenchmark.ExitCode -ne 0) {
    throw "The final benchmark failed with exit code $($finalBenchmark.ExitCode)."
}

if (Test-Path -LiteralPath $packageDir) {
    Remove-Item -LiteralPath $packageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
Copy-Item -LiteralPath $finalExe -Destination $packageDir
Copy-Item -LiteralPath $network -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $repoRoot 'AUTHORS') -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $repoRoot 'Copying.txt') -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $repoRoot 'README.md') -Destination $packageDir

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $packageDir 'xfish.exe')
"$($hash.Hash.ToLowerInvariant())  xfish.exe" |
    Set-Content -LiteralPath (Join-Path $packageDir 'xfish.exe.sha256') -Encoding ascii

$compilerVersion = (& $clangCl --version | Select-Object -First 1)
$sourceCommit = (& git -C $repoRoot rev-parse HEAD).Trim()
@(
    'xfish Windows x64 AVX2 baseline'
    "Source: https://github.com/mualanhlung017/xfish/tree/$sourceCommit"
    "Commit: $sourceCommit"
    "Compiler: $compilerVersion"
    'ABI/runtime: MSVC x64 ABI, static MSVC runtime'
    'Optimization: AVX2, LLVM LTO, LLVM PGO trained with the built-in benchmark'
    "NNUE SHA256: $networkHash"
    "Executable SHA256: $($hash.Hash.ToLowerInvariant())"
    ''
    'Benchmark on the build host (results are machine-dependent):'
) + @($benchmarkSummary.Line) |
    Set-Content -LiteralPath (Join-Path $packageDir 'BUILD_INFO.txt') -Encoding ascii

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $packageDir '*') -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host ''
Write-Host "Build complete: $zipPath"
Write-Host "Compiler      : $compilerVersion"
Write-Host "Architecture  : x86-64-avx2"
Write-Host "PGO profile   : $mergedProfile"
Write-Host "Executable SHA: $($hash.Hash.ToLowerInvariant())"
