// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Native opening extraction; all inputs originate in this original rule engine.
#define C4_NATIVE_LIBRARY
#include "native.cpp"
#include <functional>
#include <unordered_map>

Board canonical_board(Board b,bool& flip) {
    U r=reflected(b.red),y=reflected(b.yellow);
    flip=std::pair<U,U>{r,y}<std::pair<U,U>{b.red,b.yellow};
    return flip?Board{r,y,b.player}:b;
}

std::string board_name(const Board& b) {
    std::ostringstream out;out<<std::hex<<b.red<<'/'<<b.yellow<<'/'<<b.player;return out.str();
}

struct Training {U good,bad;};
bool order_model(const std::vector<Training>& constraints,std::array<int,42>& rank) {
    std::vector<Training> pending=constraints;
    U remaining=(U(1)<<42)-1;
    for(int level=0;level<42;++level) {
        U blocked=0;for(auto c:pending)blocked|=c.bad;
        U available=remaining&~blocked;
        if(!available)return false;
        int selected=-1;
        for(int col:order)for(int row=0;row<6;++row) {
            int cell=6*col+row;
            if(selected<0&&(available&(U(1)<<cell)))selected=cell;
        }
        U bit=U(1)<<selected;rank[selected]=level;remaining&=~bit;
        pending.erase(std::remove_if(pending.begin(),pending.end(),[bit](Training t){return t.good&bit;}),pending.end());
    }
    return true;
}

struct Link {int col;U child;bool flip;};
struct Vertex {
    Board board;char type='E';
    std::array<int,42> rank{};
    std::vector<Link> links;
    uint64_t verified=0;int iterations=0;
};

class Generator {
    Oracle& oracle;
    std::unordered_map<U,Vertex> graph;
    std::unordered_set<U> failed_leaves;
    std::vector<Board> active;
    std::string output;
    int max_iterations;
    std::chrono::steady_clock::time_point started,last_save;
    bool complete=false;
public:
    Generator(Oracle& oracle,std::string output,int iterations):oracle(oracle),output(output),max_iterations(iterations) {
        started=last_save=std::chrono::steady_clock::now();
    }
    void seed(const std::string& path) {
        if(path.empty())return;
        std::ifstream input(path);std::string magic;size_t count,root;
        if(!(input>>magic>>count>>root)||magic!="C4HYBRID1")throw std::runtime_error("bad seed header");
        std::vector<Vertex> nodes(count);
        struct Ref{int col;size_t child;bool flip;};
        std::vector<std::vector<Ref>> refs(count);
        for(size_t i=0;i<count;++i) {
            std::string red,yellow;int player;char type;
            input>>red>>yellow>>player>>type;
            Vertex& node=nodes[i];node.board={std::stoull(red,nullptr,16),std::stoull(yellow,nullptr,16),player};node.type=type;
            if(type=='L')for(int& r:node.rank)input>>r;
            else if(type=='E') {
                size_t degree;input>>degree;
                for(size_t j=0;j<degree;++j){int col,flip;size_t child;input>>col>>child>>flip;refs[i].push_back({col-1,child,bool(flip)});}
            } else if(type!='T')throw std::runtime_error("unsupported seed kind");
        }
        if(!input)throw std::runtime_error("truncated seed");
        for(size_t i=0;i<count;++i) {
            for(auto ref:refs[i])nodes[i].links.push_back({ref.col,nodes.at(ref.child).board.absolute_key(),ref.flip});
            graph.emplace(nodes[i].board.absolute_key(),std::move(nodes[i]));
        }
        std::cerr<<"Loaded "<<count<<" completed seed vertices\n";
    }
    bool leaf(Board b,Vertex& result) {
        U key=b.absolute_key();
        if(failed_leaves.count(key))return false;
        std::vector<Training> constraints;
        for(int iteration=0;iteration<max_iterations;++iteration) {
            std::array<int,42> rank;
            if(!order_model(constraints,rank))break;
            RankVerifier verifier(rank,20000000);std::string path;
            bool won;
            try{won=verifier.verify(b,path);}catch(Exhausted&){break;}
            if(won) {
                result.board=b;result.type='L';result.rank=rank;result.verified=verifier.nodes;result.iterations=iteration+1;
                return true;
            }
            Board state=b;bool added=false;
            for(char ch:verifier.witness) {
                int col=ch-'1';Board child=state.drop(state.piece(col));
                if(state.player==1&&!oracle.solve(child)) {
                    U good=0,bad=0;
                    for(int c:order)if(U bit=state.piece(c)) {
                        int row=__builtin_ctzll(bit)-7*c;
                        U cell=U(1)<<(6*c+row);
                        if(oracle.solve(state.drop(bit)))good|=cell;else bad|=cell;
                    }
                    if(!good)throw std::runtime_error("nonwinning leaf entry");
                    constraints.push_back({good,bad});added=true;break;
                }
                state=child;
            }
            if(!added)throw std::runtime_error("counterexample without a bad decision");
        }
        failed_leaves.insert(key);return false;
    }
    Link visit(Board original,int col=-1) {
        bool flip;Board b=canonical_board(original,flip);U key=b.absolute_key();
        if(graph.count(key))return {col,key,flip};
        active.push_back(b);save(false);
        Vertex node;node.board=b;
        if(four(b.red))node.type='T';
        else if(four(b.yellow)||b.occupied()==full)throw std::runtime_error("loss or draw in extracted graph");
        else if(b.ply()!=0&&leaf(b,node)) {}
        else if(b.player==1) {
            int chosen=-1;
            for(int c:order)if(U bit=b.piece(c)) {
                Board child=b.drop(bit);
                if(!oracle.solve(child))continue;
                if(chosen<0)chosen=c;
                // Decouple this Red move from the continuing local ordering.
                bool child_flip;Board target=canonical_board(child,child_flip);
                if(graph.count(target.absolute_key())) {chosen=c;break;}
                Vertex local;
                if(leaf(target,local)) {graph.emplace(target.absolute_key(),std::move(local));chosen=c;break;}
                if(b.ply()==0)break; // The first proven opening is sufficient.
            }
            if(chosen<0)throw std::runtime_error("no winning Red move");
            node.type='E';node.links.push_back(visit(b.drop(b.piece(chosen)),chosen));
        } else {
            node.type='E';
            for(int c:order)if(U bit=b.piece(c))node.links.push_back(visit(b.drop(bit),c));
        }
        graph.emplace(key,std::move(node));active.pop_back();save(false);return {col,key,flip};
    }
    void save(bool force) {
        auto now=std::chrono::steady_clock::now();
        if(!force&&std::chrono::duration<double>(now-last_save).count()<10)return;
        last_save=now;
        std::vector<const Vertex*> sorted;sorted.reserve(graph.size());
        for(auto& [key,node]:graph)sorted.push_back(&node);
        std::sort(sorted.begin(),sorted.end(),[](auto a,auto b){return board_name(a->board)<board_name(b->board);});
        std::ofstream out(output+".tmp");
        out<<"{\"format\":\"independent-c4-hybrid-v1\",\"root\":\"0/0/1\",\"complete\":"<<(complete?"true":"false")
           <<",\"source\":\"original rule-only native generator\",\"nodes\":{";
        size_t leaves=0,edges=0;
        bool comma=false;
        for(auto ptr:sorted) {
            const Vertex& node=*ptr;
            out<<(comma?",":"")<<'"'<<board_name(node.board)<<"\":{";comma=true;
            if(node.type=='L') {
                ++leaves;out<<"\"ranks\":[";
                for(size_t i=0;i<42;++i)out<<(i?",":"")<<node.rank[i];
                out<<"],\"verification_nodes\":"<<node.verified<<",\"iterations\":"<<node.iterations;
            } else if(node.type=='T')out<<"\"terminal\":\"red\"";
            else {
                edges+=node.links.size();out<<"\"edges\":{";
                for(size_t i=0;i<node.links.size();++i) {
                    const Link& link=node.links[i];
                    out<<(i?",":"")<<'"'<<link.col+1<<"\":{\"key\":\""<<board_name(graph.at(link.child).board)
                       <<"\",\"flip\":"<<int(link.flip)<<'}';
                }
                out<<'}';
            }
            out<<'}';
        }
        double seconds=std::chrono::duration<double>(now-started).count();
        out<<"},\"generator_stats\":{\"oracle_nodes\":"<<oracle.nodes<<",\"seconds\":"<<seconds<<"},\"frontier\":[";
        for(size_t i=0;i<active.size();++i)out<<(i?",":"")<<'"'<<board_name(active[i])<<'"';
        out<<"]}\n";out.close();
        if(!out||std::rename((output+".tmp").c_str(),output.c_str()))throw std::runtime_error("checkpoint write failed");
        std::cout<<"{\"nodes\":"<<graph.size()<<",\"leaves\":"<<leaves<<",\"edges\":"<<edges
                 <<",\"oracle_nodes\":"<<oracle.nodes<<",\"seconds\":"<<seconds<<",\"complete\":"<<(complete?"true":"false")<<"}"<<std::endl;
    }
    void run() {
        oracle.budget(UINT64_MAX/4);
        Board root;
        if(!oracle.solve(root))throw std::runtime_error("root not winning");
        Link entry=visit(root);
        std::unordered_set<U> live;
        std::function<void(U)> mark=[&](U key){if(!live.insert(key).second)return;for(auto link:graph.at(key).links)mark(link.child);};
        mark(entry.child);
        for(auto it=graph.begin();it!=graph.end();)if(!live.count(it->first))it=graph.erase(it);else++it;
        complete=true;save(true);
    }
};

int main(int argc,char**argv) {
    try {
        std::string cache,output,seed;unsigned bits=25;int iterations=64;
        for(int i=1;i<argc;++i) {
            std::string arg=argv[i];
            if(arg=="--cache"&&i+1<argc)cache=argv[++i];
            else if(arg=="--output"&&i+1<argc)output=argv[++i];
            else if(arg=="--seed"&&i+1<argc)seed=argv[++i];
            else if(arg=="--table-bits"&&i+1<argc)bits=std::stoul(argv[++i]);
            else if(arg=="--iterations"&&i+1<argc)iterations=std::stoi(argv[++i]);
            else throw std::runtime_error("invalid argument");
        }
        if(output.empty())throw std::runtime_error("provide output");
        Oracle oracle(bits);if(!cache.empty())oracle.load(cache);
        Generator generator(oracle,output,iterations);generator.seed(seed);generator.run();
        if(!cache.empty())oracle.save(cache);
    }catch(std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
