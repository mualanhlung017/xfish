# Xfish v0.5.0: no perpetual rook chase of the same unprotected rook

The owner requested this rule variant on 2026-10-03. Its source is a direct
child of accepted baseline v0.4.0 (`a8ed59a924bd7a0ef2062c0d801b5f609faccc46`).
This version change implements an owner-selected rule, not an Elo promotion.
The common NNUE remains SHA-256
`3cd15292bf8c979884262f57fc723959fc0dea43b4d8d544f88db5ceb2479e24`.

## Build contract

The flag name is **NO_ROOT_ROOT**, preserving the spelling requested by the
owner (the chess piece is called ROOK internally).

| Setting | Perpetual chase rule |
| --- | --- |
| OFF (default) | Exact v0.4.0 adjudication, including its symmetric-attack exceptions |
| ON | Additionally forbid a rook continuously creating a new legal capture threat against the same unprotected enemy rook |

The final owner instruction deliberately narrows the new rule to ROOK -> ROOK.
ON includes symmetric rook attacks but only when the victim rook is unprotected.
All other piece relationships keep their v0.4.0 adjudication, including rook ->
cannon, king/pawn exceptions and attacks on more valuable pieces.
A piece is protected if, after its hypothetical capture, its side has at least
one legal recapture. A pinned defender that cannot legally recapture does not
protect it. An attack on a protected rook does not activate this new rule.
Perpetual check,
ordinary repetition draws, the 60-move rule, legal movement, static evaluation,
NNUE architecture and network bytes are unchanged. A single
attack is still a legal move. This flag changes repetition adjudication, not
the legal move generator. The one-sided perpetual chaser loses when repetition
is adjudicated. Mutual perpetual chase remains a draw, as does quiet repetition.

The legacy `Position::chased()` remains intact in both builds. ON additionally
uses `rook_chased()`, which retains attacker and victim IDs, excludes defended
rooks by simulating capture/recapture, and removes pre-existing attacks on each
pair before intersecting the maps over the full repeated cycle. A standing
attack by one rook cannot hide another rook's new attack. Alternating attacker
or victim IDs cannot manufacture the required continuous rook pair. Legacy
chase masks are tracked separately, preserving all previously prohibited cases.
`rule_judge()` continues to identify the offending colour. Engine IDs
distinguish `Xfish 0.5.0` and `Xfish 0.5.0-no-root-root`.

Windows clang-cl AVX2 full-LTO PGO:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-clangcl-pgo.ps1 -NoRootRoot ON -BuildDirectory build/windows-on -PackageName xfish-v0.5.0-windows-avx2-pgo-no-root-root -Jobs 18
```

For CMake directly use `-DNO_ROOT_ROOT=ON` or `-DNO_ROOT_ROOT=OFF` at configure
time. Use a different PGO directory/profile for each variant.

Linux LLVM 22 AVX2 full-LTO PGO:

```sh
export PATH=/usr/lib/llvm-22/bin:$PATH
cd src
make -j32 ARCH=x86-64-avx2 COMP=clang NO_ROOT_ROOT=ON profile-build
```

GNU Make accepts exactly ON/OFF; an invalid value is a build error. A rule
configuration stamp invalidates existing objects when the setting changes.
Train PGO again after changing the flag. Build each Linux CPU family on its
own host; do not substitute a Broadwell binary for the EPYC/Zen2 artifact.

## Prebuilt packages

Each platform ZIP contains both variants and the common `pikafish.nnue`:

- `xfish` (Linux) or `xfish.exe` (Windows): NO_ROOT_ROOT=OFF, v0.4.0 rules.
- `xfish-no-root-root` or `xfish-no-root-root.exe`: NO_ROOT_ROOT=ON, additionally
  forbid a rook perpetually chasing the same unprotected enemy rook.

Choose the matching EPYC/Zen2, Broadwell `.55`, Broadwell `.66` or Windows
artifact. Linux executables may need `chmod +x` after extracting a ZIP.

## Regression evidence

`tests/data/huashan-rook-chase.pgn` preserves the complete owner-supplied
153-ply game; `tests/data/huashan-rook-cannon-chase.pgn` preserves the second
194-ply game. Tests resolve Chinese notation through Xfish's legal move list,
then reconstruct every prefix. Synthetic colour-reversed cycles cover pinned
rook chase, symmetric rook attacks, protected targets, king/pawn attackers,
other chased piece types and checks.
The optional CMake target `xfish-rule-probe` calls the actual production
`rule_judge()` and verifies repeated calls and complete undo restore the board.
Verification artifacts and binary hashes are retained under
`build/release/v0.5.0-rook-chase` in the main workspace.

Future Elo comparisons must use identical NO_ROOT_ROOT settings for candidate,
baseline and match-runner adjudication. v0.4.0 remains archived as the
standard-rules reference; an ON build explicitly uses a custom ruleset.

The final rule regression has 882 full-history cases on each of Windows,
LLVM-22 Zen2 `.7`, native Broadwell `.55` and native Broadwell `.66`. Both
complete supplied games (153 and 194 plies) and their colour-reversed copies
are exercised without skipping any prefix. Every host agrees on every rule
decision, FEN and legal move set. Protected targets, pinned-rook legacy cases,
perpetual check, quiet repetition, king/pawn exceptions and non-rook targets
pass. In the first owner game, after Black's move 73 (ply 146), OFF gives a draw
and ON gives a Black loss. The same result recurs at plies 150 and 152. The
entire second, rook/cannon game retains the exact OFF outcome in ON.

Additionally, both final AVX2 full-LTO PGO variants pass the 644-case gameplay
suite on all four hosts (5,152 total cases, zero failures). OFF requires exact
deterministic search identity with v0.4.0 and retains its bench 2,270,229; ON's
bench is 2,260,022. These bench values identify the builds; no NPS or Elo gate
was used for this owner-requested rule variant.
