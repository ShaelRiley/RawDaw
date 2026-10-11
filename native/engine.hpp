#pragma once
// Native sample clock. No JSON, disk I/O, allocation, locks, synthesis, or
// pitch/rate parameters occur inside process(). Preparation is non-real-time.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>
#include "dsp.hpp"

namespace prde1 {
constexpr std::uint32_t sample_rate = 48000;
constexpr std::size_t max_voices = 64;
constexpr std::uint32_t boundary_attack_frames = 48; // 1 ms, independent of expressive attack.

struct Asset {
    std::vector<float> pcm;
    std::uint32_t channels = 1, frames = 0, onset = 0, loop_start = 0, loop_end = 0;
};
struct Event {
    std::uint32_t asset = 0;
    std::uint64_t start = 0, end = 0;
    std::uint32_t attack = 0, release = 240;
    float gain = 1, pan = 0;
    double left_gain = 0, right_gain = 0;
    std::size_t channel = 0; // lead, bass, rhythm, then the eight drum slots
};

class Engine {
public:
    Engine(std::vector<Asset> assets, std::vector<Event> events, Compressor compressor, float master_gain,
           MixProcessing mix = {})
        : assets_(std::move(assets)), events_(std::move(events)), master_gain_(master_gain), mix_(mix) {
        master_dynamics_.configure(compressor);
        drum_dynamics_.configure(mix.drum_compressor);
        const auto& sc=mix.bass_sidechain;
        sidechain_.configure({sc.on,sc.threshold_db,sc.ratio,sc.attack_ms,sc.release_ms,0},sc.max_duck_db);
        for (std::size_t i=0;i<drum_count;++i) drum_eq_[i].configure(mix.drum_eq[i]);
        const double angle=(mix.drum_pan+1)*0.78539816339744830962;
        drum_left_=std::min(1.0,std::cos(angle)*1.4142135623730951)*mix.drum_gain;
        drum_right_=std::min(1.0,std::sin(angle)*1.4142135623730951)*mix.drum_gain;
        std::size_t previous = 0;
        for (auto& event : events_) {
            if (event.asset >= assets_.size() || event.end <= event.start || event.start < previous || event.release == 0 || event.channel >= channel_count)
                throw std::runtime_error("Invalid prepared event plan");
            previous = event.start;
            const auto& asset = assets_[event.asset];
            if (asset.onset >= asset.frames) throw std::runtime_error("Invalid prepared sample onset");
            // The sample player also protects natural exhaustion. A longer gate
            // must not bypass the release by running off the immutable buffer.
            if (asset.loop_end <= asset.loop_start) {
                const auto available = asset.frames - asset.onset;
                if (event.end - event.start > available) event.end = event.start + available;
            }
            event.release = static_cast<std::uint32_t>(std::min<std::uint64_t>(event.release, event.end - event.start));
            const double angle = (event.pan + 1) * 0.78539816339744830962;
            event.left_gain=std::cos(angle); event.right_gain=std::sin(angle);
            if (assets_[event.asset].channels==2) {
                event.left_gain=std::min(1.0,event.left_gain*1.4142135623730951);
                event.right_gain=std::min(1.0,event.right_gain*1.4142135623730951);
            }
        }
        // Bound concurrency once during preparation. End-before-start ordering
        // preserves half-open intervals, including simultaneous retriggers.
        std::vector<std::pair<std::uint64_t, int>> boundaries;
        boundaries.reserve(events_.size() * 2);
        for (const auto& event : events_) {
            boundaries.emplace_back(event.start, 1);
            boundaries.emplace_back(event.end, -1);
        }
        std::sort(boundaries.begin(), boundaries.end());
        int active = 0;
        for (const auto& boundary : boundaries) {
            active += boundary.second;
            if (active > static_cast<int>(max_voices)) throw std::runtime_error("64-voice budget exceeded");
        }
    }

    void process(float* stereo, std::size_t frames) noexcept {
        for (std::size_t offset = 0; offset < frames; ++offset, ++clock_) {
            for (auto& voice : voices_) if (voice && voice->end <= clock_) voice = nullptr;
            while (next_event_ < events_.size() && events_[next_event_].start <= clock_) {
                const auto* event = &events_[next_event_++];
                if (event->end <= clock_) continue;
                for (auto& voice : voices_) if (!voice) { voice = event; break; }
            }
            double left = 0, right = 0;
            std::array<std::array<double,2>,channel_count> channels{};
            for (const auto* event : voices_) {
                if (!event) continue;
                const auto& asset = assets_[event->asset];
                const auto elapsed = clock_ - event->start;
                std::uint64_t index = asset.onset + elapsed;
                if (asset.loop_end > asset.loop_start && index >= asset.loop_end)
                    index = asset.loop_start + (index - asset.loop_start) % (asset.loop_end - asset.loop_start);
                if (index >= asset.frames) continue;
                // Pack onset offsets can skip their baked fade. Always begin at
                // zero, including a retrigger or an authored Attack=0 event.
                const auto start_span = std::min<std::uint64_t>(boundary_attack_frames, event->end - event->start - 1);
                double envelope = start_span ? smooth_boundary(std::min(1.0, static_cast<double>(elapsed) / start_span)) : 0;
                if (event->attack) envelope *= std::min(1.0, static_cast<double>(elapsed) / event->attack);
                const auto remaining = event->end - clock_;
                if (remaining <= event->release)
                    envelope *= event->release > 1 ? smooth_boundary(static_cast<double>(remaining - 1) / (event->release - 1)) : 0;
                const double gain = envelope * event->gain;
                const std::size_t base = static_cast<std::size_t>(index) * asset.channels;
                const double l=asset.pcm[base]*gain*event->left_gain;
                const double r=asset.pcm[base+(asset.channels==2 ? 1 : 0)]*gain*event->right_gain;
                if (mix_.on) { channels[event->channel][0]+=l; channels[event->channel][1]+=r; }
                else { left+=l; right+=r; } // exact legacy dry accumulation
            }
            if (mix_.on) {
                double drums_left=0,drums_right=0,kick_detector=0;
                for (std::size_t i=0;i<drum_count;++i) {
                    auto& channel=channels[i+3];drum_eq_[i].process(channel[0],channel[1]);
                    if (i==0) kick_detector=std::max(std::abs(channel[0]),std::abs(channel[1]));
                    drums_left+=channel[0];drums_right+=channel[1];
                }
                const double duck=sidechain_.gain(kick_detector);
                channels[1][0]*=duck;channels[1][1]*=duck;
                const double drum_gain=drum_dynamics_.gain(std::max(std::abs(drums_left),std::abs(drums_right)));
                // Exactly one drum-group contribution; detector is never audible.
                left=channels[0][0]+channels[1][0]+channels[2][0]+drums_left*drum_gain*drum_left_;
                right=channels[0][1]+channels[1][1]+channels[2][1]+drums_right*drum_gain*drum_right_;
            }
            left *= master_gain_; right *= master_gain_;
            const double master_gain=master_dynamics_.gain(std::max(std::abs(left),std::abs(right)));
            left*=master_gain;right*=master_gain;
            stereo[offset * 2] = static_cast<float>(left);
            stereo[offset * 2 + 1] = static_cast<float>(right);
        }
    }
    std::uint64_t clock() const noexcept { return clock_; }
    double drum_reduction_db() const noexcept { return drum_dynamics_.max_reduction_db(); }
    double bass_duck_db() const noexcept { return sidechain_.max_reduction_db(); }
    double master_reduction_db() const noexcept { return master_dynamics_.max_reduction_db(); }
private:
    // Cubic endpoints have zero slope: no linear-ramp corner at either side.
    // This changes amplitude only; the prepared frame clock advances at 1x.
    static double smooth_boundary(double x) noexcept { return x * x * (3 - 2 * x); }
    std::vector<Asset> assets_;
    std::vector<Event> events_;
    float master_gain_;
    MixProcessing mix_;
    std::array<DrumEq,drum_count> drum_eq_{};
    Dynamics master_dynamics_,drum_dynamics_,sidechain_;
    double drum_left_=1,drum_right_=1;
    std::array<const Event*, max_voices> voices_{};
    std::size_t next_event_ = 0;
    std::uint64_t clock_ = 0;
};
} // namespace prde1
