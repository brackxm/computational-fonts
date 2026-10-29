// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
typedef unsigned long long U;
typedef struct { U a, b, c; } Triple;
__attribute__((noinline)) Triple make_triple(U x, U y) {
    Triple result = {x + y, x ^ y, x - y};
    return result;
}
__attribute__((noinline)) Triple reverse_triple(U x, U y) { return make_triple(y, x); }
__attribute__((noinline)) U use_triple(Triple value) {
    value.a += 7;
    return value.a ^ value.b ^ value.c;
}
U call_triple(U x, U y) { return use_triple(make_triple(x, y)); }
typedef Triple (*Maker)(U, U);
static Maker const makers[2] = {make_triple, reverse_triple};
Triple choose_triple(unsigned which, U x, U y) { return makers[which & 1](x, y); }
