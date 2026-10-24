// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Replace independent leaves by shared orders only after exhaustive checking.
#define C4_NATIVE_LIBRARY
#include "native.cpp"
#include <numeric>
#include <unordered_map>
struct E{int col;size_t child;bool flip;};
struct V{Board b;char type;std::array<int,42> rank{};std::vector<E> edges;};
std::string name(const Board& b){std::ostringstream out;out<<std::hex<<b.red<<'/'<<b.yellow<<'/'<<b.player;return out.str();}
std::string rank_key(const std::array<int,42>& r){std::string s;for(int x:r)s.push_back(char(x));return s;}
int main(int argc,char**argv){try{
    if(argc!=3)throw std::runtime_error("provide seed and output");
    std::ifstream input(argv[1]);std::string magic;size_t count,root;
    input>>magic>>count>>root;if(magic!="C4HYBRID1"||root>=count)throw std::runtime_error("bad seed");
    std::vector<V> nodes(count);
    for(auto& n:nodes){
        std::string r,y;input>>r>>y>>n.b.player>>n.type;n.b.red=std::stoull(r,nullptr,16);n.b.yellow=std::stoull(y,nullptr,16);
        if(n.type=='L')for(int& v:n.rank)input>>v;
        else if(n.type=='E'){size_t degree;input>>degree;while(degree--){int col,flip;size_t child;input>>col>>child>>flip;n.edges.push_back({col,child,bool(flip)});}}
        else if(n.type!='T')throw std::runtime_error("bad kind");
    }
    if(!input)throw std::runtime_error("truncated seed");
    std::vector<size_t> leaves;
    for(size_t i=0;i<count;++i)if(nodes[i].type=='L')leaves.push_back(i);
    std::stable_sort(leaves.begin(),leaves.end(),[&](size_t a,size_t b){return nodes[a].b.ply()<nodes[b].b.ply();});
    std::vector<std::array<int,42>> pool;
    std::vector<size_t> use;
    std::unordered_map<std::string,size_t> ids;
    auto add=[&](const std::array<int,42>& r){std::string k=rank_key(r);auto f=ids.find(k);if(f!=ids.end())return f->second;size_t id=pool.size();pool.push_back(r);use.push_back(0);ids[k]=id;return id;};
    std::array<int,42> center{};int priority=0;for(int col:order)for(int row=0;row<6;++row)center[6*col+row]=priority++;
    add(center);std::array<int,42> reflected{};for(int col=0;col<7;++col)for(int row=0;row<6;++row)reflected[6*col+row]=center[6*(6-col)+row];add(reflected);
    std::vector<size_t> popular{0,1};size_t done=0,replaced=0;uint64_t work=0;
    for(size_t id:leaves){
        if(done%1000==0){popular.resize(pool.size());std::iota(popular.begin(),popular.end(),0);std::stable_sort(popular.begin(),popular.end(),[&](size_t a,size_t b){return use[a]>use[b];});if(popular.size()>64)popular.resize(64);}
        std::vector<size_t> candidates=popular;
        for(size_t i=pool.size()>8?pool.size()-8:0;i<pool.size();++i)if(std::find(candidates.begin(),candidates.end(),i)==candidates.end())candidates.push_back(i);
        size_t selected=SIZE_MAX;
        for(size_t p:candidates){
            RankVerifier verifier(pool[p],10000);std::string path;bool verified=false;
            try{verified=verifier.verify(nodes[id].b,path);}catch(Exhausted&){}
            work+=verifier.nodes;
            if(verified){selected=p;break;}
        }
        if(selected==SIZE_MAX)selected=add(nodes[id].rank);
        if(nodes[id].rank!=pool[selected])++replaced;
        nodes[id].rank=pool[selected];++use[selected];++done;
        if(done%10000==0)std::cout<<"{\"pooled_leaves\":"<<done<<",\"library\":"<<pool.size()<<",\"replaced\":"<<replaced<<",\"checked_states\":"<<work<<"}"<<std::endl;
    }
    std::ofstream out(argv[2]);out<<"{\"format\":\"independent-c4-hybrid-v1\",\"root\":\""<<name(nodes[root].b)<<"\",\"complete\":true,\"source\":\"rule-only graph with exhaustively checked shared leaf policies\",\"nodes\":{";
    for(size_t i=0;i<count;++i){auto& n=nodes[i];out<<(i?",":"")<<'"'<<name(n.b)<<"\":{";
        if(n.type=='T')out<<"\"terminal\":\"red\"";
        else if(n.type=='L'){out<<"\"ranks\":[";for(int j=0;j<42;++j)out<<(j?",":"")<<n.rank[j];out<<']';}
        else{out<<"\"edges\":{";for(size_t j=0;j<n.edges.size();++j){auto e=n.edges[j];out<<(j?",":"")<<'"'<<e.col<<"\":{\"key\":\""<<name(nodes[e.child].b)<<"\",\"flip\":"<<int(e.flip)<<'}';}out<<'}';}
        out<<'}';
    }
    out<<"},\"pooling\":{\"library\":"<<pool.size()<<",\"replaced\":"<<replaced<<",\"checked_states\":"<<work<<"},\"frontier\":[]}\n";
    out.close();if(!out)throw std::runtime_error("output failed");
    std::cout<<"{\"complete\":true,\"library\":"<<pool.size()<<",\"replaced\":"<<replaced<<"}"<<std::endl;
}catch(std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
