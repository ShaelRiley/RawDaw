#pragma once
// Fixed downstream mix processors. Coefficients/state are prepared off-thread;
// process() performs no allocation, I/O, locks, or harmonic transformations.
#include <array>
#include <algorithm>
#include <cmath>
#include <cstddef>

namespace prde1 {
constexpr std::size_t drum_count = 8;
constexpr std::size_t channel_count = 3 + drum_count;
struct Compressor {
    bool on = true;
    double threshold_db = -12, ratio = 2, attack_ms = 10, release_ms = 150;
    double makeup_db = 0;
};
struct EqSettings {
    bool on = false;
    double highpass_hz = 30, bell_hz = 200, bell_db = 0, bell_q = 0.8;
    double shelf_hz = 6000, shelf_db = 0;
};
struct SidechainSettings {
    bool on = false;
    double threshold_db = -30, ratio = 4, attack_ms = 1, release_ms = 140, max_duck_db = 6;
};
struct MixProcessing {
    bool on = false;
    std::array<EqSettings, drum_count> drum_eq{};
    Compressor drum_compressor{false, -26, 3, 25, 100, 3};
    SidechainSettings bass_sidechain{};
    double drum_gain = 1, drum_pan = 0;
};

class Biquad {
public:
    enum Kind { highpass, bell, high_shelf };
    void configure(Kind kind, double hz, double db = 0, double q = 0.7071067811865475) noexcept {
        // RBJ coefficient formulae: https://www.w3.org/TR/audio-eq-cookbook/
        const double w = 6.2831853071795864769 * hz / 48000;
        const double c = std::cos(w), s = std::sin(w), a = std::pow(10.0, db / 40);
        double b0, b1, b2, a0, a1, a2;
        if (kind == highpass) {
            const double alpha = s / (2 * q);
            b0 = (1+c)/2; b1 = -(1+c); b2 = b0;
            a0 = 1+alpha; a1 = -2*c; a2 = 1-alpha;
        } else if (kind == bell) {
            const double alpha = s / (2 * q);
            b0 = 1+alpha*a; b1 = -2*c; b2 = 1-alpha*a;
            a0 = 1+alpha/a; a1 = -2*c; a2 = 1-alpha/a;
        } else {
            const double t = 2 * std::sqrt(a) * s / std::sqrt(2.0); // shelf slope S=1
            b0 = a*((a+1)+(a-1)*c+t); b1 = -2*a*((a-1)+(a+1)*c); b2 = a*((a+1)+(a-1)*c-t);
            a0 = (a+1)-(a-1)*c+t; a1 = 2*((a-1)-(a+1)*c); a2 = (a+1)-(a-1)*c-t;
        }
        b_ = {b0/a0,b1/a0,b2/a0}; a_ = {a1/a0,a2/a0};
        state_ = {};
    }
    double process(double input, std::size_t channel) noexcept {
        auto& st = state_[channel];
        const double output = b_[0]*input + st[0];
        st[0] = b_[1]*input - a_[0]*output + st[1];
        st[1] = b_[2]*input - a_[1]*output;
        // Prevent denormal slowdowns during long rests, far below audible PCM.
        for (auto& value : st) if (std::abs(value)<1e-30) value=0;
        return output;
    }
private:
    std::array<double,3> b_{1,0,0};
    std::array<double,2> a_{};
    std::array<std::array<double,2>,2> state_{};
};

class DrumEq {
public:
    void configure(EqSettings settings) noexcept {
        on_=settings.on;
        filters_[0].configure(Biquad::highpass,settings.highpass_hz);
        filters_[1].configure(Biquad::bell,settings.bell_hz,settings.bell_db,settings.bell_q);
        filters_[2].configure(Biquad::high_shelf,settings.shelf_hz,settings.shelf_db);
    }
    void process(double& left, double& right) noexcept {
        if (!on_) return;
        for (auto& filter : filters_) { left=filter.process(left,0); right=filter.process(right,1); }
    }
private:
    bool on_=false;
    std::array<Biquad,3> filters_{};
};

class Dynamics {
public:
    void configure(Compressor settings, double max_duck_db=200) noexcept {
        settings_=settings;
        attack_=std::exp(-1.0/(48000*settings.attack_ms/1000));
        release_=std::exp(-1.0/(48000*settings.release_ms/1000));
        threshold_=std::pow(10.0,settings.threshold_db/20);
        makeup_=std::pow(10.0,settings.makeup_db/20);
        floor_=std::pow(10.0,-max_duck_db/20); envelope_=0; min_gain_=1;
    }
    double gain(double detector) noexcept {
        if (!settings_.on) return 1; // Bypass includes makeup gain.
        const double coefficient=detector>envelope_ ? attack_ : release_;
        envelope_=coefficient*envelope_+(1-coefficient)*detector;
        if (envelope_<1e-30) envelope_=0;
        const double reduction=envelope_>threshold_ ? std::max(floor_,std::pow(envelope_/threshold_,1/settings_.ratio-1)) : 1;
        min_gain_=std::min(min_gain_,reduction);
        return reduction*makeup_;
    }
    double max_reduction_db() const noexcept { return -20*std::log10(min_gain_); }
private:
    Compressor settings_{};
    double attack_=0,release_=0,threshold_=1,makeup_=1,floor_=0,envelope_=0,min_gain_=1;
};
} // namespace prde1
