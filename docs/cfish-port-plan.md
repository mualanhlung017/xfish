# Cfish optimization port plan

Source: [`syzygy1/Cfish`](https://github.com/syzygy1/Cfish), audited at
`d77dd434f99c265f20efd1b55c5c99abdb0bb583` (2025-09-05). Cfish is a C port
of Stockfish whose performance work is concentrated in the 2016-2020 code
base. The current xfish/Pikafish base is newer, so a Cfish commit is evidence
for an idea, not a patch to cherry-pick blindly. The 2026-08-10 history census
covered all 638 commits (619 non-merge); after obvious upstream Stockfish
imports were separated, 330 locally described commits remained in the
family-by-family source audit.

## Non-negotiable scope

- Keep the accepted NNUE file and SHA-256 unchanged. Do not change the NNUE
  architecture, feature set, layer dimensions, quantization, or training data.
- Keep Xiangqi rules, legal moves, repetition/perpetual-check handling, cannon
  geometry, flying-general handling, move encoding, and UCI behavior unchanged.
- Port one implementation fragment at a time. Never combine unrelated Cfish
  commits in one candidate.
- A candidate that intentionally changes search decisions is not a gameplay-
  identical speed patch. It needs a separately justified Elo experiment and
  must still pass all rule, legal-move, and NNUE score checks.

## Audit results before experimentation

| ID | Cfish source | Idea | Current xfish finding | Decision |
| --- | --- | --- | --- | --- |
| CF001 | `f0bfc78` | Avoid piece-count work on quiet moves | `move_piece()` already leaves `pieceCount` untouched; only structural `put_piece()`/`remove_piece()` operations update counts. | Already present |
| CF002 | `9057638` | Avoid copying an uncomputed NNUE accumulator on null move | Accumulators live in `Search::Worker::accumulatorStack`, outside `StateInfo`; `do_null_move()` copies no accumulator. | Already present |
| CF003 | `5e6c94a` | Clear a large TT with all threads and distribute first-touch memory across NUMA nodes | `TranspositionTable::clear(ThreadPool&)` already clears in parallel and sorts threads by NUMA node. | Already present, newer implementation |
| CF004 | `913e713`, `b6a3d2d`, `4d1dfb7` | Large/transparent pages for NNUE and TT | TT uses the large-page allocator; accepted baseline `v0.3.0-nnue-thp` routes Linux NNUE through the NUMA-local large-page/THP path. | Already present and benchmarked |
| CF005 | `8957fe9` | Remove old NNUE piece lists | Current accumulator stack records compact dirty pieces/threats and has no Cfish-era piece-list copy. | Already present |
| CF006 | `1edc207`, `f350cbc`, `9c41eac` | Tile accumulator updates and keep each tile in SIMD registers until the final store | Current `nnue_accumulator.cpp::apply_combined()` loads a tile into `vec_t` registers, applies PSQ/threat deltas, then stores once. | Core optimization already present; assembly audit only |
| CF007 | `d19ec78` | Permute layer weights at load time to remove AVX2 shuffles | Current feature transformer already permutes weights reversibly, and current affine layers are structurally different. | Do not port the old layout; inspect only for an absent equivalent shuffle |
| CF008 | `45108c1`, `710cf87`, `4ce2352` | GCC flags, LTO and PGO/code-generation choices | Required builds already use clang/clang-cl, Full LTO, PGO and AVX2. GCC-only `-fno-tree-pre` is not a cross-platform candidate. | Not applicable as source patch |
| CF009 | `a5f1deb` | Cheaper post-move TT key | Current `prefetch_key()` is already compact and also preserves xfish's rule-60 key adjustment. | Already present/newer |
| CF010 | `a69b464` | Remove a target argument from slider-blocker calculation | Current API exposes the cached `blockers_for_king(Color)` bitboard and has no matching hot target argument. | Already present/newer |
| CF011 | `ad4eacb` | Faster chess draw detection | Based on chess 50-move/repetition invariants that do not match Xiangqi rule-60/perpetual-check logic. | Reject |
| CF012 | `e4658fd`, `a68c149`, `1727e53` | 64-square AVX2/BMI rook attack generation | Assumes one 64-bit chess board and chess slider geometry. It does not represent a 90-square Xiangqi board or cannon screens. | Reject; Y014 already supplied negative local evidence for related slider work |

## Candidate queue

The table records every bounded family considered in the current Cfish pass.
Only a row marked `queued` may become a worktree; closed rows are retained so
the same old optimization is not rediscovered later.

| Priority | Candidate | Upstream evidence | Exact experiment |
| ---: | --- | --- | --- |
| queued | CFS01 Xiangqi SEE least-value ordering | Cfish `7fffbff` inspired the audit; xfish value change `ec962113` exposed the distinct issue | Move the knight branch before cannon, require four known baseline/oracle mismatches to be corrected without new oracle failures, then follow the master STC/LTC queue. |
| closed | CF101 AVX2 sparse-affine scheduling | `6dbb408`, `8f8106f`, `d4f33d4`, `f9fe7b1` | Static audit found every applicable mechanism already present in a newer form; no source candidate is opened. See the closure record below. |
| closed | CF102 accumulator refresh register residency | `1edc207`, `f350cbc`, `9c41eac` | Source and AVX2 PGO assembly audits found the tiled accumulators already resident in registers on both clang and clang-cl. No source candidate is opened. See the closure record below. |
| closed | CF103 reversible affine weight permutation | `d19ec78`, `f9fe7b1` | Current xfish already pre-permutes affine weights reversibly at load time, and both clang and clang-cl AVX2 PGO code contain no runtime lane shuffle in `NetworkArchitecture::propagate`. See the closure record below. |
| closed | CF104 Xiangqi-safe SEE branch ordering | `3d0293c`, `7fffbff`, `1b11920` | The applicable null-window and unrolled-attacker mechanisms are already present in a Xiangqi-specific implementation; the remaining chess geometry cannot be transplanted. See the closure record below. |
| closed | CF105 small hot-path C idioms | `fe80bc8`, `60d9950`, `bd354cf`, `81079bb` | Every hunk is chess-only, already represented in modern C++, or already emitted by LLVM; the remaining packed-table trick is counterproductive for 90 squares. See the closure record below. |
| closed | CF106 keep large move generators out of `generate<LEGAL>` | `2892af8` | The retained Windows clang-cl AVX2 PGO/LTO image already inlines only the small legal wrapper while calling the large pseudo-legal/evasion bodies out of line. |
| closed | CF107 power-of-two TT mask | `c74ce7c` | Current xfish deliberately supports arbitrary cluster counts with `mul_hi64`; Cfish's `count - 1` mask would change the allocation contract. |
| closed | CF108 shared per-thread generated-move array | `c4eb692` | Obsolete invasive C layout; current MovePicker-local storage is the later Stockfish design and has no isolated strength evidence for reverting it. |
| closed | CF109 packed ply counters and shared increment | `ed4deba`, `a5c7710` | The proposed shared update is invalid for xfish's conditional Xiangqi rule-60/check counters; narrowing them alone has no demonstrated hot-path benefit. |
| closed | CF110 reduce recursive-search arguments | `db2086f` | Current `NodeType` templates already specialize PV/NonPV invariants at compile time. |
| closed | CF111 preallocated state objects | `fdb9134` | Recursive search already uses stack `StateInfo`; no per-node dynamic allocation exists to remove. |
| closed | CF112 NUMA/per-thread continuation histories | `5debfec`, `34f6220` | Current `Worker` and `SharedHistories` ownership already implements the newer topology-aware form. |
| closed | CF113 inlining and LTO controls | `a860ea1`, `5ba1a6d`, `7b7cdbd` | Current AVX2 PGO/LTO builds supersede these old compiler controls; any remaining clang-cl-only experiment is already SF-B33. |
| closed | CF114 compact piece/move layouts | `56eba10e`, `9843636` | Current byte-backed enums and 16-bit `Move` already represent the safe parts; the rest assumes chess encoding and 64 squares. |

CF101-CF103 are NNUE *implementation* audits only. Any fragment that changes
the network header/hash, dimensions, stored weights, feature indices or an
evaluation result is immediately rejected without a performance or Elo run.

### CF101 closure record

CF101 was source-audited on 2026-08-09 and closed without a worktree, build, or
benchmark:

- `6dbb408` and `8f8106f` target the old 512-to-32 HalfKP network. Their AVX2
  path scans an explicit mask, pairs nonzero inputs, and replaces lane
  permutation/sign-extension with unpacking. Current xfish instead scans the
  feature transformer's 256-bit NNZ blocks, hoists input/weight base pointers,
  uses load-time `ChunkSize=4` weight scrambling, and accumulates directly with
  `m256_add_dpbusd_epi32` (`maddubs` + `madd` on AVX2). There is no remaining
  equivalent shuffle or sign-extension hunk to remove.
- `d4f33d4` selected dense multiplication for AVX2 on Cfish's old network and
  retained sparse mode mainly for older CPUs. Current xfish's materially larger
  first layer deliberately uses the modern block-sparse implementation and a
  precomputed NNZ bitset; copying the old dense/sparse policy would not be a
  separable scheduling optimization.
- `f9fe7b1` imports official Stockfish commit `d862ba4` for load-time weight
  layout and paired dot-product scheduling. That official commit is already an
  ancestor of xfish, and the current implementation has received many later
  sparse-affine improvements. Accepted xfish commit `f10beeb4` additionally
  optimized the AVX2 NNUE sparse scan and accumulator path.

Result: `already present/newer`, with no NNUE architecture or network change.

### CF102 closure record

CF102 was source- and assembly-audited on 2026-08-09 and closed without a
worktree, source patch, or benchmark:

- Cfish `1edc207` keeps one accumulator tile live in SIMD registers;
  `f350cbc` imports the later official Stockfish tiling implementation; and
  `9c41eac` applies the same lifetime principle to incremental updates.
- Current `apply_combined()` explicitly loads `Tiling::NumRegs` vectors,
  applies all PSQ and threat removals/additions to that local register array,
  and stores the completed tile. The refresh-cache path uses the same tiled
  lifetime, updating the cached PSQ value before applying active threats and
  writing the final accumulator.
- In the Linux clang 22 Full-LTO/PGO AVX2 binary, disassembly of
  `AccumulatorStack::evaluate`, `evaluate_side`, and `apply_combined` contains
  zero YMM references through `%rsp`. `%rbp` is used as a data pointer/index,
  not a frame pointer, so its vector memory operands are accumulator or weight
  accesses rather than spills.
- The retained Windows clang-cl 19 AVX2 PGO ThinLTO object was lowered through
  the matching LLVM backend and inspected function by function. `evaluate`
  (125 assembly lines), `evaluate_side` (537), and `apply_combined` (524) each
  contain zero YMM stack references. `apply_combined` saves and restores only
  the lower halves of XMM6-XMM9 in its prologue/epilogue, as required by the
  Microsoft x64 callee-saved ABI; there is no accumulator-tile spill/reload in
  the loop body.

Result: `already-generated-by-compiler/current source`. A rewrite would merely
re-express an optimization already present and would add NNUE risk without an
absent machine-code mechanism to test. The next Cfish implementation audit is
CF103.

### CF103 closure record

CF103 was source- and assembly-audited on 2026-08-09 and closed without a
worktree, source patch, or benchmark:

- Cfish `d19ec78` rearranges the old 32-by-32 layer with `wt_idx()` at network
  load time so AVX2/AVX512 affine multiplication no longer needs a runtime lane
  shuffle. `f9fe7b1` then imports official Stockfish `d862ba4`, an ancestor of
  current xfish, with a newer form of the same weight-layout strategy.
- Current `AffineTransform::get_weight_index_scrambled()` performs the
  output-transpose and the inverse pack-lane permutation while parameters are
  read. `write_parameters()` uses the identical index mapping, restoring the
  canonical serialized order. The accepted compressed network remains
  `3cd15292bf8c979884262f57fc723959fc0dea43b4d8d544f88db5ceb2479e24`.
- Current upstream commit `e54738e2` is already an ancestor of xfish and makes
  this invariant explicit for AVX2: fused squared/clipped activations retain
  their 128-bit-lane pack order, while the following layer's weights are
  reverse pre-permuted at load time. It is marked `No functional change`.
- In the Linux clang 22 Full-LTO/PGO AVX2 implementation of
  `NetworkArchitecture::propagate` (182 disassembly lines), runtime counts are
  zero `vperm*`, zero `vpshuf*`, zero `vpunpck*`, and zero `vinsert*`. The two
  `vextracti128` instructions belong to scalar/final horizontal reductions,
  not lane repair between activation and affine layers.
- Lowering the retained Windows clang-cl 19 AVX2 PGO ThinLTO object through
  the matching backend gives the same result over the 229-line function: zero
  `vperm*`, `vpshuf*`, `vpunpck*`, or `vinsert*`; only the same two reduction
  extracts remain.

Result: `already present/newer`. There is no runtime shuffle for a new
load-time permutation to remove, so opening an NNUE candidate would violate the
one-mechanism rule without a testable mechanism. The next Cfish audit is CF104.

### CF104 closure record and CFS01 follow-up

CF104 was source-audited on 2026-08-09 and closed as a speed-only candidate:

- Cfish `3d0293c` changes SEE to the null-window `swap`/alternating-`res`
  formulation. Current `Position::see_ge()` already uses that formulation,
  including both early bounds.
- Cfish `7fffbff` unrolls least-valuable-attacker selection and filters pinned
  attackers before each exchange. Current xfish already has an unrolled
  Xiangqi-specific chain with separate pawn, bishop, advisor, cannon, knight,
  rook, and king paths.
- The current implementation also performs mechanisms absent from Cfish:
  cannon-screen recomputation, advisor removal exposing a horse-leg attack,
  flying-general handling, and Xiangqi pinner/blocker filtering. Replacing
  those paths with bishop/rook/queen chess X-rays would change rules and is
  rejected.
- Cfish `1b11920` has no SEE change; its material hunk removes an early check
  and changes indexing in chess upcoming-repetition detection. It is not a
  CF104 source fragment.

During the audit, a separate strength hypothesis was found and is retained as
`CFS01`, not disguised as an equivalent speed patch:

- The unrolled order was introduced when `CannonValue=686` and
  `KnightValue=893`, so checking cannon before knight was least-value-first.
  Commit `ec962113` changed the constants to `CannonValue=773` and
  `KnightValue=720` but did not reorder the two SEE branches. Those values and
  the stale branch order are still present in current xfish and in upstream
  Pikafish snapshot `9da21ca0bf438599e3cbc8896227b0b45f7946c0` from 2026-08-06.
- CFS01 will move the knight block immediately before the cannon block while
  retaining the exact per-piece occupancy and cannon-screen updates. This can
  intentionally change `see_ge()` and search decisions, so deterministic bench
  equality is not an invariant for this candidate.
- Before Elo, a dedicated test must compare the candidate with a recursive
  legal-capture exchange oracle over targeted cannon/horse-screen positions and
  a large deterministic random Xiangqi corpus. Legal move sets, perft, cannon
  and flying-general rules, repetition outcomes, raw NNUE scores, network hash,
  and crashes/assertions must remain identical to both v1.0.0 and the accepted
  baseline.
- The test-only hook is now defined by
  `tools/see-verifier/xfish-verify-see-command.patch` and the durable runner is
  `scripts/verify-see.py`. The hook is guarded by `XFISH_VERIFY_SEE` and is
  applied only to throwaway verification worktrees, never to performance, Elo,
  baseline, or release builds. Its slow oracle recursively enumerates
  `MoveList<LEGAL>` captures on one square, while the runner rejects any new
  oracle regression and, for CFS01, requires at least one corrected baseline
  mismatch.
- Two legal color-mirrored minimal positions now reproduce the stale decision:
  a pawn captures a pawn, the opponent can recapture with either knight or
  cannon, and the first side can recapture with a knight. The exhaustive value
  is `0`, while the accepted baseline reports `see_ge(move, 1) == true` for
  both colors. The same defect is also reached when the knight makes the root
  capture, giving four deterministic failing capture probes across the two
  positions. These built-in cases give CFS01 a correction requirement instead
  of relying on random coverage.
- The hook compiled cleanly from accepted baseline `1699e6ba` on Ubuntu `.55`
  with LLVM 22, AVX2 and libstdc++ assertions. A 513-position deterministic
  playout survey covered 795 natural captures, and a separate 4,097-position
  opening-book survey covered 5,686 natural captures; the current SEE matched
  the exhaustive oracle for all of them. The synthetic color-mirrored cases
  then isolated the four expected stale-order mismatches. Preserved artifact
  SHA-256 values are `dd0319ed454691fbb85fbe298be74aaf65e5e4f6095b865eb041f276d6fe67f4`
  (instrumented assertion binary),
  `9c4a6a5eba1d79e3e0e3e081dc764c1e1e70f16f3bb2a85e0aaaafc6d030200c`
  (build log), `2d3ee1b196f69a72995d6b10eb5c1c3bef75edd8bc030e42d6bdcc173dc74a03`
  (513-position JSON), `1b3cfbc891a8f9ae473e9a39ea32ac8611a41c828d41bccdbd95bc177e81ab0c`
  (4,097-position JSON), and
  `7e6339482c652046bf8951842a80cf7b8dc2e57e72e2bb2fa09e40f916ddd994`
  (targeted baseline JSON).
- CFS01 is a strength candidate. Skip NPS benchmarking; after its dedicated
  oracle and the full gameplay/rule/NNUE verification pass, run STC
  `SPRT(0.0, 2.0)`. Only an upper-bound crossing advances to an independent-seed
  LTC `SPRT(0.5, 2.5)`, whose upper-bound crossing is required for promotion.
  It cannot start until Y015 has been accepted or rejected and its turn in the
  master queue is reached.

Result for CF104: `already present/newer`; result for CFS01: `queued strength
hypothesis`. The next Cfish implementation audit is CF105.

### CF105 closure record

CF105 was source- and machine-code-audited on 2026-08-09 and closed without a
worktree, source patch, or benchmark:

- `fe80bc8` replaces chess en-passant square subtraction with `square ^ 8` in
  legal/do/undo paths. Xiangqi has no en passant and its board stride is nine,
  so there is no corresponding operation.
- `81079bb` mainly moves a C helper below its dependencies and simplifies
  en-passant/castling occupancy. Modern xfish has neither chess special move,
  and its check information is maintained by C++ position methods with
  Xiangqi cannon, horse-leg, and flying-general semantics.
- `60d9950` narrows chess castling arrays, changes old C enum/integer types,
  caches a piece type, and changes move-type encoding. Current `Move` is
  already a 16-bit class with zero as `Move::none()`, while `Color`,
  `PieceType`, and `Piece` use byte-sized underlying types. `pseudo_legal()`
  already caches the moved piece. In the clang 22 PGO/LTO implementation of
  `Position::legal()`, the source-square board byte is loaded once, masked once,
  and retained across the non-king path; spelling a local variable would not
  remove a machine instruction.
- `bd354cf` removes the old `MOVE_NONE` macro, narrows standalone magic-shift
  arrays, and indexes a chess 64-by-64 line table with the 12-bit move value.
  The first item is already represented by the `Move` class. Current
  `Magic` embeds a shift beside 128-bit fields and remains 48 bytes whether
  that field is `unsigned` or `u8`; LLVM already emits a byte load for the
  shift. Current moves encode `from * 128 + to`, whereas `LineBB` is a dense
  90-by-90 table. Direct raw-move indexing would require a sparse 128-by-128
  128-bit table, roughly doubling this hot table from 129,600 to 262,144
  bytes, or would still require arithmetic and provide no removed operation.
- The remaining hunks alter classical chess evaluation/endgames, 64-square
  magics, castling, build rules, comments, or debug-only checks. None maps to
  the NNUE Xiangqi hot path.

Result: `no applicable absent mechanism`.

### CF106-CF114 deep-history closure record

The remaining implementation families were source-audited on 2026-08-10. No
additional candidate was opened:

- Cfish `2892af8` marks `generate_legal()` for minimum code size so its larger
  generators are not duplicated through inlining. A diagnostic relink of the
  retained Windows clang-cl 19 ThinLTO+PGO+AVX2 objects produced map SHA-256
  `b16fcfeca1701b596a5a26a7593b75c329189dc44d0e7c6ad73d176e6516d3de`
  and executable SHA-256
  `1e1fa2ed7cfff2ce3bbf6e8419a5753b940d9b766a60b9f6ba976c5941930992`.
  The map contains standalone specializations for captures, quiets, quiet
  checks, and evasions but no `generate<LEGAL>` symbol: LLVM inlined the small
  wrapper. Disassembly retains nine calls to the pseudo-legal body and two to
  the evasion body. The intended code-size behavior is therefore already
  emitted without a source attribute; CF106 is closed without benchmarking.
- `c74ce7c` replaces TT reduction arithmetic with a power-of-two mask. Current
  xfish's `mul_hi64(key, clusterCount)` intentionally maps arbitrary cluster
  counts, so copying the mask would be a behavior/allocation regression, not a
  free optimization (CF107).
- `c4eb692` gives each old C search thread one shared generated-move array.
  Modern xfish uses bounded MovePicker-local arrays and later Stockfish object
  lifetimes. Reintroducing the global scratch layout is invasive and lacks an
  isolated Elo result (CF108).
- `ed4deba` and `a5c7710` pack or jointly update chess ply/rule counters. Xfish
  conditionally updates rule-60 and check counters under Xiangqi semantics, so
  the shared increment is incorrect; type narrowing alone has no measured
  mechanism (CF109).
- `db2086f` removes recursive arguments inferred from chess PV/NonPV state.
  Current `search<NodeType>` templates already expose those invariants to the
  compiler (CF110). `fdb9134` avoids repeated state allocation, whereas xfish
  already creates recursive `StateInfo` on the stack (CF111).
- `5debfec` and `34f6220` reorganize continuation histories and NUMA ownership;
  current `Worker`/`SharedHistories` code is the newer equivalent (CF112).
  The inlining/LTO family `a860ea1`, `5ba1a6d`, and `7b7cdbd` is superseded by
  current PGO/LTO builds; the only distinct clang-cl experiment is already
  tracked as SF-B33 (CF113).
- `56eba10e` and `9843636` optimize old C piece/move layouts. Xfish already has
  byte-sized color/piece enums and a 16-bit move class; remaining hunks depend
  on chess-only encoding and a 64-square board (CF114).

The full Cfish re-audit is complete. Only the independently discovered CFS01
strength hypothesis remains in the executable experiment queue.

## Per-candidate workflow

1. Record source commit(s), a one-sentence invariant, changed files/lines, and
   an independent patch identity in the port log.
2. Build assertions first. Verify the accepted network SHA-256 and bench
   signature before measuring anything.
3. Run `scripts/verify-gameplay.py` against both `v1.0.0` and the latest
   accepted baseline on Windows and Ubuntu. Speed-only candidates require
   identical legal moves, perft, NNUE scores and deterministic search output.
   Strength candidates may deliberately change search output, but not legal
   moves, perft, rule outcomes, raw NNUE scores, or network bytes. CFS01 also
   requires the dedicated legal-capture exchange oracle described above.
4. Build independent baseline and candidate binaries with AVX2, Full LTO and
   PGO: clang-cl on Windows, native LLVM/clang on each Linux CPU family.
5. Run only a short launch/signature/hash/crash smoke check. Do not schedule or
   analyze comparative NPS benchmarks; incidental Elo calibration output is
   ignored.
6. Run paired STC `SPRT(0.0, 2.0)` across Windows (10 cores), Ubuntu `.7` (32),
   Ubuntu `.8` (up to 64), and Ubuntu `.55` (44), with
   `alpha=beta=0.05` and normalized-Elo pentanomial LLR bounds
   `+/-ln(19) = +/-2.944438979`. An upper crossing passes; a lower crossing
   fails; reaching an administrative game cap between the bounds is
   inconclusive, not a pass.
7. After an STC pass, drain and integrity-check every STC task, then run LTC
   `SPRT(0.5, 2.5)` with an independent opening seed and the same statistical
   bounds. Only an LTC upper crossing may become the new baseline, commit, tag,
   and release asset. Preserve PGNs, W/L/D, pentanomial, Elo/CI/LLR, time
   control, book/network hashes, binary hashes, and worker split.
8. Mark every inspected or rejected Cfish commit in the durable log so it is
   not rediscovered later.

The active Y015 run remains the sole candidate. Cfish experiments start only
when their turn in `docs/experiment-queue.md` is reached, preventing Elo
capacity from overlapping candidates.
