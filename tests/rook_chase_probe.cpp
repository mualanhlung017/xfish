// Rule regression probe. Production engine sources are linked unchanged.
#include <algorithm>
#include <deque>
#include <iostream>
#include <sstream>
#include <string>

#include "attacks.h"
#include "movegen.h"
#include "position.h"
#include "uci.h"

using namespace Stockfish;

int main() {
    Attacks::init();
    Position::init();
    std::string fen, line;
    while (std::getline(std::cin, fen) && std::getline(std::cin, line))
    {
        Position pos;
        std::deque<StateInfo> states(1);
        if (auto error = pos.set(fen, &states.back()))
        {
            std::cout << "ERROR " << error->what() << std::endl;
            continue;
        }
        const Key initialKey = pos.key();
        std::istringstream moves(line);
        std::string token;
        std::deque<Move> played;
        bool invalid = false;
        while (moves >> token)
        {
            const Move m = UCIEngine::to_move(pos, token);
            if (m == Move::none())
            {
                std::cout << "ERROR illegal " << token << std::endl;
                invalid = true;
                break;
            }
            played.push_back(m);
            states.emplace_back();
            pos.do_move(m, states.back());
        }
        if (invalid)
            continue;
        const std::string finalFen = pos.fen();
        const Key finalKey = pos.key();
        Value result = VALUE_NONE, repeatedResult = VALUE_NONE;
        bool judged = pos.rule_judge(result);
        bool judgedAgain = pos.rule_judge(repeatedResult);
        Value searchResult = VALUE_NONE, searchRepeated = VALUE_NONE;
        const int searchPly = std::min(32, int(played.size()));
        bool searchJudged = pos.rule_judge(searchResult, searchPly);
        bool searchJudgedAgain = pos.rule_judge(searchRepeated, searchPly);
        bool restored = finalKey == pos.key() && finalFen == pos.fen()
                     && judged == judgedAgain && result == repeatedResult
                     && searchJudged == searchJudgedAgain && searchResult == searchRepeated;
        std::string legal;
        for (const auto& m : MoveList<LEGAL>(pos))
            legal += UCIEngine::move(m) + " ";
        while (!played.empty())
        {
            pos.undo_move(played.back());
            played.pop_back();
            states.pop_back();
        }
        restored &= pos.key() == initialKey;
        std::cout << "RESULT " << judged << " " << int(result) << " " << restored
                  << "|" << finalFen << "|" << legal << "|" << searchJudged << " "
                  << int(searchResult) << std::endl;
    }
}
