/* Compile-time dual-oracle ledger for SF-3DDDD4C-XQ2-DP. */

#ifndef LEGAL_MOVEGEN_VERIFY_H_INCLUDED
#define LEGAL_MOVEGEN_VERIFY_H_INCLUDED

#include <cstdint>
#include <sstream>
#include <string>

namespace Stockfish::LegalMovegenVerify {

struct Counters {
    bool          enabled     = false;
    std::uint64_t decisions   = 0;
    std::uint64_t fastProofs  = 0;
    std::uint64_t fallbacks   = 0;
    std::uint64_t mismatches  = 0;
};

inline thread_local Counters counters;

inline void begin_search() {
    counters         = {};
    counters.enabled = true;
}

inline void record(bool fastProof, bool legacy) {
    auto& c = counters;
    if (!c.enabled)
        return;

    ++c.decisions;
    c.fastProofs += fastProof;
    c.fallbacks += !fastProof;
    c.mismatches += fastProof && !legacy;
}

inline std::string finish_search_json() {
    auto& c = counters;
    std::ostringstream out;
    out << "{\"schema\":1"
        << ",\"decisions\":" << c.decisions
        << ",\"fast_proofs\":" << c.fastProofs
        << ",\"fallbacks\":" << c.fallbacks
        << ",\"mismatches\":" << c.mismatches << '}';
    c.enabled = false;
    return out.str();
}

}  // namespace Stockfish::LegalMovegenVerify

#endif  // LEGAL_MOVEGEN_VERIFY_H_INCLUDED
