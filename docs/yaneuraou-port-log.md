# YaneuraOu optimization port log

This log tracks ideas audited from the official YaneuraOu Shogi engine and
tested as isolated xfish candidates. The reference checkout is pinned at
`33ccf1f907eb7184889fa23051243f81ab0bf973` (2026-08-05); the official remote
`master` was rechecked on 2026-08-10 and still pointed to this commit. The
2025-2026 upstream test-history audit is recorded separately in
`docs/yaneuraou-test-evidence-2025-2026.md`.

## Safety and acceptance policy

- Do not import Shogi rules, drops, promotions, repetition adjudication, move
  encoding, or board-layout assumptions.
- Do not change the NNUE architecture, feature numbering, dimensions, weights,
  or network file.
- Adapt one separable idea at a time on top of the accepted baseline. The
  owner-grandfathered active baseline is `v0.3.0-nnue-thp`; post-v0.3
  candidates must earn a new promotion under the SPRT policy below.
- Verify legal-root maps, depth-3 perft, repetition cases, raw NNUE, static
  evaluation, network architecture, and searched-bestmove legality against
  both `v0.1.0-baseline` and the accepted baseline on Windows and Ubuntu.
- NPS benchmarking is retired for every candidate. After the PGO AVX2 build
  and full gameplay/NNUE/rule verification, run only a short
  launch/signature/hash/crash smoke check before Elo testing. Incidental timing
  printed by signature smoke or worker calibration is not a candidate gate.
- Gate 1 is STC `SPRT(0.0, 2.0)`; only an upper-bound crossing advances to
  independent-seed LTC `SPRT(0.5, 2.5)`. Both use `alpha=beta=0.05`, paired
  pentanomial normalized-Elo LLR, and nominal bounds `+/-ln(19)`. Only an LTC
  upper-bound crossing permits commit, release, tag, or baseline promotion.
  Fixed-game results below remain historical evidence only.

## Direct-Elo retest queue for historical NPS rejections

Every safe YaneuraOu candidate rejected only by comparative NPS is reopened.
Y015 is first being re-qualified against `v0.3.0-nnue-thp`; after it reaches a
terminal SPRT decision, each entry below is isolated against the then-valid
baseline and follows the same STC-to-LTC sequence.

1. `Y004` - corrected precomputed checker update fast path (next candidate).
2. `Y007-R1` - destination-only split-half bitboard iteration.
3. `Y009` - POPCNT `more_than_one()`.
4. `Y012` - split-word global bitboard pop.
5. `Y007` - broader move-generation split-half iteration.
6. `Y011` - directional SEE ray refresh.
7. `Y014` - shared rook/cannon magic occupancy index.
8. `Y013-R` - direct half-ray rook attacks.
9. `Y013-R2` - compact rank table plus direct file rays.
10. `Y013-R3` - packed rook ray lengths.

This source-local order is incorporated into the authoritative cross-project
order in `docs/experiment-queue.md`; that master queue decides which family is
run next after Y015.

`Y003` is not reopened: its later audit found a stale/uninitialized
`StateInfo::blockersForKing` source, so it is unsafe independently of NPS and
is superseded by corrected `Y004`. `Y001`, `Y002`, and `Y006` are not in this
queue because they already reached an Elo gate and finished with a negative
point estimate. Already-present/audit-only ideas are likewise not candidates.

## Initial audit

- YaneuraOu's 81-square overlapping bitboard and Qugiy sliding attacks depend
  on its Shogi-specific layout. xfish already uses 90-square magic attack
  tables (with an optional PEXT build) and Xiangqi cannon geometry, so this is
  not a safe small port.
- Finny accumulator caches are already present in xfish and adapted to its
  king, mirror, and attack buckets.
- The current YaneuraOu accumulator tiling work is either AVX-512/SFNN-specific
  or equivalent to xfish's existing combined accumulator update path.
- The unsigned enum representation, relaxed load/store node counter, native
  plain bitboard storage, and early TT prefetch ideas are already present.
- Configurable two-entry TT clusters trade density for wider keys and have an
  upstream speed penalty versus the default cluster layout; no candidate was
  opened.
- Randomized repetition scoring was rejected before testing because Xiangqi's
  repetition, perpetual-check, and chase rules must remain authoritative.

## Candidate Y001 — exact one-ply mate probe in qsearch

- Source idea: YaneuraOu calls a specialized `Mate::mate_1ply()` at fresh
  qsearch nodes before static evaluation.
- Xiangqi adaptation: enumerate xfish pseudo-legal moves, retain only moves
  that are legal and give check, make each move with the existing `Position`
  code, and accept it only when no generated evasion passes xfish's existing
  legality test. No Shogi move/drop code is imported.
- Scope: 41 added lines in `src/search.cpp`; no changes to move generation,
  game rules, NNUE, network data, or UCI move encoding.
- Candidate identity: `6503d4a87e5a189af369c459b9fa06a0e42ffbc5`.
- Windows clang-cl 19 Full-LTO PGO AVX2 SHA-256:
  `6e3d2816defacc303bf776e04fa22ccaf5a4c81a355337201fba2a8bb82db490`.
- Ubuntu clang 22 Full-LTO PGO AVX2 SHA-256:
  `2dd567b5b34adc864f68e4157d0935ca1202395c847a76f46f7ae485bb72bfe9`.
- Both binaries produce depth-13 bench signature `2400903`; the accepted
  baseline signature is `2483430`.
- Verification passed `132/132` cases on Windows, `132/132` on Ubuntu, and a
  deeper `324/324` Ubuntu suite at search depth 8. Report SHA-256 values are
  `2ff134d024f4cd13a58ec0c65d7b358de01568cc5c8a1b30f97bb3c78f38d2b8`,
  `0bb7f5ad246f4ec45071c19eac11d150552ce3cb5dcd1f79d81de6c35a8231a0`,
  and `d148089b45afe9232185f826ede08765b1334894e494fa129de63415d5e7d6a8`.
- Gate 2: 1,000-game paired run `6a77bd08530f0d7c1190cb00` completed with
  W/L/D `118/113/769`, pentanomial `[1,26,440,33,0]`, Elo
  `+1.7379 +/- 5.4035` (95%), LOS `73.58%`, zero crashes, and zero time losses.
- The positive point estimate advances Y001 to the independent 5,000-game
  confirmation run `6a77c4a09283eb3a37e6a4ae`, using opening seed
  `xfish-xiangqi-20260809-y001-gate3`. No baseline, commit, tag, or release
  change is allowed until that gate also completes positively.
- Gate 3 completed all 5,000 games with W/L/D `554/582/3864`, pentanomial
  `[0,181,2168,149,2]`, Elo `-1.9458 +/- 2.5028` (95%), LOS `6.38%`, zero
  crashes, and zero time losses. Strict aggregation verified 2,500 unique,
  contiguous paired openings (`0..2499`) and the expected Windows/Linux
  engine and network hashes. Report SHA-256 is
  `becf48547ceba701c04e1b23d171a8850026084875d3d1beda092ec5b693dc01`.
- Y001 is rejected because the required 5,000-game point estimate is
  negative. Its source remains isolated in the candidate worktree; master,
  the accepted baseline, tags, and releases are unchanged.

## Queued and rejected follow-up ideas

- Y002 is the next isolated strength candidate: YaneuraOu commit
  `db295b894df4fe685bcacdee434c0312d2d8826a` prevents capture moves from
  receiving double or triple singular extensions. The patch is five effective
  lines in search only and does not change move generation, rules, or NNUE.
- The adaptation is built from accepted baseline
  `1699e6ba6df744f83951c66bfd5832647d65e41d`; candidate identity is
  `f4f038fdecd687d88589ed907a2003febe1ac09c`. Windows clang-cl 19 and
  Ubuntu clang 22 Full-LTO PGO AVX2 binaries share bench signature `1968269`.
  Their SHA-256 values are
  `de6af8002faa3ed7f831d48746d6ef01ee8164ce1b9e17daac341f6767bb16d5`
  and `f3f8048eb9c31f172a011f99ffacbf9249836e6ba2df42c18e922764ab415c2e`.
- Gameplay verification passed `132/132` cases on Windows, `132/132` on
  Ubuntu, and the deeper `324/324` Ubuntu suite at search depth 8. A separate
  assertions-enabled Windows AVX2 build completed its depth-10 bench with
  `438851` nodes and no assertion or state failure.
- Gate 2 run `6a77e369deadefa8812ade52` completed all 1,000 games with W/L/D
  `113/126/761`, pentanomial `[2,38,431,29,0]`, Elo
  `-4.5162 +/- 5.8857` (95%), LOS `6.63%`, zero crashes, and zero time losses.
  Strict aggregation verified 500 unique, contiguous paired openings
  (`0..499`) and the expected Windows/Linux engine and network hashes. Report
  SHA-256 is
  `8ed2b202d79d0cb324b3d93bbb1c8acfa466e04819e3222ec591d29421546274`.
- Y002 is rejected at the 1,000-game gate because its Elo point estimate is
  negative. The 5,000-game confirmation is not run; master, baseline, tags,
  and releases remain unchanged.

## Candidate Y003 — conservative checker update fast path

- Source idea: YaneuraOu commit
  `fbaec111f08914073abd6962e97985516125be7d` updates the checking-piece
  bitboard incrementally in `do_move()` instead of rebuilding every attack
  class after each checking move.
- Xiangqi adaptation: use a narrow fast path only when the moved pawn, knight,
  cannon, or rook directly checks and the source square cannot uncover another
  checker. Discovered checks, hollow-cannon screens, and every ambiguous case
  retain the original full `checkers_to()` calculation. No move generation,
  rule, NNUE, feature, or network data changes are made. Candidate identity is
  `85fbd9d5ed8c8109cb94b747420cde50c9a24e3a`.
- Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries retain the
  built-in bench signature `2483430`; their SHA-256 values are
  `7127a831567ae518dd5974e7549b330229af9dcee1e1b9974323e1dd9512c2e6`
  and `2459ea4357435a72b0e5d536dbf99fd7c2bcc6d54de07f1dc87f0573a156b3dd`.
  An assertions-enabled Windows build completed a depth-10 bench with 533,773
  nodes and no checker/state assertion failure.
- Strict `--expect-search-identical` verification passed `132/132` cases on
  Windows, `132/132` on Ubuntu, and a deeper `324/324` Ubuntu suite at search
  depth 8. This covers legal-root maps, depth-3 perft, repetition, raw NNUE,
  static evaluation, architecture, and deterministic searched results against
  both v1.0.0 and the accepted baseline.
- Paired PGO AVX2 timing retained the depth-13 signature `2221258` but measured
  `-0.369%` median on Windows and `-0.279%` on Ubuntu over nine alternating
  pairs per platform; the arithmetic mean is `-0.324%`. Y003 therefore fails
  the cross-platform NPS gate. No 1,000/5,000-game Elo run, commit, tag,
  release, or baseline change is made.
- A later Y004 signature audit exposed an additional implementation flaw:
  Y003 queried `blockersForKing` through the new `StateInfo` before
  `set_check_info()` recomputed that field. Although the sampled assertions and
  verifier runs happened to pass, this is an invalid state source and can be
  undefined behavior. Y003 is permanently rejected independently of its NPS
  result; Y004 reads the immutable data explicitly from `st->previous`.

## Candidate Y004 — precomputed checker update fast path

- Y004 keeps the YaneuraOu checker-update idea but removes Y003's per-piece
  attack generation. It reads the old `blockersForKing` and `checkSquares`
  explicitly from `st->previous`, detects possible discovered or hollow-cannon
  checks only when `givesCheck` is true, and otherwise records the moved square
  as the sole checker. Its debug assertion compares the complete checker
  bitboard with the original `checkers_to()` result. Candidate identity is
  `935d26047f2b9b4c14e3e406d854769bea489a67`.
- An early implementation accidentally read uncopied checker fields from the
  new `StateInfo`; its changed bench signature exposed the error immediately.
  That build was discarded before verification and timing and is not included
  in any result below.
- The corrected Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2
  binaries both retain built-in signature `2483430`; SHA-256 values are
  `16dd5769916a0894e8826d6acb806553bf95264d7b438098e74167150fddb45c`
  and `c2216f16f9b7ef56b4a2a3be645f612a16f6358f589332883af71be6f395e92d`.
  Assertions passed 533,773 depth-10 nodes with full checker-bitboard equality.
- Strict search-identical verification passed `132/132` cases on Windows,
  `132/132` on Ubuntu, and `324/324` in the deep Ubuntu suite.
- Nine-pair PGO AVX2 timing measured `-0.120%` median on Windows and `-0.853%`
  on Ubuntu, with arithmetic mean `-0.487%`; signature `2221258` matched on
  both platforms. Y004 fails the NPS gate, so no Elo test, commit, tag, release,
  or baseline change is made.
- A generic main-search mate-in-one probe is deferred. YaneuraOu can afford it
  through a specialized Shogi mate routine; xfish's exhaustive legality-based
  adaptation is substantially more expensive and must first prove useful in
  qsearch through Y001.
- YaneuraOu commit `c117c9c8496661ba2cea985c29df284a02e2e1bc` removes null-move
  verification, but upstream later rolled it back in
  `436b117451b0fe0673b4671c4677211163e5755e`. It is rejected from the normal
  queue because the upstream rollback is stronger evidence than the original
  short-time result.
- The historical AVX2 SuperSort commit
  `392ed9fac1320b57ab3431544c870de2fecef3e6` is rejected before testing. It
  was disabled by default upstream, deliberately changes equal-score move
  ordering, relies on 64-bit `ExtMove` representation details, and targets
  Shogi move lists sized near 600; xfish caps lists at 128 and already has a
  safe scalar partial insertion sort (plus its AVX-512 path).

## Candidate Y005 — shuffling detection audit

- YaneuraOu commit `20064ba13baeb9452556cb3fe94e9de7b6ffdb5c`
  suppresses singular extensions for reversible back-and-forth moves. The
  accepted xfish baseline already contains the same `is_shuffling()` helper
  and applies it to the singular-extension condition, including Xiangqi's
  `rule60_count()` guard. Y005 is therefore classified as already present;
  no duplicate patch, build, or Elo run is made.
- Only that isolated helper was considered. The source commit's unrelated
  reduction, TT-depth, and tablebase edits were not bundled into a candidate.

## Candidate Y006 — static-evaluation history tuning

- Source idea: retained YaneuraOu commit
  `65fb9606084d9d880c64591479fc58f644de8352` changes the clamp used to turn
  two-ply static-evaluation change into quiet-move history and reduces the
  corresponding main-history multiplier.
- Xiangqi adaptation changes only two expressions in `src/search.cpp`:
  `clamp(-110, 187) + 34` becomes `clamp(-214, 171) + 60`, and the
  main-history weight changes from `13` to `10`. The existing xfish pawn
  history weight remains `12`. No Shogi rule, drop, promotion, move encoding,
  move generation, NNUE feature, architecture, or network data is imported.
- Candidate identity is `91d9505f2e8449a93ad44da2a64ae172f61c1f46`.
  Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries share
  bench signature `2191156`; SHA-256 values are
  `ea4a2f3f00d0e60b641e26aa4a6c98bb033a408d07a6c3753d0e90f2ba5894ac`
  and `0ed2afc39f5b0a0412f948ddd6fa28cbc060b6e55bf3006af3e4c6f977b63441`.
- Gameplay verification passed `132/132` cases on Windows, `132/132` on
  Ubuntu, and `324/324` in the deeper Ubuntu suite at search depth 8. An
  assertions-enabled Windows AVX2 build completed its depth-10 bench with
  `454844` nodes.
- Gate 2 is run `6a77f81872f81a712e5b3078`: 1,000 paired games at `10+0.1`
  using independent opening seed `xfish-xiangqi-20260809-y006-gate2`. It must
  finish with a positive Elo point estimate before any 5,000-game run; no
  baseline, commit, tag, or release change is allowed yet.
- Gate 2 completed all 1,000 games. Strict aggregation selected exactly one
  complete result set for each task after detecting and stopping stale duplicate
  worker processes, then verified 500 unique, contiguous paired openings
  (`0..499`) and the expected Windows/Linux engine and network hashes. The
  audited result is W/L/D `108/114/778`, pentanomial `[0,31,444,25,0]`, Elo
  `-2.0846 +/- 5.0935` (95%), LOS `21.12%`, zero crashes, and zero time losses.
  Report SHA-256 is
  `6e07d18c152c8c8144fd707a311e5b245ee0be877e62516889c5ed08607babed`.
- Y006 is rejected at the 1,000-game gate because its Elo point estimate is
  negative. The 5,000-game confirmation is not run; master, baseline, tags,
  and releases remain unchanged.

## Candidate Y007 — split-half bitboard iteration in move generation

- Source idea: YaneuraOu commit
  `78dfc93ef48f86692d0bda01977fddcac61af6ff` introduced an inlined
  `Bitboard::foreach()` that extracts the two machine-word halves of its large
  board once and iterates each half independently.
- Xiangqi adaptation adds `for_each_square()` for xfish's 90-square `u128`
  bitboard and uses it only in move generation. Low squares are emitted first,
  then high squares with offset 64, preserving the exact ascending order of the
  original `pop_lsb()` loops. This avoids repeated 128-bit subtraction and
  low/high selection without changing move encoding, legality, rules, search,
  NNUE features, architecture, or network data. Candidate identity is
  `197567dbe31d74354d55610dd933624f3acd3989`.
- Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries retain the
  accepted baseline's built-in bench signature `2483430`; SHA-256 values are
  `9f68c66bf5f57c4f5176620dce9d4d4525b26e781cea859ad49824e7086be59a`
  and `3d3259585e4cc173990859f76d654a0c955de86d7944fa304a6ce624a08558db`.
- Strict search-identical verification passed `132/132` cases on Windows,
  `132/132` on Ubuntu, and `324/324` in the deeper Ubuntu suite at search depth
  8. Report SHA-256 values are
  `04d750c4ecd8827eea4fb62cb5574e5123900b1214786e192b6f5aecec84a833`,
  `9c197d02c2c5533c897af163ec5be7283677db3fc91166e68c49c1f0c91c3cd4`,
  and `070a40a1511dfc9cd4a7f5032b527932a1e732b7a266cf050d16197757929866`.
  An assertions-enabled Windows AVX2 build completed its depth-10 bench with
  `533773` nodes.
- Gate 1 is an extended 15-pair alternating PGO AVX2 benchmark on each platform.
  It must satisfy the existing cross-platform rule (both gains positive and
  their arithmetic mean greater than `0.2%`) before any Elo games are run.
- The Windows half completed all 15 pairs with matching `2,221,258`-node
  signatures: baseline median `422,513`, candidate median `425,130`, median
  paired gain `+1.1186%`, mean paired gain `+1.3303%`, and bootstrap 95% ratio
  interval `1.00552..1.01573`. The Windows CSV SHA-256 is
  `f03d935c81cc5e449c689ed08b9ea211911afac12ff602f2890ed67aecc1c62a`.
  This is only one half of Gate 1; no Elo test is authorized until the
  prespecified primary Linux run also completes and the combined rule passes.
- The first Ubuntu run on `.7` was detached safely after an SSH interruption,
  but the host load later rose above 80 while measured pairs were running. It
  was retained to completion as a secondary loaded-host stress measurement.
  Its 15 paired samples ended at median paired gain `+0.0832%`, mean paired
  gain `-0.9561%`, and bootstrap 95% ratio interval
  `0.97944..1.00396`; the wide spread is consistent with the observed load and
  this result is not used for acceptance. Its CSV SHA-256 is
  `dd80187cbb06c77937f9eaf7ec797690a592ee2a84294c8d94e917cdd6dc634d`.
  Before seeing any completed result from the replacement host, `.8` was
  designated as the authoritative Linux gate run because its load was near 11;
  it uses the same binary hashes, 15-pair AB/BA protocol, and cores 120-123.
  Gate selection will not be switched between the two Linux runs after their
  results are known.
- The authoritative `.8` run completed all 15 pairs with matching
  `2,221,258`-node signatures: baseline median `3,145,692`, candidate median
  `3,129,925`, median paired gain `-0.4045%`, mean paired gain `-0.4063%`, and
  bootstrap 95% ratio interval `0.99070..0.99776`. Its CSV, summary, and stdout
  SHA-256 values are
  `bd97acc4ea690e9130dfb83d3372d9840d091ecea5c82eb912374e29e97f22dc`,
  `418ae6f9696f77867ffbe27410d9496c939c5bc11045345ba949ac7f405abf36`,
  and `ecfc8c05b630f5817df07edc0cdf438e94fade7fc90d5b890288dd22c8ada12a`.
- Across the prespecified Windows and primary Linux runs, the arithmetic mean
  platform gain is `+0.3571%`, but Linux is negative. Y007 therefore fails the
  mandatory per-platform-positive condition and is rejected at Gate 1. No Elo
  games are run; master, baseline, tags, and releases remain unchanged.

## Candidate Y007-R1 — destination-only split-half iteration

- This is a fresh candidate from the unchanged accepted baseline, not a
  post-result substitution into Y007. It follows the narrower usage intended by
  upstream commit `78dfc93ef48f86692d0bda01977fddcac61af6ff`: the original
  outer source-piece loops remain intact and only four small destination
  bitboards use `for_each_square()`. Candidate identity is
  `5d7f09bfb43c8583bb4eff19e5202f508b0e98e9`.
- Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries retain the
  accepted baseline's built-in bench signature `2483430`; SHA-256 values are
  `08594746fe65b3f9c288d60de29f22117b03f86d780c9f67f1432a86f06a3a09`
  and `f6b16b7158d818149f1909a83a1bea1914d32681796ab7f21781b6f3be88d0cc`.
- The reduced scope avoids Y007's large Linux code expansion. Windows `.text`
  changes from `829,186` to `822,850` bytes; Linux `.text` changes from
  `502,901` to `510,325` bytes. The Linux increase is `1.48%`, substantially
  below Y007's `5.88%`, but performance is still decided only by measured pairs.
- Strict Windows verification passed `132/132` cases with deterministic search
  identical to the accepted baseline; report SHA-256 is
  `e6268066755f04b51e9cb48f56664efc64e7a10c4453be01542b331fd0f0ef50`.
  A clang-cl AVX2 assertions build also completed its depth-10 bench with
  `533773` nodes and no assertion failure.
- Standard Ubuntu verification passed `132/132` cases and the deeper search
  depth-8 suite passed `324/324`; both require deterministic search identity in
  addition to legal moves, perft, rules, NNUE values, and network architecture.
  Report SHA-256 values are
  `2eb263233cd9ef90d3d61414d37f1875f5e8924124bae5289a5d61f617a12232`
  and `ec3d759a5bc53e92d00ef57e60090354adf112e56d80afd967631fe72c869482`.
  With all correctness gates complete, 15-pair AB/BA Gate-1 measurements are
  authorized on Windows CPU 35 and Ubuntu `.8` CPUs 120-123.
- The authoritative Ubuntu `.8` run completed all 15 AB/BA pairs with matching
  signatures. Baseline median was `3,141,372` NPS, candidate median was
  `3,120,450` NPS, and median paired gain was `-0.7530%` with bootstrap 95% CI
  `-1.535%..+0.067%`. The benchmark CSV SHA-256 is
  `bbaa6d14fc3456caff4397cdd75cb46ad4d45cab5efb6e315c08dc4b163b6b10`.
- Because Gate 1 requires both Windows and Linux gains to be positive, the full
  Linux failure made acceptance impossible regardless of the pending Windows
  result. The Windows job was therefore stopped during its third candidate
  warmup, before any measured pair, and all partial logs were retained. Y007-R1
  is rejected at Gate 1; no Elo games, baseline update, commit, tag, or release
  are authorized.

## Candidate Y008 - follow-PV pruning audit

- YaneuraOu commit `ec88681a8f899532f9f298fb83c2d2d45f872764`
  preserves the previous iterative-deepening PV and suppresses IIR and quiet
  shallow pruning while the current search follows that line.
- The accepted xfish baseline already has the same `lastIterationIdxPV` and
  `Stack::followPV` propagation, uses `!ss->followPV` in IIR, and retains quiet
  shallow pruning only outside followed PV nodes. Y008 is therefore classified
  as already present; no duplicate patch, build, or Elo run is made.

## Queued candidate Y009 - POPCNT `more_than_one()`

- YaneuraOu commit `e76bc765ed3493d7738332b2b19c1df98f0c9d6e`
  implements its two-or-more-bits test with POPCNT after combining the two
  board words. xfish cannot merge its disjoint 64-bit halves because equal bit
  positions would overlap, but `popcount(low) + popcount(high) > 1` is exactly
  equivalent for the 90-square board.
- A clang AVX2 assembly check reduces the current 128-bit subtract/borrow/AND
  sequence from eight core instructions to two independent POPCNTs plus add,
  compare, and set. PGO also identifies `more_than_one()` as hot. Y009 remains
  queued and untouched until Y007 is accepted or rejected, so it can be based
  on the correct accepted baseline.

## Rejected candidate Y010 - null-move verification removal

- YaneuraOu commit `c117c9c8496661ba2cea985c29df284a02e2e1bc` removes the
  high-depth verification search after a successful null-move cutoff for its
  Shogi branch while retaining Stockfish's verified path for chess. The stated
  rationale is that positions where passing is beneficial are much rarer in
  Shogi; avoiding the second search can spend the saved nodes elsewhere.
- The YaneuraOu PR identifies this as a WCSC36 tanuki- team patch. Its original
  isolated Shogi test ran 14,600 games at `8.0+0.08`, Threads 1, Hash 16 MB and
  reported W/L/D `7173/6846/581`, pentanomial
  `[1576,265,3469,236,1754]`, and `+7.78 +/- 5.49` Elo (95%). This is useful
  upstream evidence, not a claim that the result transfers to Xiangqi.
- Later commit `436b117451b0fe0673b4671c4677211163e5755e` explicitly rolls this
  change back to the V9.30 behavior: it restores `nmpMinPly` for the Shogi path
  and removes the unconditional `return nullValue`, so current YaneuraOu again
  performs the high-depth verification search. This is a direct functional
  rollback, despite the commit subject spelling it “MNP”.
- The accepted xfish baseline also retains the verified path. The later
  upstream rollback outweighs the earlier short-time positive result,
  especially because Xiangqi has zugzwang-like endings too. Y010 is therefore
  rejected without a source patch, build, or Elo run. A late-game Xiangqi
  corpus remains useful for future pruning candidates but no longer authorizes
  this reverted one.

## Queued candidate Y011 - directional SEE x-ray refresh

- YaneuraOu's directional-effect SEE updates only the ray exposed by the
  removed attacker instead of recalculating every sliding direction. This part
  has a useful Xiangqi analogue even though the Shogi piece set cannot be copied
  directly: xfish's `ray_pass_bb()` and `between_bb()` already identify the
  affected rank/file half-ray.
- Upstream commit `e76bc765ed3493d7738332b2b19c1df98f0c9d6e` reports roughly
  `+3%` NPS from its directional SEE update (and separately `+1%` from the
  checking-piece update already tested as Y003/Y004). Those are Shogi results,
  not transferable xfish measurements, but they make an exact Xiangqi-native
  SEE experiment higher priority than bulk search-constant tuning.
- The Xiangqi-specific experiment will rebuild only that half-ray's first two
  occupied squares after a pawn, rook, or cannon is removed. The first square
  can expose a rook (or the existing flying-general case), while the second can
  expose a cannon. Other directions and leaper attackers remain untouched. This
  preserves the current cannon-hurdle semantics while avoiding repeated full
  rook and cannon magic-table lookups in `see_ge()`.
- The accepted-baseline profile attributes `4.01%` self time to `see_ge()` and
  calls it about 30.9 million times in the profile run, so the idea is worth an
  isolated candidate after Y009. Before any engine build, a randomized
  property test must prove the directional refresh equal to the current full
  recomputation for legal and synthetic occupancies. No Y011 source change has
  been made yet.
- The first representation-independent property test has now passed 2,000,000
  synthetic 90-square occupancies with seed `20260809`. For every target,
  affected orthogonal direction, removed square, and randomized rook/cannon
  placement, replacing only that direction's first rook and second cannon
  matched a full four-direction recomputation exactly. This proves the ray
  update identity in isolation; an eventual engine candidate must still add
  flying-general handling and pass the normal assertions/gameplay suites.

## Queued candidate Y012 - split-word global bitboard pop

- The same YaneuraOu commit
  `e76bc765ed3493d7738332b2b19c1df98f0c9d6e` implements
  `Bitboard::pop()` by extracting the low 64-bit word, clearing its LSB in that
  word, and touching the high word only when the low word is empty. xfish's
  current `pop_lsb(Bitboard&)` first locates the word but then clears the bit
  through a full 128-bit `b &= b - 1`.
- On Ubuntu clang 22 with the production AVX2/BMI flags, the current helper
  emits two `tzcnt`, a conditional move, and an `add/adc` 128-bit decrement
  followed by two ANDs. The proposed common low-word path emits one `tzcnt`,
  one `blsr`, and the two result stores; its high-word path is similarly local
  and has no carry chain. Unlike Y007, this changes the shared pop primitive
  rather than duplicating large caller loop bodies.
- The first same-process microbenchmark was discarded: the read-only repeated
  pass could be hoisted by the optimizer and its timings also depended on call
  order. A corrected harness builds one implementation per binary, runs each
  observation in a fresh process pinned to one CPU, places a compiler memory
  barrier before every timed pass, and verifies every emitted square against
  the original implementation before timing. An exploratory five-pair run on
  the currently loaded `.7` host measured median paired speedups of `+1.560%`
  for mixed 1--14-bit boards, `-1.334%` for sparse 1--5-bit boards, `+17.365%`
  for dense 16--32-bit boards, and `+9.074%` for high-word-only boards. This
  distribution sensitivity is useful prioritization evidence only; the loaded
  host result (artifact SHA-256
  `b0dd1f05e4ab9d9d1e7bb079897baad5e4053ccbee7fb466650792ec1e422d6c`)
  is not an engine NPS gate and will not be used for acceptance.
- Y012 is likely broader than the destination-only Y007-R1 because the helper
  is used throughout move generation, threat maintenance, legality, and SEE.
  It remains only a queued design until Y007-R1 is decided. It must preserve
  ascending square order, pass assertions and strict search-identical gameplay,
  then pass the standard STC `SPRT(0.0, 2.0)` and independent-seed LTC
  `SPRT(0.5, 2.5)` sequence. Comparative NPS is not run or used as a gate.

## Candidate Y013-R - Xiangqi-native half-ray rook attacks

- YaneuraOu's Qugiy implementation removes its large magic sliding-attack
  tables and reports about `+5%` NPS in the Shogi engine. Its overlapping
  81-square representation cannot be copied into xfish, but the underlying
  carry-propagation identity has a layout-independent Xiangqi form. xfish's
  non-PEXT AVX2 build currently allocates `0x108000` 128-bit entries for each
  of the rook and cannon tables, about 33 MiB in total, which is larger than a
  Zen 2 CCX's local L3 cache.
- The upstream source is commit
  `386e8bbc744745f415afa65ae2eb5b38ec20a57f`. Y013-R is an independent
  Xiangqi adaptation of its carry-propagation idea, not a copy of Shogi board
  layout, drops, promotion, move generation, or evaluation code.
- For an increasing rank/file half-ray, let `blockers = occupied & mask`; then
  `(blockers ^ (blockers - 1)) & mask` yields every attacked square through the
  first blocker, including the no-blocker case. A decreasing half-ray uses the
  most-significant blocker as a cutoff. Applying the same operation again to
  the mask beyond the first blocker produces the Xiangqi cannon ray: it skips
  the hurdle and continues through the second occupied square.
- A representation-independent test passed 1,000,000 random 90-square
  occupancies with seed `20260809`, comparing both rook and cannon results at a
  random source square: 2,000,000 direct-ray results exactly matched the current
  step-by-step reference. This only proves the formula, not engine integration.
- A C++ harness using the accepted-baseline headers then exhausted all
  `1,081,344` relevant occupancy subsets across the 90 source squares. Both
  direct paths and both current magic tables exactly matched
  `sliding_attack<ROOK/CANNON>()` in every case.
- Separate-process AVX2 screening on the currently loaded `.7` host strongly
  favors isolating the rook path first. Over five alternating pairs, direct
  rook was `+51.730%` median in the pure rook kernel and a rook-direct/
  cannon-magic mixture was `+39.514%` versus alternating access to both magic
  tables. The unchanged cannon kernel in that binary was within noise
  (`+0.561%`). Artifact SHA-256 is
  `8dd0d6ed72ef503347e663ae31c0b48eded7ecc6f9417ec8c3e32a2e6f1cd6f1`.
- Direct cannon alone was `-23.377%` in its pure kernel, although the mixed
  kernel was `+6.872%`, apparently because avoiding one of the two 16.5 MiB
  tables reduces cross-table cache pressure. Artifact SHA-256 is
  `4676b10d74967100a2be3c0b60f46d3246c995717cd40b3353f45bb3a8975582`.
  These loaded-host kernels are screening evidence, not an engine NPS gate.
- To keep changes isolated, Y013-R changes only direct rook attacks in non-PEXT
  builds and retains the magic cannon and PEXT paths. It adds 72 lines across
  `attacks.cpp`, `attacks.h`, and `bitboard.h`; no NNUE, search, rules, move
  encoding, or cannon code is changed. Stable patch identity is
  `8515ccdb543e21ffa8826def1feffe7132c1c04d`.
- A Windows assertions build compared the integrated direct rook result against
  `sliding_attack<ROOK>()` during exhaustive magic initialization, then finished
  the depth-10 bench with `533773` nodes. The earlier standalone harness also
  checked both rook and cannon formulas and both magic paths over all
  `1,081,344` relevant subsets (`2,162,688` direct results).
- Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries retain the
  baseline bench signature `2483430`; SHA-256 values are
  `558b311dc9bc7504a3b838eb6074dc948f76a65f32668f4986fa15018411cd88`
  and `9ad169661fd17a2fcd95fe3df7a5c58fd7bbb489f568fa1481c538d7dd0454ff`.
- Strict search-identical gameplay verification passed `132/132` cases on both
  Windows and Ubuntu, plus `324/324` in the Ubuntu depth-8 suite. These compare
  legal moves, perft, repetition, raw NNUE output, network architecture, and
  deterministic search against both the v1.0.0 rule/NNUE reference and the
  accepted baseline.
- Gate 1 is now running as 15 alternating PGO AVX2 pairs per platform: Windows
  uses one thread on CPU 35 and Ubuntu `.8` uses four threads on CPUs 120-123.
  Each engine receives three warmups and 5,000,000 nodes per bench position.
  Elo remains unauthorized until both platform gains are positive and their
  arithmetic mean exceeds `0.2%`.
- A separate follow-up screen was prepared without changing the active R1
  candidate: horizontal rook attacks use a 9 KiB rank table while only the two
  file rays remain direct. It independently passed all `1,081,344` relevant
  occupancies. Five loaded-host pairs on Ubuntu `.7` measured `+79.588%` median
  in the isolated rook kernel and `+67.980%` in the alternating rook/cannon
  kernel; artifact SHA-256 is
  `c3abf82f2ae55fa101c7a6f6c2f9bc3230a56bd9ecd12542070ec1fecfed5274`.
  This is only micro-kernel prioritization evidence for a possible Y013-R2,
  not an engine candidate, NPS gate, or reason to alter R1 mid-run.
- Y013-R was stopped after eight complete authoritative Linux pairs because all
  eight paired ratios were negative. With only seven pairs left in the
  prespecified 15-pair run, a positive final median had become mathematically
  impossible. Across the eight complete pairs, baseline median was
  `3,140,154.5` NPS, candidate median was `3,046,589.5` NPS, and median paired
  gain was `-3.0690%` with bootstrap 95% CI `-3.462%..-2.361%`. The preserved
  complete-pairs CSV SHA-256 is
  `c464d5c786d95b503bf29066cd49fb2a40090e9a708017a6f3a5b19ea1c3eabd`.
- Windows had completed one full warmup pair (`421,253` versus `414,048` NPS,
  `-1.711%`) but no measured pair when the mandatory Linux-positive condition
  failed. Its job was stopped during the second candidate warmup and all logs
  were retained. Y013-R is rejected at Gate 1; no Elo games, baseline change,
  commit, tag, or release are authorized.

### Candidate Y013-R2 - compact rank table plus direct file rays

- R2 is a fresh adaptation from accepted baseline
  `1699e6ba6df744f83951c66bfd5832647d65e41d`, not a modification selected
  inside the R1 benchmark. Its horizontal rook component uses a 9 KiB table
  indexed by the contiguous nine-bit rank occupancy; only north and south rays
  use direct 128-bit carry/MSB operations. Cannon and PEXT remain unchanged.
  Stable patch identity is `4d2b08b8ccbd31c027d6d7e50488652c497259fd`.
- The integrated assertions build exhausted the relevant rook occupancies and
  finished depth-10 bench at `533773` nodes. Strict gameplay passed `132/132`
  cases on each platform and the Ubuntu depth-8 suite passed `324/324`, all with
  deterministic search identity plus v1.0.0 rule/NNUE comparisons.
- Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries retain
  signature `2483430`; SHA-256 values are
  `9b60e3ebde43f10ba24e99b81846a58d47187d8f1ac9db90b7a02a493a8f73c7`
  and `cb777f8c01e8dc6bff07e95d0d32e68ae0cd5f1db43129cf06e5fdcc8c2a81ad`.
- The authoritative Ubuntu `.8` Gate-1 run was stopped after eight complete
  pairs because all eight paired gains were negative. With only seven pairs
  left in the prespecified 15-pair run, a positive final median was then
  mathematically impossible. Baseline median was `3,082,002.5` NPS, candidate
  median was `3,009,261.5` NPS, and median paired gain was `-2.3681%` with a
  bootstrap 95% CI of `-2.851%..-1.711%`.
- The complete-pairs CSV SHA-256 is
  `ca124e9ba3c53ebfe8751f2af24c8e51d170828579bb7b8b0f7054da6d94167c`;
  analysis JSON SHA-256 is
  `66b14ff8a46dffe6cb4969c174e09daf4a3149d810e62f73a42deb7233d31686`.
  Windows timing was not started because the mandatory Linux-positive
  condition failed. Y013-R2 is rejected at Gate 1: no Elo games, baseline
  change, commit, tag, or release.
- A separate prospective R3 screen keeps the current magic occupancy index but
  stores only four 4-bit ray lengths per rook-table entry. It reduces random
  entry width from 16 bytes to 2 bytes (about 16.5 MiB to 2.1 MiB), then rebuilds
  the attack from a roughly 56 KiB hot prefix table. It passed all `1,081,344`
  relevant occupancies. Five loaded-host pairs measured `+52.414%` median in
  the isolated rook kernel and `+38.886%` in mixed rook/cannon access; artifact
  SHA-256 is
  `33369c938f507b074052daca2446939383932cd41b012637a18e61c5262a1638`.
  This remains screening evidence only and does not alter the active R2 gate.

### Candidate Y013-R3 - packed rook ray lengths

- R3 starts again from accepted baseline
  `1699e6ba6df744f83951c66bfd5832647d65e41d`. For non-PEXT AVX2 builds it
  retains the existing collision-free magic occupancy index, but replaces the
  active random rook lookup with a two-byte entry containing four 4-bit ray
  lengths. Four prefixes are then loaded from a 57,600-byte hot table. Cannon,
  PEXT, search, NNUE, rule, and move-encoding paths are unchanged. Stable patch
  identity is `697e2b4072f2464b4c0dd46d5a7c356473660a43`.
- The integrated debug assertion compared every packed lookup with
  `sliding_attack<ROOK>()` for all `1,081,344` relevant occupancy subsets, then
  completed depth-10 bench at `533773` nodes. Windows and Ubuntu strict suites
  passed `132/132` cases, and the Ubuntu depth-8 suite passed `324/324`; legal
  moves, perft, repetition, raw NNUE, network architecture, and deterministic
  search all match v1.0.0 plus the accepted baseline.
- Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries retain
  signature `2483430`; their SHA-256 values are
  `6453a5a4303a7dcedd2f20786d57d58c365e891aa54a092f56e0ca3ddd574955`
  and `4524f9a6b1ae9350ddd4728dd0fca31e8ac3aed21b5281d9093f71b41c64f9be`.
  `.text` changes from `829,186` to `830,002` bytes on Windows and from
  `502,901` to `514,744` bytes on Linux.
- The authoritative Ubuntu `.8` Gate-1 run was stopped after eight complete
  pairs because all eight paired gains were negative. With only seven pairs
  left in the prespecified 15-pair run, a positive final median was
  mathematically impossible. Baseline median was `3,093,515.5` NPS, candidate
  median was `2,970,550.0` NPS, and median paired gain was `-3.9833%` with a
  bootstrap 95% CI of `-4.228%..-3.880%`.
- Complete-pairs CSV SHA-256 is
  `4d1638b93525b13f43c0299433e980c9fcd952d14df31ba2b55436b69aa21354`;
  analysis JSON SHA-256 is
  `ea52a8caad3da762681e4eddab779b8dff243605c743ebb24f42d2fac3df07ac`.
  Windows timing was not started because the mandatory Linux-positive
  condition failed. Y013-R3 is rejected at Gate 1: no Elo games, baseline
  change, commit, tag, or release.

### Candidate Y011 - directional SEE ray refresh

- Y011 is a fresh Xiangqi adaptation of YaneuraOu commits
  `f5813faf867fdb792f0f4aa5029c3795d9f8d5b8` and
  `94b4241c7ed23e3dcccbcb7187cfc0089670d0b2`. When SEE removes an
  orthogonal pawn, cannon, or rook attacker, only the affected rook/cannon
  half-ray is refreshed; the accepted baseline currently repeats full
  four-direction magic lookups. Stable patch identity is
  `07ae64ae3eab3e71114d91126c7624ec4eb95f4e`.
- An independent exhaustive screen passed `219,212` directional occupancy
  cases against a square-by-square rook/cannon scan. The assertions build also
  compares every partial refresh reached in SEE with the original full refresh
  and completed depth-10 bench at `533773` nodes.
- Windows and Ubuntu strict gameplay passed `132/132` cases, and the Ubuntu
  depth-8 suite passed `324/324`. Legal moves, perft, repetition, raw NNUE,
  network architecture, and deterministic search match v1.0.0 plus the
  accepted baseline exactly.
- Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries retain
  signature `2483430`; SHA-256 values are
  `4b038cb8c063d0f8091e80f31ae51c8984d3a0a5695e3eb6b3047c8f2c7ac111`
  and `7375ef2f7829a5c3c83de205cece42bf5bea45b0c429513a46d9f473aaf12e1d`.
- The authoritative Ubuntu `.8` Gate-1 run used CPUs 120-123, three warmups per
  engine, four threads, and 5,000,000 nodes per position. All first eight
  measured pairs were negative, so the run was stopped at the prespecified
  proof point: with eight negative values, a positive median over 15 pairs was
  mathematically impossible. Baseline median NPS was `3,113,926`, candidate
  median NPS was `3,075,839`, median paired gain was `-1.0499%`, mean paired
  gain was `-1.1568%`, and the paired bootstrap 95% interval was
  `-1.5988%..-0.8436%`.
- Raw CSV SHA-256 is
  `19e3d785fd59b117a816c0134f67febadf79c00af899e38a897bef0c7b1a2273`,
  complete-pairs CSV SHA-256 is
  `8791e517aacbc52c25cdf9985a65ec8840b413ea611fb2244273f35aa283467f`,
  and analysis JSON SHA-256 is
  `bf09909df6831f1ebd58629168c307b976b254035705a3b24dc0b92ce57bcbff`.
  Y011 is rejected at Gate 1. The mandatory Linux-positive condition failed,
  so Windows timing, Elo games, baseline change, commit, tag, and release were
  not started.

### Candidate Y014 - shared rook/cannon magic index

- Y014 is a Xiangqi-native follow-up to the sliding-attack audit around
  YaneuraOu/Qugiy commit `386e8bbc744745f415afa65ae2eb5b38ec20a57f`.
  xfish deliberately initializes rook and cannon magics with the same mask,
  multiplier, shift, and per-square table layout, but several hot callers
  independently calculate that 128-bit magic index twice. The candidate adds a
  paired lookup that calculates it once and reads both result tables. Stable
  patch identity is `58cc20a8c8d32373e9b928d3f27f06c49c2b077c`.
- A debug exhaustive assertion checked all `1,081,344` relevant
  square/occupancy cases and proved both returned bitboards equal the original
  independent rook and cannon lookups. Its depth-10 bench completed at
  `533773` nodes.
- Windows and Ubuntu strict gameplay passed `132/132` cases, and the Ubuntu
  depth-8 suite passed `324/324`. Legal moves, perft, repetition, raw NNUE,
  network architecture, and deterministic search match v1.0.0 plus the
  accepted baseline exactly.
- Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries retain
  signature `2483430`; SHA-256 values are
  `8d986c6aebf85d25d7767d4c7db2a6a5eee403ad248067081891cdb4d6901b23`
  and `ee46b502c71c0ae71d74bb70c9747a188124e465091c8f068f8949764de57c39`.
- The authoritative Ubuntu `.8` Gate-1 run used otherwise-idle CPUs 120-123,
  three warmups per engine, four threads, and 5,000,000 nodes per position.
  All first eight measured pairs were negative, so the run was stopped at the
  prespecified proof point: a positive median over 15 pairs was then
  mathematically impossible. Baseline median NPS was `3,091,125.5`, candidate
  median NPS was `3,067,264`, median paired gain was `-0.9301%`, mean paired
  gain was `-0.8909%`, and the paired bootstrap 95% interval was
  `-1.1786%..-0.3153%`.
- Raw and complete-pairs CSV SHA-256 is
  `6ca9ecb3f204b4d344db978bc0741cb2f39cec16bcf2850ab247e68aefdaed74`;
  analysis JSON SHA-256 is
  `b902e6cd72cecab818d9c475e4928544db87e23f205ebdcf773c5e63963c83ab`.
  Y014 is rejected at Gate 1. Windows timing, Elo games, baseline change,
  commit, tag, and release were not started.

### Candidate Y015 - cached king squares

- Y015 adapts YaneuraOu commit
  `e250dc00583285c0d7984f46a0781a5393795964`: `Position` incrementally caches
  the two king squares rather than recovering them repeatedly with lower- and
  upper-half `lsb()` scans on xfish's 90-square bitboard. Stable patch identity
  is `5c5a96df264ea2dbd70a6133826bad42207bd3c4`.
- Debug assertions verify that each cached square is valid and contains the
  requested color's king. Windows and Ubuntu strict gameplay passed `132/132`
  cases, and the Ubuntu depth-8 suite passed `324/324`; legal moves, perft,
  repetition, raw NNUE, network architecture, and deterministic search match
  v1.0.0 and the accepted baseline.
- Windows clang-cl 19 and Ubuntu clang 22 Full-LTO PGO AVX2 binaries retain
  signature `2483430`; SHA-256 values are
  `d096a11f60c41a13e8558151b73371853a28e95d51b301794a150874973ecaef`
  and `1d2a5c54afd653e18881c9f2f9680045e91d01bf865df3ec3f9be440887be7da`.
- A non-authoritative scheduling screen on Ubuntu `.7` was positive in all
  five pairs: baseline median `3,272,483`, candidate median `3,307,269`, median
  paired gain `+1.5014%`, mean paired gain `+1.2967%`, and bootstrap 95%
  interval `+0.7479%..+1.6850%`. This result only selected Y015 for the clean
  gate; it does not replace that gate.
- The former Windows NPS run was stopped at the user's request after nine
  complete pairs; its median paired gain was `-0.0095%` and mean was
  `+0.0814%`. Pair 10 is excluded in full because only its candidate half
  completed. The primary Ubuntu `.8` timing run on CPUs 120-123 had completed
  all 15 pairs: baseline median `3,094,253`, candidate
  median `3,108,811`, median paired gain `+0.5092%`, mean paired gain
  `+0.4657%`, and bootstrap 95% interval `+0.1643%..+1.0103%`; signatures
  matched. These timing results are retained as diagnostic history only. On
  2026-08-09 the user retired NPS benchmarking entirely and directed Y015 and
  every future candidate to proceed from correctness/smoke verification
  directly to the 2,000-game Elo gate.
  The first `.8` launch produced only a
  baseline signature and exited because the deployment lacked the NNUE file;
  that failed start is preserved separately. The run was restarted from an
  empty output directory only after the network SHA-256 matched
  `3cd15292bf8c979884262f57fc723959fc0dea43b4d8d544f88db5ceb2479e24`.
- Per the expanded host budget, additional 32-thread, 15-pair PGO AVX2 runs
  completed on Ubuntu `.7` and `.8` at 20,000,000 nodes per bench position.
  Each run selected 32 initially idle physical CPUs inside one NUMA node while
  excluding CPUs used by pinned third-party engines. These are full-capacity
  scaling validations and do not replace the completed clean four-thread
  primary `.8` gate.
- The `.7` run remained clean: signatures matched, baseline median was
  `20,758,514`, candidate median was `20,887,531`, median paired gain was
  `+0.7735%`, mean paired gain was `+0.8739%`, and bootstrap 95% interval was
  `+0.0744%..+2.0931%`.
- The `.8` run is excluded from every decision. Unrelated VirtualBox and
  engine jobs migrated onto its selected CPUs after pair 10; absolute NPS
  collapsed, both engine CV values exceeded `21%`, and the final five paired
  gains ranged from `-23.1051%` to `+16.1620%`. The first ten pairs had a
  diagnostic geometric gain of `+1.6524%`, but they are not cherry-picked as
  a formal result. No user workload was moved or stopped; `.8` will be rerun
  only when one NUMA node stays independently idle for the entire sample.
- A new 44-physical-core Xeon host (`192.168.100.55`) is an additional
  performance/Elo worker. Because its Broadwell CPU differs from the Zen 2
  Ubuntu hosts, Ubuntu LLVM/clang/lld 22.1.2 was installed user-locally there.
  Baseline and candidate were built independently on that host with Full-LTO,
  PGO, and AVX2. Clang 22 required the compile-only limit
  `-fconstexpr-steps=10000000` for the existing NNUE lookup-table expression.
  Native binary SHA-256 values are
  `4c7220a24b6316b437816bf3fe82f3f8de1b11d3998730da1ffbd0ec7fd1f3ac`
  and `5afb1da160a63c2849ea41fe45848d41b775238c5e5a28ee33c715ebf8728dab`;
  both produce signature `2221258`. Native gameplay verification passed
  `132/132` with identical searches. The first 44-core timing run overlapped
  worker staging, is preserved as contaminated evidence, and is excluded from
  every decision. The clean 15-pair run on physical CPUs 0-43 completed with
  baseline median `23,108,667`, candidate median `23,130,200`, median paired
  gain `+0.1067%`, mean paired gain `+0.0655%`, and bootstrap 95% interval
  `-0.2581%..+0.2552%`. Both point estimates are positive and the interval
  shows no material Broadwell regression, although this 44-thread result does
  not independently prove a speedup. It is retained as historical diagnostic
  evidence and is not an acceptance gate.
- Two `.55` Elo configs are staged with mode `0600`: concurrency 22 pinned at
  launch to socket 0 CPUs 0-21 and concurrency 22 pinned to socket 1 CPUs
  22-43. They reference the native binary hashes above, the checked NNUE/book,
  and separate state/result roots. Their opening seed is aligned with the
  `.7`/`.8` Gate 1 seed `xfish-xiangqi-20260809-y015-gate1-2000`. A dedicated
  host-local credential was registered without displaying its value under the
  worker-only account `gr17xeon55`; the account has no admin group. The config
  usernames were updated and the two workers are running as PIDs `23001` and
  `23002` on the active 2,000-game screen.
- Ubuntu `.7` and `.8` now also have the checksum-verified Y015 Linux binary
  and two host-local Gate 1 configs staged with mode `0600`, 16 physical cores
  per socket config and the same opening seed. Their existing worker secret was
  neither read nor copied. Both workers on each host are now running, pinned to
  16 physical cores per socket config.
- The Windows clang-cl PGO binary and a separate ten-core Gate 1 worker config
  are staged locally with the same opening seed and isolated state/result
  directories. The pre-existing local worker secret was not read. The worker is
  running after the obsolete timing job was stopped. A Windows topology audit
  found that Gate 1's initial `0x3ff` mask is ten logical CPUs on five SMT
  cores. Because its clock was already calibrated under that exact loaded
  topology, the mask remains unchanged for the rest of this task. Gate 2 and
  every later Windows run start from calibration on ten verified physical
  cores `0,2,4,6,8,10,12,14,16,18` (`0x55555`).
- The server preflight remains healthy (`HTTP 302`, container unchanged) and a
  read-only unfinished-run audit was empty before launch. Elo Gate 1 run
  `6a78819ce2a139bff1cb92fe` now contains 2,000 paired games at `10+0.1`,
  `Threads=1`, and `Hash=16`, using color-reversed deterministic Xiangqi
  openings. Windows contributes 10 cores, `.7` and `.8` contribute 32 each,
  and `.55` contributes 44. All candidate-specific configs contain only the
  baseline and Y015 engine identities, preventing assignment of an obsolete
  incompatible task.
- Elo Gate 1 completed all 2,000 games with W/L/D `249/232/1519` and
  pentanomial `[0,63,861,72,4]`. The paired estimate is
  `+2.9529 +/- 4.1804 Elo` (95%), LOS `91.69%`, normalized Elo `+10.7567`,
  with zero crashes and zero time losses. The audited set contains exactly
  1,000 unique contiguous opening indices `0..999` and the expected revision,
  network, and platform-native binary hashes.
- To remove the slow Windows tail without discarding valid work, task 4 kept
  the 48 Windows pairs already reported for indices `400..447`; Xeon `.55`
  socket 0 resumed only indices `448..499`. Full raw logs, including four
  unreported Windows completions excluded from the authoritative set, are
  preserved. The report SHA-256 is
  `60d58916854101ada750a6bcdfccae0ae13c90456995b250f30de2af7b2c0f4d`;
  the 4,051-file artifact manifest SHA-256 is
  `4fe6ded1a920459c20e40dce8936ed598f4b74c3d87215ba3574ef04035d0c1e`.
- The positive point estimate authorizes Elo Gate 2. Run
  `6a788b320cda1ec97ce5bc90` contains 10,000 games in 100-game chunks with
  independent seed `xfish-xiangqi-20260809-y015-gate2-10000`. All seven
  workers are active on 118 physical cores total. Windows was calibrated from
  launch on verified core representatives `0,2,4,6,8,10,12,14,16,18`; its
  loaded baseline rose from Gate 1's `210,428` to `358,577` NPS/thread, cutting
  the normalized wall-clock allocation from `29.844+0.298` to
  `17.514+0.175` while preserving the nominal `10+0.1` test control.
- Elo Gate 2 completed all 10,000 games with W/L/D `1125/1093/7782` and
  pentanomial `[4,312,4340,336,8]`. The paired estimate is
  `+1.1118 +/- 1.7963 Elo` (95%), LOS `88.75%`, normalized Elo `+4.2149`,
  with zero crashes and zero time losses. Strict aggregation found exactly
  5,000 unique contiguous opening indices `0..4999`, the expected baseline and
  candidate revisions, identical NNUE SHA-256 on both sides, and only the three
  expected platform-native executable hashes per side.
- Gate 2 artifacts contain 5,000 canonical pair summaries plus all raw logs and
  seven worker configs. The result report SHA-256 is
  `e36be59a616c7e3040bd93314f41ea513e3c7405a228cb1f358d2257c667900b`;
  the 20,108-entry artifact manifest SHA-256 is
  `787a40912472d070dbcb2f108651711a2462f70abe0bfe535fe62e848d46df40`.
- Under the historical fixed-game policy, the positive 10,000-game point
  estimate promoted Y015 as `v0.4.0-king-square-cache`. It changes only how the two
  existing king-square values are recovered; Xiangqi rules, legal moves, search
  policy, NNUE architecture/features/weights, and evaluation outputs are
  unchanged.
- On 2026-08-10 the owner replaced that policy with mandatory STC and LTC
  SPRT. v0.3.0 remains grandfathered, while the historical Y015 promotion is
  revoked until both new stages pass. The first requalification run
  `6a79134e100ca3033dd24db4` was stopped and disqualified at 8,228 games after
  an audit found that the variant-fishtest server was calculating legacy
  trinomial BayesElo LLR. It had W/L/D `902/890/6436`, zero failures, and no
  baseline effect.
- The harness now sends and validates pentanomial task statistics and computes
  normalized-Elo LLR with `LLRcalc.py` pinned to official Stockfish fishtest
  commit `b571c90db880f973a7eea57bd344600fe89a7e8e`. End-to-end smoke run
  `6a7922f9d4f4fd50e97a2ce2` proved the server receives the pair vector and the
  watcher records a safety cap reached between the boundaries as
  `inconclusive`.
- Y015 STC requalification restarted from zero as run
  `6a7923f7fc55491a56830ef8`, seed
  `xfish-xiangqi-20260810-y015-v030-stc-pentanomial-v2`, on nine workers and
  150 physical cores (Windows 10, `.7` 32, `.8` 64, `.55` 44). It was
  administratively retired as `invalid` after 16,600 games because the
  historical `xiangqi.epd` opening source produced a `76.93%` draw rate and
  was superseded. The preserved result is W/L/D `1922/1907/12771`,
  pentanomial `[10,502,7263,513,12]`, LLR `+0.059938396`, zero crashes, and
  zero time losses. This is an opening-book rejection, not an STC decision on
  Y015.
- A replacement STC must restart at game zero with the immutable
  Xfish-generated `xfish-uho-3mvs-w65-85-v1.epd` book. Y004 remains next and
  cannot start until Y015 reaches a terminal decision under the replacement
  book.
- The replacement book passed generation with 79,270 unique positions and
  SHA-256
  `5ede082489580fb6aeb8c06c3eb34f72a916c5dbb7ee621b350b835dbdc48b0f`.
  The expanded Ubuntu gameplay gate passed all 644 positions against both
  `v1.0.0` and `v0.3.0-nnue-thp`; its report SHA-256 is
  `3d5e003ee56697b72466dbf715326b046cbf91383e892f8b69d103118931fd58`.
- Replacement STC run `6a79571cdcb6ab381712a7cf` started from game zero
  with seed `xfish-uho-3mvs-w65-85-v1-y015-stc-20260810`. MongoDB records the
  exact book ID/hash/count, the expected engine revisions and signatures,
  `10+0.1`, `Threads=1`, and `Hash=16`. Its first 224 games had W/L/D
  `72/73/79`, draw rate `35.27%`, pentanomial `[1,20,73,15,3]`, LLR
  `-0.015749`, and zero runtime failures. All nine workers are active on the
  intended 150 physical cores. LTC is preconfigured with the same artifact and
  independent seed `xfish-uho-3mvs-w65-85-v1-y015-ltc-20260810`, but may start
  only after an STC upper-bound crossing.

## Additional core-speed audit after Y007

- YaneuraOu commit `276faf80d51dd6cae053112db8021171d5dbf4e8`
  selects multiplication-based magic bitboards instead of BMI2 PEXT on
  Zen/Zen2, where the older PEXT instruction is slow. xfish already makes that
  exact build distinction: `ARCH=x86-64-avx2` does not define `USE_PEXT`, and
  `Magic::index()` uses `(occupied & mask) * magic`; only explicit BMI2 targets
  enable PEXT. The Windows AVX2 pipeline likewise enables BMI1 but not
  `USE_PEXT`. This is especially relevant because both Ubuntu hosts are Zen2,
  but it is already present and needs no candidate.
- YaneuraOu commit `aa6184a7106e68a4ad01865d0cae071b0cdad8fc`
  removes an SSE `union` from its Shogi bitboard representation to help alias
  analysis. xfish already represents a bitboard directly as an unsigned
  128-bit integer, with no union or vector alias, so the optimization is
  already structural and no candidate is needed.
- Commit `3b4422d37c43899ea4bf158cd80ccdf50486cfa5` specializes
  color-dependent attack calls at compile time. xfish's hot `attackers_to()`
  already calls compile-time `attacks_bb<...>` instantiations for every piece
  type and both pawn colors, so this is also already present.
- Commit `c7596bed6233cf4ff633d9f58ae18ab4e9a7d18b` adds a distinct
  compile-time Root node type, but it bundles unrelated search tuning. xfish
  already has `NodeType::{NonPV,PV,Root}`, calls `search<Root>()`, and makes
  `rootNode` constexpr; no port is required.
- Commit `26deea80e55e1988dedb336f7b938c4e75e65a6f` replaces propagation
  shifts with MSB for Shogi lance attacks. Xiangqi has no lance and xfish's
  rook/cannon attacks use precomputed magic tables, so there is no equivalent
  hot operation to replace.
- The partial-ray ideas in `f5813faf867fdb792f0f4aa5029c3795d9f8d5b8`
  and the larger directional-effect work in
  `e76bc765ed3493d7738332b2b19c1df98f0c9d6e` remain worth a later,
  Xiangqi-native experiment: PGO shows xfish's attack/threat maintenance is
  hot. They are not copied directly because Shogi's directions, lance/drop
  rules, and bit layout differ, while xfish must additionally maintain cannon
  hurdles and NNUE attack-feature dirties. Any experiment here must be isolated
  behind deeper gameplay verification before NPS or Elo gates.
- Static inspection of Y007's Linux Full-LTO binary found that splitting the
  *outer* source-square loop duplicates its relatively large per-piece body:
  the three main generated `generate<...>()` functions grow from
  `4,618/6,116/5,942` bytes to `11,766/11,468/9,142` bytes, and total `.text`
  grows from `502,901` to `532,469` bytes (`+5.88%`). A second inspection of
  upstream commit `78dfc93e` confirms
  that YaneuraOu itself warns about this code expansion and applies the helper
  mainly to small destination bitboards while retaining ordinary source-piece
  pops. If the authoritative Linux gate rejects Y007, a more faithful narrowed
  follow-up will retain the original outer loop and split only the small
  destination-square loops, then restart build and verification from the
  accepted baseline. This refinement is not substituted into the running Y007
  measurements.
- The current upstream NNUE speed commit
  `5f90c55f69cc546acebd41cef00a4a7f726a9e90` was audited separately because
  it reports about 3% faster inference. Its AVX2-relevant techniques are tiled
  accumulator updates and a paired squared/linear clipped-ReLU pass. The
  accepted xfish baseline already has both: `apply_combined()` keeps each
  accumulator tile in SIMD registers while applying PSQ and threat deltas, and
  `SqrClippedReLU::propagate_pair()` is enabled for AVX2. xfish's implementation
  also has the specialized one-removed/one-added int8 pair path. No duplicate
  candidate is needed, and no network shape or weights are changed.
- YaneuraOu's new Finny-table commit
  `72c91d8101512741f6a286f57e80cfd3f5fdc6c3` is likewise already represented
  by xfish's accumulator cache and refresh-entry update path. The adjacent
  AVX-512/VNNI commits are outside the requested AVX2 target and are not queued.
- Strength-oriented MovePicker commit
  `f3ef7beb4211f4b8ceb27e526a4cca0d8b4b54dd` restores full capture sorting
  and partial quiet sorting, reportedly recovering about R40 in that Shogi
  version. xfish already performs a full capture sort with the minimum integer
  limit and uses a depth-scaled partial quiet sort. Likewise, the older
  `15ff26c01cfa0955895c3f7bc82ab3e485f2acc2` optimization that avoids
  generating quiets after `skip_quiet_moves()` is already present in xfish's
  `QUIET_INIT` stage.
- Commit `286a9a6c951fc77a8093e9771be5216587281133` changes how promoted
  Shogi captures enter `capturesSearched`; Xiangqi has no promotion, so the
  condition has no rule-preserving analogue. Commit
  `0eec4bd61b2559d166a208fa5c37b935c8bf6c0b` is a bulk Shogi parameter
  retune rather than an isolated algorithm and is not ported.
- The 2026 compact-type commit
  `3a41f1848d8b67d1b933d46ad6b85954f8a78bf1` makes Shogi `Square`,
  `Piece`, `PieceType`, `Color`, and `Bound` unsigned byte enums. xfish already
  declares all five with `u8` underlying storage, so the large-board cache-size
  benefit is already present. Its unrelated TT and Shogi-hand edits are not
  bundled.
- Commit `a5c84b4c505b81e32659182b1a7977e008d84e88` removes an SEE test
  from the ProbCut TT-move constructor. xfish's constructor already admits a
  pseudo-legal capture without that extra SEE call; the normal ProbCut move
  stage still applies its intended threshold. No duplicate candidate is made.
- Commit `62b25ce51ac5eae32f65cd5b4a2fca0c5fe0cf76` imports Stockfish's
  newer transposition-table generation packing and depth-minus-eight-times-age
  replacement rule. xfish already has the same five generation bits, packed
  bound/PV fields, relative-age arithmetic, three-entry cluster scan, and
  replacement expression, so it is recorded as already present.
- Commit `0056b408e904f0733f3cfd2c2a7e57c3d74fcd62` avoids reevaluating a
  PV node when a valid static evaluation was read from the TT. xfish's normal
  search and qsearch both already reuse `ttData.eval` and call NNUE only when
  that value is invalid. The Shogi-specific differential-evaluation plumbing
  therefore offers no additional AVX2 candidate.
- Commit `81b9b8c671c1f16b01a8f3383e5a4cc3e828ed7f` combines three
  Stockfish search ideas: improving-aware null move, simplified ProbCut depth,
  and next-ply `cutoffCnt` reduction. All three structures already exist in
  xfish with later Pikafish-tuned constants, so copying the older Shogi numbers
  would be a bulk retune rather than a missing algorithm.
- The adjacent April 2026 commits `dc943f897baf6dcd77c2a22170e2b19e2e37c1d0`,
  `27e2a75b1fca2b8480b81a5c52d7c5a1020dac46`,
  `78164c290d692f4286238358627d200e8965fb60`,
  `8f317db4459f7441249e223ed0dfac153018a5ec`, and
  `9531890b72b0a7b4400144adfe67812788f10dcc` are interdependent Shogi
  search-parameter batches. Their underlying pruning/history mechanisms are
  already present in xfish; without an isolated algorithm or upstream A/B
  result, transplanting their constants would violate the one-change-at-a-time
  rule and is intentionally not queued.
