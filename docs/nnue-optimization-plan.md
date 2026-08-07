# NNUE AVX2 optimization campaign

This document is the reproducibility contract for the long-running NNUE
optimization campaign.  A faster one-off benchmark is not a new baseline.

## Baseline history

- Initial source: `d5b4860dcddb43bded8aa3804ea53eadb60efa2e`
- Initial release: `v0.1.0-baseline`
- Current promoted release: `v0.2.0-nnue`
- Current change set: AVX2 one-removed/one-added HalfKA delta update plus a
  native 64-bit sparse-FC bit scan
- Windows: clang-cl, AVX2, profile-guided optimization, ThinLTO
- Linux: Clang 22, `ARCH=x86-64-avx2`, profile-guided optimization, Full LTO
- Linux execution: four threads pinned to CPUs `120-123`
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
| A06 | Accumulator | Specialize the 2-removed/1-added PSQ update | retained, below gate |
| F01 | Transformer | Fuse clamp/shift/pack/nonzero-mask work | queued |
| F02 | Transformer | Remove avoidable lane permutations via stored layout | queued |
| F03 | Transformer | Specialize the 1024-wide AVX2 transform loop | queued |
| S01 | Sparse FC | Split non-VNNI AVX2 dot products into two chains | rejected |
| S02 | Sparse FC | Unroll sparse columns in pairs with a scalar tail | rejected |
| S03 | Sparse FC | Use a native 64-bit bitset scan | accepted with A02 |
| S04 | Sparse FC | Prefetch the next 128-byte random FC0 column | rejected |
| D01 | Dense FC | Schedule broadcasts/loads around `vpmaddubsw` latency | rejected after confirmation |
| D02 | Dense FC | Tune fixed 64/128 input kernels and reduction tree | queued |
| R01 | Activation | Fuse paired square/clipped ReLU stores | queued |
| R02 | Reduction | Compare horizontal-sum dependency trees in final FC | queued |
| M01 | Memory | Validate alignment annotations and selective prefetch | in progress |
| M02 | Memory | Check cache-line placement of per-evaluation buffers | queued |

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
with a 95% interval of `+0.116%` to `+0.845%` relative to A02+S03.  It is kept
as a candidate to combine with another independent gain, but is not part of
`v0.2.0-nnue` and receives no optimization commit by itself.

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
