[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Baseline,

    [Parameter(Mandatory)]
    [string]$Candidate,

    [string]$OutputDirectory = '',

    [ValidateRange(3, 99)]
    [int]$Runs = 9,

    [ValidateRange(0, 20)]
    [int]$Warmups = 2,

    [ValidateRange(1, 65536)]
    [int]$Hash = 128,

    [ValidateRange(1, 256)]
    [int]$Threads = 1,

    [ValidateRange(1000, 2000000000)]
    [int]$Nodes = 1000000,

    [ValidateRange(1, 100)]
    [int]$SignatureDepth = 13,

    [ValidateRange(0, 63)]
    [int[]]$Cpu = @(2)
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workingDirectory = Join-Path $repoRoot 'src'
$baselinePath = (Resolve-Path -LiteralPath $Baseline).Path
$candidatePath = (Resolve-Path -LiteralPath $Candidate).Path

if ($Cpu.Count -lt $Threads) {
    throw "Cpu must contain at least Threads entries ($Threads)."
}

$affinity = [UInt64]0
foreach ($cpuIndex in $Cpu) {
    $affinity = $affinity -bor ([UInt64]1 -shl $cpuIndex)
}

if (-not $OutputDirectory) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $OutputDirectory = Join-Path $repoRoot "benchmarks/results/windows-$stamp"
}
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
$logRoot = Join-Path $outputRoot 'logs'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

function Invoke-XfishBench {
    param(
        [Parameter(Mandatory)] [string]$Engine,
        [Parameter(Mandatory)] [string]$Label,
        [Parameter(Mandatory)] [string]$Kind,
        [Parameter(Mandatory)] [int]$Pair,
        [Parameter(Mandatory)] [int]$Sequence,
        [Parameter(Mandatory)] [string[]]$BenchArguments
    )

    $logName = '{0}-{1:D2}-{2:D2}-{3}.log' -f $Kind, $Pair, $Sequence, $Label
    $stdoutPath = Join-Path $logRoot "$logName.stdout"
    $stderrPath = Join-Path $logRoot "$logName.stderr"
    $process = Start-Process -FilePath $Engine -ArgumentList $BenchArguments `
        -WorkingDirectory $workingDirectory -NoNewWindow -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    # PowerShell can discard the native process handle unless it is materialized
    # before WaitForExit(), leaving ExitCode empty on Windows PowerShell 5.1.
    $null = $process.Handle
    try {
        $process.ProcessorAffinity = [IntPtr]::new([Int64]$affinity)
    }
    catch {
        if (-not $process.HasExited) { $process.Kill() }
        throw "Unable to set CPU affinity/priority for PID $($process.Id): $_"
    }
    $process.WaitForExit()
    $stdout = Get-Content -Raw -LiteralPath $stdoutPath
    $stderr = Get-Content -Raw -LiteralPath $stderrPath
    $combined = "$stdout`n$stderr"
    Set-Content -LiteralPath (Join-Path $logRoot $logName) -Value $combined -Encoding utf8
    if ($process.ExitCode -ne 0) {
        throw "$Label benchmark failed with exit code $($process.ExitCode); see $logName"
    }

    $timeMatch = [regex]::Match($combined, '(?m)^Total time \(ms\)\s*:\s*(\d+)\s*$')
    $nodesMatch = [regex]::Match($combined, '(?m)^Nodes searched\s*:\s*(\d+)\s*$')
    $npsMatch = [regex]::Match($combined, '(?m)^Nodes/second\s*:\s*(\d+)\s*$')
    if (-not ($timeMatch.Success -and $nodesMatch.Success -and $npsMatch.Success)) {
        throw "Unable to parse benchmark totals from $logName"
    }

    [pscustomobject]@{
        timestamp_utc = [DateTime]::UtcNow.ToString('o')
        platform      = 'windows'
        kind          = $Kind
        pair          = $Pair
        sequence      = $Sequence
        label         = $Label
        engine        = $Engine
        sha256        = (Get-FileHash -Algorithm SHA256 -LiteralPath $Engine).Hash.ToLowerInvariant()
        threads       = $BenchArguments[2]
        target        = $BenchArguments[3]
        limit_type    = $BenchArguments[5]
        time_ms       = [Int64]$timeMatch.Groups[1].Value
        nodes         = [Int64]$nodesMatch.Groups[1].Value
        nps           = [Int64]$npsMatch.Groups[1].Value
        cpu_list      = ($Cpu -join ',')
        log           = $logName
    }
}

$records = [Collections.Generic.List[object]]::new()
$signatureArguments = @('bench', "$Hash", '1', "$SignatureDepth", 'default', 'depth')
Write-Host '=== Correctness signatures ==='
$records.Add((Invoke-XfishBench -Engine $baselinePath -Label baseline -Kind signature `
    -Pair 0 -Sequence 1 -BenchArguments $signatureArguments))
$records.Add((Invoke-XfishBench -Engine $candidatePath -Label candidate -Kind signature `
    -Pair 0 -Sequence 2 -BenchArguments $signatureArguments))
if ($records[0].nodes -ne $records[1].nodes) {
    throw "Correctness signature mismatch: baseline=$($records[0].nodes), candidate=$($records[1].nodes)"
}

$performanceArguments = @('bench', "$Hash", "$Threads", "$Nodes", 'default', 'nodes')
Write-Host "=== Warmups ($Warmups per engine) ==="
for ($warmup = 1; $warmup -le $Warmups; ++$warmup) {
    $records.Add((Invoke-XfishBench -Engine $baselinePath -Label baseline -Kind warmup `
        -Pair $warmup -Sequence 1 -BenchArguments $performanceArguments))
    $records.Add((Invoke-XfishBench -Engine $candidatePath -Label candidate -Kind warmup `
        -Pair $warmup -Sequence 2 -BenchArguments $performanceArguments))
}

Write-Host "=== Measured alternating A/B pairs ($Runs) ==="
for ($pair = 1; $pair -le $Runs; ++$pair) {
    $order = if ($pair % 2) { @('baseline', 'candidate') } else { @('candidate', 'baseline') }
    for ($sequence = 0; $sequence -lt $order.Count; ++$sequence) {
        $label = $order[$sequence]
        $engine = if ($label -eq 'baseline') { $baselinePath } else { $candidatePath }
        $record = Invoke-XfishBench -Engine $engine -Label $label -Kind performance `
            -Pair $pair -Sequence ($sequence + 1) -BenchArguments $performanceArguments
        $records.Add($record)
        Write-Host ('pair {0:D2} {1,-9} {2,12:N0} NPS' -f $pair, $label, $record.nps)
    }
}

$csvPath = Join-Path $outputRoot 'benchmark.csv'
$records | Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath $csvPath
$metadata = [ordered]@{
    generated_utc   = [DateTime]::UtcNow.ToString('o')
    baseline        = $baselinePath
    candidate       = $candidatePath
    runs            = $Runs
    warmups         = $Warmups
    hash_mb         = $Hash
    threads         = $Threads
    nodes           = $Nodes
    signature_depth = $SignatureDepth
    cpu_list        = $Cpu
}
$metadata | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $outputRoot 'metadata.json')
Write-Host "CSV: $csvPath"

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    & $python.Source (Join-Path $PSScriptRoot 'analyze-ab.py') $csvPath `
        --json (Join-Path $outputRoot 'summary.json')
}
