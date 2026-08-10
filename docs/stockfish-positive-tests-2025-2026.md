# Stockfish Finished Tests positive-Elo inventory (2025-2026)

Source: [Stockfish Finished Tests](https://tests.stockfishchess.org/tests/finished)
through its public `/api/finished_runs` endpoint. The catalog uses the
finished timestamp and retains successful runs whose score point estimate
is positive (`wins > losses`). `score_elo` is the logistic conversion of
W/L/D and is used only for sign/ranking; the original SPRT model and LLR
remain in the JSON artifact.

## Coverage

- Window: `2025-01-01T00:00:00+00:00` through `2027-01-01T00:00:00+00:00`.
- API mode: `successful/green only`.
- Finished runs read: 2429.
- Positive point-estimate runs: 2311.
- Positive runs cited by official Stockfish commit messages: 759.
- Distinct official commits represented: 426.
- Diagnostic only: 84 runs had an exact `resolved_new` on master; these are not used for attribution.
- New automatic manual-review queue after durable xfish ledgers: 17.

A green SPRT result and a positive W/L/D point estimate are separate
conditions. Requiring both avoids treating a non-regression test with a
slightly negative observed score as an Elo-gain candidate.

## Official-commit review queue

| Date | Commit | Subject | Best positive test | W-L-D | Elo | Flags |
| --- | --- | --- | --- | ---: | ---: | --- |
| 2026-07-10 | [`9d4090e8`](https://github.com/official-stockfish/Stockfish/commit/9d4090e82685cca447265dcd7093d617cb34a107) | Scale Null Move Pruning reduction dynamically based on evaluation margin | [`6a4b864f`](https://tests.stockfishchess.org/tests/view/6a4b864ff97ff95f78795e52) | 53879-53224-98697 | +1.106 | post-sf18 |
| 2026-07-03 | [`99489f57`](https://github.com/official-stockfish/Stockfish/commit/99489f57dddb121e1db887d35561ea58abd4158a) | Simplify out pext attacks | [`6a421b46`](https://tests.stockfishchess.org/tests/view/6a421b46f97ff95f78795061) | 21240-21075-39317 | +0.702 | post-sf18 |
| 2026-06-30 | [`60888387`](https://github.com/official-stockfish/Stockfish/commit/6088838797d6333711c17fe2c0962fa0858517ec) | Yeet psqt weights | [`6a3eaac6`](https://tests.stockfishchess.org/tests/view/6a3eaac63036e45021aeb937) | 53521-53489-100382 | +0.054 | post-sf18 |
| 2026-06-06 | [`9eb836b3`](https://github.com/official-stockfish/Stockfish/commit/9eb836b3b5302483319daa83e6d58749ab2e31c0) | Compute simplified HQ r/rr at runtime | [`6a15f031`](https://tests.stockfishchess.org/tests/view/6a15f031818cacc1db0aca49) | 104369-103556-202283 | +0.689 | post-sf18, chess-specific-review |
| 2026-05-17 | [`f8aa78e0`](https://github.com/official-stockfish/Stockfish/commit/f8aa78e0a7e8853370e5989fc23783f3b244ac42) | Simplify ttMove reduction formula | [`69fa69c8`](https://tests.stockfishchess.org/tests/view/69fa69c83a3c3e525bb2b645) | 28313-28180-54227 | +0.417 | post-sf18 |
| 2026-05-10 | [`a12dc6cc`](https://github.com/official-stockfish/Stockfish/commit/a12dc6cc1fdf754fd061780548d57fa89d92f59d) | VVLTC parameter's tune | [`69fa262f`](https://tests.stockfishchess.org/tests/view/69fa262f3a3c3e525bb2b5e7) | 20207-19894-38071 | +1.391 | post-sf18 |
| 2026-05-04 | [`dc168634`](https://github.com/official-stockfish/Stockfish/commit/dc1686345cf29789cdb823441bf198928a5f0d66) | Hyperbola quintessence for ARM | [`69f44c1e`](https://tests.stockfishchess.org/tests/view/69f44c1e1e5788938e86aa2a) | 7340-7053-13287 | +3.603 | post-sf18 |
| 2026-05-04 | [`1554a2ca`](https://github.com/official-stockfish/Stockfish/commit/1554a2ca0b85c8fa94cfe8f4b68bd85e62107d6c) | Precompute moves and use magics index as compress mask on AVX512ICL | [`69f6df65`](https://tests.stockfishchess.org/tests/view/69f6df65b64b50e29dbed427) | 29195-28782-54247 | +1.279 | post-sf18 |
| 2026-04-26 | [`e17725f4`](https://github.com/official-stockfish/Stockfish/commit/e17725f445e52544f749ef65107cda8ac93d0449) | Constexpr attacks (pext only) | [`69d20732`](https://tests.stockfishchess.org/tests/view/69d2073261a12cebe17edc04) | 10057-9749-18594 | +2.787 | post-sf18 |
| 2026-04-15 | [`b1fb50ae`](https://github.com/official-stockfish/Stockfish/commit/b1fb50ae697265369d51c002603a621ffe8f9bfa) | Simplify away the special case for en passant in the legality check | [`696ffb65`](https://tests.stockfishchess.org/tests/view/696ffb6512ee1f6231b96fe8) | 20380-20210-38482 | +0.747 | post-sf18, chess-specific-review |
| 2026-04-09 | [`ead7e650`](https://github.com/official-stockfish/Stockfish/commit/ead7e650da1dd07a2614ba4d8207470fe921a87b) | Fix weird indexing bug | [`69d00a7e`](https://tests.stockfishchess.org/tests/view/69d00a7ee2b443cb2670b5c6) | 25867-25732-49657 | +0.463 | post-sf18, chess-specific-review |
| 2026-04-09 | [`969542e4`](https://github.com/official-stockfish/Stockfish/commit/969542e4f02c7aa396d727d9630da28fd8cef098) | Simplify HalfKAv2_hm::write_indices() | [`69bb1faf`](https://tests.stockfishchess.org/tests/view/69bb1fafd7d60419badf31a3) | 30024-29895-56625 | +0.385 | post-sf18 |
| 2026-03-18 | [`add17326`](https://github.com/official-stockfish/Stockfish/commit/add173263d12ea1b2ec7d6a6ebf2566894b2402c) | VVLTC Tune | [`69b43f66`](https://tests.stockfishchess.org/tests/view/69b43f666c456d3a77a50a5d) | 18119-17814-33877 | +1.518 | post-sf18 |
| 2026-03-18 | [`8b499683`](https://github.com/official-stockfish/Stockfish/commit/8b499683863640c8359a9d853176761a7dc0c09f) | Speed up update_accumulator_refresh_cache with AVX512ICL | [`69ab916c`](https://tests.stockfishchess.org/tests/view/69ab916ccb31ee884aed62ea) | 55550-54991-102419 | +0.912 | post-sf18 |
| 2026-02-18 | [`e6d04b4e`](https://github.com/official-stockfish/Stockfish/commit/e6d04b4ec59f3439fb050c9bb24a281a407dcf13) | VVLTC tune | [`69923ea8`](https://tests.stockfishchess.org/tests/view/69923ea872254723ef22c6fa) | 8784-8499-16127 | +2.964 | post-sf18 |
| 2026-02-04 | [`24af6a6b`](https://github.com/official-stockfish/Stockfish/commit/24af6a6bc409541a3d6e5cab7c5923ac397476fd) | Update castling rights unconditionally. | [`697e6f4e`](https://tests.stockfishchess.org/tests/view/697e6f4e5f56030af97b5a3c) | 42214-42137-79329 | +0.163 | post-sf18, chess-specific-review |
| 2026-02-04 | [`2321cf2f`](https://github.com/official-stockfish/Stockfish/commit/2321cf2f77b241d685ee68c9896f6574a6f12d0d) | Simplify en passant square update in Position::do_move(). | [`6973b06c`](https://tests.stockfishchess.org/tests/view/6973b06c6cd60a8e97ca62e5) | 31011-30884-57785 | +0.369 | post-sf18, chess-specific-review |

Automatic exclusions are intentionally conservative. A row reaching
this queue still needs a source-level Xiangqi applicability review; it
is not authorization to apply several patches together.
