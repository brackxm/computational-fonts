// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Independent exhaustive negamax. No symmetry, external policy, or pruning.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

constexpr int SIZE = 14348907; // 3^15
std::vector<int8_t> values(SIZE);
std::array<int, 15> powers;
std::array<bool, 32768> triangle{};

int solve(int code, int first, int second, int side) {
    if (values[code]) return values[code];
    if (triangle[first] || triangle[second]) return values[code] = 1;
    int fastest = 100, slowest = 0;
    for (int edge = 0; edge < 15; ++edge) {
        int bit = 1 << edge;
        if ((first | second) & bit) continue;
        int child = solve(code + (side + 1) * powers[edge],
                          first | (side == 0 ? bit : 0),
                          second | (side == 1 ? bit : 0), 1-side);
        int distance = std::abs(child); // child's remoteness + one ply
        if (child < 0) fastest = std::min(fastest, distance);
        else slowest = std::max(slowest, distance);
    }
    if (fastest < 100) return values[code] = fastest + 1;
    if (!slowest) throw std::runtime_error("Unexpected draw/full triangle-free board");
    return values[code] = -(slowest + 1);
}

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    int edge[6][6]{}, n = 0, power = 1;
    for (int a = 0; a < 6; ++a) for (int b = a+1; b < 6; ++b) {
        edge[a][b] = n; powers[n++] = power; power *= 3;
    }
    for (int mask = 0; mask < 32768; ++mask)
        for (int a = 0; a < 6; ++a) for (int b = a+1; b < 6; ++b)
            for (int c = b+1; c < 6; ++c) {
                int t = (1 << edge[a][b]) | (1 << edge[a][c]) | (1 << edge[b][c]);
                if ((mask & t) == t) triangle[mask] = true;
            }
    int result = solve(0, 0, 0, 0), count = 0;
    for (int value : values) count += value != 0;
    std::ofstream out(argv[1], std::ios::binary);
    out.write(reinterpret_cast<const char*>(values.data()), values.size());
    if (!out) return 3;
    std::cout << "Solved " << count << " reachable positions; root " << result << '\n';
}
