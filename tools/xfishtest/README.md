# xfish Xiangqi fishtest

This directory contains the reproducible glue used to run distributed,
paired Xiangqi engine matches for xfish.

The server is pinned to `ianfab/fishtest` commit
`4358b10e7901f63be94a51500d7a75040627e016`.  Games are run with
`fairy-stockfish/variantfishtest` commit
`acecc04a3501f2efbe6b07a87187fd105b37ac3a`.  The opening source is
`fairy-stockfish/books` commit
`aecb9b0cfe0a8a97b13f8ea8b86157fa07e13f45`, file `xiangqi.epd`
(SHA-256 `a52a4630ad69b99c26ee587232d9d209b82d9e4dc3142dbd4d31a93857d1ea5f`).

## Test policy

- Each opening is played twice with colors reversed.
- Openings are assigned deterministically from the server task index, with no
  overlap between machines.
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
- The server stores W/L/D while workers retain the paired pentanomial and full
  move logs.  `worker/report.py` computes paired Elo, confidence interval, and
  LOS without treating color-reversed games as independent.
- Baseline promotion uses two sequential SPRT stages with `alpha=beta=0.05`:
  STC `10+0.1` must cross the upper LLR boundary under
  `SPRT(0.0, 2.0)`, then LTC `60+0.6` with an independent opening seed must
  cross the upper boundary under `SPRT(0.5, 2.5)`. The nominal boundaries are
  `+/-ln(19)`, or about `+/-2.94444`. Fixed-game point estimates do not
  qualify a baseline.
- Create STC with `server/admin.py create-run --sprt-stage stc ...`. Create
  LTC with `--sprt-stage ltc --parent-run-id <accepted-stc-run> ...`; the
  server rejects LTC if the parent did not reach the STC upper boundary or if
  either engine SHA differs. SPRT defaults to a 100,000-game safety cap;
  STC uses 200-game tasks and LTC uses 40-game tasks unless explicitly
  overridden.

The upstream runner expects a `UCI_Variant` option.  Pikafish is Xiangqi-only
and intentionally does not expose that option, so `worker/xiangqi_match.py`
accepts a missing option only for `xiangqi` and suppresses only that one
unsupported `setoption` command.

## Layout

- `docker-compose.yml` and `server/`: Pyramid fishtest UI/API plus MongoDB.
- `worker/worker.py`: cross-platform worker and deterministic task adapter.
- `worker/xiangqi_match.py`: strict two-game Xiangqi match wrapper.
- `worker/report.py`: paired result aggregation and integrity checks.

Secrets and machine-local configuration are deliberately ignored by Git.
Use `server/admin.py create-user --worker-only` for dedicated machine accounts;
this keeps worker credentials separate without granting the web/API admin
group. Before activating a new experiment, use `server/admin.py list-runs` to
audit unfinished tests so a worker is never assigned an obsolete task whose
engine hashes are absent from its candidate-specific config.
