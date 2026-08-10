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

## Execution ledger

### SF-B01 - raw scaled prior reduction (skipped; inconclusive)

- Accepted baseline: `v0.3.0-nnue-thp` at
  `1699e6ba6df744f83951c66bfd5832647d65e41d`.
- The upstream experiment is the two-commit comparison
  `253aaefbc03fab2e0c2a0ed83c0abf0ee9be4f92..29dc894d1bfd1fbc397ec55482bffa573e9fc7de`:
  parent `f80e489` stores the raw scaled LMR value and changes the hindsight
  thresholds from `3/2` to `3200/2000`; `29dc894d` changes the old IIR guard
  from `<=3` to `<=3072`.
- Upstream evidence was checked live: STC run
  [`697b9de65f56030af97b54ac`](https://tests.stockfishchess.org/tests/view/697b9de65f56030af97b54ac)
  accepted at LLR `2.946535` after 99,968 games, and LTC run
  [`697cbee75f56030af97b56d6`](https://tests.stockfishchess.org/tests/view/697cbee75f56030af97b56d6)
  accepted at LLR `2.941455` after 73,326 games under upstream's blue
  `[-1.75, 0.25]` non-regression bounds.
- The xfish adaptation changes only three live lines in `src/search.cpp`: it
  stores `r` in `Stack::reduction`, compares it with `3200/2000`, and retains
  xfish's Xiangqi-tuned static-evaluation threshold `193`. The old IIR guard is
  not ported because current xfish uses a later `followPV` IIR formulation that
  no longer reads `priorReduction`; restoring the old guard would mix a
  superseded search policy into this candidate.
- Normalized full-index patch SHA-256:
  `1f46dde6a57f84e78bb33bb716ea0929aebfef56f61a82e331d5ffd316972683`.
- Frozen candidate revision used by xfishtest:
  `7e90a11d58de2a183661c6fbd88092a8a2262925`; candidate `search.cpp`
  SHA-256 on Windows, `.7`, and `.55`:
  `9e9ac7bcb2086c0f7488b8c93d8540d692a84f4724f22026bac93510353197c5`.
- Native AVX2 Full-LTO PGO builds are frozen independently for each CPU:
  Windows clang-cl 19.1.5 SHA-256 `9ff984261dbe38635afb4a230b096d91af69d958af70ce936ba78a73d92860d8`;
  Ubuntu `.7/.8` clang 22.1.8 SHA-256
  `80787af0f8eb6e6c5b1fb0f139062e7528ac93024c0ca3c869aaef3eccf50745`;
  Ubuntu `.55` native clang 22.1.2 SHA-256
  `2d602df0e314c8b471ddfae6f760774cd25716513b8e3b3646942dbeb1e5dd22`.
  Candidate bench signature is `2188749`; frozen v0.3.0 is `2483430` on all
  three platforms.
- Gameplay verification passed before Elo testing against both v1.0.0 and
  accepted v0.3.0: `644/644`, zero failures, on Windows PGO, Ubuntu `.7` PGO,
  Ubuntu `.55` native PGO, and a separate `.55` assertions + UBSan build.
  Report SHA-256 values are respectively
  `7b84485f5a7650ceeae355c5c874a9ec06e26a9ea9dd2ae5873752a1fe29f2eb`,
  `8f9fdefab7868a4c8f89fe92051ed541100af620c6fee98034061936c32fcbbd`,
  `620ef3f4fb8715d4121b8a099b64278fe88771f3e3a658a42107d2c68e78123c`,
  and `368047161f4b6273af9f171d46a42c0b7f34da88f36156aaef578099a3c548d6`.
  The suite covered 512 frozen-book roots plus derived playout/repetition
  cases, legal maps, perft, raw/final NNUE evaluation, network architecture,
  and best-move legality. All 67 search cases changed as expected for an
  active strength patch, while every rule/evaluation invariant matched.
- STC run
  [`6a7980eb7747bc9087defc6e`](http://192.168.100.7:6543/tests/view/6a7980eb7747bc9087defc6e)
  started only after that verification. It uses pentanomial normalized-Elo
  SPRT `(0.0, 2.0)`, `alpha=beta=0.05`, LLR bounds `+/-2.944439`, `10+0.1`,
  Threads `1`, Hash `16`, 200-game chunks, the frozen Xfish UHO v1 book and
  seed `xfish-uho-3mvs-w65-85-v1-sf-b01-stc-20260810`. Nine pinned workers
  advertise 150 physical cores: Windows 10, `.7` 32, `.8` 64, and `.55` 44.
- At the owner's request, STC was stopped and retired before either SPRT
  boundary so Y007 could be retested. Terminal run state is `inconclusive` at
  5,928 games / 2,964 pairs, W/L/D `2017/2060/1851`, pentanomial
  `[19,570,1821,543,11]`, and LLR `-0.641199995`; crashes and time losses are
  both zero. All assigned tasks drained (`active=0`, `pending=0`). SF-B01 is
  skipped, does not authorize LTC, and has no baseline, source, tag, or release
  effect.

### SF-B02 - remove the late TT prefetch (stopped; inconclusive)

- Accepted baseline remains `v0.3.0-nnue-thp` at
  `1699e6ba6df744f83951c66bfd5832647d65e41d`. The isolated source idea is
  contributor commit `e8d83f5a8169d82be33510fa9ef2dc15ed5c19b1`: remove the
  late TT prefetch in `Position::do_move()` while retaining xfish's earlier
  speculative prefetch in `Search::Worker::do_move()`.
- The contributor fork is no longer available, so the exact two-line deletion
  was recovered from the immutable Fishtest source snapshot and checked against
  both upstream runs. Run `696a0f72fa8ace4d6d448177` accepted at LLR
  `2.931778` after 31,072 games, W/L/D `8128/7910/15034`, pentanomial
  `[83,3326,8508,3528,91]`; the 8-thread SMP follow-up
  `696cb5da942b47defb5a9401` accepted at LLR `2.939626` after 89,744 games,
  W/L/D `23069/22915/43760`, pentanomial
  `[101,10107,24308,10249,107]`. Both used upstream's blue non-regression
  bounds and reported zero crashes; the SMP run recorded four time losses.
- The xfish patch changes only `src/position.cpp` by deleting the two-line
  conditional prefetch after the move key is finalized. Normalized full-index
  patch SHA-256 is
  `a22eebd2c57431f70616d7034989796fb66503923a51d8a3d1d4b7a75bb6adbe`;
  the frozen synthetic candidate revision is
  `d2e187eb3c161e546fbbab8c7ebb8e0bfaef9787`. Candidate `position.cpp` has
  git blob `e9e69819a93b6770a6982d4946ad294d571ebce7` and SHA-256
  `ec7ad1adcc16582bd994de3f498202b6dbf1b287a4c932e49c254ce8a878281a`
  on Windows, `.7`, and `.55`.
- Native AVX2 Full-LTO PGO builds retain bench signature `2483430`. Candidate
  SHA-256 is
  `b736ae0cdc720b60f62256ac63b75951c97167a4da591d0515063290bd748792`
  for Windows clang-cl 19,
  `93d3cf331b4bd03e76fe2e702ee7e5df5a2b44ac948437bc9d8b4825f674763a`
  for Ubuntu `.7/.8` clang 22.1.8, and
  `5390f73613e0b2e4451a2ec36587a46baa6dd6457efda52e2db22088d3f6b699`
  for the independently built `.55` clang 22.1.2 CPU family. The separate
  `.55` assertions + UBSan binary has SHA-256
  `b8d9787b8954c12c3db08394659ef486c74c466dca2ac92eb67f8e8b91b67274`.
- Before Elo, strict `--expect-search-identical` gameplay verification passed
  `644/644` cases with zero failures on Windows PGO, Ubuntu `.7` PGO, `.55`
  native PGO, and `.55` assertions + UBSan. Report SHA-256 values are
  respectively
  `00a4d24b90f98addd2a872ed54edfce0eef414833882b4985a7020689ff4c21`,
  `077db5c47d02bb992c26cfdd4d9c13a7f59b3f9ee50ed243a35eac2a2e7d18f9`,
  `4883205b349c52a3f82fcdcedb44275f585ee8a07d4df81ae4a9b0221912336`,
  and `6cb30b6b04245463929bb5dfec226912771f134fb73952913dcdaa8385bef2d1`.
  Legal maps, perft, repetition behavior, raw/final NNUE evaluation, network
  architecture, depth-7 search result, PV, score, and node count all match the
  accepted baseline; no rule, gameplay, evaluation, or search-semantic change
  was found.
- STC run
  [`6a79a8423272cca3362ea289`](http://192.168.100.7:6543/tests/view/6a79a8423272cca3362ea289)
  started only after verification. It uses pentanomial normalized-Elo
  `SPRT(0.0, 2.0)`, `alpha=beta=0.05`, bounds `+/-2.944438979`, `10+0.1`,
  Threads `1`, Hash `16`, 200-game chunks, Xfish UHO v1 book SHA-256
  `5ede082489580fb6aeb8c06c3eb34f72a916c5dbb7ee621b350b835dbdc48b0f`,
  and seed `xfish-uho-3mvs-w65-85-v1-sf-b02-stc-20260810`. Nine pinned
  workers advertise 150 physical cores: Windows 10, `.7` 32, `.8` 64, and
  `.55` 44. LTC remains forbidden unless STC reaches the upper boundary and
  the complete integrity audit is clean.
- The first three completed chunks were independently audited with
  `scripts/audit-xfishtest-task.py` SHA-256
  `16ec0b54e9331d8949889da84d677ed559c4112021765856ddb541d69de5efad`.
  Tasks 0 and 1 on `.8` and task 2 on `.7` each pass all 100 paired openings /
  200 games: contiguous opening offsets `0/100/200`, 100 unique FEN hashes,
  exact revision/binary/NNUE identities, two color-reversed Xiangqi games per
  pair, Hash 16, Threads 1, zero time losses, and 300 complete artifacts.
  Recomputed W/L/D and pentanomial exactly match the server: task 0 is
  `66/72/62` with `[1,19,65,15,0]`; task 1 is `72/70/58` with
  `[0,17,65,17,1]`; task 2 is `68/65/67` with `[1,17,62,18,2]`. Audit-report
  SHA-256 values are
  `d025b47d861cd48733eb169ca8492d86c0d0acee1af7b9cb48707d410261f2c8`,
  `b3d5ee8c2f955422c2d4e97a3a396051700e019ae523b9f6937876b7c16bca19`,
  and `f8955cf92e25bb31139a275c04a06813ad4a5be0f9e251e1fda4cc753d05db40`;
  their complete artifact-manifest hashes are respectively
  `b9b39b231243036073dccca27483570ef52188b32f0cf7f9e0e07500947f03fa`,
  `e25047fbcc57612ad0e12cc98135de70fd8cb9fc42eb31ed3a84e6e101ba59f7`,
  and `e492b517f9a30775eb325e1eb71ed0c03de9238e38da5b51dcddd4d8faa87e4b`.
- At the owner's request, STC was stopped before either boundary and the run
  was atomically retired as `inconclusive` with reason
  `owner-requested-stop-SF-B02-continue-SF-B03`. Terminal statistics are 1,860
  games / 930 pairs, W/L/D `629/660/571`, pentanomial
  `[3,172,614,135,6]`, and LLR `-0.444776368`; crashes and time losses are
  both zero, and server work is drained (`active=0`, `pending=0`). SF-B02 does
  not authorize LTC and has no baseline, source, tag, or release effect.

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
