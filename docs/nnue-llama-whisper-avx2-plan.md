# NNUE AVX2 campaign from llama.cpp and whisper.cpp

## Reproducible source inventory

The review is pinned to the following upstream snapshots rather than a moving
branch:

- `ggml-org/llama.cpp` at `3653e6d6d547ec763317d9ecd0ace334a7e21359`
- `ggml-org/whisper.cpp` at `592feef04a1802b18cbeffd0fd0eb5d02570c2ec`

At these revisions, the x86 GGML files relevant to AVX2 integer dot products
have identical Git blob IDs in both projects: `arch/x86/quants.c`,
`simd-mappings.h`, `vec.h`, `vec.cpp`, `simd-gemm.h`,
`llamafile/sgemm.cpp`, and `repack.cpp`. Consequently, whisper.cpp confirms
the same implementation lineage; it is not treated as an independent source
of benchmark candidates.

The transferable techniques are:

1. use native unsigned-byte by signed-byte `vpmaddubsw`, followed by
   `vpmaddwd`, for four-way `u8 * i8` dot products;
2. expose independent products before reduction, then use a balanced add tree;
3. size a micro-kernel against the 16-register AVX2 register file;
4. keep the hot weight dimension contiguous through load-time repacking;
5. use restricted pointers in leaf kernels so byte inputs do not force
   conservative alias reloads;
6. delay horizontal reduction until the end of a dot-product block.

NNUE already implements items 1, 4, and 6. Its serialized weights are
scrambled on load into four-input-by-32-output contiguous FC0 columns, so no
network-format change is required. The signed-to-unsigned conversion used by
GGML (`vpsignb` before `vpmaddubsw`) is unnecessary here because clipped NNUE
activations are already unsigned bytes.

## Candidate queue

Each candidate is a small, independently reversible change. An entry that is
equivalent to a previously rejected A/S/D experiment is closed without being
rebuilt.

| ID | Kernel | Change | Relation to the pinned GGML code | Status |
|---|---|---|---|---|
| LW01 | sparse FC0 | Process four nonzero columns and reduce four independent dot products with a balanced tree | four-product `p0/p1/p2/p3` tree in `arch/x86/quants.c` | rejected: Linux -0.799%, CI -1.136%..-0.038% |
| LW02 | sparse FC0 | Two-column balanced block if LW01 spills registers | two independent accumulators used by quant dot loops | closed: no spill; LLVM reassociated LW01 to the existing serial reduction, leaving only batching overhead |
| LW03 | sparse/dense FC | Add compiler-correct restricted leaf pointers, with no arithmetic change | pervasive `GGML_RESTRICT` kernel contracts | rejected: Linux +0.018%, CI -0.504%..+0.547% |
| LW04 | sparse FC0 | Explicit 6x2-style input/output micro-tile | AVX2 register budget in `simd-gemm.h` | closed: current 4-output-vector layout plus S01/S02/S05/S10 already covers it |
| LW05 | dense FC | Multiple output rows per input traversal | integer GEMM MRxNR tiling in `llamafile/sgemm.cpp` | closed: D03-D08 measured this family below the cross-platform gate |
| LW06 | signed dot | Convert signed operands with `vpsignb` before `vpmaddubsw` | llamafile signed-int8 `updot` | closed: NNUE input is naturally unsigned, so conversion only adds work |
| LW07 | packed input | Nibble/bit unpack with `vpshufb` | quantized GGML decode helpers | closed: NNUE activations and weights are already byte-native |
| LW08 | accumulator weights | Losslessly pack HalfKA i8 weights into a q4 base plus sparse outliers, if the measured distribution permits it | GGML q4 unpack/repack and outlier-aware quantization | closed: q4 outliers are 71.86% PSQ and 49.63% threat |
| LW09 | threat accumulator | Prefetch the same feature's next 128-byte tile one outer-loop iteration ahead | one-loop-ahead panel prefetch in GGML/llamafile kernels | rejected: Linux -1.169%, CI -1.919%..-0.654% |

## Measurement and promotion protocol

The immutable comparison point for this campaign is
`v0.3.0-nnue-thp`; semantic scoring is additionally checked against
`v0.1.0-baseline` on Ubuntu.

1. Build every candidate with Clang AVX2 PGO. Linux training and tests are
   pinned to CPUs 120-123 with four build/search workers; Windows builds use
   at most four workers and benchmark one engine on CPU 2.
2. Run a correctness signature and alternating A/B, B/A warmups before every
   screen. Screen on Ubuntu with seven 500k-node pairs.
3. Advance only stable candidates near the gate to at least nine independent
   1M-node pairs on both Ubuntu and Windows. Use paired NPS ratios and the
   deterministic bootstrap analyzer already in `scripts/analyze-ab.py`.
4. Reject a candidate if either platform median is below -0.30%, either 95%
   confidence lower bound is below -0.30%, or the cross-platform geometric
   gain is below +1.00%.
5. Before promotion, run the Ubuntu NNUE equivalence harness against
   `v0.1.0-baseline`: static scores, raw PSQT/positional terms, fixed-depth
   score/nodes/PV/bestmove, and incremental-versus-refresh checks must all be
   exact.
6. Only a candidate passing both performance and semantic gates gets a source
   commit, a new baseline tag, pushed release assets, and becomes the baseline
   for the next round.
7. Re-profile after every promotion. Stop when every source-derived candidate
   is closed by equivalence, code inspection, or repeatable measurements and
   no remaining profile-visible NNUE path can plausibly produce a one-percent
   whole-engine gain.

## Results

### LW01: four-column balanced sparse reduction

The Ubuntu Clang 22 AVX2 PGO binary matched the depth-13 correctness signature.
Seven alternating 500k-node pairs against the clean `v0.3.0-nnue-thp` binary
measured `-0.799%`, with a deterministic bootstrap 95% interval of
`-1.136%` to `-0.038%`. It was rejected before Windows testing.

Disassembly explains why the source-level GGML tree did not transfer. LLVM
legally reassociated modular integer vector additions back into four serial
updates of each output accumulator. The function had no additional YMM spill
stores; its remaining difference was the popcount, four-index extraction, and
larger loop body. A two-column source tree would be canonicalized the same way,
while the stronger two-accumulator form was already measured as S01, so LW02
is closed without duplicating that experiment.

### LW03: restricted affine pointers

Clang 22 produced a sparse/dense network propagation function with the same
950-byte size, 183-instruction count, and exact opcode sequence as the
baseline. Seven alternating Ubuntu pairs confirmed the code-generation
evidence: `+0.018%`, with a 95% interval of `-0.504%` to `+0.547%` and a
matching node signature. LW03 was rejected before Windows testing.

### LW08: lossless compact accumulator weights

The production network already stores both accumulator tables as signed int8,
so the straightforward i16-to-i8 compression is already present. A complete
Ubuntu load-time census found 16,932,864 PSQ weights spanning `-128..127` and
46,640,128 threat weights spanning `-128..127`. Only 28.136% of PSQ weights
and 50.370% of threat weights fit signed q4; a lossless q4 base would therefore
need correction entries for 71.864% and 49.630% respectively. Even signed q6
covers only 77.666% of PSQ weights. The exception data plus per-update unpack
work would exceed the bytes saved in the dominant PSQ path, so LW08 is closed
before implementing a slower representation.

### LW09: one-tile-ahead threat prefetch

The generated `apply_combined` code contained the intended
`prefetcht0 [column + 0x80]` before each next-tile threat update. Its
depth-13 node signature matched the baseline, but seven alternating Ubuntu
500k-node pairs measured `-1.169%`, with a 95% interval of `-1.919%` to
`-0.654%`. The extra cache traffic and per-feature guard outweighed any hidden
latency, so the whole prefetch branch is closed without a Windows run.

## Saturation decision

No source change in this campaign reached the Linux contender threshold, so
none was eligible for Windows confirmation, the full `v0.1.0-baseline`
semantic gate, a source commit, or a release. The immutable production
baseline therefore remains `v0.3.0-nnue-thp`, whose Ubuntu semantic comparison
against `v0.1.0-baseline` is already bit-exact.

The pinned llama.cpp/whisper.cpp inventory is exhausted for this NNUE and AVX2
target: byte dot products and weight repacking are already native; signed-dot,
MRxNR, independent-chain, sparse-index, dense-row, activation, and horizontal
reduction variants are either structurally inapplicable or covered by the
earlier A/S/D/F sweeps; the new balanced-tree, alias, lossless packing, and
panel-prefetch branches are now closed by code generation, distribution data,
or repeatable measurements. With `apply_combined` and sparse FC0 still the only
gate-sized profile regions and both having multiple negative variants, another
AVX2 rewrite of the same arithmetic no longer has a plausible one-percent
whole-engine path. Further work requires a different network architecture,
new ISA (for example AVX-VNNI), or a changed target CPU rather than another
same-shape AVX2 kernel.
