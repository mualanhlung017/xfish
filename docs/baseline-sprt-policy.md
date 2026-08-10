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

The LLR statistic is the paired pentanomial normalized-Elo calculation from
the pinned official Stockfish fishtest implementation. For every update,
`games == 2 * sum(pentanomial)` is mandatory. Trinomial-only LLR, including
results produced by the legacy variant-fishtest SPRT implementation, is not a
valid gate result.

## Retrospective baseline audit

`v0.3.0-nnue-thp` is the owner-approved grandfathered baseline. The new SPRT
policy applies to every baseline promotion after v0.3.0.

| Baseline | Historical evidence | SPRT audit | Decision |
| --- | --- | --- | --- |
| `v0.3.0-nnue-thp` | owner-approved pre-policy baseline | grandfathered | retained |
| `v0.4.0-king-square-cache` | 2,000/10,000 fixed STC games; final `+1.11 +/- 1.80` Elo | no STC LLR; no LTC run | revoked |
| `v0.5.0-checker-fastpath` | 2,000/10,000 fixed STC games; final `+0.69 +/- 1.73` Elo | no STC LLR; no LTC run | revoked |

The accepted baseline therefore rolls back to `v0.3.0-nnue-thp` at commit
`1699e6ba6df744f83951c66bfd5832647d65e41d`. Historical tags, releases, and
test evidence remain immutable for audit, but they are not accepted baselines.
The source rollback restores `src/position.h` and `src/position.cpp` to that
baseline while retaining v0.3.0's Linux THP path in `src/shm.h`.
