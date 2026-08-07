#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 BASELINE CANDIDATE [OUTPUT_DIR] [RUNS] [NODES]" >&2
    exit 2
}

[[ $# -ge 2 && $# -le 5 ]] || usage

baseline=$(readlink -f "$1")
candidate=$(readlink -f "$2")
output_dir=${3:-"benchmarks/results/linux-$(date -u +%Y%m%d-%H%M%S)"}
runs=${4:-9}
nodes=${5:-1000000}
warmups=${WARMUPS:-2}
hash_mb=${HASH_MB:-128}
threads=${THREADS:-4}
signature_depth=${SIGNATURE_DEPTH:-13}
cpu_list=${CPU_LIST:-120-123}
working_directory=${WORKING_DIRECTORY:-src}

[[ -x "$baseline" ]] || { echo "baseline is not executable: $baseline" >&2; exit 2; }
[[ -x "$candidate" ]] || { echo "candidate is not executable: $candidate" >&2; exit 2; }
[[ "$runs" =~ ^[0-9]+$ && "$runs" -ge 3 ]] || usage
[[ "$nodes" =~ ^[0-9]+$ && "$nodes" -ge 1000 ]] || usage

mkdir -p "$output_dir/logs"
csv="$output_dir/benchmark.csv"
printf '%s\n' 'timestamp_utc,platform,kind,pair,sequence,label,engine,sha256,threads,target,limit_type,time_ms,nodes,nps,cpu_list,log' > "$csv"

baseline_sha=$(sha256sum "$baseline" | awk '{print $1}')
candidate_sha=$(sha256sum "$candidate" | awk '{print $1}')

run_bench() {
    local engine=$1 label=$2 kind=$3 pair=$4 sequence=$5 bench_threads=$6 target=$7 limit_type=$8
    local log_name log_path exit_code elapsed searched nps sha
    printf -v log_name '%s-%02d-%02d-%s.log' "$kind" "$pair" "$sequence" "$label"
    log_path="$output_dir/logs/$log_name"
    set +e
    (
        cd "$working_directory"
        taskset -c "$cpu_list" "$engine" bench "$hash_mb" "$bench_threads" "$target" default "$limit_type"
    ) > "$log_path" 2>&1
    exit_code=$?
    set -e
    [[ $exit_code -eq 0 ]] || { echo "$label benchmark failed ($exit_code): $log_path" >&2; exit "$exit_code"; }

    elapsed=$(awk -F: '/^Total time \(ms\)/ {gsub(/[[:space:]]/, "", $2); value=$2} END {print value}' "$log_path")
    searched=$(awk -F: '/^Nodes searched/ {gsub(/[[:space:]]/, "", $2); value=$2} END {print value}' "$log_path")
    nps=$(awk -F: '/^Nodes\/second/ {gsub(/[[:space:]]/, "", $2); value=$2} END {print value}' "$log_path")
    [[ -n "$elapsed" && -n "$searched" && -n "$nps" ]] || { echo "cannot parse $log_path" >&2; exit 2; }
    if [[ $label == baseline ]]; then sha=$baseline_sha; else sha=$candidate_sha; fi
    printf '%s,%s,%s,%d,%d,%s,%s,%s,%d,%d,%s,%s,%s,%s,%s,%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" linux "$kind" "$pair" "$sequence" "$label" \
        "$engine" "$sha" "$bench_threads" "$target" "$limit_type" "$elapsed" "$searched" \
        "$nps" "$cpu_list" "$log_name" >> "$csv"
    printf 'pair %02d %-9s %12d NPS\n' "$pair" "$label" "$nps"
}

echo '=== Correctness signatures ==='
run_bench "$baseline" baseline signature 0 1 1 "$signature_depth" depth
run_bench "$candidate" candidate signature 0 2 1 "$signature_depth" depth
baseline_signature=$(awk -F, '$3 == "signature" && $6 == "baseline" {print $13}' "$csv")
candidate_signature=$(awk -F, '$3 == "signature" && $6 == "candidate" {print $13}' "$csv")
[[ "$baseline_signature" == "$candidate_signature" ]] || {
    echo "correctness signature mismatch: baseline=$baseline_signature candidate=$candidate_signature" >&2
    exit 1
}

echo "=== Warmups ($warmups per engine) ==="
for ((warmup = 1; warmup <= warmups; ++warmup)); do
    run_bench "$baseline" baseline warmup "$warmup" 1 "$threads" "$nodes" nodes
    run_bench "$candidate" candidate warmup "$warmup" 2 "$threads" "$nodes" nodes
done

echo "=== Measured alternating A/B pairs ($runs) ==="
for ((pair = 1; pair <= runs; ++pair)); do
    if ((pair % 2)); then
        run_bench "$baseline" baseline performance "$pair" 1 "$threads" "$nodes" nodes
        run_bench "$candidate" candidate performance "$pair" 2 "$threads" "$nodes" nodes
    else
        run_bench "$candidate" candidate performance "$pair" 1 "$threads" "$nodes" nodes
        run_bench "$baseline" baseline performance "$pair" 2 "$threads" "$nodes" nodes
    fi
done

cat > "$output_dir/metadata.json" <<EOF
{
  "generated_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "baseline": "$baseline",
  "candidate": "$candidate",
  "runs": $runs,
  "warmups": $warmups,
  "hash_mb": $hash_mb,
  "threads": $threads,
  "nodes": $nodes,
  "signature_depth": $signature_depth,
  "cpu_list": "$cpu_list"
}
EOF

echo "CSV: $csv"
if command -v python3 >/dev/null 2>&1; then
    python3 "$(dirname "$0")/analyze-ab.py" "$csv" --json "$output_dir/summary.json"
fi
