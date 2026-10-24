// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Try shared rule-generated orders at internal vertices. Keep the original
// proved subtree whenever a candidate fails or exhausts its checking budget.
#define C4_NATIVE_LIBRARY
#include "native.cpp"
#include <functional>
#include <map>
#include <unordered_map>
struct Edge {int col;size_t child;bool flip;};
struct Node {Board b;char type;std::array<int,42> rank{};std::vector<Edge> edges;};
std::string name(const Board& b){std::ostringstream o;o<<std::hex<<b.red<<'/'<<b.yellow<<'/'<<b.player;return o.str();}
int main(int argc,char** argv){try{
    if(argc<3||argc>4)throw std::runtime_error("provide original certificate tape, output JSON, and optional candidate count");
    size_t candidate_count=argc==4?std::stoull(argv[3]):256;
    if(!candidate_count)throw std::runtime_error("candidate count must be positive");
    std::ifstream in(argv[1]);std::string magic;size_t count,root;in>>magic>>count>>root;
    if(magic!="C4HYBRID1"||root>=count)throw std::runtime_error("bad certificate");
    std::vector<Node> nodes(count);std::map<std::array<int,42>,size_t> frequency;
    for(auto& n:nodes){std::string r,y;in>>r>>y>>n.b.player>>n.type;n.b.red=std::stoull(r,nullptr,16);n.b.yellow=std::stoull(y,nullptr,16);
        if(n.type=='L'){for(auto& x:n.rank)in>>x;++frequency[n.rank];std::array<int,42> flip{};for(int c=0;c<7;++c)for(int r=0;r<6;++r)flip[6*c+r]=n.rank[6*(6-c)+r];++frequency[flip];}
        else if(n.type=='E'){size_t d;in>>d;while(d--){Edge e;int flip;in>>e.col>>e.child>>flip;e.flip=flip;n.edges.push_back(e);}}
        else if(n.type!='T')throw std::runtime_error("unsupported node");}
    if(!in)throw std::runtime_error("truncated certificate");
    std::vector<std::pair<size_t,std::array<int,42>>> sorted;
    for(auto& [rank,n]:frequency)sorted.push_back({n,rank});std::sort(sorted.rbegin(),sorted.rend());
    std::vector<std::array<int,42>> popular;for(size_t i=0;i<std::min(candidate_count,sorted.size());++i)popular.push_back(sorted[i].second);
    auto start=std::chrono::steady_clock::now();size_t visited=0,replaced=0;uint64_t work=0;
    std::vector<bool> live(count,false);
    std::function<void(size_t)> visit=[&](size_t id){if(live[id])return;live[id]=true;auto& n=nodes[id];++visited;
        double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        if(n.type=='E'&&n.b.ply()>=6){
            std::vector<std::array<int,42>> candidates=popular;
            for(auto e:n.edges)if(nodes[e.child].type=='L'){
                auto rank=nodes[e.child].rank;if(e.flip){auto old=rank;for(int c=0;c<7;++c)for(int r=0;r<6;++r)rank[6*c+r]=old[6*(6-c)+r];}
                if(std::find(candidates.begin(),candidates.end(),rank)==candidates.end())candidates.push_back(rank);
            }
            for(auto& rank:candidates){RankVerifier verify(rank,10000);std::string path;bool won=false;try{won=verify.verify(n.b,path);}catch(Exhausted&){}work+=verify.nodes;
                if(won){n.type='L';n.rank=rank;n.edges.clear();++replaced;break;}}
        }
        if(visited%10000==0)std::cout<<"{\"visited\":"<<visited<<",\"replaced\":"<<replaced<<",\"checked_states\":"<<work<<",\"seconds\":"<<seconds<<"}"<<std::endl;
        for(auto e:n.edges)visit(e.child);
    };visit(root);
    // A shared node can be replaced after it was visited through another path;
    // recompute reachability to omit every now-unreachable descendant.
    std::fill(live.begin(),live.end(),false);std::function<void(size_t)> mark=[&](size_t id){if(live[id])return;live[id]=true;for(auto e:nodes[id].edges)mark(e.child);};mark(root);
    std::ofstream out(argv[2]);out<<"{\"format\":\"independent-c4-hybrid-v1\",\"root\":\""<<name(nodes[root].b)<<"\",\"complete\":true,\"source\":\"original rule-generated graph with exhaustively checked shared internal policies\",\"nodes\":{";
    bool comma=false;size_t kept=0;for(size_t i=0;i<count;++i)if(live[i]){++kept;auto& n=nodes[i];out<<(comma?",":"")<<'"'<<name(n.b)<<"\":{";comma=true;
        if(n.type=='L'){out<<"\"ranks\":[";for(int j=0;j<42;++j)out<<(j?",":"")<<n.rank[j];out<<']';}
        else if(n.type=='T')out<<"\"terminal\":\"red\"";
        else{out<<"\"edges\":{";for(size_t j=0;j<n.edges.size();++j){auto e=n.edges[j];out<<(j?",":"")<<'"'<<e.col<<"\":{\"key\":\""<<name(nodes[e.child].b)<<"\",\"flip\":"<<int(e.flip)<<'}';}out<<'}';}out<<'}';}
    out<<"},\"frontier\":[],\"compaction\":{\"replaced_internal_vertices\":"<<replaced<<",\"checked_states\":"<<work<<",\"candidates\":"<<candidate_count<<"}}\n";out.close();if(!out)throw std::runtime_error("output failed");
    std::cout<<"{\"complete\":true,\"vertices\":"<<kept<<",\"replaced\":"<<replaced<<",\"checked_states\":"<<work<<"}"<<std::endl;
}catch(std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
