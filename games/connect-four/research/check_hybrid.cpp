// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Independent certificate checker: row-major cells and geometric line tests.
// Does not include or link native.cpp, an exact oracle, or a strategy dataset.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using U=uint64_t;
constexpr std::array<int,7> order{3,2,4,1,5,0,6};
struct Board {
    std::array<uint8_t,42> cells{};
    std::array<uint8_t,7> height{};
    int player=1,ply=0;
    U red=0,yellow=0; // Row-major cache identity, never used to detect wins.
    bool operator==(const Board& b) const { return cells==b.cells && player==b.player; }
    void drop(int col) {
        if(col<0||col>=7||height[col]>=6) throw std::runtime_error("illegal drop");
        int row=height[col]++,i=7*row+col;
        cells[i]=player;
        (player==1?red:yellow)|=U(1)<<i;
        ++ply;player=3-player;
    }
    bool at(int row,int col,int who) const {
        return row>=0&&row<6&&col>=0&&col<7&&cells[7*row+col]==who;
    }
    bool line(int row,int col,int who) const {
        for(auto direction: {std::pair<int,int>{1,0},{0,1},{1,1},{1,-1}}) {
            auto [dr,dc]=direction;int count=1;
            for(int sign:{-1,1}) {
                int r=row+sign*dr,c=col+sign*dc;
                while(at(r,c,who)) {++count;r+=sign*dr;c+=sign*dc;}
            }
            if(count>=4) return true;
        }
        return false;
    }
    bool won(int who) const {
        for(int r=0;r<6;++r) for(int c=0;c<7;++c)
            if(at(r,c,who)&&line(r,c,who)) return true;
        return false;
    }
    bool wins_at(int col,int who) const {
        return height[col]<6&&line(height[col],col,who);
    }
    Board mirror() const {
        Board b;b.player=player;
        for(int c=0;c<7;++c) for(int r=0;r<height[c];++r) {
            int i=7*r+6-c,who=cells[7*r+c];
            b.cells[i]=who;b.height[6-c]++;
            (who==1?b.red:b.yellow)|=U(1)<<i;
            ++b.ply;
        }
        return b;
    }
};

Board decode(U r,U y,int player) {
    if((r&y)||player<1||player>2) throw std::runtime_error("invalid entry board");
    Board b;b.player=player;
    for(int col=0;col<7;++col) {
        bool gap=false;
        for(int row=0;row<6;++row) {
            U mask=U(1)<<(7*col+row);
            int who=(r&mask)?1:(y&mask)?2:0;
            if(!who) gap=true;
            else {
                if(gap) throw std::runtime_error("floating piece");
                int i=7*row+col;b.cells[i]=who;b.height[col]++;b.ply++;
                (who==1?b.red:b.yellow)|=U(1)<<i;
            }
            r&=~mask;y&=~mask;
        }
    }
    if(r||y||player!=1+b.ply%2 || __builtin_popcountll(b.red)!=(b.ply+1)/2)
        throw std::runtime_error("invalid board bits or parity");
    return b;
}

struct Edge {int column;size_t child;bool flip;};
struct Node {Board board;char type;std::array<int,42> ranks{};std::vector<Edge> edges;};
struct Key {U r,y;bool operator==(const Key& k) const{return r==k.r&&y==k.y;}};
struct Hash {size_t operator()(const Key& k)const {
    U x=k.r*U(0x9e3779b97f4a7c15)^(k.y+U(0x517cc1b727220a95));
    x^=x>>30;x*=U(0xbf58476d1ce4e5b9);return x^(x>>27);
}};

class Leaf {
    const std::array<int,42>& rank;
    bool ties;
    std::unordered_map<Key,int,Hash> memo;
public:
    uint64_t calls=0;
    Leaf(const std::array<int,42>& rank,bool ties=false):rank(rank),ties(ties){}
    int select(const Board& b) const {
        for(int who:{1,2})for(int col:order)if(b.wins_at(col,who))return col;
        if(ties){for(int level=0;level<42;++level){int count=0,selected=-1;for(int col=0;col<7;++col)if(b.height[col]<6&&rank[6*col+b.height[col]]==level){++count;selected=col;}if(count==1)return selected;}}
        else{int best=43,selected=-1;for(int col:order)if(b.height[col]<6&&rank[6*col+b.height[col]]<best){best=rank[6*col+b.height[col]];selected=col;}return selected;}
        return -1;
    }
    std::string path(Board b){
        std::string result;
        for(;;){
            int col=-1;
            if(b.player==1)col=select(b);
            else{int maximum=-1;for(int c:order)if(b.height[c]<6){Board child=b;child.drop(c);int score=verify(child);if(score>maximum){maximum=score;col=c;}}}
            int who=b.player,row=b.height[col];b.drop(col);result.push_back('1'+col);
            if(b.line(row,col,who))return result;
        }
    }
    int verify(const Board& b) {
        // Recursive callers test the just-played move before entering here.
        if(b.ply==42) throw std::runtime_error("leaf permits a draw");
        Key key{b.red,b.yellow};
        auto found=memo.find(key);
        if(found!=memo.end())return found->second;
        ++calls;int longest=0;
        if(b.player==1) {
            int selected=-1;
            for(int who:{1,2}) {
                for(int col:order) if(b.wins_at(col,who)){selected=col;break;}
                if(selected>=0)break;
            }
            if(selected<0) {
                if(ties) {
                    for(int level=0;level<42;++level) {
                        int count=0,column=-1;
                        for(int col=0;col<7;++col)if(b.height[col]<6&&rank[6*col+b.height[col]]==level){++count;column=col;}
                        if(count==1){selected=column;break;}
                    }
                } else {
                    int best=43;
                    for(int col:order) if(b.height[col]<6) {
                        int value=rank[6*col+b.height[col]];
                        if(value<best){best=value;selected=col;}
                    }
                }
            }
            if(selected<0)throw std::runtime_error("leaf has no instruction");
            Board child=b;int row=b.height[selected];child.drop(selected);
            if(child.line(row,selected,1))longest=1;
            else longest=1+verify(child);
        } else {
            for(int col:order) if(b.height[col]<6) {
                Board child=b;int row=b.height[col];child.drop(col);
                if(child.line(row,col,2))throw std::runtime_error("leaf permits a Yellow win");
                longest=std::max(longest,1+verify(child));
            }
        }
        memo.emplace(key,longest);return longest;
    }
};

class Checker {
    std::vector<Node> nodes;
    std::vector<int> longest;
    std::vector<bool> visited;
    std::vector<std::string> paths;
    uint64_t leaf_states=0;
    size_t leaves=0,edges=0;
public:
    void run(bool allow_subgame) {
        auto start=std::chrono::steady_clock::now();
        std::string magic;size_t count,root;
        if(!(std::cin>>magic>>count>>root)||magic!="C4HYBRID1"||root>=count)
            throw std::runtime_error("bad certificate header");
        nodes.resize(count);longest.assign(count,-1);visited.assign(count,false);paths.resize(count);
        for(size_t id=0;id<count;++id) {
            std::string red,yellow;int player;char type;
            if(!(std::cin>>red>>yellow>>player>>type))throw std::runtime_error("truncated node");
            Node& node=nodes[id];node.board=decode(std::stoull(red,nullptr,16),std::stoull(yellow,nullptr,16),player);node.type=type;
            if(type=='L'||type=='P') {
                std::array<bool,42> seen{};
                for(int& value:node.ranks) {
                    if(!(std::cin>>value)||value<0||value>=42||(type=='L'&&seen[value]))throw std::runtime_error("bad priorities");
                    seen[value]=true;
                }
            } else if(type=='E') {
                size_t degree;if(!(std::cin>>degree)||degree>7)throw std::runtime_error("bad degree");
                for(size_t i=0;i<degree;++i) {
                    int col,flip;size_t child;
                    if(!(std::cin>>col>>child>>flip)||col<1||col>7||child>=count||(flip!=0&&flip!=1))
                        throw std::runtime_error("bad edge");
                    node.edges.push_back({col-1,child,bool(flip)});
                }
            } else if(type!='T')throw std::runtime_error("unknown node kind");
        }
        std::string extra;if(std::cin>>extra)throw std::runtime_error("trailing data");
        Board empty;
        bool empty_board=nodes[root].board==empty;
        if(!empty_board&&!allow_subgame)throw std::runtime_error("certificate must start at empty board");
        int maximum=visit(root);
        for(bool v:visited)if(!v)throw std::runtime_error("unreachable nodes");
        double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        std::string human="b";for(size_t i=empty_board?1:0;i<paths[root].size();i+=2)human+=paths[root][i];
        std::cout<<"{\"verified\":true,\"empty_board\":"<<(empty_board?"true":"false")
                 <<",\"nodes\":"<<count<<",\"edges\":"<<edges
                 <<",\"rank_leaves\":"<<leaves<<",\"leaf_states_checked\":"<<leaf_states
                 <<",\"maximum_plies\":"<<maximum<<",\"longest_full_history\":\""<<paths[root]
                 <<"\",\"longest_human_history\":\""<<human<<"\",\"seconds\":"<<seconds<<"}"<<std::endl;
    }
    int visit(size_t id) {
        if(visited[id])return longest[id];
        Node& node=nodes[id];const Board& b=node.board;
        if(b.won(2))throw std::runtime_error("Yellow-win node");
        bool red=b.won(1);int result=0;
        if(node.type=='T') {
            if(!red)throw std::runtime_error("false Red-win terminal");
        } else {
            if(red||b.ply==42)throw std::runtime_error("nonterminal node has finished board");
            if(node.type=='L'||node.type=='P') {
                Leaf leaf(node.ranks,node.type=='P');result=leaf.verify(b);leaf_states+=leaf.calls;++leaves;
                paths[id]=leaf.path(b);
                if(leaves%10000==0)std::cerr<<"checked "<<leaves<<" leaves, "<<leaf_states<<" states\n";
            } else {
                std::array<bool,7> seen{};
                if(b.player==1&&node.edges.size()!=1)throw std::runtime_error("Red needs one move");
                for(const Edge& edge:node.edges) {
                    if(seen[edge.column])throw std::runtime_error("duplicate move");
                    seen[edge.column]=true;Board after=b;after.drop(edge.column);
                    if(edge.flip)after=after.mirror();
                    if(!(nodes[edge.child].board==after))throw std::runtime_error("child board mismatch");
                    if(after.ply!=b.ply+1)throw std::runtime_error("nonmonotone edge");
                    ++edges;int candidate=1+visit(edge.child);
                    if(candidate>result){result=candidate;std::string suffix=paths[edge.child];if(edge.flip)for(char& ch:suffix)ch='8'-ch+'0';paths[id]=std::string(1,'1'+edge.column)+suffix;}
                }
                if(b.player==2)for(int col=0;col<7;++col)
                    if(seen[col]!=(b.height[col]<6))throw std::runtime_error("missing or illegal Yellow reply");
            }
        }
        visited[id]=true;longest[id]=result;return result;
    }
};

int main(int argc,char**argv) {
    try {
        bool subgame=argc==2&&std::string(argv[1])=="--allow-subgame";
        if(argc!=1&&!subgame)throw std::runtime_error("invalid arguments");
        Checker{}.run(subgame);return 0;
    }
    catch(std::exception& e){std::cerr<<"Certificate rejected: "<<e.what()<<"\n";return 1;}
}
