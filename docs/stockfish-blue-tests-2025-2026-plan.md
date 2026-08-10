# Stockfish blue Fishtest port queue (2025-2026)

This plan is derived from the exhaustive blue-run inventory in
`docs/stockfish-blue-tests-2025-2026.md` and its generated JSON ledger at
`build/audit/stockfish-blue-tests-2025-2026.json`.

## Meaning and coverage

The current official Fishtest UI colors an accepted SPRT blue when
`elo0 + elo1 < 0`, normally normalized-Elo `[-1.75, +0.25]`. Blue therefore
means **accepted as non-regressing under those bounds**; it does not prove a
positive Elo gain.

The audit covers every successful run finished from `2025-01-01T00:00:00Z`
through, but not including, `2027-01-01T00:00:00Z`, observed on 2026-08-10:

- 2,431 successful finished runs read from the public API;
- 723 blue accepted runs, including all 118 whose observed W/L was not
  positive;
- 251 official Stockfish commits directly citing at least one blue run;
- 238 distinct uncited source objects from contributor forks;
- 74 fork objects survived the automatic relevance filter and received a
  source-level review below.

The only unblocked official commit was `e093339c`, which merely replaces the
remove/put sequence used to undo a chess pawn promotion with `swap_piece()`.
Xiangqi has no promotion, so it is rejected. All other directly cited official
commits are already in xfish, already recorded in a durable ledger, NNUE
architecture/network changes, infrastructure-only changes, reverts, or
chess-specific changes.

## Execution order

The authoritative inter-project order is `docs/experiment-queue.md`. By owner
direction on 2026-08-10, this blue pool now runs first: start with SF-B01, then
process exactly one row at a time in Tier A, Tier B, and Tier C numeric order.
The initial accepted baseline is `v0.3.0-nnue-thp`. A later row is always
rebased on the latest candidate that passed both STC and LTC; if an earlier
acceptance makes a row identical or structurally obsolete, record it as
superseded and skip it. The deferred YaneuraOu, Cfish, and earlier Stockfish
queue resumes only after this pool is exhausted or the owner reprioritizes it.

### Tier A: clean, portable search or performance changes

| Queue | Source | Isolated idea | Upstream blue evidence |
| --- | --- | --- | --- |
| SF-B01 | [`29dc894d`](https://github.com/FauziAkram/Stockfish/commit/29dc894d1bfd1fbc397ec55482bffa573e9fc7de) | Store the raw scaled LMR reduction in the stack and compare it in the same units. | 2 runs, aggregate W-L `+318` |
| SF-B02 | [`e8d83f5a`](https://github.com/jake-ciolek/Stockfish/commit/e8d83f5a8169d82be33510fa9ef2dc15ed5c19b1) | Remove the late TT prefetch performed after `do_move`; retain and test xfish's earlier speculative prefetch separately. | 2 runs, `+372` |
| SF-B03 | [`22133a72`](https://github.com/kennethlee33/Stockfish/commit/22133a7241e8d4e83af8b7fc32aa7d9d8f4030a9) | Simplify the singular-beta PV term from `ttPv && !PvNode` to `ttPv`. | 2 runs, `+449` |
| SF-B04 | [`75cb3711`](https://github.com/maximmasiutin/Stockfish/commit/75cb3711f68b32d5eb08fd639d5d538ae499b6f0) | Use signed, rather than absolute, correction history in singular-extension margins. | 1 run, `+233` |
| SF-B05 | [`f0d24d4b`](https://github.com/pb00068/Stockfish/commit/f0d24d4b079420a4dae752165c797420a4a92263) | Cap multiple extensions for bouncing/triangulation move patterns to contain search explosions. | 1 run, `+105` |
| SF-B06 | [`9019d35f`](https://github.com/FauziAkram/Stockfish/commit/9019d35fb7eeae4f444fc4432b5de006284a2f69) | Remove the `improving` dependency from the main ProbCut margin. | 1 run, `+189` |
| SF-B07 | [`103bb2c4`](https://github.com/FauziAkram/Stockfish/commit/103bb2c48e291149ca2846dc29f7c75dbd422c34) | Remove the correction-value adjustment from LMR. | 1 run, `+131` |
| SF-B08 | [`2e0c2964`](https://github.com/maximmasiutin/Stockfish/commit/2e0c2964db379812ba19cfa247543bab792bc2d1) | Update all configured continuation histories while in check instead of stopping after distance two. | 1 run, `+59` |
| SF-B09 | [`640da5a3`](https://github.com/maximmasiutin/Stockfish/commit/640da5a3cbdddf7b6b911a99bb42e647e33f08e8) | Remove the root-depth term from the singular double-extension margin. | 2 runs, `+301` |
| SF-B10 | [`adcd7b97`](https://github.com/Ergodice/Stockfish/commit/adcd7b97ceef15392c2ff34dd285c63e1158f282) | Scale correction history once in `correction_value()` instead of repeatedly dividing at consumers. | 1 run, `+203` |
| SF-B11 | [`f26b3f88`](https://github.com/xu-shawn/Stockfish/commit/f26b3f88b5deec2aecc2e9142d85655b3ea8d5ab) | Permit the reduced LMR search to reach depth zero and remove the redundant depth guard. | 1 run, `+78` |
| SF-B12 | [`4d2cfbbf`](https://github.com/FauziAkram/Stockfish/commit/4d2cfbbf539533a9c4474cb499f9c1fabc397d80) | Do not increment next-ply `cutoffCnt` solely because the current node is PV. | 1 run, `+207` |

### Tier B: portable strength changes with more tuning interaction

| Queue | Source | Isolated idea | Upstream blue evidence |
| --- | --- | --- | --- |
| SF-B13 | [`16739297`](https://github.com/FauziAkram/Stockfish/commit/16739297861f866a09f3059e8899f5f8189967e3) | Apply the deep-TT LMR bonus only at cut nodes and collapse its coefficient. | 1 run, `+134` |
| SF-B14 | [`96451ce9`](https://github.com/FauziAkram/Stockfish/commit/96451ce9b605a07ac0a95207862780408bd0510a) | Tighten the quiet-pruning guard to depend only on `followPV`. | 1 run, `+229` |
| SF-B15 | [`1f8487d0`](https://github.com/rn5f107s2/Stockfish/commit/1f8487d07b967ddd74e0d6bc0862a6c6fdd46fae) | Use a uniform `-2` negative extension when a TT move is not singular. | 1 run, `+25` |
| SF-B16 | [`8d9719c6`](https://github.com/FauziAkram/Stockfish/commit/8d9719c696ff38eb46e353cfb70c8fc4535d937b) | Simplify next-ply fail-high count thresholds in LMR. | 1 run, `+230` |
| SF-B17 | [`65a2c208`](https://github.com/FauziAkram/Stockfish/commit/65a2c208f76cedececf5c8bc58f7869838e2064e) | Remove the decisive-score special case when extending a TT move above qsearch. | 1 run, `+134` |
| SF-B18 | [`a8123bc2`](https://github.com/FauziAkram/Stockfish/commit/a8123bc224d57eb4b482aae8a9a43c9ca885d2b3) | Stop negative updates to pawn history in the tested quiet-history path. | 1 run, `+226` |
| SF-B19 | [`bff6d3a0`](https://github.com/FauziAkram/Stockfish/commit/bff6d3a08afbac55a7eeb0b5ae3265e599f92db6) | Remove the node-effort threshold from the high-best-move time reduction. | 1 run, `+216` |
| SF-B20 | [`4e1f4fad`](https://github.com/ces42/Stockfish/commit/4e1f4fad18ddd974041083c5e182820ccc0ab500) | Do not model the move-rule counter in speculative TT prefetch keys; adapt `rule50` only to xfish's `rule60` representation, without changing real keys. | 1 run, `+99` |
| SF-B21 | [`24a6b13e`](https://github.com/pb00068/Stockfish/commit/24a6b13e7d211703dbac83bf2c8f0053d56d560d) | Replace high-depth NMP verification with the tested double-null form. | 1 run, `+201` |
| SF-B22 | [`6d0fd92f`](https://github.com/daniel-monroe/Stockfish/commit/6d0fd92fd66cf5da2bef2bad3fbb8659b7e4ef9a) | Test a constant null-move reduction instead of the dynamic depth term. | 1 run, `+117` |
| SF-B23 | [`ec8c7bdb`](https://github.com/FauziAkram/Stockfish/commit/ec8c7bdb275667047069bb352ad832d7bbb38132) | Penalize TT-move history only when the best move was not the TT move. | 1 run, `+212` |
| SF-B24 | [`4a989a8c`](https://github.com/joergoster/Stockfish/commit/4a989a8cfdd4e8e761cc850e4db8acc9c5ff7e92) | Remove random equal-score best-move switching; this is distinct from the failed mask `15 -> 14` experiment. | 2 runs, `+87` |
| SF-B25 | [`05cde714`](https://github.com/FauziAkram/Stockfish/commit/05cde714db610e0fe5b50c33a53f28e79be5b382) | Remove the extra previous-ply continuation-history refutation penalty. | 1 run, `+195` |
| SF-B26 | [`083b58d8`](https://github.com/Ergodice/Stockfish/commit/083b58d8c7adbe783890ce6d4f88fd9179a0a89f) | Recompute `ttPv` during excluded-move searches instead of preserving its old value. | 1 run, `+193` |
| SF-B27 | [`c108b246`](https://github.com/xu-shawn/Stockfish/commit/c108b246be68d4f4394874e413899ced6f37f81b) | Try depth-independent best-move history bonus/malus. | 1 run, `+211` |
| SF-B28 | [`bdde8406`](https://github.com/FauziAkram/Stockfish/commit/bdde840651e671a81ec4ee94693b3ac0a13b6ef4) | Remove the upper-depth cap on reducing remaining moves after an alpha improvement. | 2 runs, `+296` |
| SF-B29 | [`f56721c4`](https://github.com/FauziAkram/Stockfish/commit/f56721c4a1dd3316b234bff718d50736240c54b2) | Replace the singular double-extension margin formula with the tested constant form. | 1 run, `+192` |
| SF-B30 | [`61f6262c`](https://github.com/FauziAkram/Stockfish/commit/61f6262c201efadb50f9a49aeff40d1cc459fdf4) | Limit the TT-capture/non-capture LMR penalty to depth below ten. | 1 run, `+215` |
| SF-B31 | [`f9b41b8a`](https://github.com/FauziAkram/Stockfish/commit/f9b41b8a859c7e7bcb75f72072f0b026b297118e) | Sibling of SF-B30 with a depth-below-eight cutoff; test only if SF-B30 fails. | 1 run, `+140` |

### Tier C: low-confidence or platform-limited non-regression ideas

| Queue | Source | Isolated idea | Upstream blue evidence |
| --- | --- | --- | --- |
| SF-B32 | [`ceecb086`](https://github.com/FauziAkram/Stockfish/commit/ceecb086fcb8e6d8fbc9d2a388f4816f4fb97a7b) | Remove previous-time-reduction feedback from the time manager. | 1 run, observed W-L `+1` |
| SF-B33 | [`b277d3ec`](https://github.com/lemteay/Stockfish/commit/b277d3ecafa6bcff29adf94ab1073a4a707b0140) | Revisit the Clang inline-threshold change under the later no-NPS policy; Linux already has it, so isolate only the missing clang-cl build path. | 1 run, `+114`; platform-limited |

## Reviewed but not queued

All 41 remaining rows from the 74-object source-review pool have a durable
disposition:

| Count | Source objects | Decision |
| ---: | --- | --- |
| 1 | `b38e604e` | Quarantine: submitter explicitly marked the only run as having an apparently wrong bench. |
| 2 | `0d5d1f14`, `166643a4` | Reject: change final evaluation scaling and fail the required NNUE/static-score identity check. |
| 7 | `e71db0e3`, `0e3d15ec`, `f1e13d03`, `6cd5828d`, `9f952304`, `9e74bc93`, `34a1296c` | Reject: depend on chess stalemate, pawn double-push/promotion/castling, rule-50, or chess repetition semantics. |
| 5 | `d899e696`, `39f3a755`, `44d75cc7`, `dd4bfe53`, `370fcb0b` | Reject from Elo queue: PGO-build duration, UCI reporting, or retrograde-analysis/UI behavior rather than an engine-strength patch. |
| 9 | `65134163`, `a95991ae`, `9b75ec65`, `3cc10218`, `cfcf7067`, `4a0cca47`, `d7e2a3de`, `9fa8cec4`, `da7e1ae1` | Reject: non-positive observed score and no clean independent runtime/NFC rationale. |
| 12 | `712db16c`, `985de873`, `2bbaa1a6`, `aec74528`, `e0ac2aa6`, `33d45a21`, `a6d14c21`, `54e1efad`, `0d567963`, `a01b43c6`, `4a5e0e04`, `699c66aa` | Already present or superseded by the current xfish end state. |
| 5 | `1122503d`, `ca98f789`, `92f2ed24`, `e39d503d`, `c6f7d7a2` | Reject: removes xfish's live anti-shuffle safeguard, targets an obsolete accumulator/qsearch path, or bundles inseparable refactoring and strength changes. |

## Per-candidate protocol

1. Use one ignored worktree based on the latest accepted baseline and apply
   exactly one source idea. Record the source SHA, exact upstream test IDs,
   minimal adaptation, and patch identity before building.
2. Never change the NNUE architecture, dimensions, feature numbering, weights,
   network file, Xiangqi legal generation, flying-general/cannon rules, or
   perpetual-check/chase adjudication.
3. Run `scripts/verify-gameplay.py` against both v1.0.0 and the latest accepted
   baseline on Windows and Ubuntu. Require identical network hashes, raw NNUE
   and final static evaluation, legal maps, perft, and rule adjudication. A
   strength patch may change PV/search signatures; a claimed NFC/performance
   patch must remain search-identical as well.
4. Build independent baseline and candidate binaries with AVX2, Full LTO and
   PGO using clang-cl on Windows and native clang on Linux. Do only signature,
   hash, launch and crash smokes; do not run a comparative NPS benchmark.
5. Run paired Xiangqi STC `10+0.1`, Threads=1, Hash=16 with official
   pentanomial normalized-Elo `SPRT(0.0, 2.0)`, `alpha=beta=0.05`. Reject at
   LLR `<= -ln(19)`; continue only after LLR `>= +ln(19)` with zero integrity
   errors, crashes, time losses, or missing pairs.
6. After a valid STC pass, drain all STC tasks and start an independent-seed
   LTC `60+0.6` with `SPRT(0.5, 2.5)` and the same boundaries. A safety-cap
   result between the boundaries is inconclusive, never a pass.
7. Only a valid LTC upper-bound pass may create a commit, tag, release assets,
   or new baseline. Preserve all PGNs, opening indices, W/L/D, pentanomial,
   LLR history, compiler/PGO provenance, CPU affinity, and hashes.
