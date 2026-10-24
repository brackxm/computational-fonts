// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Compile an existing decision DAG to indexed GSUB. No chess/proof search.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <numeric>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <unordered_map>
#include <vector>
using U = uint16_t;
using Bytes = std::vector<uint8_t>;
constexpr int MISS = INT32_MIN;
constexpr int BASE = 48000;
struct Bin : Bytes {
  void u16(uint32_t v) {
    if (v > 65535)
      throw std::runtime_error("uint16 overflow " + std::to_string(v));
    push_back(v >> 8);
    push_back(v);
  }
  void u32(uint32_t v) {
    push_back(v >> 24);
    push_back(v >> 16);
    push_back(v >> 8);
    push_back(v);
  }
  void patch16(size_t at, uint32_t v) {
    if (v > 65535)
      throw std::runtime_error("offset16 overflow " + std::to_string(v));
    at0(at, v >> 8);
    at0(at + 1, v);
  }
  void patch32(size_t at, uint32_t v) {
    at0(at, v >> 24);
    at0(at + 1, v >> 16);
    at0(at + 2, v >> 8);
    at0(at + 3, v);
  }
  void at0(size_t at, uint32_t v) {
    if (at >= size())
      throw std::runtime_error("bad patch");
    (*this)[at] = v;
  }
  void add(const Bytes &b) { insert(end(), b.begin(), b.end()); }
};
uint32_t le32(const uint8_t *p) {
  uint32_t n;
  std::memcpy(&n, p, 4);
  return n;
}
uint32_t be16(const uint8_t *p) { return (uint32_t(p[0]) << 8) | p[1]; }
uint32_t be32(const uint8_t *p) { return (be16(p) << 16) | be16(p + 2); }
uint64_t verified_mapping_rows = 0;
std::vector<U> decode_coverage(const Bin &b, size_t at) {
  std::vector<U> ids;
  int format = be16(b.data() + at), count = be16(b.data() + at + 2);
  if (format == 1) {
    for (int i = 0; i < count; ++i)
      ids.push_back(be16(b.data() + at + 4 + 2 * i));
  } else if (format == 2) {
    for (int i = 0; i < count; ++i) {
      size_t r = at + 4 + 6 * i;
      int first = be16(b.data() + r), last = be16(b.data() + r + 2);
      if (be16(b.data() + r + 4) != ids.size())
        throw std::runtime_error("coverage index mismatch");
      for (int g = first; g <= last; ++g)
        ids.push_back(g);
    }
  } else
    throw std::runtime_error("bad coverage format");
  return ids;
}
Bytes readfile(const std::string &path) {
  std::ifstream f(path, std::ios::binary | std::ios::ate);
  if (!f)
    throw std::runtime_error("missing " + path);
  Bytes b(f.tellg());
  f.seekg(0);
  f.read(reinterpret_cast<char *>(b.data()), b.size());
  if (!f)
    throw std::runtime_error("truncated " + path);
  return b;
}
struct Node {
  int32_t feature;
  std::array<int32_t, 2> child;
};
static_assert(sizeof(Node) == 12);
Bin coverage(std::vector<U> ids) {
  std::sort(ids.begin(), ids.end());
  ids.erase(std::unique(ids.begin(), ids.end()), ids.end());
  std::vector<std::array<U, 3>> ranges;
  for (size_t i = 0; i < ids.size();) {
    size_t j = i;
    while (j + 1 < ids.size() && ids[j + 1] == ids[j] + 1)
      ++j;
    ranges.push_back({ids[i], ids[j], U(i)});
    i = j + 1;
  }
  Bin b;
  if (4 + 6 * ranges.size() < 4 + 2 * ids.size()) {
    b.u16(2);
    b.u16(ranges.size());
    for (auto r : ranges)
      for (U n : r)
        b.u16(n);
  } else {
    b.u16(1);
    b.u16(ids.size());
    for (U n : ids)
      b.u16(n);
  }
  return b;
}
Bin classes(const std::map<U, U> &values) {
  Bin b;
  b.u16(2);
  std::vector<std::array<U, 3>> ranges;
  for (auto [glyph, cl] : values) {
    if (!ranges.empty() && ranges.back()[1] + 1 == glyph && ranges.back()[2] == cl)
      ranges.back()[1] = glyph;
    else
      ranges.push_back({glyph, glyph, cl});
  }
  b.u16(ranges.size());
  for (auto r : ranges)
    for (auto n : r)
      b.u16(n);
  return b;
}
std::vector<Bin> singles(std::vector<std::pair<U, U>> rows) {
  std::sort(rows.begin(), rows.end());
  std::vector<Bin> result;
  for (size_t begin = 0; begin < rows.size(); begin += 30000) {
    size_t end = std::min(begin + 30000, rows.size());
    Bin b;
    b.u16(2);
    b.u16(6 + 2 * (end - begin));
    b.u16(end - begin);
    std::vector<U> ids;
    for (size_t j = begin; j < end; ++j) {
      ids.push_back(rows[j].first);
      b.u16(rows[j].second);
    }
    b.add(coverage(ids));
    auto decoded = decode_coverage(b, be16(b.data() + 2));
    if (decoded.size() != end - begin)
      throw std::runtime_error("single coverage size");
    for (size_t j = begin; j < end; ++j) {
      if (decoded[j - begin] != rows[j].first ||
          be16(b.data() + 6 + 2 * (j - begin)) != rows[j].second)
        throw std::runtime_error("single decode mismatch");
      ++verified_mapping_rows;
    }
    result.push_back(std::move(b));
  }
  return result;
}
std::vector<Bin> multiples(std::vector<std::pair<U, std::vector<U>>> rows) {
  std::sort(rows.begin(), rows.end());
  std::vector<Bin> result;
  for (size_t begin = 0; begin < rows.size();) {
    size_t end = begin, estimate = 6;
    while (end < rows.size() && end - begin < 4000) {
      size_t cost = 6 + 2 * rows[end].second.size();
      if (end > begin && estimate + cost > 54000)
        break;
      estimate += cost;
      ++end;
    }
    Bin b;
    b.u16(1);
    b.u16(0);
    b.u16(end - begin);
    for (size_t j = begin; j < end; ++j)
      b.u16(0);
    std::vector<U> ids;
    std::map<std::vector<U>, size_t> emitted;
    for (size_t j = begin; j < end; ++j) {
      ids.push_back(rows[j].first);
      auto &seq = rows[j].second;
      auto it = emitted.find(seq);
      size_t offset;
      if (it != emitted.end())
        offset = it->second;
      else {
        offset = b.size();
        emitted.emplace(seq, offset);
        b.u16(seq.size());
        for (U glyph : seq)
          b.u16(glyph);
      }
      b.patch16(6 + 2 * (j - begin), offset);
    }
    b.patch16(2, b.size());
    b.add(coverage(ids));
    auto decoded = decode_coverage(b, be16(b.data() + 2));
    if (decoded.size() != end - begin)
      throw std::runtime_error("multiple coverage size");
    for (size_t j = begin; j < end; ++j) {
      size_t pos = be16(b.data() + 6 + 2 * (j - begin));
      auto &seq = rows[j].second;
      if (decoded[j - begin] != rows[j].first || be16(b.data() + pos) != seq.size())
        throw std::runtime_error("multiple header mismatch");
      for (size_t k = 0; k < seq.size(); ++k)
        if (be16(b.data() + pos + 2 + 2 * k) != seq[k])
          throw std::runtime_error("multiple decode mismatch");
      ++verified_mapping_rows;
    }
    result.push_back(std::move(b));
    begin = end;
  }
  return result;
}
struct Look {
  int type = 0;
  std::vector<int> payloads;
  int markset = -1;
};
struct Payload {
  int type;
  Bin bytes;
  int foreign = -1;
};
// Convert only disjoint coverage families: every class expands to exactly its
// original glyph set, including explicit wildcard sets. Class zero is unused.
Bin chain_classes(const Bin &source, const std::vector<Payload> &payloads, const Look &look) {
  struct Rule {
    std::array<std::vector<std::vector<U>>, 3> sides;
    std::vector<std::pair<U, U>> calls;
  };
  std::vector<Rule> rules;
  std::array<std::map<std::vector<U>, U>, 3> ids;
  std::array<std::map<U, U>, 3> maps;
  for (int id : look.payloads) {
    auto &p = payloads[id];
    if (p.foreign < 0 || be16(source.data() + p.foreign) != 3)
      return {};
    size_t at = p.foreign + 2;
    Rule r;
    for (int side = 0; side < 3; ++side) {
      int count = be16(source.data() + at);
      at += 2;
      for (int i = 0; i < count; ++i) {
        auto set = decode_coverage(source, p.foreign + be16(source.data() + at));
        at += 2;
        if (set.empty())
          return {};
        r.sides[side].push_back(set);
        if (!ids[side].count(set)) {
          U cl = ids[side].size() + 1;
          for (U g : set)
            if (maps[side].count(g))
              return {};
          ids[side][set] = cl;
          for (U g : set)
            maps[side][g] = cl;
        }
      }
    }
    if (r.sides[1].empty())
      return {};
    int count = be16(source.data() + at);
    at += 2;
    for (int i = 0; i < count; ++i) {
      r.calls.push_back({U(be16(source.data() + at)), U(be16(source.data() + at + 2))});
      at += 4;
    }
    rules.push_back(std::move(r));
  }
  std::vector<std::vector<Bin>> sets(ids[1].size() + 1);
  std::vector<U> cover;
  for (auto &r : rules) {
    U first = ids[1].at(r.sides[1][0]);
    cover.insert(cover.end(), r.sides[1][0].begin(), r.sides[1][0].end());
    Bin rule;
    for (int side = 0; side < 3; ++side) {
      rule.u16(r.sides[side].size());
      for (size_t i = side == 1 ? 1 : 0; i < r.sides[side].size(); ++i)
        rule.u16(ids[side].at(r.sides[side][i]));
    }
    rule.u16(r.calls.size());
    for (auto [pos, lookup] : r.calls) {
      rule.u16(pos);
      rule.u16(lookup);
    }
    sets[first].push_back(std::move(rule));
  }
  Bin out;
  out.u16(2);
  for (int i = 0; i < 4; ++i)
    out.u16(0);
  out.u16(sets.size());
  for (size_t k = 0; k < sets.size(); ++k)
    out.u16(0);
  for (size_t i = 0; i < sets.size(); ++i)
    if (!sets[i].empty()) {
      out.patch16(12 + 2 * i, out.size());
      size_t base = out.size();
      out.u16(sets[i].size());
      for (size_t k = 0; k < sets[i].size(); ++k)
        out.u16(0);
      for (size_t j = 0; j < sets[i].size(); ++j) {
        out.patch16(base + 2 + 2 * j, out.size() - base);
        out.add(sets[i][j]);
      }
    }
  out.patch16(2, out.size());
  out.add(coverage(cover));
  for (int side = 0; side < 3; ++side) {
    out.patch16(4 + 2 * side, out.size());
    out.add(classes(maps[side]));
  }
  // Decode the serialized class definitions and rules back to coverage sets.
  std::array<std::map<U, std::vector<U>>, 3> inverse;
  for (int side = 0; side < 3; ++side) {
    size_t at = be16(out.data() + 4 + 2 * side);
    if (be16(out.data() + at) != 2)
      throw std::runtime_error("chain class format");
    int n = be16(out.data() + at + 2);
    for (int i = 0; i < n; ++i) {
      size_t r = at + 4 + 6 * i;
      int lo = be16(out.data() + r), hi = be16(out.data() + r + 2), cl = be16(out.data() + r + 4);
      for (int g = lo; g <= hi; ++g)
        inverse[side][cl].push_back(g);
    }
  }
  std::vector<size_t> next(sets.size(), 0);
  for (auto &r : rules) {
    U first = ids[1].at(r.sides[1][0]);
    size_t set = be16(out.data() + 12 + 2 * first);
    size_t at = set + be16(out.data() + set + 2 + 2 * next[first]++);
    for (int side = 0; side < 3; ++side) {
      int n = be16(out.data() + at);
      at += 2;
      if (size_t(n) != r.sides[side].size())
        throw std::runtime_error("chain length mismatch");
      for (int i = 0; i < n; ++i) {
        int cl = side == 1 && i == 0 ? first : be16(out.data() + at);
        if (!(side == 1 && i == 0))
          at += 2;
        if (inverse[side][cl] != r.sides[side][i])
          throw std::runtime_error("chain class coverage mismatch");
      }
    }
    int n = be16(out.data() + at);
    at += 2;
    if (size_t(n) != r.calls.size())
      throw std::runtime_error("chain call count");
    for (auto [pos, lookup] : r.calls) {
      if (be16(out.data() + at) != pos || be16(out.data() + at + 2) != lookup)
        throw std::runtime_error("chain call mismatch");
      at += 4;
    }
  }
  return out;
}
struct Builder {
  std::vector<Look> looks;
  std::vector<Payload> payloads;
  int pipeline;
  Bytes foreign;
  Builder(int count) : looks(count), pipeline(count) {}
  int payload(int type, Bin b) {
    int id = payloads.size();
    payloads.push_back({type, std::move(b)});
    return id;
  }
  std::vector<int> tables(int type, std::vector<Bin> bs) {
    std::vector<int> ids;
    for (auto &b : bs)
      ids.push_back(payload(type, std::move(b)));
    return ids;
  }
  int lookup(int type, std::vector<Bin> bs) {
    int id = looks.size();
    looks.push_back({type, tables(type, std::move(bs))});
    return id;
  }
  void import(const Bytes &blob, int glyph_count) {
    foreign = blob;
    size_t list = be16(blob.data() + 8);
    int count = be16(blob.data() + list);
    if (size_t(count) != looks.size())
      throw std::runtime_error("import count");
    for (int i = 0; i < count; ++i) {
      size_t at = list + be16(blob.data() + list + 2 + 2 * i);
      int type = be16(blob.data() + at), flags = be16(blob.data() + at + 2),
          n = be16(blob.data() + at + 4);
      if (flags)
        throw std::runtime_error("unexpected imported flags");
      Look look;
      for (int j = 0; j < n; ++j) {
        size_t sub = at + be16(blob.data() + at + 6 + 2 * j);
        int inner = type;
        if (type == 7) {
          inner = be16(blob.data() + sub + 2);
          sub += be32(blob.data() + sub + 4);
        }
        if (look.type && look.type != inner)
          throw std::runtime_error("mixed extension types");
        look.type = inner;
        look.payloads.push_back(payloads.size());
        payloads.push_back({inner, {}, int(sub)});
      }
      constexpr int chain_max = 16;
      if (look.type == 6 && look.payloads.size() > 1 && look.payloads.size() <= chain_max) {
        Bin src;
        src.add(blob);
        auto converted = chain_classes(src, payloads, look);
        if (!converted.empty()) {
          std::cerr << "CHAIN_CLASSES lookup " << i << " subtables " << look.payloads.size()
                    << " bytes " << converted.size() << std::endl;
          look.payloads = {payload(6, std::move(converted))};
        }
      }
      if (look.payloads.size() > 500) {
        std::vector<int> children;
        for (size_t begin = 0; begin < look.payloads.size(); begin += 400) {
          int id = looks.size();
          children.push_back(id);
          looks.push_back({look.type,
                           {look.payloads.begin() + begin,
                            look.payloads.begin() + std::min(begin + 400, look.payloads.size())}});
        }
        Bin wrapper;
        wrapper.u16(3);
        wrapper.u16(1);
        wrapper.u16(children.size());
        wrapper.u16(8 + 4 * children.size());
        for (int id : children) {
          wrapper.u16(0);
          wrapper.u16(id);
        }
        std::vector<U> all(glyph_count);
        std::iota(all.begin(), all.end(), 0);
        wrapper.add(coverage(all));
        looks[i] = {5, {payload(5, std::move(wrapper))}};
      } else
        looks[i] = look;
    }
  }
  Bin compile() {
    Bin script;
    script.u16(1);
    script.insert(script.end(), {'D', 'F', 'L', 'T'});
    script.u16(8);
    script.u16(4);
    script.u16(0);
    script.u16(0);
    script.u16(65535);
    script.u16(1);
    script.u16(0);
    Bin feature;
    feature.u16(1);
    feature.insert(feature.end(), {'l', 'i', 'g', 'a'});
    feature.u16(8);
    feature.u16(0);
    feature.u16(pipeline);
    for (int i = 0; i < pipeline; ++i)
      feature.u16(i);
    {
      uint64_t header_bytes = 2 + 2 * looks.size(), subtables = 0, body_bytes = foreign.size();
      for (auto &l : looks) {
        header_bytes += 6 + 2 * l.payloads.size() + (l.markset >= 0 ? 2 : 0);
        subtables += l.payloads.size();
      }
      for (auto &p : payloads)
        if (p.foreign < 0)
          body_bytes += p.bytes.size() + (p.bytes.size() % 2);
      std::cerr << "ESTIMATE header_bytes " << header_bytes << " subtables " << subtables
                << " body_bytes " << body_bytes << std::endl;
      Bin list;
      list.u16(looks.size());
      for (size_t i = 0; i < looks.size(); ++i)
        list.u16(0);
      std::vector<size_t> headers(looks.size());
      std::vector<int> order(looks.size());
      std::iota(order.begin(), order.end(), 0);
      std::stable_sort(order.begin(), order.end(), [&](int a, int b) {
        return looks[a].payloads.size() < looks[b].payloads.size();
      });
      size_t remaining = 0;
      for (auto &l : looks)
        remaining += 6 + 2 * l.payloads.size() + (l.markset >= 0 ? 2 : 0);
      constexpr size_t header_limit = 65534;
      struct Ext {
        size_t pos;
        int payload;
      };
      std::vector<Ext> exts;
      std::vector<std::pair<int, int>> deferred;
      auto extension = [&](int i, int j) {
        auto &l = looks[i];
        int p = l.payloads[j];
        size_t at = list.size();
        if (at - headers[i] > 65535)
          std::cerr << "EXT overflow lookup " << i << " sub " << j << " header " << headers[i]
                    << " extension " << at << " lookups " << looks.size() << std::endl;
        list.patch16(headers[i] + 6 + 2 * j, at - headers[i]);
        list.u16(1);
        list.u16(payloads[p].type);
        list.u32(0);
        exts.push_back({at, p});
      };
      for (int i : order) {
        auto &l = looks[i];
        if (!l.type || l.payloads.empty())
          throw std::runtime_error("unfilled lookup");
        headers[i] = list.size();
        list.patch16(2 + 2 * i, list.size());
        list.u16(7);
        list.u16(l.markset >= 0 ? 16 : 0);
        list.u16(l.payloads.size());
        for (size_t k = 0; k < l.payloads.size(); ++k)
          list.u16(0);
        if (l.markset >= 0)
          list.u16(l.markset);
        remaining -= 6 + 2 * l.payloads.size() + (l.markset >= 0 ? 2 : 0);
        for (size_t j = 0; j < l.payloads.size(); ++j) {
          if (list.size() + 8 + remaining <= header_limit)
            extension(i, j);
          else
            deferred.push_back({i, j});
        }
      }
      for (auto [i, j] : deferred)
        extension(i, j);
      size_t wrapper_end = list.size();
      std::vector<size_t> positions(payloads.size(), 0);
      for (auto ext : exts)
        if (payloads[ext.payload].foreign < 0 && !positions[ext.payload]) {
          positions[ext.payload] = list.size();
          list.add(payloads[ext.payload].bytes);
          if (list.size() % 2)
            list.push_back(0);
        }
      // Imported GSUB headers have already been rebuilt above. Every offset
      // inside an imported subtable is unsigned and relative to that subtable
      // or a later child, so bytes before the first referenced subtable are dead.
      size_t first_foreign = foreign.size();
      for (auto ext : exts)
        if (payloads[ext.payload].foreign >= 0)
          first_foreign = std::min(first_foreign, size_t(payloads[ext.payload].foreign));
      size_t foreign_start = list.size();
      list.insert(list.end(), foreign.begin() + first_foreign, foreign.end());
      for (auto ext : exts) {
        auto &p = payloads[ext.payload];
        size_t target = p.foreign >= 0 ? foreign_start + p.foreign - first_foreign
                                       : positions[ext.payload];
        list.patch32(ext.pos + 4, target - ext.pos);
      }
      std::cerr << "INTERLEAVED lookups " << looks.size() << " header_and_wrapper_bytes "
                << wrapper_end << " foreign_bytes " << foreign.size() - first_foreign << std::endl;
      Bin gsub;
      gsub.u32(0x10000);
      gsub.u16(10);
      gsub.u16(10 + script.size());
      gsub.u16(10 + script.size() + feature.size());
      gsub.add(script);
      gsub.add(feature);
      gsub.add(list);
      return gsub;
    }
  }
};
Bin context2(const std::vector<U> &cover, const std::map<U, U> &classmap,
             const std::vector<std::vector<Bin>> &sets) {
  Bin b;
  b.u16(2);
  b.u16(0);
  b.u16(0);
  b.u16(sets.size());
  for (size_t k = 0; k < sets.size(); ++k)
    b.u16(0);
  for (size_t i = 0; i < sets.size(); ++i)
    if (!sets[i].empty()) {
      b.patch16(8 + 2 * i, b.size());
      size_t set = b.size();
      b.u16(sets[i].size());
      for (size_t k = 0; k < sets[i].size(); ++k)
        b.u16(0);
      for (size_t j = 0; j < sets[i].size(); ++j) {
        b.patch16(set + 2 + 2 * j, b.size() - set);
        b.add(sets[i][j]);
      }
    }
  b.patch16(2, b.size());
  b.add(coverage(cover));
  b.patch16(4, b.size());
  b.add(classes(classmap));
  return b;
}
Bin classrule(const std::vector<U> &input, const std::vector<std::pair<U, U>> &calls) {
  Bin b;
  b.u16(input.size() + 1);
  b.u16(calls.size());
  for (U cl : input)
    b.u16(cl);
  for (auto [pos, look] : calls) {
    b.u16(pos);
    b.u16(look);
  }
  return b;
}
Bin context3(const std::vector<std::vector<U>> &input, const std::vector<std::pair<U, U>> &calls) {
  Bin b;
  b.u16(3);
  b.u16(input.size());
  b.u16(calls.size());
  for (size_t k = 0; k < input.size(); ++k)
    b.u16(0);
  for (auto [pos, look] : calls) {
    b.u16(pos);
    b.u16(look);
  }
  std::map<std::vector<U>, size_t> emitted;
  for (size_t i = 0; i < input.size(); ++i) {
    auto key = input[i];
    std::sort(key.begin(), key.end());
    auto it = emitted.find(key);
    size_t offset;
    if (it != emitted.end())
      offset = it->second;
    else {
      offset = b.size();
      emitted.emplace(key, offset);
      b.add(coverage(key));
    }
    b.patch16(6 + 2 * i, offset);
  }
  return b;
}
std::vector<U> range(int begin, int count) {
  std::vector<U> v;
  for (int i = 0; i < count; ++i)
    v.push_back(begin + i);
  return v;
}
struct Bank {
  int feature;
  std::vector<int> nodes;
  std::array<int, 2> dispatch;
  Bank(int f) : feature(f) { dispatch.fill(-1); }
};
