# YaneuraOu/Shogi test evidence audit (2025-2026)

Audit date: 2026-08-10.

This document answers two separate questions: whether the Shogi ecosystem has
a public accepted-test database comparable to Stockfish Fishtest, and whether
YaneuraOu's 2025-2026 positive self-play changes expose a safe, distinct
mechanism that xfish should test. It does not authorize a source change while
Y015 or another experiment is active.

## Sources and coverage

- Official engine: [`yaneurao/YaneuraOu`](https://github.com/yaneurao/YaneuraOu),
  pinned locally at `33ccf1f907eb7184889fa23051243f81ab0bf973`
  (2026-08-05).
- Official wiki: pinned at
  `a88cfd89950f37ac653fcf9dc1e00b6c55825ea9`, including the
  [2025](https://github.com/yaneurao/YaneuraOu/wiki/%E3%82%84%E3%81%AD%E3%81%86%E3%82%89%E7%8E%8B%E3%81%AE%E6%9B%B4%E6%96%B0%E5%B1%A52025)
  and
  [2026](https://github.com/yaneurao/YaneuraOu/wiki/%E3%82%84%E3%81%AD%E3%81%86%E3%82%89%E7%8E%8B%E3%81%AE%E6%9B%B4%E6%96%B0%E5%B1%A52026)
  development/test journals.
- The bounded history pass covered every non-merge commit dated 2025-2026:
  220 in 2025 and 143 in 2026. A keyword/source pass reduced those 363 commits
  to 113 search, move-generation, bitboard, threading, compiler, and NNUE
  implementation changes for manual inspection. NNUE architecture/training
  changes and Shogi-only rules were rejected before candidate selection.
- A parser extracted 58 journal result rows where the candidate-facing `R`
  value was negative. In these A/B logs `R` is printed from engine 1's
  perspective, so a negative value can favor engine 2. The rows are discovery
  evidence only: many are coupled parameter batches, migrations from
  Stockfish, or short `T2,b1000` tests rather than isolated portable patches.

## What Shogi uses for testing

The official
[USI self-play guide](https://github.com/yaneurao/YaneuraOu/wiki/USI%E5%AF%BE%E5%BF%9C%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%B3%E3%81%AE%E8%87%AA%E5%B7%B1%E5%AF%BE%E5%B1%80)
documents local parallel self-play through `script/engine_invoker5.py` and also
points to [Floodgate](https://wdoor.c.u-tokyo.ac.jp/), a public Shogi arena.
The 2025/2026 development journals publish many individual W-D-L and confidence
interval results. No official public, commit-gated, distributed accepted-run
database equivalent to Stockfish Fishtest was found. Floodgate ratings are
useful external evidence, but mixed opponents, hardware, time controls, and
versions make them unsuitable as xfish's promotion gate.

[ShogiArena](https://github.com/nyoki-mtl/ShogiArena) is a separate open-source
USI tournament system. As checked on 2026-08-10, its current release is 1.2.5
and it supports local/SSH workers, SPRT/GSPRT, SPSA, a dashboard, and
SFEN/KIF/CSA records. It is useful design reference, not an official YaneuraOu
result archive. Xfish's existing paired-pentanomial STC/LTC controller is
already stricter for this project, so no second test service is deployed.

YaneuraOu's official
[BalancedPositions2025 release](https://github.com/yaneurao/YaneuraOu/releases)
is the most transferable testing lesson. It filters opening positions with a
strong reference search at 200 million nodes and retains only positions with
absolute evaluation at most 50: 30,053 SFENs at ply 24 and 26,273 at ply 32.
The SFENs are Shogi-specific and cannot be used in Xiangqi, but the method can
later improve xfish's opening set: generate Xiangqi openings, score them deeply
with a frozen reference engine, balance by side-to-move evaluation, deduplicate
symmetries/transpositions, and freeze the resulting book hash before SPRT.
That book project is test infrastructure and must not be mixed with an engine
candidate.

## Positive-result source audit

| Family | Upstream positive-looking evidence | Xfish disposition |
| --- | --- | --- |
| PV-line IIR and shallow quiet pruning | YaneuraOu merge `ec88681a` records the tested Stockfish change `e20ef7ed`; its journal result favors disabling both in PV lines. | Already present: xfish's `followPV` guards the relevant IIR/quiet-pruning paths, recorded as Y008. |
| Null-move, improving, ProbCut-depth, and `cutoffCnt` refinements | Several 2026 journal rows show favorable candidate-side `R`. | Current xfish already contains the mechanisms from its newer Stockfish search base; no isolated absent hunk remains. |
| 2025 search migration series | Large cumulative gains appear while bringing the Shogi search closer to then-current Stockfish. | Coupled imports/tuning. Portable isolated end states are already covered by the Stockfish candidate ledgers; do not duplicate them under a Yaneura ID. |
| MovePicker capture/quiet sorting | `f3ef7beb` reports recovery of a large Shogi rating loss. | Current xfish already has full capture sorting and partial quiet sorting. |
| Avoid generating quiet moves in capture-only stages | `15ff26c0` is a clean implementation idea. | Already present in current staged Xiangqi MovePicker. |
| Finny/cache and NNUE SIMD work | `5f90c55f`, `72c91d81`, and adjacent commits contain real speed work. | Applicable accumulator cache, tiled update, and AVX2 paths are already present; AVX-512/VNNI and all architecture/training changes are out of scope. |
| Directional rays and split-word bitboards | `e76bc765`, `78dfc93e`, and related source provide small implementation-only mechanisms. | The distinct absent pieces are already recorded as Y007-R1, Y009, Y011, and Y012. |
| April 2026 search-tuning batches | Journal rows sometimes favor the batch. | Reject as a batch: constants and pruning terms interact, and there is no separable Shogi-origin mechanism not already in the Stockfish queue. |
| Shogi drops, promotions, repetition, entering-king, 81-square Qugiy/PEXT | Some changes improve upstream strength or speed. | Reject: rules, encoding, geometry, and invariants do not map to Xiangqi. |

## Queue decision

The audit found no new safe candidate family beyond the existing YaneuraOu
ledger. It did elevate two previously designed but never engine-tested items
into the direct-Elo sequence:

1. `Y009`: use POPCNT for the 128-bit `more_than_one()` test. PGO/assembly
   evidence shows a distinct small mechanism, and it does not alter bitboard
   semantics.
2. `Y012`: pop the low/high 64-bit halves explicitly while preserving ascending
   square order. Its standalone microbenchmark is design evidence only and is
   not an NPS gate.

The authoritative inter-project order is `docs/experiment-queue.md`. Every
candidate is rebased on the latest accepted baseline, verified against
`v1.0.0` and that baseline, built independently as AVX2 PGO on Windows and each
Linux CPU family, and given only launch/signature/hash/crash smoke before Elo.
Acceptance requires STC `SPRT(0.0, 2.0)` followed by independent-seed LTC
`SPRT(0.5, 2.5)`, both with paired pentanomial normalized-Elo LLR,
`alpha=beta=0.05`, and upper bound `+ln(19)`. A fixed game count or positive
point estimate never promotes a baseline.
