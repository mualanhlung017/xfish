# Xfish authoritative experiment queue

Updated: 2026-08-10.

This is the single execution order across the YaneuraOu, Cfish, and Stockfish
research ledgers. Source-specific documents remain the technical specification
for each experiment, but their local ordering does not override this file. On
2026-08-10 the owner moved the reviewed Stockfish blue-Fishtest pool to the
front of the queue, explicitly skipped SF-B01, stopped the inconclusive full
Y007, SF-B02, SF-B03, and SF-B13 tests, and then selected SF-B14 next. The
older cross-project queue is retained below it.

## Promotion contract

- Run exactly one engine candidate at a time. Research and verification may be
  prepared while Elo is active, but no second candidate may consume workers or
  alter the active baseline.
- `v0.3.0-nnue-thp` is the owner-grandfathered baseline. Every post-v0.3
  promotion must pass this contract; historical fixed-game positive estimates
  do not qualify.
- Do not change the NNUE architecture, feature indices, layer dimensions,
  quantization, network bytes, Xiangqi rules, legal moves, repetition/
  perpetual-check behavior, cannon geometry, flying-general behavior, or move
  encoding.
- Before Elo, compare against both `v1.0.0` and the accepted baseline on
  Windows and Ubuntu: legal-root maps, perft, rule cases, raw NNUE/static
  scores, network identity, assertions, crashes, and searched-bestmove
  legality must pass. Implementation-only candidates additionally require
  deterministic search identity; strength candidates may deliberately alter
  search choices but not game rules or evaluation-network semantics.
- Build independent baseline and candidate binaries with AVX2 and PGO:
  clang-cl on Windows and native LLVM/clang on every Linux CPU family. Run only
  launch/signature/hash/crash smoke; comparative NPS benchmarking is retired.
- Gate 1 is paired STC `SPRT(0.0, 2.0)`. Only its upper-bound crossing advances
  to an independent-opening-seed paired LTC `SPRT(0.5, 2.5)`. Both use
  pentanomial normalized-Elo LLR, `alpha=beta=0.05`, and bounds
  `+/-ln(19) = +/-2.944438979`. The upper bound passes, the lower bound fails,
  and an administrative cap between bounds is inconclusive.
- Drain all assigned tasks and verify exact game/pair counts, PGNs,
  pentanomial totals, crashes, time losses, binary/network/book hashes, opening
  colors, and worker manifests before advancing. Only an LTC upper crossing
  permits baseline promotion, commit, tag, release, and new Windows/Linux
  assets.
- Capacity ceiling: Windows 10 cores, Ubuntu `.7` 32, Ubuntu `.8` 64, Ubuntu
  `.55` 44, and Ubuntu `.66` 44: 194 physical cores total. Build independently
  on `.55` and `.66` with native LLVM even though both currently report the
  same Broadwell CPU family.

## Locked execution order

| Order | Candidate | Isolated experiment | Source record |
| ---: | --- | --- | --- |
| stopped | `Y007` | Owner-requested stop at an inconclusive STC result; no baseline effect. | `docs/yaneuraou-port-log.md` |
| skipped | `SF-B01` | Owner-requested stop at an inconclusive STC result; no baseline effect. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| stopped | `SF-B02` | Owner-requested stop at an inconclusive STC result; no baseline effect. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| stopped | `SF-B03` | Owner-requested stop at an inconclusive STC result; no baseline effect. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| stopped | `SF-B13` | Owner-requested stop at an inconclusive STC result; no baseline effect. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| active | `SF-B14` | Suppress the quiet-pruning block whenever the search follows the prior PV. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| B004-B012 | `SF-B04` through `SF-B12` | Deferred by owner while SF-B14 runs; resume exactly one at a time in numeric order. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| B015-B031 | `SF-B15` through `SF-B31` | Remaining Tier-B blue candidates in numeric order; run sibling SF-B31 only if SF-B30 fails. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| B032-B033 | `SF-B32` through `SF-B33` | Tier-C blue candidates in numeric order. | `docs/stockfish-blue-tests-2025-2026-plan.md` |

Every blue candidate starts from the latest accepted source. Initially that is
`v0.3.0-nnue-thp`; after an STC-upper and LTC-upper pass, its promoted release
becomes the baseline for the next row. No candidate may be promoted on an STC
result alone.

The previous Y015 run `6a79571cdcb6ab381712a7cf` was stopped at the owner's
request after 5,832 games with LLR `-0.171829659`, between both boundaries. It
is recorded as inconclusive and is not an accepted baseline or an active run.

The Y007 retest `6a7995332e0aebc469f20885` was likewise stopped at the
owner's request between both boundaries. It is retired as `inconclusive` at
8,238 games / 4,119 pairs, W/L/D `2829/2827/2582`, pentanomial
`[15,729,2634,721,20]`, and LLR `-0.110296180`; crashes and time losses are
zero. It has no baseline, source, tag, or release effect.

SF-B02 run `6a79a8423272cca3362ea289` was stopped at the owner's request
between both boundaries and retired as `inconclusive` at 1,860 games / 930
pairs, W/L/D `629/660/571`, pentanomial `[3,172,614,135,6]`, and LLR
`-0.444776368`; crashes and time losses are zero. It has no baseline, source,
tag, or release effect.

SF-B03 passed the full pre-Elo gameplay audit and its first three artifact
audits, but the owner stopped its STC between both boundaries. Run
[`6a79b32fbbd5154d9e7e405d`](http://192.168.100.7:6543/tests/view/6a79b32fbbd5154d9e7e405d)
is retired as `inconclusive` at 3,468 games / 1,734 pairs, W/L/D
`1160/1198/1110`, pentanomial `[8,349,1057,313,7]`, and LLR
`-0.536779417`; crashes and time losses are zero, and active/pending work is
drained. It has no baseline, source, tag, or release effect.

SF-B13 passed the full pre-Elo gameplay audit on Windows PGO, Ubuntu PGO,
Xeon-native PGO, and Xeon assertions + UBSan: all four reports contain 644
cases, zero failures, and exact legal-map, perft, repetition, raw/final NNUE,
and network-architecture agreement. Its first STC attempt
[`6a79be7308efa0ef6f2f7baa`](http://192.168.100.7:6543/tests/view/6a79be7308efa0ef6f2f7baa)
was discarded in full as `invalid` after a strict artifact audit exposed a
benign but unacceptable variantfishtest stderr-close thread race. The harness
fix passed unit, match, and 256-process teardown stress tests. Clean R2 run
[`6a79c533e53e34859ff2d9c8`](http://192.168.100.7:6543/tests/view/6a79c533e53e34859ff2d9c8)
was stopped at the owner's request and atomically retired as `inconclusive`.
Terminal statistics are 13,878 games / 6,939 pairs, W/L/D
`4772/4777/4329`, pentanomial `[39,1346,4174,1341,39]`, and LLR
`-0.291852887`; crashes and time losses are zero, and server work is drained
(`active=0`, `pending=0`). It does not authorize LTC and has no baseline,
source, tag, or release effect.

SF-B14 is isolated from `v0.3.0-nnue-thp` as a one-line search-policy change.
The replacement Xfish-generated book is frozen at 132,503 unique positions
with exact UHO Lichess draw component `D=481..519`; its manifest and
independent reconstruction audit pass. The 644-position gameplay gate passes
on Windows and three Linux build modes. Live STC run
[`6a7a5dc6bcdd59842df8ba5f`](http://192.168.100.7:6543/tests/view/6a7a5dc6bcdd59842df8ba5f)
uses official pentanomial normalized-Elo `SPRT(0.0,2.0)` and 194 pinned
physical cores across Windows, `.7`, `.8`, `.55`, and `.66`. SF-B14 remains
uncommitted and cannot enter LTC or affect the baseline unless STC reaches the
upper LLR boundary with a clean final audit.

## Deferred queue after the blue pool

| Order | Candidate | Isolated experiment | Source record |
| ---: | --- | --- | --- |
| D001 | `Y004` | Correct precomputed checker-update fast path without reading stale state. | `docs/yaneuraou-port-log.md` |
| D002 | `CFS01` | Restore least-value-first knight/cannon ordering in Xiangqi SEE; requires the dedicated exhaustive capture oracle. | `docs/cfish-port-plan.md` |
| D003 | `SF-X01` | Share continuation-correction history at the tested ownership scope. | `docs/stockfish-fishtest-2025-2026-plan.md` |
| D004 | `SF-X02` | Apply the tested null-move ancestor cap. | `docs/stockfish-fishtest-2025-2026-plan.md` |
| D005 | `Y007-R1` | Destination-only split-half bitboard iteration. | `docs/yaneuraou-port-log.md` |
| D006 | `Y009` | POPCNT `more_than_one()` for the two-word Xiangqi bitboard. | `docs/yaneuraou-port-log.md` |
| D007 | `Y012` | Split-word global bitboard pop while preserving ascending square order. | `docs/yaneuraou-port-log.md` |
| stopped above | `Y007` | Broader move-generation split-half iteration. | `docs/yaneuraou-port-log.md` |
| D009 | `Y011` | Directional SEE x-ray refresh with Xiangqi cannon/horse/flying-general property checks. | `docs/yaneuraou-port-log.md` |
| D010 | `Y014` | Shared rook/cannon magic occupancy index. | `docs/yaneuraou-port-log.md` |
| D011 | `Y013-R` | Direct half-ray rook attacks. | `docs/yaneuraou-port-log.md` |
| D012 | `Y013-R2` | Compact rank table plus direct file rays. | `docs/yaneuraou-port-log.md` |
| D013 | `Y013-R3` | Packed rook ray lengths. | `docs/yaneuraou-port-log.md` |

## Queue transition rule

At every terminal decision, record the complete statistics and integrity audit,
then re-audit the next row against the new accepted source. If it is already
present, reverted upstream, unsafe for Xiangqi, dependent on an NNUE network
change, or made structurally obsolete by an earlier acceptance, mark it with a
durable reason and advance without building or testing it. A failed candidate
is removed completely before the next candidate worktree is based.

Newly discovered ideas are appended unless they fix a proven correctness issue
or the owner explicitly reprioritizes them. Reordering never changes a running
candidate's predeclared SPRT hypotheses, seed, binaries, or baseline.
