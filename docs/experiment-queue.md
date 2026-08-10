# Xfish authoritative experiment queue

Updated: 2026-08-10.

This is the single execution order across the YaneuraOu, Cfish, and Stockfish
research ledgers. Source-specific documents remain the technical specification
for each experiment, but their local ordering does not override this file. On
2026-08-10 the owner moved the reviewed Stockfish blue-Fishtest pool to the
front of the queue; the older cross-project queue is retained below it.

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
- Capacity ceiling: Windows 10 cores, Ubuntu `.7` 32, Ubuntu `.8` 64, and
  Ubuntu `.55` 44. Use native `.55` builds because its CPU family differs.

## Locked execution order

| Order | Candidate | Isolated experiment | Source record |
| ---: | --- | --- | --- |
| active | `SF-B01` | Store the raw scaled LMR reduction in the stack and compare it in the same units. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| B002-B012 | `SF-B02` through `SF-B12` | Remaining Tier-A blue candidates, exactly one at a time in numeric order. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| B013-B031 | `SF-B13` through `SF-B31` | Tier-B blue candidates in numeric order; run sibling SF-B31 only if SF-B30 fails. | `docs/stockfish-blue-tests-2025-2026-plan.md` |
| B032-B033 | `SF-B32` through `SF-B33` | Tier-C blue candidates in numeric order. | `docs/stockfish-blue-tests-2025-2026-plan.md` |

Every blue candidate starts from the latest accepted source. Initially that is
`v0.3.0-nnue-thp`; after an STC-upper and LTC-upper pass, its promoted release
becomes the baseline for the next row. No candidate may be promoted on an STC
result alone.

The previous Y015 run `6a79571cdcb6ab381712a7cf` was stopped at the owner's
request after 5,832 games with LLR `-0.171829659`, between both boundaries. It
is recorded as inconclusive and is not an accepted baseline or an active run.

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
| D008 | `Y007` | Broader move-generation split-half iteration. | `docs/yaneuraou-port-log.md` |
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
