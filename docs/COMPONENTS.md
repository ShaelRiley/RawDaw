# Component manifest

| Component | Version / distribution | License / state |
| --- | --- | --- |
| PRDE1 application code and authored synthetic fixtures | 0.2.0 source / compiled Linux renderer | MIT, `LICENSE` |
| Three prepared Song Packs and source-derived estimated drum MIDI | Curated CC stem profile 0.2.0; 69 assets | CC BY 3.0; source credits/license/change notices embedded and listed in `SONG_PACKS.md` |
| nlohmann/json | 3.12.0 vendored single header | MIT; original license/embedded notices retained |
| Python | System interpreter 3.11+; tested with 3.12.14 | PSF terms; not bundled |
| GNU compiler / libstdc++ / libgcc / glibc | System g++ 13 / Ubuntu 24.04 libraries | Compiler and system runtime terms/exceptions apply; libraries not bundled |
| FFmpeg and ffprobe with Rubber Band filter | System 6.1.1-3ubuntu5 | GPL-enabled system build; preparation-only, no binaries bundled |
| Rubber Band | System FFmpeg filter dependency | GPL/commercial library; preparation-only, not bundled with PRDE1 |
| NumPy | 2.3.5 | BSD; optional preparation dependency, not bundled/imported by runtime |
| SciPy | 1.17.0 | BSD; optional preparation dependency, not bundled/imported by runtime |
| Qt6/PySide6 | Shortlisted for desktop slice | LGPL/commercial module obligations; not bundled/implemented |
| PortAudio | Shortlisted for device I/O | MIT; not bundled/implemented |
| Steinberg VST3 SDK | Future native hosting dependency | Official SDK license reviewed as MIT; not yet vendored |

Pinned vendored artifacts:

```text
third_party/nlohmann/json.hpp
SHA256 aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63
third_party/nlohmann/LICENSE.MIT
SHA256 46a65cffd1ea955132d95a8dd921640714a8d6b537d2e4e482d31145ae95b603
```

Prepared media does not contain the original complete mixes/stems. No plug-ins,
models, fonts or external MIDI collections are bundled. Source recordings were
licensed on their primary upload pages; the estimated source drum MIDI is
labeled as a transcription, not artist-original data. MIT application licensing
does not relicense dependencies or content.

Primary references:

* https://github.com/nlohmann/json/tree/v3.12.0
* https://docs.python.org/3/license.html
* https://ffmpeg.org/legal.html
* https://breakfastquay.com/rubberband/licence.html
* https://numpy.org/doc/stable/license.html
* https://scipy.org/about/
* https://creativecommons.org/licenses/by/3.0/
* https://doc.qt.io/qtforpython-6/commercial/index.html
* https://portaudio.com/license.html
* https://steinbergmedia.github.io/vst3_dev_portal/pages/VST%2B3%2BLicensing/VST3%2BLicense.html
