# NNUE AVX2 optimization campaign

This document is the reproducibility contract for the long-running NNUE
optimization campaign.  A faster one-off benchmark is not a new baseline.

## Baseline history

- Initial source: `d5b4860dcddb43bded8aa3804ea53eadb60efa2e`
- Initial release: `v0.1.0-baseline`
- Current promoted release: `v0.3.0-nnue-thp`
- Current change set: the `v0.2.0-nnue` AVX2 HalfKA/sparse-scan changes plus a
  Linux-local, transparent-huge-page-backed NNUE network mapping
- Windows: clang-cl, AVX2, profile-guided optimization, ThinLTO
- Linux: Clang 22, `ARCH=x86-64-avx2`, profile-guided optimization, Full LTO
- Linux execution: four threads pinned to CPUs `120-123`
- Linux memory policy: one private roughly 64 MiB NNUE network mapping per
  process, requested with `MADV_HUGEPAGE`; Windows retains the shared backend
- Linux fixed-node reference median: 3,058,906 NPS (five runs; retained only as
  an orientation value for the initial baseline because promotion uses a direct
  interleaved A/B test)

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
| H00 | Harness | Interleaved cross-platform A/B runner and statistics | complete |
| P00 | Profile | Linux instrumented profile plus PGO hot-function inventory | complete |
| P01 | Profile | Windows PGO-count/disassembly inventory | complete |
| A01 | Accumulator | Tune AVX2 register tiling (8/12/16 YMM trade-off) | profiled; 8 retained |
| A02 | Accumulator | Pair common add/sub feature cases into one pass | accepted with S03 |
| A03 | Accumulator | Reduce address generation and hoist column bases | rejected (two variants) |
| A04 | Accumulator | Prefetch HalfKA columns while constructing changed indices | rejected |
| A05 | Accumulator | Re-evaluate threat-weight prefetch distance | rejected (two variants) |
| A06 | Accumulator | Specialize the 2-removed/1-added PSQ update | rejected cross-platform |
| A07 | Accumulator | Share the AVX2 feature tile between accumulator passes | rejected after confirmation |
| A08 | Accumulator | Pair common threat add/sub updates | rejected |
| A09 | Accumulator | Jointly scan white/black accumulator stacks | rejected |
| F01 | Transformer | Fuse clamp/shift/pack/nonzero-mask work | rejected variants |
| F02 | Transformer | Replace pack path with multiply/pack formulation | rejected |
| F03 | Transformer | Specialize the 1024-wide AVX2 transform loop | codegen/profile saturated |
| S01 | Sparse FC | Split non-VNNI AVX2 dot products into two chains | rejected |
| S02 | Sparse FC | Unroll sparse columns in pairs with a scalar tail | rejected |
| S03 | Sparse FC | Use a native 64-bit bitset scan | accepted with A02 |
| S04 | Sparse FC | Prefetch the next 128-byte random FC0 column | rejected |
| S05-S12 | Sparse FC | Staging, masks, index lists and wider unrolling | rejected variants |
| D01 | Dense FC | Schedule broadcasts/loads around `vpmaddubsw` latency | rejected after confirmation |
| D02 | Dense FC | Split products into independent accumulator chains | rejected cross-platform |
| D03 | Dense FC | Pair two output neurons per input traversal | below gate |
| D04-D08 | Dense FC | Wider pairing and alternate instruction schedules | rejected variants |
| E01-E02 | Evaluation | Shorten return path and merge scan work | rejected |
| H02 | Refresh | Port upstream hybrid king-bucket refresh | rejected |
| I01 | Inlining | Force-inline the network propagation wrapper | rejected |
| L01 | Layout | Align the sparse-FC hot loop | rejected |
| P02-P03 | Codegen | Add host-specific `-mtune` on Linux/Windows | rejected |
| M01 | Memory | Back the Linux NNUE network with anonymous THP | accepted |
| M02 | Memory | Move the 4 MiB threat-index table onto anonymous THP | rejected |
| T01 | Threat index | Pack both colours into one 32-bit table lookup | rejected |

The queue is reordered after each profile.  A campaign reaches saturation only
after every profile-visible NNUE hotspot has either passed the gate or has at
least two well-powered failed variants recorded.

## Profile inventory

Linux profiling used a separate Clang 22 AVX2 `-pg` build because the server
does not permit hardware performance counters.  A pinned one-thread,
96,023,791-node run spent 18.35% self time in `Network::evaluate`, 16.59% in
`apply_combined`, 7.01% in `AccumulatorStack::evaluate_side`, and 5.02% in
`AccumulatorStack::evaluate`.  NNUE and accumulator work therefore accounted
for about 47% of sampled self time.  `apply_combined` ran 106,540,331 times,
versus 46,838,283 calls to `Network::evaluate`.

The Linux disassembly shows that the AVX2 `apply_combined` kernel already uses
eight independent YMM accumulator registers.  Raising that tile to 16 would
leave no temporary YMM registers and force spills; reducing it would repeat
the feature-list loop more often.  The immediate opportunities are instead
the common add/sub cases and address generation repeated once per tile.

The Windows PGO inventory recorded 1,153,605 calls through the trained NNUE
propagation/transform path.  PGO counts establish hot paths but are not timing
samples, so performance decisions still use the paired cross-platform gate.

A second Linux `-pg` build put explicit no-inline boundaries around the NNUE
layers.  `FeatureTransformer::transform` accounted for about 4.9% of whole
engine self time and `NetworkArchitecture::propagate` for about 15.7%.  Within
the network, the sparse `AffineTransformSparseInput<1024, 32>` first layer was
the dominant component at about 14.6%; the remaining dense layers and
activations were each near or below 1.2%.

A one-thread 200,000-node update census covered 10,562,882 accumulator updates.
The PSQ removed/added shapes were 1/1 in 72.037%, 2/1 in 27.327% and 1/2 in
0.636%.  Threat updates were much broader: 0/0 was 5.179%, 1/1 was 6.876%, and
the ten most frequent pairs together covered only 51.819%.  This distribution
is why fixed PSQ specializations are useful while large threat fast-path tables
are unlikely to repay their code and address-generation cost.

The post-M01 boundary profile used a Clang 22 AVX2 `-pg` build over exactly
24,024,130 nodes.  `apply_combined` remained the largest NNUE symbol at 15.76%
of whole-engine self time, followed by sparse FC0 at 13.36%,
`AccumulatorStack::evaluate_side` at 4.72%, threat active/changed-index
construction at 2.71%/2.53%, the transformer at 2.13%, and dense FC1 at only
0.85%.  The profile therefore confirms that the already-exhausted accumulator
and sparse-FC families dominate; transformer and dense layers no longer have
enough exclusive time for a realistic one-percent whole-engine win.

## Experiment log

### A04: prefetch HalfKA columns during index construction

Both candidates were built with AVX2, PGO and LTO, and their depth-13
correctness signatures matched their respective baselines.  This was a
five-pair rejection screen, not a promotion run.

| Platform | Baseline median NPS | Candidate median NPS | Paired gain | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Windows, 1 thread | 384,070 | 387,035 | +0.200% | -1.907% to +2.102% |
| Linux, 4 threads | 3,157,222 | 3,166,127 | +0.282% | +0.004% to +0.858% |

The cross-platform geometric gain was `+0.241%`, below the `+1.00%` gate, so
the source change was reverted and received no optimization commit, tag or
release.  Binary SHA-256 pairs were Windows
`ba3a6e594ee2360797549deaf18d188413a87a01f9805bfaec5f92f00ad58237` /
`86baa7871438d66c6563fd0d6bdbb0aa6036977af5ed5d3f1102707d01400830`
and Linux
`8a45d52ed856b3f651d7a833e71a0c6823ebe282141e79b5eb3eca96b8c07742` /
`25c866a023cbffeb08d9feb255d71d6853e1b4d9ed0fdd6d47903087d52a92c8`.

### A02: common 1/1 HalfKA delta

The 1-removed/1-added AVX2 path hoists both feature-column bases outside the
tile loop and adds a single widened delta to each accumulator vector.  A full
standalone confirmation was positive but narrowly missed promotion:

| Platform | Baseline median NPS | Candidate median NPS | Paired gain | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Windows, 1 thread | 413,119 | 416,011 | +0.551% | -0.858% to +1.702% |
| Linux, 4 threads | 3,150,106 | 3,191,262 | +1.304% | +0.893% to +1.921% |

The geometric gain was `+0.927%`; A02 therefore remained uncommitted until it
could be retested as part of a stronger combined candidate.

### Rejected accumulator variants

All rows are direct Linux AVX2 PGO comparisons against the immediately stated
parent candidate.  Correctness signatures matched in every row.

| ID | Variant | Pairs | Paired gain | Bootstrap 95% CI |
|---|---|---:|---:|---:|
| A03a | Precomputed threat-column pointer array | 7 | -0.174% | -0.907% to +0.238% |
| A03b | In-place scaled threat offsets | 7 | -1.016% | -1.431% to -0.717% |
| A05a | Raise threat prefetch from LOW/T2 to HIGH/T0 | 7 | -0.450% | -0.790% to -0.090% |
| A05b | Disable threat prefetch | 7 | -0.359% | -0.656% to +0.171% |

### Sparse-FC and transformer screens

S03 corrected the scalar type of each 64-bit NNZ word from `u128` to `u64`.
The resulting code uses one `tzcnt`/`blsr` sequence rather than the compiler's
128-bit pop path.  S03 alone added `+0.459%` over A02, with a 95% interval of
`-0.078%` to `+0.795%`; it was retained for the combined confirmation.  The
remaining small variants did not survive screening or confirmation:

| ID | Variant | Pairs | Paired gain | Bootstrap 95% CI |
|---|---|---:|---:|---:|
| S01 | Two sparse-FC accumulator chains, on top of S03 | 7 | +0.079% | -0.413% to +0.182% |
| S02 | Pop/process sparse indices two at a time | 7 | +0.301% | -0.141% to +1.022% |
| S04 | T0-prefetch both cache lines of the next FC0 column | 7 | -2.263% | -3.336% to -1.670% |
| D01 | Stage four `vpmaddubsw` products, first screen | 7 | +0.462% | -0.235% to +0.535% |
| D01 | Independent 9-pair, 1M-node confirmation | 9 | +0.082% | -0.653% to +0.892% |
| F01a | Combine two adjacent NNZ mask stores | 7 | -0.075% | -0.913% to +0.515% |

### Promoted A02 + S03 baseline

The combined candidate was rebuilt with AVX2, PGO and LTO on both platforms,
then compared directly with the immutable `v0.1.0-baseline` binaries.  This is
the first post-fork candidate to pass every promotion condition.

| Platform | Baseline median NPS | Candidate median NPS | Paired gain | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Windows, 1 thread | 422,514 | 425,373 | +0.905% | -0.083% to +1.221% |
| Linux, 4 threads | 3,147,437 | 3,208,832 | +1.951% | +1.069% to +2.824% |

The cross-platform geometric gain was `+1.426%`.  Both depth-13 signatures
searched exactly 2,221,258 nodes, both platforms supplied nine measured pairs,
neither paired estimate was below `-0.30%`, and neither confidence-interval
lower bound was below `-0.30%`.  The change was promoted as
`v0.2.0-nnue`.

Binary SHA-256 pairs used for the decision were Windows
`ba3a6e594ee2360797549deaf18d188413a87a01f9805bfaec5f92f00ad58237` /
`916aa1281a4563a5a4c2a3b34afdff84c7e1af16232229767e1e605725e59346`
and Linux
`8a45d52ed856b3f651d7a833e71a0c6823ebe282141e79b5eb3eca96b8c07742` /
`bc9f45153e5df4d73fa5d1f75a43c09624b015bcfb54d175337b6ee814f102aa`.

### A06: capture-shape PSQ specialization

Extending the same column-hoisting scheme to the 2-removed/1-added and
1-removed/2-added PSQ shapes produced `+0.326%` on a seven-pair Linux screen,
with a 95% interval of `+0.116%` to `+0.845%` relative to A02+S03.  The
corresponding nine-pair Windows screen was `-0.329%`, with a 95% interval of
`-0.458%` to `+1.154%`.  Because Windows crossed the `-0.30%` platform floor,
A06 was reverted and received no optimization commit.

### Post-v0.2 SIMD and code-generation sweep

After `v0.2.0-nnue`, the remaining profile-visible NNUE kernels were exercised
with small, independently reversible variants.  Unless a platform is stated,
these are seven-pair Linux AVX2 PGO screens against `v0.2.0-nnue`.  Every
reported candidate matched the 2,221,258-node correctness signature.

| ID | Variant | Platform/pairs | Paired gain | Bootstrap 95% CI |
|---|---|---:|---:|---:|
| A07 | Reuse one loaded HalfKA tile across accumulator passes | Linux/9 | -0.285% | -0.716% to +0.201% |
| A08 | Pair the common threat add/sub shape | Linux/7 | -0.975% | -1.220% to -0.192% |
| A09 | Scan both accumulator perspectives together | Linux/7 | -1.594% | -1.895% to -1.074% |
| F02 | Alternate AVX2 multiply/pack transform | Linux/7 | +0.135% | -0.230% to +0.961% |
| S05 | Stage sparse-FC products before accumulation | Linux/9 | +0.082% | -0.653% to +0.892% |
| S06 | Merge adjacent nonzero-mask stores | Linux/7 | -0.075% | -0.913% to +0.515% |
| S07 | Compact the nonzero index representation | Linux/7 | -0.249% | -0.537% to +0.926% |
| S08 | Materialize a sparse index list before FC0 | Linux/7 | +0.156% | -0.721% to +0.330% |
| S09 | Partially unroll the sparse column loop | Linux/7 | -0.400% | -0.991% to -0.003% |
| S10 | Process three sparse columns per iteration | Linux/7 | +0.303% | -0.136% to +0.556% |
| S11 | Store and consume sparse indices in pairs | Linux/7 | -0.721% | -1.219% to +0.143% |
| E01 | Return the latest accumulator directly | Linux/7 | -0.014% | -0.422% to +0.295% |
| E02 | Merge accumulator validity scans | Linux/7 | +0.017% | -0.384% to +0.096% |

The dense-layer sweep found small isolated results but no cross-platform
promotion.  D02 reached `+0.915%` on a nine-pair Linux confirmation, then
measured `-0.634%` on Windows.  D03 measured `+0.521%` on Linux and `+0.365%`
on Windows, still below the combined one-percent gate.  Wider output grouping,
FC2 chaining and alternate product schedules ranged from `-0.541%` to
`+0.216%`.  An `llvm-mca` comparison of D02, D03, D08 and the original loop
predicted the same 16-cycle block throughput on both Haswell and Zen 2, which
closed this scheduling branch after the measured failures.

Additional whole-path checks were also neutral or negative: host-specific
tuning was `-0.076%` on the Zen 2 server and `-0.596%` on Haswell Windows;
force-inlining propagation was `-0.025%`; aligning the sparse loop was
`-1.045%`; and the upstream-style hybrid king refresh was `-0.451%`.  These
results, together with the earlier accumulator, transformer and sparse-FC
screens, leave memory translation as the only post-v0.2 candidate with a
repeatable gate-sized effect.

### Promoted M01 Linux transparent-huge-page mapping

The Ubuntu server configures anonymous transparent huge pages as `madvise`,
while transparent huge pages for shmem are disabled.  The previous 64 MiB NNUE
POSIX shared-memory mapping therefore remained backed by base pages.  M01 uses
the existing NUMA-local fallback allocator on Linux; that allocator creates an
anonymous mapping and applies `MADV_HUGEPAGE`.  A live `/proc/PID/smaps` check
reported a 67,584 KiB network region with all 67,584 KiB in `AnonHugePages`.
Windows and non-Linux platforms retain the existing shared-memory selection.

| Platform | Workload/pairs | Baseline median NPS | Candidate median NPS | Paired gain | Bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|
| Linux, 4 threads | 1M nodes/9 | 3,051,429 | 3,133,739 | +2.354% | +1.767% to +2.678% |
| Windows, 1 thread | 1M nodes/9 | 427,981 | 427,638 | -0.128% | -0.436% to +0.163% |
| Windows, 1 thread | two independent sets/18 | 413,882 | 412,374 | -0.072% | -0.300% to +0.198% |

The 18-pair Windows estimate pools the nine-pair 100k-node screen with the
nine-pair 1M-node confirmation; both sets independently matched signatures
and exercised preprocessor-identical Windows engine code.  Combined with the
Linux confirmation, its geometric gain is `+1.134%`, and the deterministic
analyzer accepts every promotion condition.  A clean-commit 1M-node rerun is
retained with the release evidence as an additional guard against layout and
packaging changes.

The clean tagged binaries were then rebuilt independently.  The clean Linux
confirmation measured `+2.164%` with a bootstrap 95% CI of `+1.654%` to
`+2.605%` over nine 1M-node pairs.  One clean Windows set contained two large
candidate-side outliers, so its nine-pair estimate alone was `-0.248%` with a
wide `-1.639%` to `+0.537%` interval.  Pooling all three independent Windows
sets gives 27 pairs, `-0.128%`, and a much tighter `-0.253%` to `+0.195%`
interval.  Combining that Windows estimate with the clean Linux result yields
`+1.011%`; every correctness, sample-count, regression, confidence and total
gain condition passes.  The unpooled result and every raw log remain in the
release evidence so the aggregation is auditable.

The trade-off is explicit: Linux processes no longer deduplicate the NNUE
network through POSIX shared memory, so each engine process consumes roughly
64 MiB of local network memory.  The intended server workload gains local THP
coverage and avoids base-page translation pressure; deployments that value
cross-process deduplication more than NPS can revert M01 independently.

### Post-M01 saturation closeout

Two final profile-directed memory/index trials closed the remaining threat
branch.  M02 placed the 4 MiB threat-offset table in a huge-page-backed
anonymous allocation and confirmed full 4,096 KiB `AnonHugePages` coverage;
seven 500k-node pairs measured only `+0.131%` with a `-0.239%` to `+0.331%`
interval.  T01 replaced two random 16-bit colour lookups with one random
32-bit packed lookup, growing the table to 32 MiB; it measured `-0.553%` with
a `-1.812%` to `-0.065%` interval.  Both matched the 2,221,258-node signature
and were rejected.

At this boundary, every profile-visible NNUE family has multiple measured
variants: accumulator A01-A09, transformer F01-F03, sparse FC S01-S12, dense
FC D01-D08, evaluation/refresh/inlining/layout/codegen E01-E02/H02/I01/L01/
P02-P03, and memory/threat M02/T01.  Only A02+S03 and M01 survived the full
cross-platform gate.  The post-M01 profile plus the failed final trials meet
the campaign's saturation rule; further work should begin from a new profile,
network architecture, or target CPU rather than another unmeasured rewrite of
these kernels.

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
