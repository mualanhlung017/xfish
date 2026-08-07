# NNUE AVX2 optimization campaign

This document is the reproducibility contract for the long-running NNUE
optimization campaign.  A faster one-off benchmark is not a new baseline.

## Frozen baseline

- Source: `d5b4860dcddb43bded8aa3804ea53eadb60efa2e`
- Release: `v0.1.0-baseline`
- Windows: clang-cl, AVX2, profile-guided optimization, ThinLTO
- Linux: Clang 22, `ARCH=x86-64-avx2`, profile-guided optimization, Full LTO
- Linux execution: four threads pinned to CPUs `120-123`
- Linux fixed-node reference median: 3,058,906 NPS (five runs; retained only as
  an orientation value because promotion uses a direct interleaved A/B test)

## Measurement and promotion gate

Every candidate is built from a clean tree with AVX2, PGO and LTO.  Its PGO
training command and network must be identical to the current baseline.  The
old and new binaries are retained so that they can run back-to-back on the
same machine and under the same load conditions.

1. Run a one-thread depth-13 benchmark and require identical total searched
   nodes.  A mismatch is a correctness failure, not a performance result.
2. Warm both executables twice.
3. Run at least nine fixed-node pairs, alternating order `AB`, `BA`, `AB`, ...
   to cancel temperature, background-load and clock drift.
4. Use the median of the paired `candidate NPS / baseline NPS` ratios on each
   platform.  Report raw medians, coefficient of variation and a deterministic
   bootstrap 95% confidence interval as diagnostics.
5. Promote only when the geometric mean of the Windows and Linux paired
   medians is at least `+1.00%`, neither platform is below `-0.30%`, the lower
   bootstrap bound on neither platform is below `-0.30%`, and signatures match.
6. A promoted change receives one focused commit, a new immutable baseline
   tag/release, both platform assets, logs, CSV summaries, compiler details,
   hashes and exact build commands.  Failed candidates are reverted and logged.

The default confirmation workload is `bench 128 T 1000000 default nodes`, with
`T=1` on the pinned Windows logical CPU and `T=4` on Linux CPUs `120-123`.
Shorter tests may reject an obviously bad idea, but cannot promote it.

## FFmpeg technique map

Reference tree: official `FFmpeg/FFmpeg`, pinned during research at
`5c395992f99feb47860e4cc99a0cea2009457870`.

The useful libavcodec/libavutil x86 patterns are treated as design techniques,
not copied implementations:

- split long-latency arithmetic into independent accumulator chains;
- unroll around load/use latency while respecting the 16 architectural YMM
  registers available in AVX2 mode;
- keep inner-loop loads contiguous, aligned where the data contract permits,
  and avoid redundant address generation;
- arrange packed data once at load time to avoid repeated lane-crossing
  shuffles in hot kernels;
- delay horizontal reductions until the end and reduce 256-bit lanes with the
  smallest dependency tree;
- combine saturation, packing and zero detection rather than materializing
  temporary buffers;
- specialize kernels for common fixed widths instead of adding runtime
  branches inside the inner loop;
- use checkasm-style correctness checks and many-cycle benchmarks for every
  SIMD specialization.

## Candidate queue

Each item is deliberately small so its effect can be measured and reverted.

| ID | Area | Candidate | State |
|---|---|---|---|
| H00 | Harness | Interleaved cross-platform A/B runner and statistics | active |
| P00 | Profile | Linux cycle profile plus PGO hot-function inventory | queued |
| P01 | Profile | Windows sampled profile/disassembly inventory | queued |
| A01 | Accumulator | Tune AVX2 register tiling (8/12/16 YMM trade-off) | queued |
| A02 | Accumulator | Pair common add/sub feature cases into one pass | queued |
| A03 | Accumulator | Reduce address generation and hoist column bases | queued |
| A04 | Accumulator | Re-evaluate threat-weight prefetch distance | queued |
| F01 | Transformer | Fuse clamp/shift/pack/nonzero-mask work | queued |
| F02 | Transformer | Remove avoidable lane permutations via stored layout | queued |
| F03 | Transformer | Specialize the 1024-wide AVX2 transform loop | queued |
| S01 | Sparse FC | Split non-VNNI AVX2 dot products into two chains | queued |
| S02 | Sparse FC | Unroll sparse columns in pairs with a scalar tail | queued |
| S03 | Sparse FC | Tune bitset scan and weight-pointer arithmetic | queued |
| D01 | Dense FC | Schedule broadcasts/loads around `vpmaddubsw` latency | queued |
| D02 | Dense FC | Tune fixed 64/128 input kernels and reduction tree | queued |
| R01 | Activation | Fuse paired square/clipped ReLU stores | queued |
| R02 | Reduction | Compare horizontal-sum dependency trees in final FC | queued |
| M01 | Memory | Validate alignment annotations and selective prefetch | queued |
| M02 | Memory | Check cache-line placement of per-evaluation buffers | queued |

The queue is reordered after each profile.  A campaign reaches saturation only
after every profile-visible NNUE hotspot has either passed the gate or has at
least two well-powered failed variants recorded.

## Commands

Windows confirmation:

```powershell
scripts/benchmark-ab.ps1 -Baseline BASE.exe -Candidate CANDIDATE.exe `
  -Runs 9 -Warmups 2 -Threads 1 -Nodes 1000000 -Cpu 2
```

Linux confirmation:

```bash
CPU_LIST=120-123 THREADS=4 WARMUPS=2 \
  scripts/benchmark-ab.sh BASE CANDIDATE RESULTS 9 1000000
```

Combined decision:

```bash
python3 scripts/analyze-ab.py WINDOWS/benchmark.csv LINUX/benchmark.csv \
  --json combined-summary.json
```
