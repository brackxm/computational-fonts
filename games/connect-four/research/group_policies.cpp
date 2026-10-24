// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Merge compatible cross-column cell orders without changing a legal choice.
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>
using U=uint64_t;
struct Group{std::array<U,42> reach{};};
bool extend(Group& group,const std::vector<int>& chain){
    for(size_t i=0;i<chain.size();++i)for(size_t j=i+1;j<chain.size();++j){
        int a=chain[i],b=chain[j];if(a/6==b/6)continue;
        auto& reach=group.reach;
        if(reach[b]&(U(1)<<a))return false;
        if(reach[a]&(U(1)<<b))continue;
        U descendants=reach[b]|(U(1)<<b);
        for(int p=0;p<42;++p)if(p==a||(reach[p]&(U(1)<<a)))reach[p]|=descendants;
    }
    return true;
}
int main(){try{
    size_t count;if(!(std::cin>>count))throw std::runtime_error("missing count");
    std::vector<Group> groups;
    std::vector<size_t> assignment;assignment.reserve(count);
    for(size_t entry=0;entry<count;++entry){
        size_t n;std::cin>>n;if(n>42)throw std::runtime_error("bad chain");
        std::vector<int> chain(n);U seen=0;
        for(int& cell:chain){std::cin>>cell;if(cell<0||cell>=42||(seen&(U(1)<<cell)))throw std::runtime_error("bad cell");seen|=U(1)<<cell;}
        size_t id=0;Group merged;
        for(;id<groups.size();++id){
            U earlier=0;bool okay=true;
            for(int cell:chain){if(groups[id].reach[cell]&earlier&~(U(63)<<(6*(cell/6)))){okay=false;break;}earlier|=U(1)<<cell;}
            if(!okay)continue;
            // Multiple new edges may close a cycle through old paths, even
            // when no individual reversed cross-column pair was present.
            merged=groups[id];if(extend(merged,chain))break;
        }
        if(id==groups.size()){merged=Group{};if(!extend(merged,chain))throw std::runtime_error("invalid partial order");groups.emplace_back();}
        groups[id]=merged;
        assignment.push_back(id);
    }
    if(!std::cin)throw std::runtime_error("truncated chains");
    std::cout<<"{\"assignments\":[";
    for(size_t i=0;i<count;++i)std::cout<<(i?",":"")<<assignment[i];
    std::cout<<"],\"policies\":[";
    for(size_t id=0;id<groups.size();++id){
        U left=(U(1)<<42)-1;std::array<int,42> ranks{};
        for(int level=0;level<42;++level){
            U blocked=0;for(int p=0;p<42;++p)if(left&(U(1)<<p))blocked|=groups[id].reach[p];
            U available=left&~blocked;int chosen=-1;
            for(int c:{3,2,4,1,5,0,6})for(int r=0;r<6;++r){int cell=6*c+r;if(chosen<0&&(available&(U(1)<<cell)))chosen=cell;}
            if(chosen<0)throw std::runtime_error("cyclic merged policy");
            ranks[chosen]=level;left&=~(U(1)<<chosen);
        }
        std::cout<<(id?",":"")<<'[';for(int i=0;i<42;++i)std::cout<<(i?",":"")<<ranks[i];std::cout<<']';
    }
    std::cout<<"]}\n";return 0;
}catch(std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
