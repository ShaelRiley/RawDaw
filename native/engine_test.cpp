#include "engine.hpp"
#include <cassert>
#include <cstdlib>
#include <new>
#include <iostream>
#include <vector>

static bool processing = false;
void* operator new(std::size_t size) {
    if (processing) std::abort();
    if (auto* result=std::malloc(size)) return result;
    throw std::bad_alloc();
}
void operator delete(void* ptr) noexcept { std::free(ptr); }
void operator delete(void* ptr,std::size_t) noexcept { std::free(ptr); }

// Explicit synthetic boundary probes. They are not song material or listening proof.
static std::vector<float> render(prde1::Asset asset, std::vector<prde1::Event> events,
                                 std::size_t frames, std::size_t block) {
    prde1::Compressor comp; comp.on=false;
    prde1::Engine engine({std::move(asset)},std::move(events),comp,1);
    std::vector<float> output(frames*2);
    processing=true;
    for (std::size_t first=0;first<frames;first+=block)
        engine.process(output.data()+first*2,std::min(block,frames-first));
    processing=false;
    return output;
}

static void boundary_checks() {
    // DC deliberately exposes a nonzero crop/onset and a hard buffer ending.
    prde1::Asset dc{std::vector<float>(1200,0.25f),1,1200,100,0,0};
    const float center=0.25f*0.70710678f;
    for (const auto end : {std::uint64_t(1000),std::uint64_t(1500)}) {
        const std::size_t stop=std::min<std::uint64_t>(end,513+1100);
        auto out=render(dc,{{0,513,end,0,240,1,0}},1800,256);
        assert(out[513*2]==0 && out[(stop-1)*2]==0);
        assert(std::abs(out[600*2]-center)<0.000001f); // unchanged interior frame/gain
        assert(std::abs(out[514*2])<center*0.002f); // no onset impulse
        assert(std::abs(out[(stop-2)*2])<center*0.0001f); // gentle final slope into silence
        for (std::size_t i=1;i<1800;++i) {
            assert(std::abs(out[i*2]-out[(i-1)*2])<center*0.04f);
            if (i>=stop) assert(out[i*2]==0 && out[i*2+1]==0);
        }
        assert(out==render(dc,{{0,513,end,0,240,1,0}},1800,1));
        assert(out==render(dc,{{0,513,end,0,240,1,0}},1800,17));
    }
    // A gate beyond natural exhaustion must fade before the physical buffer ends.
    auto exhausted=render(dc,{{0,513,1800,0,240,1,0}},1900,256);
    assert(exhausted[(1613-2)*2]<center*0.0001f && exhausted[(1613-1)*2]==0);
    for (std::size_t i=1613;i<1900;++i) assert(exhausted[i*2]==0);

    // Half-open retriggers (also the hat-choke schedule) have two zero boundaries.
    auto retrigger=render(dc,{{0,255,513,0,240,1,0},{0,513,900,0,240,1,0}},1100,256);
    assert(retrigger[512*2]==0 && retrigger[513*2]==0);
    assert(std::abs(retrigger[511*2])<center*0.0001f);
    assert(std::abs(retrigger[514*2])<center*0.002f);
    for (const auto duration : {1U,2U,7U,48U,239U}) {
        auto brief=render(dc,{{0,255,255+duration,0,240,1,0}},600,17);
        assert(brief[255*2]==0 && brief[(255+duration-1)*2]==0);
        for (float value:brief) assert(std::isfinite(value) && std::abs(value)<=center);
    }
    // A saved slow attack still applies after the short safety envelope finishes.
    auto slow=render(dc,{{0,255,1100,96,240,1,0}},1200,17);
    assert(std::abs(slow[(255+48)*2]-center*0.5f)<0.000001f);
    assert(std::abs(slow[(255+96)*2]-center)<0.000001f);
}

static std::vector<float> mix_probe(std::vector<prde1::Event> events,prde1::MixProcessing mix,std::size_t block=256) {
    prde1::Asset held{std::vector<float>(48000,.08f),1,48000,0,100,1000};
    prde1::Compressor master;master.on=false;
    prde1::Engine engine({held},std::move(events),master,1,mix);
    std::vector<float> out(24000*2);
    processing=true;
    for (std::size_t first=0;first<24000;first+=block) engine.process(out.data()+first*2,std::min(block,24000-first));
    processing=false;
    return out;
}

static void mix_checks() {
    prde1::MixProcessing mix;mix.on=true;mix.drum_compressor.on=false;
    prde1::Event kick{0,1000,7000,0,240,1,0};kick.channel=3;
    prde1::Event snare=kick;snare.channel=4;
    prde1::Event bass{0,0,24000,0,240,1,0};bass.channel=1;
    prde1::Event lead=bass;lead.channel=0;
    // A bypassed graph contributes the drum signal once, never a direct copy.
    const auto dry=mix_probe({kick},mix);
    mix.on=false;assert(dry==mix_probe({kick},mix));mix.on=true;
    // Independent EQ does not reach the other drum or lead lane.
    mix.drum_eq[1]={true,120,190,3,.9,4500,2};
    assert(dry==mix_probe({kick},mix));
    const auto lead_dry=mix_probe({lead},mix);
    assert(mix_probe({snare},mix)!=dry);mix.drum_eq[1].on=false;
    // Combined drums cross a threshold which each alone does not cross.
    mix.drum_compressor={true,-24,4,1,50,0};
    const auto combined=mix_probe({kick,snare},mix);
    assert(combined[5000*2]<dry[5000*2]*1.6f);
    assert(mix_probe({lead},mix)==lead_dry);
    // Makeup lifts only drums; bypass removes the boost too.
    mix.drum_compressor={true,-24,1,1,50,3};
    assert(std::abs(mix_probe({kick},mix)[5000*2]/dry[5000*2]-std::pow(10.0,3.0/20))<.000001);
    mix.drum_compressor.on=false;assert(mix_probe({kick},mix)==dry);
    // Use bass isolated from its audible trigger to measure actual ducking.
    mix.bass_sidechain={true,-36,8,1,40,6};
    assert(mix_probe({bass},mix)==mix_probe({bass},prde1::MixProcessing{}));
    assert(mix_probe({lead,kick},mix)[5000*2]==lead_dry[5000*2]+dry[5000*2]);
    const auto ducked=mix_probe({bass,kick},mix);
    const double bass_dry=lead_dry[5000*2];
    const double duck_ratio=(ducked[5000*2]-dry[5000*2])/bass_dry;
    assert(duck_ratio>.500 && duck_ratio<.503); // cap, not arbitrary rhythmic gain
    assert((ducked[21000*2]-dry[21000*2])/lead_dry[21000*2]>.99); // recovery in a rest
    assert(ducked==mix_probe({bass,kick},mix,1));assert(ducked==mix_probe({bass,kick},mix,17));
    // Detector links the stereo pair; no channel-image movement while ducking.
    for (std::size_t i=0;i<24000;++i) assert(ducked[i*2]==ducked[i*2+1]);
    // A calibrated sine checks filter response, independently of coefficient code.
    prde1::Biquad bell;bell.configure(prde1::Biquad::bell,1000,6,1);
    double a=0,b=0;
    for (int i=0;i<48000;++i) {
        const double input=.05*std::sin(6.283185307179586*1000*i/48000);
        const double output=bell.process(input,0);
        if (i>24000) { a+=input*input;b+=output*output; }
    }
    assert(std::abs(10*std::log10(b/a)-6)<.01);
}

int main() {
    boundary_checks();
    mix_checks();
    prde1::Asset asset{{0.25f,0.5f,-0.25f,0.125f,0.0f},1,5,0,2,4};
    prde1::Event event{0,0,4096,0,240,1,0};
    prde1::Compressor comp; comp.on=false;
    prde1::Engine engine({asset},{event},comp,1);
    std::array<float,512> output{};
    processing=true;
    engine.process(output.data(),256);
    processing=false;
    assert(output[0]==0 && output[1]==0);
    assert(std::abs(output[100*2]-(-0.25f)*0.70710678f)<0.000001f); // unchanged sustain frame, no attack repetition
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
    std::cout<<"Native tests: allocation-free process, frame-copy identity, sustain-only loop, smooth start/end, natural exhaustion, retrigger/choke, tiny gates, block identity, release, silence, voice cap passed\n";
}
