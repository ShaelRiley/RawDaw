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
};
struct Compressor {
    bool on = true;
    double threshold_db = -12, ratio = 2, attack_ms = 10, release_ms = 150;
};

class Engine {
public:
    Engine(std::vector<Asset> assets, std::vector<Event> events, Compressor compressor, float master_gain)
        : assets_(std::move(assets)), events_(std::move(events)), compressor_(compressor), master_gain_(master_gain) {
        attack_coefficient_ = std::exp(-1.0 / (sample_rate * compressor.attack_ms / 1000));
        release_coefficient_ = std::exp(-1.0 / (sample_rate * compressor.release_ms / 1000));
        threshold_ = std::pow(10.0, compressor.threshold_db / 20);
        std::size_t previous = 0;
        for (auto& event : events_) {
            if (event.asset >= assets_.size() || event.end <= event.start || event.start < previous || event.release == 0)
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
                if (asset.channels == 1) {
                    left += asset.pcm[base] * gain * event->left_gain;
                    right += asset.pcm[base] * gain * event->right_gain;
                } else {
                    // Stereo balance preserves both channels at center, rather
                    // than collapsing a prepared stereo chord to mono.
                    left += asset.pcm[base] * gain * event->left_gain;
                    right += asset.pcm[base + 1] * gain * event->right_gain;
                }
            }
            left *= master_gain_; right *= master_gain_;
            if (compressor_.on) {
                const double detector = std::max(std::abs(left), std::abs(right));
                const double coefficient = detector > envelope_ ? attack_coefficient_ : release_coefficient_;
                envelope_ = coefficient * envelope_ + (1 - coefficient) * detector;
                if (envelope_ > threshold_) {
                    const double gain = std::pow(envelope_ / threshold_, 1 / compressor_.ratio - 1);
                    left *= gain; right *= gain;
                }
            }
            stereo[offset * 2] = static_cast<float>(left);
            stereo[offset * 2 + 1] = static_cast<float>(right);
        }
    }
    std::uint64_t clock() const noexcept { return clock_; }
private:
    // Cubic endpoints have zero slope: no linear-ramp corner at either side.
    // This changes amplitude only; the prepared frame clock advances at 1x.
    static double smooth_boundary(double x) noexcept { return x * x * (3 - 2 * x); }
    std::vector<Asset> assets_;
    std::vector<Event> events_;
    Compressor compressor_;
    float master_gain_;
    std::array<const Event*, max_voices> voices_{};
    std::size_t next_event_ = 0;
    std::uint64_t clock_ = 0;
    double envelope_ = 0, attack_coefficient_ = 0, release_coefficient_ = 0, threshold_ = 0;
};
} // namespace prde1
