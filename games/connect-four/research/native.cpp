// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Original rule-derived exact oracle. No imported code, books or solution data.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

using U = uint64_t;
constexpr U bottom = (U(1)<<0)|(U(1)<<7)|(U(1)<<14)|(U(1)<<21)|(U(1)<<28)|(U(1)<<35)|(U(1)<<42);
constexpr U full = bottom * 63;
constexpr U keymask = (U(1)<<49)-1;
constexpr std::array<int,7> order{3,2,4,1,5,0,6};
struct Exhausted {};

bool four(U p) {
    for (int d : {1,6,7,8}) {
        U q = p & (p>>d);
        if (q & (q>>(2*d))) return true;
    }
    return false;
}

U winning(U p) {
    U result = 0;
    for (int d : {1,6,7,8}) {
        result |= (p<<d)&(p<<(2*d))&(p<<(3*d));
        result |= (p>>d)&(p>>(2*d))&(p>>(3*d));
        result |= (p>>d)&(p<<d)&(p<<(2*d));
        result |= (p>>(2*d))&(p>>d)&(p<<d);
    }
    return result & full;
}

U reflected(U key) {
    U other = 0;
    for (int c=0;c<7;++c) other |= ((key>>(7*c))&127)<<(7*(6-c));
    return other;
}

struct Board {
    U red=0, yellow=0;
    int player=1;
    U occupied() const { return red|yellow; }
    U moves() const { return (occupied()+bottom)&full; }
    U piece(int col) const { return moves() & (U(63)<<(7*col)); }
    U own() const { return player==1 ? red : yellow; }
    U enemy() const { return player==1 ? yellow : red; }
    int ply() const { return __builtin_popcountll(occupied()); }
    Board drop(U bit) const {
        if (!(bit & moves()) || (bit&(bit-1))) throw std::runtime_error("illegal drop");
        return player==1 ? Board{red|bit,yellow,2} : Board{red,yellow|bit,1};
    }
    U key() const {
        U k = red+occupied()+bottom;
        return std::min(k,reflected(k));
    }
    U absolute_key() const { return red+occupied()+bottom; }
};

Board from_history(const std::string& history) {
    Board b;
    if (history=="-") return b;
    for (char ch:history) {
        if (ch<'1'||ch>'7'||four(b.red)||four(b.yellow)) throw std::runtime_error("illegal history");
        b=b.drop(b.piece(ch-'1'));
    }
    return b;
}

class Oracle {
    std::vector<U> table;
    unsigned bits;
    uint64_t limit=0, calls=0;
public:
    uint64_t nodes=0,hits=0;
    explicit Oracle(unsigned bits):table(size_t(1)<<bits),bits(bits) {}
    void load(const std::string& path) {
        std::ifstream input(path,std::ios::binary);
        if (!input) return;
        U header=0;input.read(reinterpret_cast<char*>(&header),sizeof(header));
        if (header!=(U(0x43344f5201000000)|bits)) throw std::runtime_error("cache version mismatch");
        input.read(reinterpret_cast<char*>(table.data()),table.size()*sizeof(U));
        if (!input || input.peek()!=EOF) throw std::runtime_error("cache length mismatch");
    }
    void save(const std::string& path) {
        std::ofstream output(path+".tmp",std::ios::binary);
        U header=U(0x43344f5201000000)|bits;
        output.write(reinterpret_cast<char*>(&header),sizeof(header));
        output.write(reinterpret_cast<char*>(table.data()),table.size()*sizeof(U));
        output.close();
        if (!output || std::rename((path+".tmp").c_str(),path.c_str())) throw std::runtime_error("cache write failed");
    }
    void budget(uint64_t n) { limit=nodes+n; }
    bool solve(const Board& b) {
        if (four(b.red)) return true;
        if (four(b.yellow) || b.occupied()==full) return false;
        U own_win = winning(b.own())&b.moves();
        if (own_win) return b.player==1;
        U danger = winning(b.enemy());
        U forced = danger&b.moves();
        if (forced && (forced&(forced-1))) return b.player==2;
        U choices = (forced ? forced : b.moves()) & ~(danger>>1);
        if (!choices) return b.player==2;
        U key=b.key();
        size_t slot=((key*U(0x9e3779b97f4a7c15))>>(64-bits))&~size_t(1);
        for (size_t s: {slot,slot+1}) {
            U entry=table[s];
            if ((entry&keymask)==key) { ++hits; return (entry>>55)&1; }
        }
        if (nodes>=limit) throw Exhausted{};
        ++nodes;
        struct Move { U bit; int score; };
        std::array<Move,7> moves;
        int count=0;
        for (int c:order) {
            U bit=choices&(U(63)<<(7*c));
            if (!bit) continue;
            U prospects=winning(b.own()|bit)&~(b.occupied()|bit);
            int score=__builtin_popcountll(prospects);
            // A safe move creating two playable threats wins after any reply.
            U next_moves=((b.occupied()|bit)+bottom)&full;
            U threats=prospects&next_moves;
            if (threats && (threats&(threats-1))) {
                store(slot,key,b.ply(),b.player==1);
                return b.player==1;
            }
            moves[count++]={bit,score};
        }
        // Stable insertion sort retains center-first tie breaks.
        for (int i=1;i<count;++i) {
            Move m=moves[i];int j=i;
            while (j && moves[j-1].score<m.score) {moves[j]=moves[j-1];--j;}
            moves[j]=m;
        }
        bool result=b.player==2;
        for (int i=0;i<count;++i) {
            bool child=solve(b.drop(moves[i].bit));
            if (child==(b.player==1)) {result=child;break;}
        }
        store(slot,key,b.ply(),result);
        return result;
    }
    void store(size_t slot,U key,int ply,bool value) {
        U entry=key|(U(ply)<<49)|(U(value)<<55);
        if (!table[slot] || ply<=int((table[slot]>>49)&63)) {
            table[slot+1]=table[slot];table[slot]=entry;
        } else table[slot+1]=entry;
    }
};

int policy_column(const Board& b,const std::array<int,42>& rank,bool ties=false) {
    for (U p : {b.red,b.yellow}) {
        U immediate=winning(p)&b.moves();
        if (immediate) for (int c:order) if (b.piece(c)&immediate) return c;
    }
    if(ties) {
        std::array<int,42> counts{},columns{};
        for(int c:order)if(U bit=b.piece(c)) {
            int row=__builtin_ctzll(bit)-7*c,level=rank[6*c+row];
            ++counts[level];columns[level]=c;
        }
        for(int level=0;level<42;++level)if(counts[level]==1)return columns[level];
        return -1;
    }
    int chosen=-1,priority=43;
    for (int c:order) if (U bit=b.piece(c)) {
        int row=__builtin_ctzll(bit)-7*c;
        int r=rank[6*c+row];
        if (r<priority) {chosen=c;priority=r;}
    }
    return chosen;
}

class RankVerifier {
    std::unordered_set<U> proved;
    const std::array<int,42>& rank;
    uint64_t budget;
    bool ties;
public:
    uint64_t nodes=0;
    std::string witness;
    RankVerifier(const std::array<int,42>& rank,uint64_t budget,bool ties=false):rank(rank),budget(budget),ties(ties) {}
    bool verify(const Board& b,std::string& path) {
        if (four(b.red)) return true;
        if (four(b.yellow)||b.occupied()==full) {witness=path;return false;}
        U key=b.absolute_key();
        if (proved.count(key)) return true;
        if (nodes>=budget) throw Exhausted{};
        ++nodes;
        if (b.player==1) {
            int c=policy_column(b,rank,ties);
            if(c<0){witness=path+"0";return false;}
            path.push_back('1'+c);
            if (!verify(b.drop(b.piece(c)),path)) return false;
            path.pop_back();
        } else {
            for (int c:order) if (U bit=b.piece(c)) {
                path.push_back('1'+c);
                if (!verify(b.drop(bit),path)) return false;
                path.pop_back();
            }
        }
        proved.insert(key);
        return true;
    }
};

class ResponseVerifier {
    std::unordered_set<U> proved;
    const std::array<std::array<int,42>,8>& ranks;
    uint64_t budget;
public:
    uint64_t nodes=0;std::string witness;
    ResponseVerifier(const std::array<std::array<int,42>,8>& ranks,uint64_t budget):ranks(ranks),budget(budget){}
    bool verify(const Board& b,std::string& path,int context=7) {
        if(four(b.red))return true;
        if(four(b.yellow)||b.occupied()==full){witness=path;return false;}
        U key=b.absolute_key()|(U(b.player==1?context:7)<<49);
        if(proved.count(key))return true;
        if(nodes>=budget)throw Exhausted{};
        ++nodes;
        if(b.player==1) {
            int c=policy_column(b,ranks[context]);path.push_back('1'+c);
            if(!verify(b.drop(b.piece(c)),path,context))return false;
            path.pop_back();
        } else {
            for(int c:order)if(U bit=b.piece(c)) {
                path.push_back('1'+c);
                if(!verify(b.drop(bit),path,c))return false;
                path.pop_back();
            }
        }
        proved.insert(key);return true;
    }
};

#ifndef C4_NATIVE_LIBRARY
int main(int argc,char**argv) {
    unsigned bits=24;
    uint64_t budget=100000000;
    std::string cache;
    for (int i=1;i<argc;++i) {
        std::string arg=argv[i];
        if (arg=="--table-bits" && i+1<argc) bits=std::stoul(argv[++i]);
        else if (arg=="--budget" && i+1<argc) budget=std::stoull(argv[++i]);
        else if (arg=="--cache" && i+1<argc) cache=argv[++i];
        else throw std::runtime_error("unknown argument");
    }
    if (bits<8 || bits>28) throw std::runtime_error("table bits must be 8..28");
    Oracle oracle(bits);
    if (!cache.empty()) oracle.load(cache);
    std::string line;
    while (std::getline(std::cin,line)) {
        auto start=std::chrono::steady_clock::now();
        auto before=oracle.nodes, hits=oracle.hits;
        std::istringstream input(line);
        std::string command,history;
        input>>command>>history;
        if (command=="quit") break;
        try {
            if (command=="save") {
                if (!cache.empty()) oracle.save(cache);
                std::cout<<"{\"saved\":true}"<<std::endl;
                continue;
            }
            Board b;
            if (command=="bits" || command=="moves-bits" || command=="rank" || command=="levels" || command=="response") {
                std::string ys;input>>ys>>b.player;
                b.red=std::stoull(history,nullptr,16);b.yellow=std::stoull(ys,nullptr,16);
                if ((b.red&b.yellow) || (b.occupied()&~full) || (b.player!=1&&b.player!=2))
                    throw std::runtime_error("invalid bits");
                if (b.player!=1+b.ply()%2) throw std::runtime_error("invalid turn parity");
                for (int c=0;c<7;++c) {
                    U column=(b.occupied()>>(7*c))&63;
                    if (column&(column+1)) throw std::runtime_error("floating discs");
                }
            } else b=from_history(history);
            if(command=="response") {
                std::array<std::array<int,42>,8> ranks;
                for(auto& rank:ranks) {
                    std::array<bool,42> used{};
                    for(int& value:rank) {
                        if(!(input>>value)||value<0||value>=42||used[value])throw std::runtime_error("invalid response ranks");
                        used[value]=true;
                    }
                }
                ResponseVerifier verifier(ranks,budget);std::string path;
                bool verified=verifier.verify(b,path);
                std::cout<<"{\"verified\":"<<(verified?"true":"false")<<",\"nodes\":"<<verifier.nodes
                         <<",\"witness\":\""<<verifier.witness<<"\"}"<<std::endl;
                continue;
            }
            if (command=="rank"||command=="levels") {
                std::array<int,42> rank;
                std::array<bool,42> used{};
                for (int& value:rank) {
                    if (!(input>>value)||value<0||value>=42||(command=="rank"&&used[value])) throw std::runtime_error("invalid priorities");
                    used[value]=true;
                }
                RankVerifier verifier(rank,budget,command=="levels");std::string path;
                bool verified=verifier.verify(b,path);
                std::cout<<"{\"verified\":"<<(verified?"true":"false")
                         <<",\"nodes\":"<<verifier.nodes<<",\"witness\":\""<<verifier.witness<<"\"}"<<std::endl;
                continue;
            }
            oracle.budget(budget);
            bool result=oracle.solve(b);
            std::vector<int> moves;
            if ((command=="moves"||command=="moves-bits") && b.player==1 && !four(b.red) && !four(b.yellow)) {
                for (int c:order) if (b.piece(c) && oracle.solve(b.drop(b.piece(c)))) moves.push_back(c+1);
            }
            double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            std::cout<<"{\"strict_red_win\":"<<(result?"true":"false")
                     <<",\"nodes\":"<<(oracle.nodes-before)<<",\"hits\":"<<(oracle.hits-hits)
                     <<",\"seconds\":"<<seconds<<",\"winning_columns\":[";
            for(size_t i=0;i<moves.size();++i) std::cout<<(i?",":"")<<moves[i];
            std::cout<<"]}"<<std::endl;
        } catch (Exhausted&) {
            std::cout<<"{\"unknown_budget_exceeded\":true,\"nodes\":"<<(oracle.nodes-before)<<"}"<<std::endl;
        } catch (std::exception& e) {
            std::cout<<"{\"error\":\""<<e.what()<<"\"}"<<std::endl;
        }
    }
    if (!cache.empty()) oracle.save(cache);
}
#endif
