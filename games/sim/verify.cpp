// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Test oracle: enumerate ternary boards backwards, independently of solver.cpp.
#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    constexpr int size = 14348907;
    std::vector<int8_t> actual(size), expected(size);
    std::ifstream input(argv[1], std::ios::binary);
    input.read(reinterpret_cast<char*>(actual.data()), size);
    if (!input || input.peek() != EOF) return 3;
    std::array<int, 15> power;
    int total = 0;
    for (int code = size-1; code >= 0; --code) {
        int digits = code, index = 0, factor = 1, counts[3]{};
        int colour[6][6]{};
        for (int a = 0; a < 6; ++a) for (int b = a+1; b < 6; ++b) {
            colour[a][b] = colour[b][a] = digits % 3;
            ++counts[digits % 3]; digits /= 3;
            power[index++] = factor; factor *= 3;
        }
        if (!(counts[1] == counts[2] || counts[1] == counts[2]+1)) {
            if (actual[code]) throw std::runtime_error("Unreachable turn counts");
            continue;
        }
        int side = counts[1] == counts[2] ? 1 : 2; // colour to play
        auto triangle = [&](int player) {
            for (int a = 0; a < 6; ++a) for (int b = 0; b < a; ++b)
                for (int c = 0; c < b; ++c)
                    if (colour[a][b] == player && colour[b][c] == player && colour[a][c] == player)
                        return true;
            return false;
        };
        if (triangle(side)) {
            if (actual[code]) throw std::runtime_error("Continued past a losing triangle");
            continue;
        }
        if (triangle(3-side)) {
            bool reachable = false;
            for (int a = 0; a < 6; ++a) for (int b = 0; b < a; ++b)
                if (colour[a][b] == 3-side) {
                    colour[a][b] = colour[b][a] = 0;
                    reachable |= !triangle(3-side);
                    colour[a][b] = colour[b][a] = 3-side;
                }
            if (reachable) expected[code] = 1;
        } else {
            int shortest_win = 100, longest_loss = 0;
            index = 0;
            for (int a = 0; a < 6; ++a) for (int b = a+1; b < 6; ++b) {
                if (!colour[a][b]) {
                    int child = expected[code+side*power[index]];
                    if (!child) throw std::runtime_error("Missing independent child");
                    if (child < 0) shortest_win = std::min(shortest_win, -child);
                    else longest_loss = std::max(longest_loss, child);
                }
                ++index;
            }
            if (shortest_win < 100) expected[code] = shortest_win+1;
            else if (longest_loss) expected[code] = -longest_loss-1;
            else throw std::runtime_error("Unexpected draw");
        }
        if (actual[code] != expected[code]) {
            std::cerr << "Mismatch at " << code << '\n'; return 1;
        }
        total += expected[code] != 0;
    }
    if (total != 2230702 || expected[0] != -16) return 1;
    std::cout << "Independent enumeration verified all " << total << " reachable states and all 3^15 table slots.\n";
}
