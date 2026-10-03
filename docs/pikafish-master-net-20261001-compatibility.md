# Pikafish master-net 2026-10-01 compatibility

The owner authorized support for the already-trained new official network.
This work starts from Xfish v0.5.0 `8f1a0eb9f5af4e0a221746ffc5e569b212768492`.
It does not train network weights or change the accepted baseline/network pool.

Pinned upstream source: Pikafish master
`1c66b9b21cf2f280ce3b3ffa80c1c6609f2b29ff` (2026-10-01).
The format change is commit
`eaa27c5a4b1b6f0c92a36afe16dbd336ecfa61d9`, "SFNNv17: Remove psqt accumulator
and update default net". The guarded LEB128 decoder follows upstream
`130a4755`; header description reads follow current master.

Official asset `602741746`, `pikafish.nnue`, updated 2026-10-01 07:57:19 UTC:

- Size: 49,982,985 bytes.
- SHA-256: `6b74ac7bbd299dc26a17803135b616eda9248bef0cbfc7b811bfcf981832ba29`.
- Source: https://github.com/official-pikafish/Networks/releases/tag/master-net

Legacy frozen network SHA-256:
`3cd15292bf8c979884262f57fc723959fc0dea43b4d8d544f88db5ceb2479e24`.

## Cause and implementation

Unmodified v0.5.0 exits with code 1 when asked to evaluate using the new file.
It prints that the network was not loaded successfully. SFNNv17 omits both
PSQT parameter blocks. The feature dimensions and header/layer hashes remain
the same, so accepting only the header cannot establish compatibility.

The compatibility loader tries a complete legacy parse, then rewinds and tries
a complete no-PSQT parse. Both must validate version, feature and layer hashes,
parameter reads and exact EOF. No hash check is weakened. Guarded LEB128 reads
reject truncated/missing/wrong magic blocks and avoid signed-shift undefined
behavior. Header descriptions are read in bounded chunks.

The existing PSQT arrays/caches remain available for legacy networks. For
SFNNv17 the unused PSQT weights are zero, the PSQT output is not read, and the
AVX2/RVV PSQT update loops are skipped. Network export retains the detected
format. Format participates in the no-PSQT content identity. UCI information
identifies SFNNv16 or SFNNv17; filenames do not determine format.

Both official Zstd containers and raw exports are accepted. Zstd errors and
incomplete final frames reject the entire decompressed payload; partially
decoded data is never passed off as a successful network load.

Legacy networks retain the exact v0.5.0 evaluation scaling. New networks use
current Pikafish master's material-alignment scaling: normalized material/NNUE
alignment, denominator 80030, and rule-60 damping 244. This replaces the old
PSQT-versus-positional complexity expression only for no-PSQT networks.

Position, move generation, repetition/chase, search heuristics, NNUE input
feature numbering and the `NO_ROOT_ROOT` contract are unchanged. The architecture
and weights are supplied by upstream; no local NNUE training is required.

## Reproduction and verification

Evidence is under `build/analysis/pikafish-master-net-20261001-compat` in the
main workspace: asset/header/source audit, old-binary rejection, raw logs,
old/new numerical comparison, full-history rook rules and final binary hashes.

Verify legacy raw NNUE/final evaluation and deterministic search against v0.5.0.
Verify new raw NNUE and final evaluation against the pinned compiled Pikafish
master. Test network switching and export/reload, malformed/truncated files,
all 644 standard cases and all prefixes of the owner games. Both rule flag
variants must retain their 882-case contract. Final PGO training uses both
network formats. Do not interpret these compatibility checks as an Elo result.

Final Windows clang-cl 19.1.5 and Zen2 LLVM 22.1.8 full-LTO/PGO artifacts pass
both formats. The legacy network retains exact raw/final evaluation and
deterministic search on all 644 standard cases, with both rule flags. The new
network matches the pinned Pikafish master on 1,450 evaluable full-history
positions with zero raw/final-score differences; all 76 in-check statuses also
match. The 1,526-position corpus combines the 644 standard cases and every
prefix of both owner games, their colour reversals and rule control positions.

Both platforms pass 882 rule cases, 5 old/new switches, old/new export/reload
and 10 malformed-file rejection cases, including a missing final Zstd byte.
Zen2 checks use a separately compiled native reference: the Broadwell reference
requires a newer glibc/libstdc++ and is not reused on the older Zen2 OS.

Run loader regressions with `tests/verify_nnue_loader_compatibility.py` and
score comparisons with `tests/compare_nnue_compatibility.py`; both take explicit
engine/network/verifier/output paths and support Python 3.8+. No source weight
file is modified by the tests.
