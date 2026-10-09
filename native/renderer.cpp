#include "engine.hpp"
#include <nlohmann/json.hpp>
#include <cerrno>
#include <cstdio>
#include <filesystem>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <string>
#include <unistd.h>

using nlohmann::json;
namespace fs = std::filesystem;

static std::uint32_t little(const unsigned char* bytes, int count) {
    std::uint32_t value = 0;
    for (int index = 0; index < count; ++index) value |= std::uint32_t(bytes[index]) << (8 * index);
    return value;
}
static std::uint64_t bounded(const json& object, const char* key, std::uint64_t low, std::uint64_t high) {
    const auto& value = object.at(key);
    if (!value.is_number_integer() || (value.is_number_integer() && value.get<std::int64_t>() < 0))
        throw std::runtime_error(std::string("Invalid integer: ") + key);
    auto integer = value.get<std::uint64_t>();
    if (integer < low || integer > high) throw std::runtime_error(std::string("Out of bounds: ") + key);
    return integer;
}
static double finite(const json& object, const char* key, double low, double high) {
    const auto value = object.at(key).get<double>();
    if (!std::isfinite(value) || value < low || value > high) throw std::runtime_error(std::string("Out of bounds: ") + key);
    return value;
}

static prde1::Asset read_asset(const fs::path& root, const json& metadata) {
    const auto relative = metadata.at("path").get<std::string>();
    fs::path child(relative);
    if (child.is_absolute() || relative.empty() || relative.find('\\') != std::string::npos || relative.find(':') != std::string::npos)
        throw std::runtime_error("Unsafe prepared asset path");
    for (const auto& part : child) if (part == ".." || part == ".") throw std::runtime_error("Asset path traversal");
    const auto path = fs::canonical(root / child);
    auto canonical_root = fs::canonical(root).string() + "/";
    if (path.string().rfind(canonical_root, 0) != 0) throw std::runtime_error("Asset escapes validated cache");
    auto size = fs::file_size(path);
    if (size > 8715536 || size < 44) throw std::runtime_error("Invalid WAV size");
    std::ifstream stream(path, std::ios::binary);
    std::vector<unsigned char> raw(size);
    if (!stream.read(reinterpret_cast<char*>(raw.data()), static_cast<std::streamsize>(size))) throw std::runtime_error("WAV read failed");
    if (std::string(reinterpret_cast<char*>(raw.data()),4) != "RIFF" || std::string(reinterpret_cast<char*>(raw.data()+8),4) != "WAVE")
        throw std::runtime_error("Not a RIFF WAV");
    prde1::Asset asset;
    bool format = false, data = false;
    std::size_t start = 0, data_size = 0;
    for (std::size_t cursor = 12; cursor + 8 <= raw.size();) {
        auto length = little(raw.data()+cursor+4,4);
        if (length > raw.size()-cursor-8) throw std::runtime_error("Truncated WAV chunk");
        const std::string kind(reinterpret_cast<char*>(raw.data()+cursor),4);
        if (kind == "fmt ") {
            if (format || length < 16) throw std::runtime_error("Invalid WAV format chunk");
            auto* f = raw.data()+cursor+8;
            asset.channels = little(f+2,2);
            if (little(f,2)!=1 || (asset.channels!=1 && asset.channels!=2) || little(f+4,4)!=prde1::sample_rate
                || little(f+14,2)!=24 || little(f+12,2)!=asset.channels*3 || little(f+8,4)!=prde1::sample_rate*asset.channels*3)
                throw std::runtime_error("Expected 48 kHz, 24-bit PCM; no runtime conversion/transposition");
            format = true;
        } else if (kind == "data") {
            if (data) throw std::runtime_error("Duplicate WAV data chunk");
            start = cursor+8; data_size = length; data = true;
        }
        cursor += 8 + length + (length & 1);
    }
    if (!format || !data || !data_size || data_size % (asset.channels*3)) throw std::runtime_error("Missing/unaligned PCM data");
    asset.frames = static_cast<std::uint32_t>(data_size / (asset.channels*3));
    if (asset.frames != bounded(metadata,"frames",1,1440000) || asset.channels != bounded(metadata,"channels",1,2))
        throw std::runtime_error("Prepared dimensions mismatch");
    asset.onset = static_cast<std::uint32_t>(bounded(metadata,"onsetFrame",0,asset.frames-1));
    asset.loop_start = static_cast<std::uint32_t>(bounded(metadata,"loopStart",0,asset.frames));
    asset.loop_end = static_cast<std::uint32_t>(bounded(metadata,"loopEnd",0,asset.frames));
    if ((asset.loop_start || asset.loop_end) && !(asset.onset < asset.loop_start && asset.loop_start < asset.loop_end))
        throw std::runtime_error("Unsafe validated sustain markers");
    asset.pcm.resize(static_cast<std::size_t>(asset.frames)*asset.channels);
    for (std::size_t index = 0; index < asset.pcm.size(); ++index) {
        auto value = little(raw.data()+start+index*3,3);
        auto signed_value = static_cast<std::int32_t>(value & 0x800000 ? value | 0xff000000 : value);
        asset.pcm[index] = static_cast<float>(signed_value / 8388608.0);
    }
    return asset;
}

class WavWriter {
public:
    WavWriter(fs::path path, std::uint64_t frames) : target_(std::move(path)), expected_(frames) {
        if (!target_.parent_path().empty()) fs::create_directories(target_.parent_path());
        std::string pattern = target_.string() + ".partial.XXXXXX";
        std::vector<char> name(pattern.begin(),pattern.end()); name.push_back('\0');
        const int descriptor = mkstemp(name.data());
        if (descriptor < 0) throw std::runtime_error("Cannot create temporary export");
        temporary_ = name.data();
        stream_ = fdopen(descriptor,"wb");
        if (!stream_) { close(descriptor); fs::remove(temporary_); throw std::runtime_error("Cannot open temporary export"); }
        try {
            write("RIFF",4); integer(static_cast<std::uint32_t>(36+frames*6),4); write("WAVEfmt ",8); integer(16,4);
            integer(1,2); integer(2,2); integer(prde1::sample_rate,4); integer(prde1::sample_rate*6,4); integer(6,2); integer(24,2);
            write("data",4); integer(static_cast<std::uint32_t>(frames*6),4);
        } catch (...) {
            std::fclose(stream_); stream_=nullptr; fs::remove(temporary_); temporary_.clear(); throw;
        }
    }
    ~WavWriter() {
        if (stream_) std::fclose(stream_);
        if (!temporary_.empty()) { std::error_code ignored; fs::remove(temporary_,ignored); }
    }
    void frames(const float* stereo, std::size_t count, std::uint64_t absolute_start) {
        std::array<unsigned char,256*6> bytes{};
        if (count > 256) throw std::runtime_error("Invalid export block");
        for (std::size_t index = 0; index < count*2; ++index) {
            const auto position = (absolute_start*2)+index;
            // Counter-addressed TPDF dither, so seek and whole-render slices match.
            const double dither = uniform(position*2) - uniform(position*2+1);
            const auto value = static_cast<std::int32_t>(std::llround(static_cast<double>(stereo[index])*8388608+dither));
            if (value < -8388608 || value > 8388607) throw std::runtime_error("Quantized export clipping");
            for (int byte = 0; byte < 3; ++byte) bytes[index*3+byte] = static_cast<unsigned char>((std::uint32_t(value)>>(byte*8))&255);
        }
        write(bytes.data(),count*6); written_ += count;
    }
    void commit() {
        if (written_ != expected_ || std::fflush(stream_) || fsync(fileno(stream_))) throw std::runtime_error("Incomplete/undurable export");
        if (std::fclose(stream_)) { stream_=nullptr; throw std::runtime_error("Export close failed"); }
        stream_=nullptr;
        fs::rename(temporary_,target_); temporary_.clear();
        auto parent = target_.parent_path().empty() ? fs::path(".") : target_.parent_path();
        const int directory = ::open(parent.c_str(), O_RDONLY | O_DIRECTORY);
        if (directory >= 0) { const auto result = fsync(directory); ::close(directory); if (result) throw std::runtime_error("Export directory sync failed"); }
    }
private:
    static double uniform(std::uint64_t position) {
        std::uint64_t value = position+0x9e3779b97f4a7c15ULL;
        value = (value^(value>>30))*0xbf58476d1ce4e5b9ULL;
        value = (value^(value>>27))*0x94d049bb133111ebULL;
        value ^= value>>31;
        return static_cast<double>(value>>11)/9007199254740992.0;
    }
    void integer(std::uint32_t value,int count) { unsigned char bytes[4]{}; for (int i=0;i<count;++i) bytes[i]=static_cast<unsigned char>(value>>(8*i)); write(bytes,count); }
    void write(const void* data,std::size_t count) { if (std::fwrite(data,1,count,stream_)!=count) throw std::runtime_error("Export write failed (check storage)"); }
    fs::path target_,temporary_;
    FILE* stream_ = nullptr;
    std::uint64_t written_ = 0,expected_;
};

int main(int argc,char** argv) {
    try {
        if (argc!=4 && argc!=5) throw std::runtime_error("Usage: prde1-render RESOLVED.json VALIDATED_PACK_ROOT OUTPUT.wav [SEEK_FRAME]");
        if (fs::file_size(argv[1]) > 64*1024*1024) throw std::runtime_error("Plan file too large");
        std::ifstream input(argv[1]);
        const auto plan = json::parse(input);
        if (plan.at("formatVersion")!="1.0.0-dev.1" || plan.at("sampleRate")!=48000) throw std::runtime_error("Incompatible event plan");
        const auto end = bounded(plan,"endFrame",1,86400000);
        const std::uint64_t seek = argc==5 ? std::stoull(argv[4]) : 0;
        if (seek>=end) throw std::runtime_error("Seek outside song");
        const auto& asset_rows = plan.at("assets");
        const auto& event_rows = plan.at("events");
        if (!asset_rows.is_array() || asset_rows.size()>1024 || !event_rows.is_array() || event_rows.size()>100000)
            throw std::runtime_error("Plan array budget exceeded");
        std::vector<prde1::Asset> assets; assets.reserve(asset_rows.size());
        std::size_t decoded = 0;
        for (const auto& row : asset_rows) {
            assets.push_back(read_asset(argv[2],row));
            decoded += assets.back().pcm.size()*sizeof(float);
            if (decoded>256*1024*1024) throw std::runtime_error("Decoded asset budget exceeded");
        }
        std::vector<prde1::Event> events; events.reserve(event_rows.size());
        for (const auto& row : event_rows) {
            if (assets.empty()) throw std::runtime_error("Events without assets");
            prde1::Event event;
            event.asset = static_cast<std::uint32_t>(bounded(row,"assetIndex",0,assets.size()-1));
            event.start = bounded(row,"startFrame",0,end-1);
            event.end = bounded(row,"endFrame",event.start+1,end);
            event.attack = static_cast<std::uint32_t>(bounded(row,"attackFrames",0,4800));
            event.release = static_cast<std::uint32_t>(bounded(row,"releaseFrames",1,std::min(std::uint64_t(4800),event.end-event.start)));
            event.gain = static_cast<float>(finite(row,"gain",0,8)); event.pan = static_cast<float>(finite(row,"pan",-1,1));
            events.push_back(event);
        }
        const auto& comp = plan.at("compressor");
        prde1::Compressor compressor{comp.at("on").get<bool>(),finite(comp,"thresholdDb",-48,0),finite(comp,"ratio",1,20),
                                     finite(comp,"attackMs",0.1,100),finite(comp,"releaseMs",10,2000)};
        prde1::Engine engine(std::move(assets),std::move(events),compressor,static_cast<float>(finite(plan,"masterGain",0,4)));
        const double ceiling = std::pow(10.0,finite(plan,"peakCeilingDb",-1,0)/20);
        WavWriter output(argv[3],end-seek);
        std::array<float,256*2> block{};
        double peak = 0;
        // Seek pre-roll deliberately reconstructs compressor/held-voice state.
        // Native device seeking can later checkpoint this state; it must not
        // skip straight to a clock value and leak or omit old processing state.
        while (engine.clock()<end) {
            const auto first=engine.clock();
            auto count=static_cast<std::size_t>(std::min(std::uint64_t(256),end-first));
            if (first<seek) count=static_cast<std::size_t>(std::min(std::uint64_t(count),seek-first));
            engine.process(block.data(),count);
            for (std::size_t i=0;i<count*2;++i) {
                peak=std::max(peak,std::abs(static_cast<double>(block[i])));
                if (!std::isfinite(block[i]) || std::abs(block[i])>ceiling) throw std::runtime_error("Export exceeds -0.1 dBFS; lower saved levels. Existing output retained.");
            }
            if (first>=seek) output.frames(block.data(),count,first);
        }
        output.commit();
        std::cout << json{{"frames",end-seek},{"sampleRate",48000},{"channels",2},{"bitsPerSample",24},
                          {"peak",peak},{"peakDbFS",peak>0 ? 20*std::log10(peak) : -200},
                          {"eventCount",event_rows.size()},{"decodedBytes",decoded},{"seekFrame",seek}}.dump() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "PRDE1 render failed: " << error.what() << '\n';
        return 1;
    }
}
