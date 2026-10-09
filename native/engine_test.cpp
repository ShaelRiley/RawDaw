#include "engine.hpp"
#include <cassert>
#include <cstdlib>
#include <new>
#include <iostream>

static bool processing = false;
void* operator new(std::size_t size) {
    if (processing) std::abort();
    if (auto* result=std::malloc(size)) return result;
    throw std::bad_alloc();
}
void operator delete(void* ptr) noexcept { std::free(ptr); }
void operator delete(void* ptr,std::size_t) noexcept { std::free(ptr); }

int main() {
    prde1::Asset asset{{0.25f,0.5f,-0.25f,0.125f,0.0f},1,5,0,2,4};
    prde1::Event event{0,0,4096,0,240,1,0};
    prde1::Compressor comp; comp.on=false;
    prde1::Engine engine({asset},{event},comp,1);
    std::array<float,512> output{};
    processing=true;
    engine.process(output.data(),256);
    processing=false;
    assert(std::abs(output[0]-0.25f*0.70710678f)<0.000001f);
    assert(std::abs(output[8]-(-0.25f)*0.70710678f)<0.000001f); // sustain repeats, not the attack
    assert(engine.clock()==256);
    for (int block=0;block<15;++block) {
        processing=true;engine.process(output.data(),256);processing=false;
    }
    assert(output[510]==0 && output[511]==0); // de-click envelope reaches zero
    processing=true;engine.process(output.data(),256);processing=false;
    for (auto value:output) assert(value==0); // stopped voice never retriggers itself
    bool rejected=false;
    try { prde1::Engine overload({asset},std::vector<prde1::Event>(65,event),comp,1); }
    catch (const std::runtime_error&) { rejected=true; }
    assert(rejected);
    std::cout<<"Native tests: allocation-free process, frame-copy identity, sustain-only loop, release, silence, voice cap passed\n";
}
