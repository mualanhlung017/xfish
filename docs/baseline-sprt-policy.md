# xfish baseline SPRT policy

Effective: 2026-08-10

## Acceptance gates

A candidate may advance the accepted baseline only after all of the following
conditions pass in order:

1. Gameplay, Xiangqi rules, legal moves, NNUE evaluation, network identity,
   engine identity, opening identity, crash, and time-loss checks are clean.
2. STC passes `SPRT(0.0, 2.0)` with `alpha = beta = 0.05`.
3. LTC then passes `SPRT(0.5, 2.5)` with `alpha = beta = 0.05` and an
   independent opening seed.

For both SPRT stages, the nominal likelihood-ratio boundaries are:

- upper: `ln((1 - beta) / alpha) = ln(19) = +2.944438979...`
- lower: `ln(beta / (1 - alpha)) = -ln(19) = -2.944438979...`

Only an LLR crossing the upper boundary passes a stage. Crossing the lower
boundary fails it. A run stopped between the boundaries is inconclusive and
must not advance the baseline. Fixed-game positive point estimates, LOS, NPS
results, or confidence intervals do not substitute for either SPRT stage.

Initial Xiangqi controls are STC `10+0.1` and LTC `60+0.6`, with
`Threads=1`, `Hash=16`, color-reversed opening pairs, PGO AVX2 platform-native
binaries, and the same NNUE on both sides.

## Retrospective baseline audit

| Baseline | Historical evidence | SPRT audit | Decision |
| --- | --- | --- | --- |
| `v0.3.0-nnue-thp` | 1,000 fixed STC games, `+2.08 +/- 5.09` Elo | no STC LLR; no LTC run | revoked |
| `v0.4.0-king-square-cache` | 2,000/10,000 fixed STC games; final `+1.11 +/- 1.80` Elo | no STC LLR; no LTC run | revoked |
| `v0.5.0-checker-fastpath` | 2,000/10,000 fixed STC games; final `+0.69 +/- 1.73` Elo | no STC LLR; no LTC run | revoked |

The accepted baseline therefore rolls back to `v0.2.0-nnue` at commit
`f10beeb4e4a60c07375f92ad2884808b824ae88f`. Historical tags, releases, and
test evidence remain immutable for audit, but they are not accepted baselines.
The source rollback restores `src/shm.h`, `src/position.h`, and
`src/position.cpp` byte-for-byte to that baseline.
