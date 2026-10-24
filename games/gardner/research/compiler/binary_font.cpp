// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
#include "packed_tables.hpp"
int main(int argc, char **argv) try {
  if (argc != 7 || std::string(argv[4]) != "game") {
    std::cerr << "binary_font TREE OUTPUT_STEM BASE_GLYPH_COUNT game GAMEPACK GSUB\n";
    return 2;
  }
  auto started = std::chrono::steady_clock::now();
  constexpr bool alias = true;
  std::ifstream f(argv[1], std::ios::binary | std::ios::ate);
  if (!f)
    throw std::runtime_error("missing tree");
  std::vector<uint8_t> data(f.tellg());
  f.seekg(0);
  f.read(reinterpret_cast<char *>(data.data()), data.size());
  if (!f || data.size() < 80 || le32(data.data()) != 0x47524232)
    throw std::runtime_error("bad tree");
  int rows = le32(data.data() + 4), count = le32(data.data() + 8), nlabels = le32(data.data() + 12),
      root = le32(data.data() + 16), features = le32(data.data() + 20),
      symbols = le32(data.data() + 24);
  if (symbols != 2 || features > 192)
    throw std::runtime_error("unsupported tree");
  if (count <= 0 || nlabels <= 0 || features <= 0 || root < 0 || root >= count)
    throw std::runtime_error("bad binary header");
  size_t offset = 80 + 4ull * nlabels;
  if (offset + 12ull * count != data.size())
    throw std::runtime_error("bad binary nodes");
  std::vector<uint32_t> labels(nlabels);
  std::memcpy(labels.data(), data.data() + 80, 4ull * nlabels);
  std::vector<Node> storage(count);
  std::vector<int> depths(count);
  for (int i = 0; i < count; ++i) {
    auto *n = data.data() + offset + 12ull * i;
    storage[i].feature = le32(n);
    storage[i].child[0] = int32_t(le32(n + 4));
    storage[i].child[1] = int32_t(le32(n + 8));
    if (storage[i].feature < 0 || storage[i].feature >= features)
      throw std::runtime_error("bad node feature");
    int depth = 0;
    for (int child : storage[i].child) {
      if (child == MISS)
        throw std::runtime_error("missing binary edge");
      if (child >= i)
        throw std::runtime_error("non-postorder DAG");
      if (child >= 0)
        depth = std::max(depth, depths[child]);
      else if (-1ll - child >= nlabels)
        throw std::runtime_error("bad leaf label");
    }
    depths[i] = depth + 1;
  }
  int steps = depths[root];
  if (steps > features)
    throw std::runtime_error("DAG depth exceeds feature count");
  auto *nodes = storage.data();
  std::vector<Bank> banks;
  std::vector<int> bankof(count), lowof(count);
  {
    std::vector<std::vector<int>> groups(features);
    for (int node = 0; node < count; ++node)
      groups[nodes[node].feature].push_back(node);
    for (int feature = 0; feature < features; ++feature) {
      int current = -1;
      for (int node : groups[feature]) {
        if (current < 0 || banks[current].nodes.size() == BASE) {
          current = banks.size();
          banks.emplace_back(feature);
        }
        bankof[node] = current;
        lowof[node] = banks[current].nodes.size();
        banks[current].nodes.push_back(node);
      }
    }
  }

  // Partition each feature's banks by the previous child-bank pair.
  // All node identities and binary edges remain unchanged.
  for (int pass = 0; pass < 2; ++pass) {
    auto previous = bankof;
    auto key = [&](int child) {
      return child < 0 ? child : previous[child];
    };
    for (int feature = 0; feature < features; ++feature) {
      std::vector<int> group, selected;
      for (size_t b = 0; b < banks.size(); ++b)
        if (banks[b].feature == feature) {
          selected.push_back(b);
          group.insert(group.end(), banks[b].nodes.begin(), banks[b].nodes.end());
        }
      std::sort(group.begin(), group.end(), [&](int a, int b) {
        auto ka = std::pair{key(nodes[a].child[1]), key(nodes[a].child[0])};
        auto kb = std::pair{key(nodes[b].child[1]), key(nodes[b].child[0])};
        return ka != kb ? ka < kb : a < b;
      });
      size_t at = 0;
      for (int b : selected) {
        auto &list = banks[b].nodes;
        for (size_t low = 0; low < list.size(); ++low) {
          int node = group[at++];
          list[low] = node;
          bankof[node] = b;
          lowof[node] = low;
        }
      }
    }
  }

  int nd = 0;
  uint64_t leaf_edges = 0, inner_edges = 0;
  for (auto &bank : banks)
    for (int value = 0; value < symbols; ++value) {
      bank.dispatch[value] = nd++;
      for (int node : bank.nodes)
        (nodes[node].child[value] < 0 ? leaf_edges : inner_edges)++;
    }
  constexpr bool boardmode = false, gamemode = true;
  constexpr bool compact_edges = true;
  if (compact_edges && !alias)
    throw std::runtime_error("compact edges require alias mode");
  Bytes game, oldgsub;
  int game_count = 0, game_ai = 0, game_stub = 0, unsupported = 0, game_alloc = 0, game_expand = 0,
      game_cleanup = 0, game_pipeline = 7, game_cursor = 0, game_draw_before = 0;
  constexpr bool nonloss = true;
  std::vector<U> game_counts, game_work, game_moves, game_marks;
  if (gamemode) {
    if (argc < 7)
      throw std::runtime_error("game needs .gamepack and .gsub");
    game = readfile(argv[5]);
    oldgsub = readfile(argv[6]);
    if (game.size() < 14428 || std::memcmp(game.data(), "GRGP", 4))
      throw std::runtime_error("bad gamepack");
    game_count = le32(game.data() + 4);
    game_ai = le32(game.data() + 8);
    game_stub = le32(game.data() + 12);
    if (game_count != std::stoi(argv[3]))
      throw std::runtime_error("base mismatch");
    size_t at = 20;
    for (int i = 0; i < 151; ++i, at += 4)
      game_counts.push_back(le32(game.data() + at));
    for (int i = 0; i < 325; ++i, at += 4)
      game_work.push_back(le32(game.data() + at));
    for (int i = 0; i < 3125; ++i, at += 4) {
      uint32_t value = le32(game.data() + at);
      game_moves.push_back(value == 0xffffffff ? 65535 : value);
    }
    int nm = le32(game.data() + at);
    at += 4;
    if (nm < 0 || at + 4ull * nm + 24 > game.size())
      throw std::runtime_error("truncated game markers");
    for (int i = 0; i < nm; ++i, at += 4)
      game_marks.push_back(le32(game.data() + at));
    unsupported = le32(game.data() + at);
    game_alloc = le32(game.data() + at + 4);
    game_expand = le32(game.data() + at + 8);
    game_cleanup = le32(game.data() + at + 12);
    game_pipeline = le32(game.data() + at + 16);
    game_cursor = le32(game.data() + at + 20);
    if (nonloss) {
      if (game.size() < at + 28)
        throw std::runtime_error("claim-aware gamepack required");
      game_draw_before = le32(game.data() + at + 24);
    }
  }
  constexpr bool mirror = true, mirror_low_only = true;
  std::array<int, 13> widths{};
  for (int i = 0; i < 13; ++i)
    widths[i] = le32(data.data() + 28 + 4 * i);
  int feature_slots = std::accumulate(widths.begin(), widths.end(), 0);
  if (!feature_slots || features % feature_slots)
    throw std::runtime_error("invalid bit feature layout");
  int bits_per_slot = features / feature_slots;
  if (bits_per_slot != 5 && bits_per_slot != 6)
    throw std::runtime_error("unsupported bit feature layout");
  int gid = std::stoi(argv[3]), lowbase = gid;
  gid += BASE;
  int hibase = gid;
  gid += banks.size();
  int opbase = gid;
  gid += features;
  int valbase = gid;
  gid += symbols;
  int dbase = gid;
  gid += nd;
  int featurebase = gid;
  gid += 26 * feature_slots;
  int slotbase = featurebase;
  int labelbase = alias ? lowbase : gid;
  if (!alias)
    gid += nlabels;
  else if (nlabels > BASE)
    throw std::runtime_error("too many alias labels");
  int startgid = gid++, endgid = gid++, padgid = gid++;
  int rawbase = gid, fingid = gid, kindstart = gid, kindend = gid, phbase = gid, locbase = gid,
      trashgid = gid;
  if (gamemode) {
    fingid = gid++;
    kindstart = gid;
    gid += 12;
    kindend = gid;
    gid += 12;
    phbase = gid;
    gid += 300;
    locbase = gid;
    gid += 312;
    trashgid = gid++;
  }
  int reflection_gid = mirror ? gid++ : 0;
  std::vector<U> piece_count_flags{U(fingid)};
  if (mirror_low_only)
    for (int i = 1; i <= 6; ++i)
      piece_count_flags.push_back(gid++);
  if (gid >= 65535)
    throw std::runtime_error("glyph budget " + std::to_string(gid));
  std::cerr << "BANKS " << banks.size() << " dispatch " << nd << " leaf_edges " << leaf_edges
            << " inner_edges " << inner_edges << " glyphs " << gid << std::endl;
  if (gamemode && (oldgsub.size() < 10 || size_t(be16(oldgsub.data() + 8)) + 2 > oldgsub.size()))
    throw std::runtime_error("bad base GSUB");
  int oldcount = gamemode ? be16(oldgsub.data() + be16(oldgsub.data() + 8)) : 0;
  Builder build(oldcount);
  if (gamemode) {
    build.pipeline = game_pipeline;
    build.import(oldgsub, game_count);
  }
  std::vector<std::vector<U>> game_filter_sets;
  constexpr int leaf_defaults = 32, high_defaults = 128;
  constexpr int leaf_begin = 2, high_begin = leaf_begin + leaf_defaults;
  constexpr int kinds = high_begin + high_defaults;
  static_assert(kinds <= 256, "route categories must fit in one byte");
  std::vector<std::array<std::array<int, high_defaults>, 2>> common_high(banks.size());
  std::vector<std::array<std::array<int, leaf_defaults>, 2>> common_leaf(banks.size());
  uint64_t rare_edges = 0;
  auto select_common = [](const std::map<int, int> &frequencies, auto &selected) {
    std::vector<std::pair<int, int>> ranked(frequencies.begin(), frequencies.end());
    std::sort(ranked.begin(), ranked.end(), [](auto a, auto b) {
      return a.second != b.second ? a.second > b.second : a.first < b.first;
    });
    selected.fill(MISS);
    for (size_t rank = 0; rank < std::min(selected.size(), ranked.size()); ++rank)
      if (ranked[rank].second >= 64)
        selected[rank] = ranked[rank].first;
  };
  for (size_t bank = 0; bank < banks.size(); ++bank)
    for (int v = 0; v < 2; ++v) {
      std::map<int, int> highs, leaves;
      for (int node : banks[bank].nodes) {
        int child = nodes[node].child[v];
        if (child >= 0)
          ++highs[bankof[child]];
        else if (child != MISS)
          ++leaves[child];
      }
      select_common(highs, common_high[bank][v]);
      select_common(leaves, common_leaf[bank][v]);
    }
  // Routes: mapped leaf (0), explicit high pair (1), shared leaves, shared high banks.
  // Classify once; sorting and serialization must use the same partition.
  std::vector<std::array<uint8_t, 2>> categories(count);
  for (size_t bank = 0; bank < banks.size(); ++bank)
    for (int node : banks[bank].nodes)
      for (int v = 0; v < 2; ++v) {
        int child = nodes[node].child[v];
        int kind = child < 0 ? 0 : 1;
        if (child >= 0)
          for (int rank = 0; rank < high_defaults; ++rank)
            if (bankof[child] == common_high[bank][v][rank]) {
              kind = high_begin + rank;
              break;
            }
        if (child < 0 && child != MISS)
          for (int rank = 0; rank < leaf_defaults; ++rank)
            if (child == common_leaf[bank][v][rank]) {
              kind = leaf_begin + rank;
              break;
            }
        categories[node][v] = kind;
      }
  auto category = [&](int node, int v) { return categories[node][v]; };
  for (size_t bank = 0; bank < banks.size(); ++bank) {
    auto &list = banks[bank].nodes;
    std::stable_sort(list.begin(), list.end(), [&](int a, int b) {
      return kinds * category(a, 0) + category(a, 1) <
             kinds * category(b, 0) + category(b, 1);
    });
    for (size_t low = 0; low < list.size(); ++low)
      lowof[list[low]] = low;
  }
  std::vector<std::pair<U, std::vector<U>>> copies, drop;
  for (int g = lowbase; g < lowbase + BASE; ++g) {
    copies.push_back({U(g), {U(g), U(g)}});
    drop.push_back({U(g), {}});
  }
  int duplicate = build.lookup(2, multiples(copies));
  int erase_low = build.lookup(2, multiples(drop));
  std::vector<std::pair<U, std::vector<U>>> clean;
  for (int d = 0; d < nd; ++d)
    clean.push_back({U(dbase + d), {}});
  auto cleanids = build.tables(2, multiples(clean));
  int erase_d = build.lookup(2, multiples(clean));
  std::array<int, high_defaults> set_high;
  for (int rank = 0; rank < high_defaults; ++rank) {
    std::vector<std::pair<U, U>> high_default;
    for (size_t bank = 0; bank < banks.size(); ++bank)
      for (int v = 0; v < 2; ++v)
        if (common_high[bank][v][rank] >= 0)
          high_default.push_back({U(dbase + banks[bank].dispatch[v]),
                                  U(hibase + common_high[bank][v][rank])});
    set_high[rank] = high_default.empty() ? -1 : build.lookup(1, singles(high_default));
  }
  std::array<int, leaf_defaults> set_leaf;
  for (int rank = 0; rank < leaf_defaults; ++rank) {
    std::vector<std::pair<U, U>> leaf_default;
    for (size_t bank = 0; bank < banks.size(); ++bank)
      for (int v = 0; v < 2; ++v)
        if (common_leaf[bank][v][rank] != MISS)
          leaf_default.push_back({U(dbase + banks[bank].dispatch[v]),
                                  U(labelbase - 1 - common_leaf[bank][v][rank])});
    set_leaf[rank] = leaf_default.empty() ? -1 : build.lookup(1, singles(leaf_default));
  }
  std::array<int, 2> pair_to_high{build.lookup(1, {}), build.lookup(1, {})};
  std::unordered_map<uint32_t, int> pair_ids;
  std::vector<std::array<int, 2>> pair_values;
  uint64_t paired_rows = 0;
  int actual_dispatch = -1, actual_fetch = -1;
  std::vector<std::array<int, 5>> dense_tables;
  std::vector<int> routes;
  size_t mapped = 0;
  for (size_t bank = 0; bank < banks.size(); ++bank) {
    std::array<int, 2> lows;
    for (int v = 0; v < 2; ++v) {
      std::vector<std::pair<U, U>> low;
      for (int node : banks[bank].nodes) {
        int child = nodes[node].child[v];
        if (category(node, v) >= leaf_begin && category(node, v) < high_begin)
          continue;
        low.push_back({U(lowbase + lowof[node]),
                       U(child < 0 ? labelbase - 1 - child : lowbase + lowof[child])});
        if (category(node, v) == 1)
          ++rare_edges;
        ++mapped;
      }
      lows[v] = low.empty() ? -1 : build.lookup(1, singles(low));
    }
    std::vector<std::pair<U, U>> pairs;
    for (int node : banks[bank].nodes) {
      std::array<int, 2> high{0, 0};
      for (int v = 0; v < 2; ++v)
        if (category(node, v) == 1)
          high[v] = bankof[nodes[node].child[v]] + 1;
      if (high[0] || high[1]) {
        uint32_t key = high[0] | uint32_t(high[1]) << 16;
        auto old = pair_ids.find(key);
        int id;
        if (old == pair_ids.end()) {
          id = pair_values.size();
          if (id >= 65535)
            throw std::runtime_error("high pair dictionary exceeds glyph address space");
          pair_ids[key] = id;
          pair_values.push_back(high);
        } else
          id = old->second;
        // The next nested lookup consumes this temporary ID with LookupFlag 0,
        // so it can reuse any glyph ID, including .notdef and marked glyphs.
        pairs.push_back({U(lowbase + lowof[node]), U(id)});
        ++paired_rows;
      }
    }
    int pair_lookup = pairs.empty() ? -1 : build.lookup(1, singles(pairs));
    std::array<int, 2> bank_routes;
    for (int v = 0; v < 2; ++v) {
      U dispatch = dbase + banks[bank].dispatch[v];
      std::map<U, U> cls{{dispatch, 1}};
      std::array<bool, kinds> present{};
      for (int node : banks[bank].nodes) {
        int kind = category(node, v);
        cls[lowbase + lowof[node]] = 3 + kind;
        present[kind] = true;
      }
      std::vector<std::vector<Bin>> sets(2);
      for (int kind = 0; kind < kinds; ++kind)
        if (present[kind]) {
          std::vector<std::pair<U, U>> calls;
          // Delete right-to-left, then turn the dispatch token into the leaf.
          if (kind >= leaf_begin && kind < high_begin)
            calls = {{2, U(erase_low)}, {1, U(erase_low)}, {0, U(set_leaf[kind - leaf_begin])}};
          else if (kind == 1)
            calls = {{1, U(pair_lookup)}, {1, U(pair_to_high[v])},
                     {2, U(lows[v])}, {0, U(erase_d)}};
          else if (kind >= high_begin)
            calls = {{1, U(lows[v])}, {2, U(erase_low)}, {0, U(set_high[kind - high_begin])}};
          else
            calls = {{1, U(lows[v])}, {2, U(erase_low)}, {0, U(erase_d)}};
          sets[1].push_back(classrule({U(3 + kind), U(3 + kind)}, calls));
        }
      bank_routes[v] = build.lookup(5, {context2({dispatch}, cls, sets)});
      routes.push_back(bank_routes[v]);
    }
    dense_tables.push_back({lows[0], lows[1], pair_lookup, bank_routes[0], bank_routes[1]});
  }
  for (int v = 0; v < 2; ++v) {
    std::vector<std::pair<U, U>> rows;
    for (size_t id = 0; id < pair_values.size(); ++id)
      if (pair_values[id][v])
        rows.push_back({U(id), U(hibase + pair_values[id][v] - 1)});
    build.looks[pair_to_high[v]] = {1, build.tables(1, singles(rows))};
  }
  gid = std::max<int>(gid, pair_values.size());
  std::cerr << "PAIRED HIGH rows " << paired_rows << " dictionary " << pair_values.size()
            << std::endl;
  std::map<U, U> routeclasses;
  std::vector<U> routecover;
  std::vector<std::vector<Bin>> routesets(2 * banks.size() + 1);
  for (size_t bank = 0; bank < banks.size(); ++bank)
    for (int v = 0; v < 2; ++v) {
      U d = dbase + banks[bank].dispatch[v];
      routecover.push_back(d);
      int route = 2 * bank + v;
      routeclasses[d] = route + 1;
      routesets[route + 1].push_back(classrule({}, {{0, U(routes[route])}}));
    }
  auto dispatchids = build.tables(5, {context2(routecover, routeclasses, routesets)});
  std::vector<std::pair<U, std::vector<U>>> prep;
  for (size_t b = 0; b < banks.size(); ++b)
    prep.push_back({U(hibase + b), {U(opbase + banks[b].feature), U(hibase + b)}});
  auto prepids = build.tables(2, multiples(prep));
  std::vector<int> setval;
  for (int v = 0; v < 2; ++v) {
    std::vector<std::pair<U, U>> map;
    for (int feature = 0; feature < features; ++feature)
      map.push_back({U(opbase + feature), U(valbase + v)});
    setval.push_back(build.lookup(1, singles(map)));
  }
  std::vector<Bin> fetch;
  int filter_offset = boardmode ? 25 : 0;
  for (int slot = 0; slot < feature_slots; ++slot)
    game_filter_sets.push_back(range(featurebase + 26 * slot, 26));
  for (int feature = 0; feature < features; ++feature) {
    int slot = feature / bits_per_slot, bit = feature % bits_per_slot;
    std::vector<Bin> rules;
    for (int value = 0; value < 2; ++value) {
      std::vector<U> inputs;
      for (int v = 0; v < 26; ++v) {
        int encoded = bits_per_slot == 6 ? (v == 25 ? 45 : (v % 5) | ((v / 5) << 3)) : v;
        if (((encoded >> bit) & 1) == value)
          inputs.push_back(featurebase + 26 * slot + v);
      }
      rules.push_back(context3({{U(opbase + feature)},
                                range(hibase, banks.size()),
                                range(lowbase, BASE),
                                range(lowbase, BASE),
                                inputs},
                               {{0, U(setval[value])}}));
    }
    int look = build.lookup(5, rules);
    build.looks[look].markset = filter_offset + slot;
    fetch.push_back(context3({{U(opbase + feature)}}, {{0, U(look)}}));
  }
  auto fetchids = build.tables(5, fetch);
  Bin liga;
  liga.u16(1);
  liga.u16(0);
  liga.u16(2);
  liga.u16(0);
  liga.u16(0);
  for (int v = 0; v < 2; ++v) {
    liga.patch16(6 + 2 * v, liga.size());
    size_t set = liga.size();
    liga.u16(banks.size());
    for (size_t i = 0; i < banks.size(); ++i)
      liga.u16(0);
    for (size_t b = 0; b < banks.size(); ++b) {
      liga.patch16(set + 2 + 2 * b, liga.size() - set);
      liga.u16(dbase + banks[b].dispatch[v]);
      liga.u16(2);
      liga.u16(hibase + b);
    }
  }
  liga.patch16(2, liga.size());
  liga.add(coverage(range(valbase, 2)));
  auto ligaids = build.tables(4, {liga});
  std::cerr << "BINARY DENSE rare_edges " << rare_edges << " low_mapping_rows " << mapped
            << std::endl;

  if (gamemode) {
    auto addlook = [&](int type, std::vector<Bin> tables, int filter = -1) {
      int id = build.lookup(type, std::move(tables));
      build.looks[id].markset = filter;
      return id;
    };
    auto filter = [&](std::vector<U> glyphs) {
      int id = game_filter_sets.size();
      game_filter_sets.push_back(std::move(glyphs));
      return id;
    };
    std::vector<U> slots;
    for (int kind = 0; kind < 12; ++kind) {
      slots.push_back(kindstart + kind);
      for (int s = 0; s < 25; ++s)
        slots.push_back(phbase + 25 * kind + s);
      slots.push_back(kindend + kind);
    }
    slots.push_back(fingid);
    build.looks[game_expand] = {2, build.tables(2, multiples({{U(game_alloc), slots}}))};
    build.looks[game_cursor] = {
        2, build.tables(
               2, multiples({{U(game_ai),
                              {U(game_ai), U(hibase + bankof[root]), U(lowbase + lowof[root])}}}))};
    std::vector<std::pair<U, U>> outercalls;
    if (mirror) {
      if (mirror_low_only) {
        std::vector<std::pair<U, U>> advance;
        for (int n = 0; n <= 6; ++n)
          advance.push_back({piece_count_flags[n], piece_count_flags[std::min(6, n + 1)]});
        int increment = addlook(1, singles(advance));
        for (int square = 0; square < 25; ++square) {
          std::vector<U> nonempty(game_work.begin() + 13 * square + 1,
                                  game_work.begin() + 13 * square + 13),
              selected = nonempty;
          selected.insert(selected.end(), piece_count_flags.begin(), piece_count_flags.end());
          int look = addlook(5, {context3({nonempty, piece_count_flags}, {{1, U(increment)}})},
                             filter(selected));
          outercalls.push_back({U(3 + square), U(look)});
        }
      }
      auto low_flags = piece_count_flags;
      if (mirror_low_only)
        low_flags.pop_back();
      std::vector<std::pair<U, U>> flip_flags;
      for (U g : low_flags)
        flip_flags.push_back({g, U(reflection_gid)});
      int setter = addlook(1, singles(flip_flags));
      auto selected = game_work;
      selected.push_back(game_ai);
      selected.insert(selected.end(), piece_count_flags.begin(), piece_count_flags.end());
      selected.push_back(reflection_gid);
      int filt = filter(selected);
      std::vector<Bin> rules;
      auto orientation = [&](int white, int black) {
        std::vector<std::vector<U>> input{
            {U(game_ai)}, range(hibase, banks.size()), range(lowbase, BASE)};
        for (int square = 0; square < 25; ++square) {
          if (square == white)
            input.push_back({game_work[13 * square + 6]});
          else if (square == black)
            input.push_back({game_work[13 * square + 12]});
          else
            input.push_back(
                {game_work.begin() + 13 * square, game_work.begin() + 13 * square + 13});
        }
        input.push_back(low_flags);
        rules.push_back(context3(input, {{28, U(setter)}}));
      };
      for (int white = 0; white < 25; ++white) {
        if (white % 5 > 2)
          orientation(white, -1);
        if (white % 5 == 2)
          for (int black = 0; black < 25; ++black)
            if (black % 5 > 2)
              orientation(white, black);
      }
      outercalls.push_back({0, U(addlook(5, std::move(rules), filt))});
      if (mirror_low_only) {
        std::vector<std::pair<U, U>> reset;
        for (U g : piece_count_flags)
          reset.push_back({g, U(fingid)});
        int normalize = addlook(1, singles(reset));
        std::vector<std::vector<U>> input{
            {U(game_ai)}, range(hibase, banks.size()), range(lowbase, BASE)};
        for (int square = 0; square < 25; ++square)
          input.push_back({game_work.begin() + 13 * square, game_work.begin() + 13 * square + 13});
        input.push_back(piece_count_flags);
        outercalls.push_back({0, U(addlook(5, {context3(input, {{28, U(normalize)}})}, filt))});
      }
    }
    std::vector<int> copyset;
    for (int piece = 0; piece < 13; ++piece) {
      std::vector<std::pair<U, U>> map;
      for (int kind = 0; kind < 12; ++kind)
        for (int s = 0; s < 25; ++s)
          map.push_back({U(phbase + 25 * kind + s),
                         U(piece == kind + 1 ? locbase + 26 * kind + s : trashgid)});
      copyset.push_back(addlook(1, singles(map)));
    }
    for (int s = 0; s < 25; ++s)
      for (int reflected = 0; reflected < (mirror ? 2 : 1); ++reflected) {
        int square = reflected ? s / 5 * 5 + 4 - s % 5 : s;
        std::vector<U> selected;
        for (int p = 0; p < 13; ++p)
          selected.push_back(game_work[13 * s + p]);
        for (int k = 0; k < 12; ++k)
          selected.push_back(phbase + 25 * k + square);
        if (mirror)
          selected.push_back(reflected ? reflection_gid : fingid);
        int filt = filter(selected);
        std::vector<Bin> rules;
        for (int piece = 0; piece < 13; ++piece) {
          std::vector<std::vector<U>> input{{game_work[13 * s + piece]}};
          std::vector<std::pair<U, U>> calls;
          for (int k = 0; k < 12; ++k) {
            input.push_back({U(phbase + 25 * k + square)});
            calls.push_back({U(k + 1), U(copyset[piece])});
          }
          if (mirror)
            input.push_back({U(reflected ? reflection_gid : fingid)});
          rules.push_back(context3(input, calls));
        }
        outercalls.push_back({U(3 + s), U(addlook(5, std::move(rules), filt))});
      }
    auto trashfilter = game_counts;
    trashfilter.push_back(trashgid);
    int tf = filter(trashfilter);
    int deletetrash = addlook(2, multiples({{U(trashgid), {}}}));
    int dropnext = addlook(5, {context3({game_counts, {U(trashgid)}}, {{1, U(deletetrash)}})}, tf);
    for (int n = 0; n < 300; ++n)
      outercalls.push_back({28, U(dropnext)});
    std::vector<int> kindfilters, pads, renames, dropkind;
    int feature = 0;
    for (int kind = 0; kind < 12; ++kind) {
      auto selected = game_counts;
      selected.push_back(kindstart + kind);
      selected.push_back(kindend + kind);
      for (int v = 0; v < 26; ++v)
        selected.push_back(locbase + 26 * kind + v);
      int filt = filter(selected);
      kindfilters.push_back(filt);
      std::vector<Bin> rules;
      for (int n = 0; n <= widths[kind + 1]; ++n) {
        int setter = addlook(
            2, multiples({{U(kindend + kind),
                           std::vector<U>(widths[kind + 1] - n, U(locbase + 26 * kind + 25))}}));
        std::vector<std::vector<U>> input{game_counts, {U(kindstart + kind)}};
        for (int j = 0; j < n; ++j)
          input.push_back(range(locbase + 26 * kind, 25));
        input.push_back({U(kindend + kind)});
        rules.push_back(context3(input, {{U(n + 2), U(setter)}}));
      }
      pads.push_back(addlook(5, std::move(rules), filt));
      std::vector<std::vector<U>> input{game_counts, {U(kindstart + kind)}};
      std::vector<std::pair<U, U>> calls;
      for (int slot = 0; slot < widths[kind + 1]; ++slot) {
        std::vector<std::pair<U, U>> map;
        for (int v = 0; v < 26; ++v)
          map.push_back({U(locbase + 26 * kind + v), U(slotbase + 26 * feature + v)});
        int setter = addlook(1, singles(map));
        input.push_back(range(locbase + 26 * kind, 26));
        calls.push_back({U(slot + 2), U(setter)});
        ++feature;
      }
      renames.push_back(addlook(5, {context3(input, calls)}, filt));
      int setter = addlook(2, multiples({{U(kindstart + kind), {}}}));
      dropkind.push_back(
          addlook(5, {context3({game_counts, {U(kindstart + kind)}}, {{1, U(setter)}})}, filt));
    }
    for (int look : pads)
      outercalls.push_back({28, U(look)});
    for (int look : renames)
      outercalls.push_back({28, U(look)});
    for (int look : dropkind)
      outercalls.push_back({28, U(look)});

    int fetchfilter = filter(range(featurebase, 26 * feature_slots));
    int preplook = addlook(2, {});
    build.looks[preplook] = {2, prepids};
    int fetchlook = addlook(5, {});
    build.looks[fetchlook] = {5, fetchids, fetchfilter};
    actual_fetch = fetchlook;
    int ligalook = addlook(4, {});
    build.looks[ligalook] = {4, ligaids};
    int dislook = addlook(5, {});
    build.looks[dislook] = {5, dispatchids};
    actual_dispatch = dislook;
    int cleanlook = addlook(2, {});
    build.looks[cleanlook] = {2, cleanids};
    std::vector<std::pair<U, U>> stepcalls{
        {1, U(preplook)}, {1, U(fetchlook)}, {1, U(ligalook)}, {1, U(dislook)}, {1, U(cleanlook)}};
    if (compact_edges)
      stepcalls.insert(stepcalls.begin(), {2, U(duplicate)});
    int step = addlook(
        5,
        {context3({{U(game_ai)}, range(hibase, banks.size()), range(lowbase, BASE)}, stepcalls)});
    for (int n = 0; n < steps; ++n)
      outercalls.push_back({0, U(step)});
    std::vector<std::pair<U, U>> choices;
    std::map<int, std::vector<U>> bybound;
    for (int label = 0; label < nlabels; ++label) {
      int move = labels[label] % 3125, bound = labels[label] / 3125;
      if (bound == 250) {
        bybound[bound].push_back(labelbase + label);
        continue;
      }
      if (game_moves[move] == 65535)
        throw std::runtime_error("missing game move");
      choices.push_back({U(labelbase + label), game_moves[move]});
      bybound[bound].push_back(labelbase + label);
    }
    int choose = addlook(1, singles(choices));
    if (mirror) {
      std::vector<std::pair<U, U>> mappings;
      std::vector<U> markers;
      for (int code = 0; code < 3125; ++code)
        if (game_moves[code] != 65535) {
          int from = code / 125, to = code / 5 % 25;
          int flipped =
              ((from / 5 * 5 + 4 - from % 5) * 25 + (to / 5 * 5 + 4 - to % 5)) * 5 + code % 5;
          if (game_moves[flipped] == 65535)
            throw std::runtime_error("missing reflected move template");
          mappings.push_back({game_moves[code], game_moves[flipped]});
          markers.push_back(game_moves[code]);
        }
      int flip = addlook(1, singles(mappings));
      auto selected = markers;
      selected.push_back(reflection_gid);
      int flipcontext =
          addlook(5, {context3({markers, {U(reflection_gid)}}, {{0, U(flip)}})}, filter(selected));
      choose = addlook(
          5, {context3({range(labelbase, nlabels)}, {{0, U(choose)}, {0, U(flipcontext)}})});
    }
    int hideai = addlook(2, multiples({{U(game_ai), {}}}));
    auto resultset = game_counts;
    resultset.push_back(game_ai);
    int resultfilter = filter(resultset);
    std::vector<Bin> result;
    int reject = addlook(1, singles({{U(game_ai), U(unsupported)}}));
    std::vector<std::pair<U, std::vector<U>>> droplabel;
    for (int label = 0; label < nlabels; ++label)
      droplabel.push_back({U(labelbase + label), {}});
    int removelabel = addlook(2, multiples(droplabel));
    int terminal_draw = nonloss ? addlook(1, singles({{U(game_ai), U(game_draw_before)}})) : -1;
    for (auto &entry : bybound) {
      if (entry.first == 250 && nonloss) {
        result.push_back(context3({{U(game_ai)}, entry.second, game_counts},
                                  {{1, U(removelabel)}, {0, U(terminal_draw)}}));
        continue;
      }

      if (entry.first < 0 || entry.first > 249 || (!nonloss && entry.first >= 150))
        throw std::runtime_error("draw labels require a claim-aware game wrapper");
      int first = entry.first >= 150 ? entry.first - 150 : 0,
          last = entry.first >= 150 ? 98 : (nonloss && entry.first != 149 ? 98 : entry.first);
      if (first <= last) {
        std::vector<U> allowed(game_counts.begin() + first, game_counts.begin() + last + 1);
        result.push_back(
            context3({{U(game_ai)}, entry.second, allowed}, {{1, U(choose)}, {0, U(hideai)}}));
      }
    }

    if (nonloss) {
      // A winning threshold >=99 means a reset or immediate mate. Preserve
      // that win instead of taking an optional intended-move draw claim.
      for (auto &entry : bybound)
        if (entry.first >= 99 && entry.first < 150)
          result.push_back(context3({{U(game_ai)}, entry.second, {game_counts[99]}},
                                    {{1, U(choose)}, {0, U(hideai)}}));
      outercalls.push_back({0, U(addlook(5, std::move(result), resultfilter))});
      result.clear();
      // Resolve to the original board's absolute move before testing reset
      // semantics. This keeps reflection out of the clock/claim implementation.
      outercalls.push_back(
          {0, U(addlook(5,
                        {context3({{U(game_ai)}, range(labelbase, nlabels), {game_counts[99]}},
                                  {{1, U(choose)}})},
                        resultfilter))});
      auto selected = resultset;
      selected.insert(selected.end(), game_work.begin(), game_work.end());
      std::vector<U> at99;
      std::array<std::vector<U>, 25> from, to;
      std::vector<std::pair<U, std::vector<U>>> erasechoices;
      for (int move = 0; move < 3125; ++move)
        if (game_moves[move] != 65535) {
          U g = game_moves[move];
          selected.push_back(g);
          at99.push_back(g);
          from[move / 125].push_back(g);
          to[(move / 5) % 25].push_back(g);
          erasechoices.push_back({g, {}});
        }
      int claimfilter = filter(selected);
      int erasechoice = addlook(2, multiples(erasechoices));
      auto claimpattern = [&](const std::vector<U> &labels, int square, const std::string &pieces) {
        std::vector<std::vector<U>> input{{U(game_ai)}, labels};
        for (int s = 0; s < 25; ++s) {
          std::vector<U> cells;
          if (s == square) {
            for (char piece : pieces) {
              auto at = std::strchr(".PNBRQKpnbrqk", piece) - ".PNBRQKpnbrqk";
              cells.push_back(game_work[13 * s + at]);
            }
          } else
            for (int p = 0; p < 13; ++p)
              cells.push_back(game_work[13 * s + p]);
          input.push_back(cells);
        }
        input.push_back({game_counts[99]});
        return input;
      };
      // Win labels also provide a nonloss guarantee above their winning bound.
      // A pawn move or capture resets the clock. Otherwise the certified legal
      // stored move supplies an intended-move claim at99, before making that move.
      for (int square = 0; square < 25; ++square) {
        if (!from[square].empty())
          result.push_back(context3(claimpattern(from[square], square, "P"), {{0, U(hideai)}}));
        if (!to[square].empty())
          result.push_back(context3(claimpattern(to[square], square, "pnbrq"), {{0, U(hideai)}}));
      }
      int draw = addlook(1, singles({{U(game_ai), U(game_draw_before)}}));
      result.push_back(context3(claimpattern(at99, -1, ""), {{1, U(erasechoice)}, {0, U(draw)}}));
      outercalls.push_back({0, U(addlook(5, std::move(result), claimfilter))});
      result.clear();
      std::vector<U> claimcounts(game_counts.begin() + 100, game_counts.end());
      result.push_back(context3({{U(game_ai)}, range(labelbase, nlabels), claimcounts},
                                {{1, U(removelabel)}, {0, U(draw)}}));
    }
    result.push_back(context3({{U(game_ai)}, range(labelbase, nlabels), game_counts},
                              {{1, U(removelabel)}, {0, U(reject)}}));
    outercalls.push_back({0, U(addlook(5, std::move(result), resultfilter))});
    std::vector<std::vector<U>> record{
        {U(game_ai)}, range(hibase, banks.size()), range(lowbase, BASE)};
    for (int j = 3; j < 29; ++j)
      record.push_back(range(0, game_count));
    auto wrapper = build.tables(5, {context3(record, outercalls)});
    auto wrapset = game_counts;
    wrapset.insert(wrapset.end(), game_work.begin(), game_work.end());
    wrapset.push_back(game_ai);
    build.looks[game_stub] = {5, wrapper, filter(wrapset)};
    auto aux = range(featurebase, 26 * feature_slots);
    auto storage = range(fingid, gid - fingid);
    aux.insert(aux.end(), storage.begin(), storage.end());
    auto auxset = game_counts;
    auxset.insert(auxset.end(), aux.begin(), aux.end());
    int auxfilter = filter(auxset);
    std::vector<std::pair<U, std::vector<U>>> cleanaux;
    for (U glyph : aux)
      cleanaux.push_back({glyph, {}});
    auto globalaux = build.tables(2, multiples(cleanaux));
    build.looks[8].payloads.insert(build.looks[8].payloads.end(), globalaux.begin(),
                                   globalaux.end());
    int auxdelete = addlook(2, multiples(cleanaux));
    // Stopped input tokens may still own preallocated packets. Sweep those
    // packets before FINISH, and let TRANSITION freeze any suffix they blocked.
    // Keep all three actions in one forward pass, at the original PRUNE stage.
    int original_prune = build.looks.size();
    build.looks.push_back(build.looks[6]);
    build.looks[6] = {
        5, build.tables(5, {context3({range(0, gid)},
                                     {{0, U(original_prune)}, {0, 5}, {0, U(auxdelete)}})})};
    int auxnext = addlook(5, {context3({game_counts, aux}, {{1, U(auxdelete)}})}, auxfilter);
    std::vector<std::vector<U>> anyrecord(53, range(0, game_count));
    std::vector<std::pair<U, U>> auxcalls(325, {52, U(auxnext)});
    build.looks[game_cleanup] = {5, build.tables(5, {context3(anyrecord, auxcalls)})};
  }
  auto gsub = build.compile();
  if (gsub.size() > 1024ull * 1024 * 1024)
    throw std::runtime_error("artifact cap");
  std::string stem = argv[2];
  std::ofstream out(stem + ".gsub", std::ios::binary);
  out.write(reinterpret_cast<char *>(gsub.data()), gsub.size());
  if (!out)
    throw std::runtime_error("write failed");
  if (gamemode || !boardmode) {
    Bin gdef;
    gdef.u32(0x10002);
    gdef.u16(14);
    gdef.u16(0);
    gdef.u16(0);
    gdef.u16(0);
    gdef.u16(0);
    std::map<U, U> markclasses;
    for (U g : game_marks)
      markclasses[g] = 3;
    for (int g = fingid; g < gid; ++g)
      markclasses[g] = 3;
    for (int g = featurebase; g < featurebase + 26 * feature_slots; ++g)
      markclasses[g] = 3;
    for (int g = slotbase; g < slotbase + 26 * feature_slots; ++g)
      markclasses[g] = 3;
    gdef.add(classes(markclasses));
    gdef.patch16(12, gdef.size());
    Bin sets;
    sets.u16(1);
    sets.u16(game_filter_sets.size());
    for (size_t k = 0; k < game_filter_sets.size(); ++k)
      sets.u32(0);
    for (size_t i = 0; i < game_filter_sets.size(); ++i) {
      sets.patch32(4 + 4 * i, sets.size());
      sets.add(coverage(game_filter_sets[i]));
    }
    gdef.add(sets);
    std::ofstream gf(stem + ".gdef", std::ios::binary);
    gf.write(reinterpret_cast<char *>(gdef.data()), gdef.size());
  }
  std::ofstream address(stem + ".addresses", std::ios::binary);
  for (int node = 0; node < count; ++node) {
    uint32_t a = bankof[node] * BASE + lowof[node];
    address.write(reinterpret_cast<char *>(&a), 4);
  }
  if (gamemode) {
    std::ofstream tablefile(stem + ".dispatch.bin", std::ios::binary);
    auto word = [&](uint32_t value) { tablefile.write(reinterpret_cast<char *>(&value), 4); };
    for (uint32_t v :
         {uint32_t(0x47504432), uint32_t(BASE), uint32_t(lowbase), uint32_t(hibase),
          uint32_t(dbase), uint32_t(labelbase), uint32_t(banks.size()), uint32_t(actual_dispatch),
          uint32_t(actual_fetch), uint32_t(featurebase), uint32_t(opbase), uint32_t(valbase),
          uint32_t(features), uint32_t(bits_per_slot)})
      word(v);
    for (auto &row : dense_tables)
      for (int v : row)
        word(v);
    if (!tablefile)
      throw std::runtime_error("dispatch manifest write");
  }
  rusage usage{};
  getrusage(RUSAGE_SELF, &usage);
  std::ofstream meta(stem + ".json");
  meta << "{\"runtime_contract\":" << "true"
       << ",\"binary\":true,\"bits_per_slot\":" << bits_per_slot
       << ",\"input_symbols\":26,\"input_features\":" << feature_slots
       << ",\"slot_base\":" << slotbase
       << ",\"symbols\":2,\"reflection_low_only\":" << (mirror_low_only ? "true" : "false")
       << ",\"reflection\":" << (mirror ? "true" : "false")
       << ",\"nonloss_enabled\":" << (nonloss ? "true" : "false")
       << ",\"capacity_probe\":" << "false" << ",\"low_count\":" << BASE
       << ",\"shared_high_count\":" << high_defaults
       << ",\"shared_high_edges\":" << inner_edges - rare_edges
       << ",\"shared_leaf_count\":" << leaf_defaults
       << ",\"shared_leaf_edges\":" << 2ull * count - mapped
       << ",\"split_bit_routes\":true"
       << ",\"label_alias\":" << (alias ? "true" : "false") << ",\"mode\":\""
       << (gamemode    ? "game"
           : boardmode ? "board"
                       : "features")
       << "\",\"raw_base\":" << rawbase << ",\"rows\":" << rows << ",\"nodes\":" << count
       << ",\"features\":" << features << ",\"steps\":" << steps << ",\"glyph_count\":" << gid
       << ",\"base_glyph_count\":" << argv[3] << ",\"low_base\":" << lowbase
       << ",\"high_base\":" << hibase << ",\"banks\":" << banks.size() << ",\"op_base\":" << opbase
       << ",\"value_base\":" << valbase << ",\"dispatch_base\":" << dbase
       << ",\"dispatch_count\":" << nd << ",\"feature_base\":" << featurebase
       << ",\"label_base\":" << labelbase << ",\"start_gid\":" << startgid
       << ",\"end_gid\":" << endgid << ",\"pad_gid\":" << padgid
       << ",\"gsub_bytes\":" << gsub.size() << ",\"lookups\":" << build.looks.size()
       << ",\"leaf_edges\":" << leaf_edges << ",\"inner_edges\":" << inner_edges
       << ",\"compile_seconds\":"
       << std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count()
       << ",\"peak_rss_bytes\":" << usage.ru_maxrss << ",\"widths\":[";
  for (int i = 0; i < 13; ++i) {
    if (i)
      meta << ',';
    meta << le32(data.data() + 28 + 4 * i);
  }
  meta << "],\"labels\":[";
  for (int i = 0; i < nlabels; ++i) {
    if (i)
      meta << ',';
    meta << labels[i];
  }
  meta << "]}\n";
  std::cout << "PACKED GSUB bytes " << gsub.size() << " mapped edges " << mapped
            << " verified serialized mapping rows " << verified_mapping_rows << std::endl;
} catch (const std::exception &e) {
  std::cerr << "FAILED " << e.what() << std::endl;
  return 1;
}
