# Xfish Xiangqi UHO opening book

## Decision

The historical `xiangqi.epd` corpus is no longer an admissible opening source
for new xfish Elo tests.  In the superseded Y015 STC attempt it produced a
`76.93%` game draw rate over 16,600 games, and its 33,921 unique positions were
also smaller than the 50,000 pairs allowed by the 100,000-game SPRT safety cap.
It remains preserved only for reproducing historical tests.

The first Xfish UHO corpus followed Pikafish's public 65--85% modeled-win
description. That is now retired for new Elo runs because its openings are too
decisive. Stockfish's actual current Fishtest book is
`UHO_Lichess_4852_v1.epd`: `4852` refers to the WDL model's *draw* component,
not win probability. Its published construction command keeps positions only
when `480 < D < 520`, and long-run Fishtest data reports about a 49.4% game draw
rate. The replacement Xiangqi corpus must reproduce that discrete
`D=481..519` filter.

The owner explicitly requires xfish, not Fairy-Stockfish, to generate this
book.  `scripts/generate-xiangqi-uho.py` consequently uses the grandfathered
`v0.3.0-nnue-thp` xfish baseline for both the move tree and the authoritative
WDL filter.  No existing EPD is an input.

## Current v2 generation policy

- Start from the standard Xiangqi initial position and generate exactly six
  plies (three full moves), leaving Red to move in every final FEN.
- Use `Threads=1`, a fixed node budget, a cleared hash before every search, and
  fixed MultiPV limits.  For every PV, retain the deepest completed exact
  iteration instead of a final aspiration-window `lowerbound`/`upperbound`;
  reject the position if either scoring PV still has only a bound.  This makes
  a path independent of worker scheduling without treating a bound as an exact
  WDL estimate.
- Broaden the deterministic Red and Black MultiPV tree relative to v1 so the
  narrow Stockfish-equivalent filter still yields at least 50,000 unique pairs.
- On Black's third move, use the perspective-invariant WDL draw component only
  as a broad cheap prefilter. The authoritative deeper final-FEN search keeps
  exactly `481..519` per mille, matching Stockfish's strict `>480 && <520`.
- Ask the same frozen xfish baseline to re-search every final FEN at the deeper
  scoring budget. Record full win/draw/loss distributions in the manifest.
- Reject checked positions, mates/non-centipawn scores, malformed 9x10 FENs,
  duplicate FENs, missing second moves, and positions where the second-best
  move is more than 150 centipawns behind.  This avoids forced one-move
  tactical starts.
- Sort the unique candidates by SHA-256 of an immutable seed plus FEN.  Save
  every path, FEN audit, score record, configuration, count, and artifact hash.
  A resumed run is rejected if any generation parameter or input hash differs.
- Before deployment, run `scripts/audit-xiangqi-uho.py` as an independent
  second implementation. It streams the final paths, position records,
  candidates and score records in lockstep; reconstructs the accepted book;
  enforces exact, unbounded two-PV WDL records with `D=481..519`; and verifies
  FEN validity, uniqueness, deterministic ordering, counts and every manifest
  artifact hash. Its current SHA-256 is
  `df1ffafe3eacf747afa93b8f520c17fd713f794943329345e92358b0944467c0`.

The generator defaults now encode the v2 draw filter and retain hidden legacy
`--wdl-win-min/--wdl-win-max` flags solely to reproduce v1 in a fresh output
directory. The final v2 command and artifact hashes are frozen after corpus
generation and audit.

## Frozen v2 corpus

The clean v2 run completed in 29,455.09 seconds with status `passed`. Its
reproducible command was:

```text
python3 scripts/generate-xiangqi-uho.py \
  --engine /home/gr17/services/xfishtest-worker/engines/xfish-v0.3.0-xeon-pgo \
  --network /home/gr17/services/xfishtest-worker/engines/pikafish.nnue \
  --engine-sha256 4c7220a24b6316b437816bf3fe82f3f8de1b11d3998730da1ffbd0ec7fd1f3ac \
  --network-sha256 3cd15292bf8c979884262f57fc723959fc0dea43b4d8d544f88db5ceb2479e24 \
  --output-dir /home/gr17/services/xfish-bookgen/xfish-uho-3mvs-d48-52-v2 \
  --book-name xfish-uho-3mvs-d48-52-v2.epd \
  --seed xfish-uho-xiangqi-3mvs-d48-52-v2 \
  --plies 6 --workers 44 \
  --generation-nodes 50000 --scoring-nodes 100000 \
  --red-branch 12 --black-branch 32 --final-black-branch 96 \
  --red-move-window-cp 200 --black-move-window-cp 500 \
  --final-black-move-window-cp 1200 --final-black-wdl-margin 100 \
  --second-move-window-cp 150 \
  --wdl-component draw --wdl-min 481 --wdl-max 519 \
  --minimum-positions 50000
```

It enumerated 6,107,083 six-ply paths and 1,608,289 unique non-check final
FENs. The exact draw-band and second-move filters accepted 132,503 positions,
rejected 1,475,599 positions outside `D=481..519`, and rejected 187 forced or
one-move starts. The independent streaming audit reconstructed the book from
all source records and passed with the same counts and WDL histograms.

- Book SHA-256:
  `7fe9ea92dd718f3a3706c8ce58de467272b5f3d67d532eec8220d4f030570e48`
- Manifest SHA-256:
  `ccb4953b259a44ced8ce0e84d2ab7d267b278d140350b74223e5fed7df76115a`
- Independent audit report SHA-256:
  `8ceef109ab85b5bd191b0dd2da0de7ffc729152c9e249123194c258f16f24354`
- Scoring records SHA-256:
  `ee8ae46fdbf150e820af369ec705cf14c6d398a1510f714900b0225a24ae7526`
- Unique-pair capacity: 132,503 pairs, or 265,006 games.

All three deployed artifacts are stored under `tools/xfishtest/books/` and
match byte-for-byte on Windows and Ubuntu workers `.7`, `.8`, `.55`, and
`.66`. A same-binary STC calibration was stopped after 486 completed games:
`91-88-307` (63.17% draws), pentanomial `[0,49,144,48,2]`, with zero crashes
and zero time losses. This confirms materially less opening bias than the
retired decisive v1 corpus while preserving enough non-draw outcomes for
pentanomial SPRT.

## Historical v1 command and artifact

The full retired v1 command was:

```text
python3 scripts/generate-xiangqi-uho.py \
  --engine xfish-v0.3.0-xeon-pgo \
  --network pikafish.nnue \
  --engine-sha256 4c7220a24b6316b437816bf3fe82f3f8de1b11d3998730da1ffbd0ec7fd1f3ac \
  --network-sha256 3cd15292bf8c979884262f57fc723959fc0dea43b4d8d544f88db5ceb2479e24 \
  --book-name xfish-uho-3mvs-w65-85-v1.epd \
  --seed xfish-uho-xiangqi-3mvs-w65-85-v1 \
  --plies 6 --workers 44 \
  --generation-nodes 50000 --scoring-nodes 100000 \
  --red-branch 6 --black-branch 16 --final-black-branch 48 \
  --red-move-window-cp 100 --black-move-window-cp 300 \
  --final-black-move-window-cp 800 --final-black-wdl-margin 100 \
  --second-move-window-cp 150 --wdl-win-min 650 --wdl-win-max 850 \
  --minimum-positions 50000
```

The exact absolute paths and output directory are machine-local and are stored
in the generated manifest.  The hashes above, not path names, identify the
generator inputs.  The exact generator implementation used for the clean v1
run has SHA-256
`5d73e44c0cb6c096a9e58ce7528b872da7b411f000ef74487fe4628dbc563e5d`.
The fork still reports the inherited UCI name
`Pikafish dev-20260808-1699e6ba`; the executable SHA-256 above identifies the
grandfathered Xfish `v0.3.0-nnue-thp` binary that actually performed every
search.

## Rejected calibration run

The first calibration parser retained the last UCI line for each MultiPV.  A
77,000-position audit found that 21,198 of 28,475 tentatively accepted
positions still carried a `lowerbound` or `upperbound` in at least one of the
two PVs.  The full attempt was stopped after 84,000 scored positions, preserved
under `xfish-uho-3mvs-w65-85-v1-bounded-parser-rejected`, and is not mixed into
the v1 book.  The generator then gained exact-iteration selection, an explicit
residual-bound rejection guard, and regression tests before clean generation
restarted from the initial Xiangqi position.

The clean run completed in 2,599.37 seconds with status `passed`. It generated
409,405 six-ply paths, rejected 2,266 checked leaves and 195,057 transpositions,
then scored 212,082 unique non-check FENs. The final filter accepted 79,270
positions (`37.377%`), rejected 132,644 outside the WDL band and 168 for the
second-move guard, with zero bounded-score records.

- Book SHA-256:
  `5ede082489580fb6aeb8c06c3eb34f72a916c5dbb7ee621b350b835dbdc48b0f`
- Manifest SHA-256:
  `015e203bf23105aa4bef7ba620c641c2670d63c883785377070398a29616349c`
- Scoring-audit SHA-256:
  `6be161802d525657d2d616d9554a5e25385d791e36ad9d0d5494e3f48c70ec20`
- Unique-pair capacity: 79,270 pairs, or 158,540 games.

The book and its unmodified generation manifest are stored under
`tools/xfishtest/books/`. Byte/FEN audit found 79,270 LF-terminated ASCII
lines, 79,270 unique valid 9x10 FENs, exactly one king per side, Red to move in
every position, and no empty line.

The Y015 pre-Elo gameplay gate sampled 256 book positions and generated 384
additional positions from 32 twelve-ply playouts, plus startpos and three
repetition cases. Across all 644 positions, `v1.0.0`, the accepted baseline and
Y015 agreed on legal moves, perft and NNUE semantics; Y015 also matched the
baseline's deterministic depth-8 search. The report SHA-256 is
`3d5e003ee56697b72466dbf715326b046cbf91383e892f8b69d103118931fd58`.
A two-game color-reversed match-runner smoke then completed with one point per
engine, zero draws, zero time losses and pentanomial `[0,0,1,0,0]`.

## Fishtest integration

Every new server run carries four immutable fields: book ID, SHA-256, unique
position count, and stage-specific opening seed.  A worker refuses a task if
any field differs from its local checked book.  The server refuses a safety
cap larger than two games per available position.  LTC must use the same book
artifact as its accepted STC parent but a different seed.

Each selected FEN is played as a color-reversed pair and contributes one
pentanomial result. No new candidate run may use v1; STC starts at game zero
only after the v2 book is frozen and deployed identically to Windows and every
Ubuntu worker.

## Primary references

- [Pikafish current testing description](https://www.pikafish.com/)
- [Pikafish self-play opening comparison](https://www.pikafish.com/wiki/index.php?title=%E7%9A%AE%E5%8D%A1%E9%B1%BC%E6%B5%8B%E8%AF%95%E6%95%B0%E6%8D%AE)
- [Stockfish regression-test opening history](https://official-stockfish.github.io/docs/stockfish-wiki/Regression-Tests.html)
- [Stockfish Fishtest/Fastchess paired-opening example](https://official-stockfish.github.io/docs/fishtest-wiki/Running-Fastchess.html)
- [Official Stockfish opening-book repository](https://github.com/official-stockfish/books)
- [UHO Lichess 4852 construction and validation](https://github.com/official-stockfish/books/pull/39)
