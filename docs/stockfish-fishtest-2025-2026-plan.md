# Stockfish Finished Tests 2025-2026 port plan

Source: [Stockfish Finished Tests](https://tests.stockfishchess.org/tests/finished)
through the official public `/api/finished_runs` endpoint. The reproducible raw
inventory is in `docs/stockfish-positive-tests-2025-2026.md`; complete compact
run records are stored in
`build/audit/stockfish-positive-tests-2025-2026.json`.

## Coverage and attribution

- Audit window: finished at or after `2025-01-01T00:00:00Z` and before
  `2027-01-01T00:00:00Z`, observed through 2026-08-09.
- Read 49 API pages containing 2,429 successful/green finished runs.
- Retained 2,311 runs whose observed score is positive (`wins > losses`).
- Cross-linked 759 positive runs explicitly cited in the messages of 426
  official Stockfish commits. A Fishtest `resolved_new` alone is not used to
  attribute an experiment to an official commit because progression tests can
  point at an unrelated current master.
- Excluded NNUE architecture/network changes, infrastructure-only changes,
  reverts, already-reviewed commits, and tests whose base/new networks differ.
- A green SPRT and a positive W/L/D point estimate are not the same claim.
  Non-regression bounds such as `[-1.75, +0.25]` can accept a patch whose true
  gain is near zero. Those tests are retained as evidence but ranked below
  gain-bound STC/LTC pairs.

The catalog is exhaustive for successful positive-score runs in the date
window. Source review remains deliberately manual: only a small isolated hunk
that is safe for Xiangqi may become a candidate.

## Official merged-commit review

After cross-checking the automatic queue against current xfish source and its
durable history, none of the 17 remaining official commits should be applied as
a new candidate.

| ID | Stockfish commit | Review result | Decision |
| --- | --- | --- | --- |
| SF-A001 | `9d4090e8` dynamic NMP evaluation margin | Current xfish already uses `R = 8 + depth / 3 + max((staticEval - beta) / 256, 0)` through a later Pikafish port. | Already present |
| SF-A002 | `99489f57` simplify out PEXT attacks | Assumes chess's 64-square attack representation and does not preserve Xiangqi cannon geometry. | Reject |
| SF-A003 | `60888387` remove PSQT weights | Current `evaluate.cpp` already uses the same `psqt + positional` end state. | Already present |
| SF-A004 | `9eb836b3` runtime hyperbola quintessence | Chess 64-square rook/rank implementation; not a 90-square cannon-safe fragment. | Reject |
| SF-A005 | `f8aa78e0` simplify TT-move reduction | Current xfish already applies the uncapped `r -= 2730` form, with later tuning around it. | Already present/newer |
| SF-A006 | `a12dc6cc` VVLTC parameter tune | Large coupled chess tune, superseded by `ebcea3ef`, already recorded as unsuitable for one-hunk Xiangqi attribution. | Superseded/reject |
| SF-A007 | `dc168634` ARM hyperbola quintessence | Wrong ISA and chess board representation; requested release target is AVX2. | Reject |
| SF-A008 | `1554a2ca` AVX-512 magic compression | AVX-512-only and tied to chess magic indices. | Reject |
| SF-A009 | `e17725f4` constexpr PEXT attacks | 64-square PEXT attack tables; no cannon-safe mapping. | Reject |
| SF-A010 | `b1fb50ae` en-passant legality | Xiangqi has no en passant. | Reject |
| SF-A011 | `ead7e650` promotion indexing fix | The affected promotion encoding does not exist in Xiangqi. | Reject |
| SF-A012 | `969542e4` HalfKAv2 index writer | AVX-512/64-square feature-layout code; changing xfish feature indices is forbidden. | Reject |
| SF-A013 | `add17326` VVLTC tune | Earlier version of the coupled tune in SF-A006. | Superseded |
| SF-A014 | `8b499683` AVX-512 accumulator refresh | AVX-512-only; not an AVX2 candidate. | Reject |
| SF-A015 | `e6d04b4e` VVLTC tune | Earlier version of the coupled tune in SF-A006. | Superseded |
| SF-A016 | `24af6a6b` castling-right update | Xiangqi has no castling rights. | Reject |
| SF-A017 | `2321cf2f` en-passant-square update | Xiangqi has no en-passant square. | Reject |

## Experimental positive-run queue

Positive Finished Tests also include unmerged commits from contributor forks.
They are lower-trust than official merged commits, so their source object,
network equality, complete STC/LTC statistics, and applicability were checked
before entering this queue.

### SF-X01 - share continuation correction history per NUMA node

- Source object: `06e704f82c168fef77b26756868a6aef75db6e3f`, `20` additions and
  `10` deletions in `history.h`, `search.h`, and `search.cpp`.
- Upstream Threads=8 STC test `699df372eaae015cd278ee81`: `34,402 / 33,968 /
  64,382`, 132,752 games, observed Elo `+1.136`, normalized SPRT `[0.0, 2.0]`
  accepted at LLR `2.9449`, identical networks, zero crashes and nine total
  time losses.
- Upstream Threads=8 LTC test `699fca9744b9136df1165df6`: `115,636 /
  114,520 / 218,158`, 448,314 games, observed Elo `+0.865`, normalized SPRT
  `[0.5, 2.5]` accepted at LLR `2.9431`, identical networks, zero crashes and
  249 total time losses.
- Applicability: xfish already shares its main correction, continuation, and
  pawn histories per NUMA node, but `continuationCorrectionHistory` is still
  private to each worker. The source layout and existing `numaThreadIdx` /
  `numaTotal` clear ranges make this a small structural adaptation.
- Scope invariant: move only this history table, its stack pointers, and its
  partitioned clear into `SharedHistories`. Do not import search constants,
  NNUE code, chess rules, or any unrelated fork change.
- Priority: **1**. This is the strongest currently absent candidate because it
  passed both gain-bound STC and LTC at the thread count where it has an effect.

SF-X01 needs a dedicated SMP test path. The local run creator now has validated
`--threads` and `--hash-mb` fields, and the worker converts its advertised
physical-core budget into `floor(cores / threads)` parallel pairs. Keep the
existing Threads=1 defaults unchanged.

1. At Threads=1, require assertion builds, identical legal maps/perft/raw NNUE,
   identical deterministic search against both v1.0.0 and the accepted
   baseline, and unchanged network SHA-256.
2. At Threads=8, repeat rule/legal/NNUE verification and run pinned PGO AVX2
   scaling measurements. Search identity is not required at Threads=8 because
   cross-worker history sharing is the intended strength change.
3. Run paired Xiangqi STC `10+0.1` at Threads=8 with color-reversed openings,
   an independent seed, and official pentanomial normalized-Elo
   `SPRT(0.0, 2.0)`, `alpha=beta=0.05`. Use concurrency `1` on Windows, `4`
   on `.7`, `4` on `.8`, and `4` on `.55`, keeping every eight-thread engine
   inside a physical-core/NUMA allocation. Start only on independently idle
   cores.
4. Reject when STC reaches `LLR <= -ln(19)`. Continue only when it reaches
   `LLR >= +ln(19)` with zero integrity errors, crashes, time losses, or
   missing pairs. A safety-cap result between the boundaries is inconclusive.
5. After draining every STC task, run an independent-seed LTC `60+0.6` at
   Threads=8 with `SPRT(0.5, 2.5)` and the same boundaries. Only an LTC
   upper-bound pass is accepted. Do not schedule a separate T1/T8 NPS
   benchmark.

### SF-X02 - cap singular extension below a null-move ancestor

- Source object: `e69356dec469e8dd95bae5cbebfe1c3461f3775b`.
- Upstream Threads=1 STC test `69202fcaacb6dbdf23d080f5`: `45,225 / 45,160 /
  85,199`, 175,584 games, observed Elo `+0.129`, non-regression SPRT
  `[-1.75, +0.25]` accepted.
- Upstream Threads=1 LTC test `692121803b03dd3a060e60d7`: `42,191 / 42,119 /
  82,136`, 166,446 games, observed Elo `+0.150`, the same non-regression bounds
  accepted.
- Exact experiment: isolate only the post-singular-search guard that limits a
  double/triple extension to one ply when `pliesFromNull < ss->ply`. xfish has
  compatible `pliesFromNull` semantics. Do **not** port the same fork commit's
  bundled `isShuffling()` changes, which depend on chess rule-50 behavior.
- Current official Stockfish master `762dd1da9a5db458180b2c5db6c53dc40ec61e1a`
  still has no equivalent null-ancestor cap, so this remains fork-only evidence
  rather than a missed official end state. Current xfish likewise computes up
  to a triple extension and increments `StateInfo::pliesFromNull` after each
  real move while resetting it on a null move, making the isolated predicate
  structurally applicable without importing chess draw rules.
- Priority: **2, low confidence**. The point estimates are positive on both
  time controls, but their SPRT bounds prove non-regression rather than an Elo
  gain. Run the normal Threads=1 safety verification, then the strict STC
  `SPRT(0.0, 2.0)` and LTC `SPRT(0.5, 2.5)` gates; skip comparative NPS
  benchmarking.

## Experimental ideas already present or superseded

These positive fork experiments were source-checked and must not be queued
again unless a genuinely newer, separable end state appears.

| Upstream object | Idea | xfish decision |
| --- | --- | --- |
| `c7cbbe79` | Prefer discovered/double checks in capture ordering | Already present via `c67fc1ec` |
| `cf8be0d6` | Check only captures with good SEE | Already present via `f93569f2`, with cannon-aware SEE |
| `39c241c7` | Depth-dependent full-depth thresholds | Ported via `f84d5d79`, later superseded by `8961eb50` |
| `55ec6076` | History-dependent futility threshold | Ported via `69ef8db6`, later retuned/superseded |
| `85bfbe48` | Adaptive ProbCut margin | Concept already passed through `a00b6d02`; current formula is newer |
| `66773b79` | Improving-aware null-move pruning | Already present and later retuned |
| `6924e79b` | Depth condition in old `stat_bonus()` | The old function no longer exists; superseded |
| `c0bbe942` | Remove `completedDepth` singular-extension condition | Already present via `8e4d773a` |
| `1429d98e` | Age secondary TT only for mate scores | Current TT has the later guarded implementation |
| `fc8603a1` | Simplify old razoring to depth one | Older form; current xfish contains later razoring tunes |

## Common execution and acceptance policy

1. Finish or reject the active Y015 candidate before opening another source
   worktree. Only one engine candidate may consume Elo capacity.
2. Apply one upstream idea at a time on the latest accepted baseline. Store the
   source URL/object, minimal diff, patch identity, affected invariants, and
   reason for every exclusion.
3. Never change NNUE architecture, dimensions, features, weights, network file,
   Xiangqi rules, move encoding, legal generation, cannon/flying-general logic,
   or repetition/perpetual-check/perpetual-chase adjudication.
4. Run `scripts/verify-gameplay.py` on Windows and Ubuntu against v1.0.0 and the
   accepted baseline. A speed-only patch requires search-identical output; a
   strength patch may change PV/search but must retain legal moves, perft, raw
   NNUE/final static evaluation, architecture, and legal bestmoves.
5. Build baseline and candidate independently with clang-cl/clang, Full LTO,
   PGO, and AVX2. On `.55`, compile natively for its Broadwell CPU; use native
   builds on the Zen 2 `.7`/`.8` hosts as well.
6. Do not run candidate NPS benchmarks. Use only a short launch, signature,
   binary/network/book hash, and crash smoke check before Elo. Incidental NPS
   printed during signature smoke or Elo clock calibration is ignored.
7. Elo Gate 1 is paired STC `10+0.1`, Threads=1, Hash=16 with official
   pentanomial normalized-Elo `SPRT(0.0, 2.0)`. Gate 2 is an independent-seed
   LTC `60+0.6` with `SPRT(0.5, 2.5)`. Both use `alpha=beta=0.05` and nominal
   boundaries `±ln(19)` (`±2.944438979`). Only an upper-bound hit passes; a
   lower-bound hit fails and a safety-cap result between the boundaries is
   inconclusive. Do not create a baseline, commit, tag, release, or binary
   asset until both gates pass with complete paired coverage and zero integrity
   errors, crashes, time losses, or missing pairs.
8. Preserve PGNs/move logs, opening indices, W/L/D, pentanomial, Elo/CI/LOS or
   LLR, worker split, time controls, compiler/PGO provenance, CPU pinning, and
   all engine/network/book SHA-256 values.

The remaining positive-run catalog will be re-generated before each new
candidate cycle. Newly finished tests enter source review, while every decision
above remains in the durable ledger to prevent duplicate experiments.
