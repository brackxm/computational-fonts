// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Independent execution of the serialized OpenType dispatch tables for every
// binary-node/value pair. Reads the actual TTF, not compiler-side maps.
#include "packed_tables.hpp"
#include <optional>
struct Reader {
  Bytes data;
  size_t list;
  Reader(const std::string &path) {
    auto font = readfile(path);
    size_t base = 0;
    for (uint32_t i = 0; i < be16(font.data() + 4); ++i) {
      size_t at = 12 + 16 * i;
      if (!memcmp(font.data() + at, "GSUB", 4)) {
        base = be32(font.data() + at + 8);
        size_t n = be32(font.data() + at + 12);
        data.assign(font.begin() + base, font.begin() + base + n);
      }
    }
    if (data.empty())
      throw std::runtime_error("missing GSUB");
    list = u16(8);
  }
  int u16(size_t at) const {
    if (at + 2 > data.size())
      throw std::runtime_error("read past GSUB");
    return be16(data.data() + at);
  }
  uint32_t u32(size_t at) const {
    if (at + 4 > data.size())
      throw std::runtime_error("read past GSUB");
    return be32(data.data() + at);
  }
  int coverage_index(size_t at, int glyph) const {
    int fmt = u16(at), n = u16(at + 2), lo = 0, hi = n;
    if (fmt == 1) {
      while (lo < hi) {
        int mid = (lo + hi) / 2;
        if (u16(at + 4 + 2 * mid) < glyph)
          lo = mid + 1;
        else
          hi = mid;
      }
      return lo < n && u16(at + 4 + 2 * lo) == glyph ? lo : -1;
    }
    if (fmt != 2)
      throw std::runtime_error("coverage format");
    while (lo < hi) {
      int mid = (lo + hi) / 2;
      if (u16(at + 4 + 6 * mid) > glyph)
        hi = mid;
      else
        lo = mid + 1;
    }
    if (!lo)
      return -1;
    size_t r = at + 4 + 6 * (lo - 1);
    return glyph <= u16(r + 2) ? u16(r + 4) + glyph - u16(r) : -1;
  }
  int glyph_class(size_t at, int glyph) const {
    if (u16(at) != 2)
      throw std::runtime_error("class format");
    int n = u16(at + 2), lo = 0, hi = n;
    while (lo < hi) {
      int mid = (lo + hi) / 2;
      if (u16(at + 4 + 6 * mid) > glyph)
        hi = mid;
      else
        lo = mid + 1;
    }
    if (!lo)
      return 0;
    size_t r = at + 4 + 6 * (lo - 1);
    return glyph <= u16(r + 2) ? u16(r + 4) : 0;
  }
  bool apply(int index, std::array<std::optional<int>, 3> &slots, int position = 0,
             int depth = 0) const {
    if (depth > 5 || !slots[position])
      throw std::runtime_error("invalid dispatch recursion");
    size_t lookup = list + u16(list + 2 + 2 * index);
    if (u16(lookup + 2))
      throw std::runtime_error("unexpected dispatch lookup flags");
    int outer = u16(lookup), count = u16(lookup + 4);
    for (int i = 0; i < count; ++i) {
      size_t sub = lookup + u16(lookup + 6 + 2 * i);
      int type = outer;
      if (type == 7) {
        type = u16(sub + 2);
        sub += u32(sub + 4);
      }
      int glyph = *slots[position];
      if (type == 1 || type == 2) {
        int at = coverage_index(sub + u16(sub + 2), glyph);
        if (at < 0)
          continue;
        if (type == 1) {
          if (u16(sub) != 2)
            throw std::runtime_error("single format");
          slots[position] = u16(sub + 6 + 2 * at);
        } else {
          size_t seq = sub + u16(sub + 6 + 2 * at);
          if (u16(seq))
            throw std::runtime_error("non-deletion in dispatch");
          slots[position].reset();
        }
        return true;
      }
      if (type != 5 || u16(sub) != 2)
        throw std::runtime_error("context format");
      if (coverage_index(sub + u16(sub + 2), glyph) < 0)
        continue;
      size_t classes = sub + u16(sub + 4);
      int first = glyph_class(classes, glyph), sets = u16(sub + 6);
      if (first >= sets || !u16(sub + 8 + 2 * first))
        continue;
      size_t set = sub + u16(sub + 8 + 2 * first);
      for (int rule = 0; rule < u16(set); ++rule) {
        size_t at = set + u16(set + 2 + 2 * rule);
        int length = u16(at), calls = u16(at + 2);
        bool match = position + length <= 3;
        for (int j = 1; match && j < length; ++j)
          match = slots[position + j] &&
                  glyph_class(classes, *slots[position + j]) == u16(at + 4 + 2 * (j - 1));
        if (!match)
          continue;
        size_t actions = at + 4 + 2 * (length - 1);
        for (int j = 0; j < calls; ++j) {
          int target = position + u16(actions + 4 * j), child = u16(actions + 4 * j + 2);
          if (target > 2 || !apply(child, slots, target, depth + 1))
            throw std::runtime_error("dispatch action did not apply");
        }
        return true;
      }
    }
    return false;
  }
};
int main(int argc, char **argv) try {
  if (argc != 5)
    return 2;
  Reader r(argv[1]);
  auto tree = readfile(argv[2]), addresses = readfile(argv[3]), manifest = readfile(argv[4]);
  auto word = [](const Bytes &b, size_t at) {
    uint32_t v;
    memcpy(&v, b.data() + at, 4);
    return v;
  };
  if (tree.size() < 80 || manifest.size() < 56)
    return 3;
  if (word(tree, 0) != 0x47524232 || word(manifest, 0) != 0x47504432)
    return 3;
  if (manifest.size() != 56 + 20ull * word(manifest, 24))
    return 4;
  int n = word(tree, 8), labels = word(tree, 12);
  if (addresses.size() != 4ull * n)
    return 4;
  int width = word(manifest, 4), low = word(manifest, 8), high = word(manifest, 12),
      dispatch = word(manifest, 16), leaf = word(manifest, 20), lookup = word(manifest, 28);
  size_t start = 80 + 4 * labels;
  uint64_t checks = 0;
  for (int node = 0; node < n; ++node) {
    int address = word(addresses, 4ull * node), bank = address / width, slot = address % width;
    for (int v = 0; v < 2; ++v) {
      std::array<std::optional<int>, 3> fields{dispatch + 2 * bank + v, low + slot, low + slot};
      if (!r.apply(lookup, fields))
        throw std::runtime_error("dispatch failed");
      std::vector<int> actual;
      for (auto x : fields)
        if (x)
          actual.push_back(*x);
      int child = int32_t(word(tree, start + 12ull * node + 4 + 4 * v));
      std::vector<int> expected;
      if (child < 0)
        expected = {leaf - 1 - child};
      else {
        int a = word(addresses, 4ull * child);
        expected = {high + a / width, low + a % width};
      }
      if (actual != expected)
        throw std::runtime_error("serialized dispatch mismatch at " + std::to_string(node) + "/" +
                                 std::to_string(v));
      ++checks;
    }
  }
  std::cout << "{\"status\":\"pass\",\"node_value_pairs\":" << checks
            << ",\"scope\":\"Every binary node and input bit independently executed through the "
               "actual TTF Context2, SingleSubst and deletion tables; exact state/leaf match\"}\n";
} catch (const std::exception &e) {
  std::cerr << e.what() << std::endl;
  return 1;
}
