# v0.4.0 baseline: sf-de948f0-xq1

`sf-de948f0-xq1` ports the evaluation/optimism scaling mechanism from
[Stockfish de948f0](https://github.com/official-stockfish/Stockfish/commit/de948f0f48f5c3217bd384ea7b5714593666d1a4), using the Xiangqi-tuned formula
previously tested by
[Pikafish 1af2701](https://github.com/official-pikafish/Pikafish/commit/1af27017ba37d482eb2c5e18f57d70a872a7fc9c).

## Stockfish-style test evidence

```text
Passed STC:
LLR: 2.96 (-2.94,2.94) <-1.75,0.25>
Total: 44860 W: 11729 L: 11531 D: 21600
Ptnml(0-2): 53, 4675, 12862, 4701, 139
http://192.168.100.7:6543/tests/view/6a7ecb7d4d58bbbdcb4e32e0

Bench: 2270229
```

The exact terminal LLR was `2.9552727429174466`; the official pentanomial
normalized-Elo boundaries were `-2.9444389791664403` and
`+2.9444389791664403`. The test used `10+0.1`, `Threads=1`, `Hash=16`, paired
color-reversed openings, and SPRT `[-1.75, 0.25]`. There were zero crashes,
zero time losses, zero missing results, and zero active or pending tasks at
the terminal snapshot. The complete server-side LLR history contains 534
samples from `2026-08-14T08:02:05Z` through `2026-08-14T12:31:11Z`; its
endpoint metadata and response SHA-256 are included in the JSON evidence.

The owner explicitly approved promotion to `v0.4.0` after this STC result.
No LTC was run for this promotion; it is therefore documented as an owner-
authorized exception to the repository's normal two-stage baseline policy.

## Reproducibility and verification

- Source diff ID: `91685dbba62e3df451bc604aed061bd96bc43406`
- NNUE SHA-256: `3cd15292bf8c979884262f57fc723959fc0dea43b4d8d544f88db5ceb2479e24`
- Opening book SHA-256: `10c9e21d9a0e8ae2a6711eff0512e29ac99cab0c79e4e233a22377472062409f`
- Gameplay verification: 2,576 cases across Windows, Zen 2 Linux, and two
  independent Broadwell Linux builds; zero failures
- Forensic replay: zero deterministic bad-move regressions

The machine-readable terminal snapshot and artifact hashes are stored beside
this record in `docs/evidence/v0.4.0-sf-de948f0-xq1-stc.json`.
