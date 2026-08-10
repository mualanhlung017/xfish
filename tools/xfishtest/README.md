# xfish Xiangqi fishtest

This directory contains the reproducible glue used to run distributed,
paired Xiangqi engine matches for xfish.

The server is pinned to `ianfab/fishtest` commit
`4358b10e7901f63be94a51500d7a75040627e016`. Its Xiangqi API is retained,
while sequential-test likelihoods are calculated with `LLRcalc.py` from
`official-stockfish/fishtest` commit
`b571c90db880f973a7eea57bd344600fe89a7e8e`. Games are run with
`fairy-stockfish/variantfishtest` commit
`acecc04a3501f2efbe6b07a87187fd105b37ac3a`.  New Elo tests use the immutable
Xfish-generated `xfish-uho-3mvs-w65-85-v1.epd` corpus documented in
`../../docs/xiangqi-uho-book.md`.  The historical `xiangqi.epd` corpus is
retained only for reproduction and must not be assigned to a new run.
Variantfishtest remains only the pinned match coordinator: no Fairy-Stockfish
engine participates in generating, scoring, or filtering the new book.
The frozen v1 artifact has 79,270 unique positions and SHA-256
`5ede082489580fb6aeb8c06c3eb34f72a916c5dbb7ee621b350b835dbdc48b0f`.

Apply `patches/variantfishtest-stderr-close-race.patch` to the pinned
variantfishtest checkout on every worker. It handles only the normal shutdown
race where the stdout reader closes standard streams while the stderr reader
is blocked in `readline()`; unexpected `ValueError` remains fatal and visible
to the artifact auditor. The patched `chess/uci.py` SHA-256 is
`b09bcb0dc8e34e5bef114c6c668d780bac5b5dd7e67ad6b577b4be76275b3f08`.

## Test policy

- Each opening is played twice with colors reversed.
- Openings are assigned deterministically from the server task index, with no
  overlap between machines.
- The run and every worker must agree exactly on book ID, SHA-256, unique
  position count, and opening seed.  Workers reject missing or mismatched
  metadata, and the server rejects a game cap that would reuse a position.
- The default short time control is Stockfish's `10+0.1`, scaled on each
  worker by `628000 / loaded_baseline_nps`.
- Normal runs default to `Threads=1`, `Hash=16`. The run creator also accepts
  validated `--threads` and `--hash-mb` values for explicit SMP experiments;
  both engines always receive the same values and the checksum-verified NNUE
  assigned to that engine. Entries without an
  engine-specific `network` use the common checked NNUE file.  Thus release
  packages with a different network architecture can be tested intact, while
  engine speed changes remain part of the Elo result.
- Worker `concurrency` is the physical-core budget advertised to Fishtest. For
  a run with `Threads=N`, the adapter starts at most
  `floor(concurrency / N)` color-reversed pair processes. Pin a worker to one
  intended NUMA/socket CPU set before launch; child engines inherit that set.
- Workers send both W/L/D and the paired pentanomial to the server while also
  retaining every pair summary and full move log. The server rejects any SPRT
  update whose game count does not equal twice the pentanomial pair count.
  `worker/report.py` computes paired Elo, confidence interval, and LOS without
  treating color-reversed games as independent.
- Baseline promotion uses two sequential SPRT stages with `alpha=beta=0.05`:
  STC `10+0.1` must cross the upper LLR boundary under
  `SPRT(0.0, 2.0)`, then LTC `60+0.6` with an independent opening seed must
  cross the upper boundary under `SPRT(0.5, 2.5)`. The nominal boundaries are
  `+/-ln(19)`, or about `+/-2.94444`. LLR uses the official fishtest
  pentanomial normalized-Elo model. Fixed-game point estimates and legacy
  trinomial LLR do not qualify a baseline.
- Create STC with `server/admin.py create-run --sprt-stage stc ...`. Create
  LTC with `--sprt-stage ltc --parent-run-id <accepted-stc-run> ...`; the
  server rejects LTC if the parent did not reach the STC upper boundary or if
  either engine SHA differs. SPRT defaults to a 100,000-game safety cap;
  STC uses 200-game tasks and LTC uses 40-game tasks unless explicitly
  overridden. `sprt-watcher` evaluates the paired LLR every two seconds and
  stops the run at either boundary; reaching the safety cap between the
  boundaries records `inconclusive`. It also persists the current LLR and
  pentanomial for the web dashboard and writes a complete `results_info`
  record atomically with every terminal decision, so finished custom SPRT runs
  remain renderable by the pinned variant-fishtest server.

The upstream runner expects a `UCI_Variant` option.  Pikafish is Xiangqi-only
and intentionally does not expose that option, so `worker/xiangqi_match.py`
accepts a missing option only for `xiangqi` and suppresses only that one
unsupported `setoption` command.

## Layout

- `docker-compose.yml` and `server/`: Pyramid fishtest UI/API, MongoDB, and the
  pentanomial SPRT watcher.
- `worker/worker.py`: cross-platform worker and deterministic task adapter.
- `worker/xiangqi_match.py`: strict two-game Xiangqi match wrapper.
- `worker/report.py`: paired result aggregation and integrity checks.
- `patches/`: audited fixes applied on top of pinned third-party test tools.

Secrets and machine-local configuration are deliberately ignored by Git.
Use `server/admin.py create-user --worker-only` for dedicated machine accounts;
this keeps worker credentials separate without granting the web/API admin
group. Before activating a new experiment, use `server/admin.py list-runs` to
audit unfinished tests so a worker is never assigned an obsolete task whose
engine hashes are absent from its candidate-specific config.
