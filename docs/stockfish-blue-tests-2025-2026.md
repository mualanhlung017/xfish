# Stockfish blue Fishtest inventory (2025-2026)

Source: [Stockfish Finished Tests](https://tests.stockfishchess.org/tests/finished)
through the official public `/api/finished_runs` endpoint.

A blue result is an accepted SPRT whose bound midpoint is negative,
for example normalized-Elo `[-1.75, +0.25]`. It proves the configured
non-regression condition, not that the patch gained Elo.

## Coverage

- Window: `2025-01-01T00:00:00+00:00` through `2027-01-01T00:00:00+00:00`.
- Successful finished runs read: 2431.
- Blue accepted runs: 723.
- Blue runs with positive observed W/L: 605.
- Blue runs with non-positive observed W/L: 118.
- Official commits directly citing a blue run: 251.
- Official commits left for manual review: 1.
- Distinct uncited source objects: 238.
- Heuristic source-review rows: 74.

## Official manual review

| Date | Commit | Subject | Blue tests | Flags |
| --- | --- | --- | ---: | --- |
| 2026-03-18 | [`e093339c`](https://github.com/official-stockfish/Stockfish/commit/e093339c2fc651eb9b5adeeb3b666b1fcfa7ad42) | Use existing function for removing and placing a piece. | 1 | - |

## Experimental source-review pool

This is an intentionally broad reproducible pool, not the execution
queue. Source-level Xiangqi decisions belong in the accompanying port
plan; rejected rows remain in the JSON ledger to prevent rediscovery.

| Date | Source | Tag | Tests | W-L delta | Files |
| --- | --- | --- | ---: | ---: | --- |
| 2026-08-09 | [`b38e604e`](https://github.com/AdrianGHUB15/Stockfish/commit/b38e604e1c93768c2efc83e4f5c6f7a96de1469d) | RazorSimp | 1 | +73 | src/search.cpp |
| 2026-08-08 | [`0d5d1f14`](https://github.com/FauziAkram/Stockfish/commit/0d5d1f146bba376f34ff6bc9c2b46ec7bf2708b1) | simpeva3 | 1 | +97 | src/evaluate.cpp |
| 2026-08-08 | [`166643a4`](https://github.com/FauziAkram/Stockfish/commit/166643a46b64aac2040e0d5ce9bba0b3dd6fba84) | simpeva2 | 1 | +85 | src/evaluate.cpp |
| 2026-07-09 | [`16739297`](https://github.com/FauziAkram/Stockfish/commit/16739297861f866a09f3059e8899f5f8189967e3) | simp205 | 1 | +134 | src/search.cpp |
| 2026-06-25 | [`4e1f4fad`](https://github.com/ces42/Stockfish/commit/4e1f4fad18ddd974041083c5e182820ccc0ab500) | simp-prefetch | 1 | +99 | src/position.cpp, src/position.h, src/search.cpp |
| 2026-06-18 | [`e71db0e3`](https://github.com/zungur/Stockfish/commit/e71db0e33089be7344633d2be45262cddc8d7c9a) | nullmove-qsearch-stalemate-fix | 1 | +119 | src/position.cpp, src/search.cpp |
| 2026-06-16 | [`65134163`](https://github.com/FauziAkram/Stockfish/commit/651341631dda3dcd9dab117bef75f37d334f615e) | simp204 | 1 | -502 | src/search.cpp |
| 2026-05-22 | [`712db16c`](https://github.com/FauziAkram/Stockfish/commit/712db16c9bc20ba8be7993c7e88d3a5f7b6b3522) | simp203 | 1 | +114 | src/search.cpp |
| 2026-05-17 | [`a95991ae`](https://github.com/FauziAkram/Stockfish/commit/a95991ae391fa9b0f25161a998ae691a3eb33155) | simpsct2 | 1 | -26 | src/search.cpp |
| 2026-05-13 | [`4d2cfbbf`](https://github.com/FauziAkram/Stockfish/commit/4d2cfbbf539533a9c4474cb499f9c1fabc397d80) | simpsct | 1 | +207 | src/search.cpp |
| 2026-05-13 | [`96451ce9`](https://github.com/FauziAkram/Stockfish/commit/96451ce9b605a07ac0a95207862780408bd0510a) | followsimp1 | 1 | +229 | src/search.cpp |
| 2026-04-26 | [`d899e696`](https://github.com/anematode/Stockfish/commit/d899e696071b5cb13d9b67c21bf9c209b6eaf294) | lesser-bench | 1 | +185 | src/Makefile |
| 2026-04-21 | [`39f3a755`](https://github.com/robertnurnberg/Stockfish/commit/39f3a7555f400463459c1138f1cb4bdf6abf82a5) | fix-isssue-6756 | 1 | +156 | src/search.cpp, src/search.h, src/thread.cpp |
| 2026-03-29 | [`75cb3711`](https://github.com/maximmasiutin/Stockfish/commit/75cb3711f68b32d5eb08fd639d5d538ae499b6f0) | singular-signed-correction | 1 | +233 | src/search.cpp |
| 2026-03-26 | [`9019d35f`](https://github.com/FauziAkram/Stockfish/commit/9019d35fb7eeae4f444fc4432b5de006284a2f69) | simp200 | 1 | +189 | src/search.cpp |
| 2026-03-05 | [`103bb2c4`](https://github.com/FauziAkram/Stockfish/commit/103bb2c48e291149ca2846dc29f7c75dbd422c34) | simpr5a | 1 | +131 | src/search.cpp |
| 2026-02-22 | [`0e3d15ec`](https://github.com/Anroshka/Stockfish/commit/0e3d15ec976565dc1a633e4d262ac7e48ddf3c05) | pos1 | 1 | +173 | src/position.cpp |
| 2026-02-18 | [`1f8487d0`](https://github.com/rn5f107s2/Stockfish/commit/1f8487d07b967ddd74e0d6bc0862a6c6fdd46fae) | alwaysNegext | 1 | +25 | src/search.cpp |
| 2026-02-15 | [`f1e13d03`](https://github.com/FauziAkram/Stockfish/commit/f1e13d03e32332b7dd0458efd55c5566cf85e8dd) | simpdep | 1 | +221 | src/search.cpp |
| 2026-02-03 | [`6cd5828d`](https://github.com/pieterteb/Stockfish/commit/6cd5828d1741270a56eb42067e1b7ed00ac863f3) | undo-move | 1 | -29 | src/position.cpp |
| 2026-01-31 | [`1122503d`](https://github.com/maximmasiutin/Stockfish/commit/1122503d07a499a8110935fc0f3af23486184c83) | simplify-shuffle-guard | 1 | +137 | src/search.cpp |
| 2026-01-30 | [`29dc894d`](https://github.com/FauziAkram/Stockfish/commit/29dc894d1bfd1fbc397ec55482bffa573e9fc7de) | prris | 2 | +318 | src/search.cpp |
| 2026-01-26 | [`44d75cc7`](https://github.com/jake-ciolek/Stockfish/commit/44d75cc7a1788087aafffcb324944e53887d16be) | pgo-depth-12 | 1 | -90 | src/Makefile |
| 2026-01-19 | [`e8d83f5a`](https://github.com/jake-ciolek/Stockfish/commit/e8d83f5a8169d82be33510fa9ef2dc15ed5c19b1) | remove-prefetch-do_move | 2 | +372 | src/position.cpp |
| 2026-01-17 | [`b277d3ec`](https://github.com/lemteay/Stockfish/commit/b277d3ecafa6bcff29adf94ab1073a4a707b0140) | raise-inline-threshold | 1 | +114 | src/Makefile, src/main.cpp |
| 2026-01-14 | [`2e0c2964`](https://github.com/maximmasiutin/Stockfish/commit/2e0c2964db379812ba19cfa247543bab792bc2d1) | feature/conthist-incheck-limit-simplify | 1 | +59 | src/search.cpp |
| 2026-01-13 | [`dd4bfe53`](https://github.com/pb00068/Stockfish/commit/dd4bfe5348a5ed1a1960c85141281fc15af5d898) | retro | 1 | +180 | src/engine.cpp, src/search.cpp, src/search.h, src/types.h |
| 2026-01-12 | [`9f952304`](https://github.com/maximmasiutin/Stockfish/commit/9f952304a32fde60e1071f9d3801f033850359d5) | feature/tt-verification-simplify | 1 | +134 | src/search.cpp |
| 2026-01-12 | [`8d9719c6`](https://github.com/FauziAkram/Stockfish/commit/8d9719c696ff38eb46e353cfb70c8fc4535d937b) | ffnt1 | 1 | +230 | src/search.cpp |
| 2026-01-11 | [`370fcb0b`](https://github.com/pb00068/Stockfish/commit/370fcb0beb667e2861558d409b16e817a4063914) | retro | 1 | +8 | src/engine.cpp, src/search.cpp, src/search.h, src/thread.cpp, src/types.h |
| 2026-01-11 | [`9e74bc93`](https://github.com/maximmasiutin/Stockfish/commit/9e74bc93eeb0609fd1d7a3ecb3deb0d73cc9ffb9) | feature/qsearch-repetition-guard-simplify | 1 | +185 | src/search.cpp |
| 2026-01-08 | [`640da5a3`](https://github.com/maximmasiutin/Stockfish/commit/640da5a3cbdddf7b6b911a99bb42e647e33f08e8) | feature/singular-margin-simplify | 2 | +301 | src/search.cpp |
| 2026-01-04 | [`65a2c208`](https://github.com/FauziAkram/Stockfish/commit/65a2c208f76cedececf5c8bc58f7869838e2064e) | isus1 | 1 | +134 | src/search.cpp |
| 2025-12-23 | [`a8123bc2`](https://github.com/FauziAkram/Stockfish/commit/a8123bc224d57eb4b482aae8a9a43c9ca885d2b3) | simp198 | 1 | +226 | src/search.cpp |
| 2025-11-27 | [`ceecb086`](https://github.com/FauziAkram/Stockfish/commit/ceecb086fcb8e6d8fbc9d2a388f4816f4fb97a7b) | simt4a | 1 | +1 | src/search.cpp |
| 2025-11-25 | [`bff6d3a0`](https://github.com/FauziAkram/Stockfish/commit/bff6d3a08afbac55a7eeb0b5ae3265e599f92db6) | simta | 1 | +216 | src/search.cpp |
| 2025-11-20 | [`985de873`](https://github.com/KazApps/Stockfish/commit/985de873dd5ecf6220911fc2593d3375c56d2f5f) | use-pushif-more | 1 | +38 | src/misc.h, src/nnue/features/full_threats.cpp, src/nnue/features/half_ka_v2_hm.cpp |
| 2025-11-18 | [`9b75ec65`](https://github.com/KazApps/Stockfish/commit/9b75ec653baef40ac071817a186b2dbfe2eec74b) | small-speedup | 1 | -348 | src/nnue/features/full_threats.cpp |
| 2025-11-16 | [`ca98f789`](https://github.com/anematode/Stockfish/commit/ca98f78959ecaf452954e150c6a65f3bff94e571) | oxpecker | 1 | +145 | src/nnue/nnue_accumulator.cpp |
| 2025-11-12 | [`3cc10218`](https://github.com/kevlu8/Stockfish/commit/3cc10218450349a28d343ef28255d379766fb474) | simp-mkidx | 1 | -37 | src/nnue/features/full_threats.cpp |
| 2025-10-17 | [`2bbaa1a6`](https://github.com/FauziAkram/Stockfish/commit/2bbaa1a655c6b51a2998cd7507191131166789d0) | simp40a | 1 | +15 | src/search.cpp |
| 2025-10-17 | [`aec74528`](https://github.com/xu-shawn/Stockfish/commit/aec745288cd3727567f43334dd9f97829f15b9a4) | try_speedup | 1 | +182 | src/nnue/nnue_accumulator.cpp |
| 2025-09-10 | [`cfcf7067`](https://github.com/pb00068/Stockfish/commit/cfcf706747f9bf31fa7b1455865d2b1b707b47ed) | simpAwayVerification | 2 | -284 | src/search.cpp |
| 2025-09-10 | [`92f2ed24`](https://github.com/FauziAkram/Stockfish/commit/92f2ed2480040da179d1d81593808a4c26b978f9) | simp191 | 1 | +152 | src/search.cpp |
| 2025-09-10 | [`24a6b13e`](https://github.com/pb00068/Stockfish/commit/24a6b13e7d211703dbac83bf2c8f0053d56d560d) | simpAwayVerification | 1 | +201 | src/search.cpp |
| 2025-09-05 | [`4a0cca47`](https://github.com/FauziAkram/Stockfish/commit/4a0cca47a5315798f9c5569c58bf85874e316e8e) | simp179g | 1 | -134 | src/search.cpp |
| 2025-09-02 | [`34a1296c`](https://github.com/ces42/Stockfish/commit/34a1296cf7fc581794845ef357766e9ceb00d9f6) | quiet-king-simp | 2 | +5 | src/movegen.cpp, src/movegen.h, src/movepick.cpp, src/movepick.h, src/position.cpp, src/position.h |
| 2025-08-31 | [`699c66aa`](https://github.com/xu-shawn/Stockfish/commit/699c66aa8cf06993ea89db19589142c40f1b7c6a) | test1562 | 1 | +74 | src/search.cpp |
| 2025-08-25 | [`e0ac2aa6`](https://github.com/Nonlinear2/Stockfish/commit/e0ac2aa638d7ba9fc60c8cf82b364b2a13631fcd) | simplify-quiet-moves-streak | 1 | +98 | src/search.cpp, src/search.h |
| 2025-08-22 | [`d7e2a3de`](https://github.com/AliceRoselia/Stockfish-1/commit/d7e2a3de15edb75dc2edc4666ef481637b1f0dae) | Simpnmpverification | 2 | -114 | src/search.cpp, src/search.h, src/thread.cpp |
| 2025-08-17 | [`33d45a21`](https://github.com/FauziAkram/Stockfish/commit/33d45a21ee7eb59229429d81782896d19a4bb9e5) | simp176 | 2 | +126 | src/search.cpp |
| 2025-07-15 | [`6d0fd92f`](https://github.com/daniel-monroe/Stockfish/commit/6d0fd92fd66cf5da2bef2bad3fbb8659b7e4ef9a) | nmpmeme | 1 | +117 | src/search.cpp |
| 2025-06-12 | [`a6d14c21`](https://github.com/Ergodice/Stockfish/commit/a6d14c21138b47772abecf80e524f8ef755a3f48) | badsimp1 | 1 | +191 | src/search.cpp |
| 2025-05-27 | [`ec8c7bdb`](https://github.com/FauziAkram/Stockfish/commit/ec8c7bdb275667047069bb352ad832d7bbb38132) | simp184a | 1 | +212 | src/search.cpp |
| 2025-05-22 | [`e39d503d`](https://github.com/FauziAkram/Stockfish/commit/e39d503d2ef834464c1a1678fda7719be06b154e) | simp182 | 1 | +63 | src/search.cpp |
| 2025-05-18 | [`f0d24d4b`](https://github.com/pb00068/Stockfish/commit/f0d24d4b079420a4dae752165c797420a4a92263) | exp352 | 1 | +105 | src/search.cpp, src/types.h |
| 2025-05-13 | [`c6f7d7a2`](https://github.com/loco-loco/Stockfish/commit/c6f7d7a21451b80c4097f0b5aea056b01e4bc95c) | expSimpl | 1 | +154 | src/search.cpp |
| 2025-05-02 | [`4a989a8c`](https://github.com/joergoster/Stockfish/commit/4a989a8cfdd4e8e761cc850e4db8acc9c5ff7e92) | simp002 | 2 | +87 | src/search.cpp |
| 2025-04-27 | [`05cde714`](https://github.com/FauziAkram/Stockfish/commit/05cde714db610e0fe5b50c33a53f28e79be5b382) | simp172a | 1 | +195 | src/search.cpp |
| 2025-04-18 | [`083b58d8`](https://github.com/Ergodice/Stockfish/commit/083b58d8c7adbe783890ce6d4f88fd9179a0a89f) | ttpvsimp | 1 | +193 | src/search.cpp |
| 2025-04-05 | [`c108b246`](https://github.com/xu-shawn/Stockfish/commit/c108b246be68d4f4394874e413899ced6f37f81b) | test1278 | 1 | +211 | src/search.cpp |
| 2025-03-23 | [`54e1efad`](https://github.com/FauziAkram/Stockfish/commit/54e1efad7cbc1f15fb976577a3d7aa49142898fe) | simp164 | 1 | +161 | src/search.cpp |
| 2025-03-02 | [`bdde8406`](https://github.com/FauziAkram/Stockfish/commit/bdde840651e671a81ec4ee94693b3ac0a13b6ef4) | sfmate11 | 2 | +296 | src/search.cpp |
| 2025-03-02 | [`0d567963`](https://github.com/AliceRoselia/Stockfish-1/commit/0d5679632f147512ba9bbcf299cb8c9959b825c3) | Pos_gives_check_move_ordering | 2 | +161 | src/movepick.cpp |
| 2025-02-25 | [`9fa8cec4`](https://github.com/xu-shawn/Stockfish/commit/9fa8cec495f9a6e68632948b115e4848122a10c9) | test1191 | 1 | -194 | src/search.cpp |
| 2025-02-23 | [`da7e1ae1`](https://github.com/Ergodice/Stockfish/commit/da7e1ae114d8dbc53283203edd3d609b3e1075e1) | futsimp2 | 1 | -169 | src/search.cpp |
| 2025-02-02 | [`f56721c4`](https://github.com/FauziAkram/Stockfish/commit/f56721c4a1dd3316b234bff718d50736240c54b2) | crazysim | 1 | +192 | src/search.cpp |
| 2025-01-30 | [`61f6262c`](https://github.com/FauziAkram/Stockfish/commit/61f6262c201efadb50f9a49aeff40d1cc459fdf4) | mrgc2 | 1 | +215 | src/search.cpp |
| 2025-01-30 | [`a01b43c6`](https://github.com/Ergodice/Stockfish/commit/a01b43c64d2b76d29186032dd078ce6add80339b) | test951 | 1 | +91 | src/search.cpp |
| 2025-01-30 | [`f9b41b8a`](https://github.com/FauziAkram/Stockfish/commit/f9b41b8a859c7e7bcb75f72072f0b026b297118e) | mrgc | 1 | +140 | src/search.cpp |
| 2025-01-26 | [`22133a72`](https://github.com/kennethlee33/Stockfish/commit/22133a7241e8d4e83af8b7fc32aa7d9d8f4030a9) | simp1 | 2 | +449 | src/search.cpp |
| 2025-01-11 | [`4a5e0e04`](https://github.com/ces42/Stockfish/commit/4a5e0e047b309cd82c86bd23e05873f77e22e0fe) | prefetch2-cleaner | 4 | +212 | src/position.cpp, src/position.h, src/search.cpp |
| 2025-01-08 | [`f26b3f88`](https://github.com/xu-shawn/Stockfish/commit/f26b3f88b5deec2aecc2e9142d85655b3ea8d5ab) | test949 | 1 | +78 | src/search.cpp |
| 2025-01-04 | [`adcd7b97`](https://github.com/Ergodice/Stockfish/commit/adcd7b97ceef15392c2ff34dd285c63e1158f282) | corrplexitysimp | 1 | +203 | src/search.cpp |
