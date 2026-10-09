# Component manifest

| Component | Version / distribution | License / state |
| --- | --- | --- |
| PRDE1 application code and authored synthetic fixtures | 0.1.0 source checkpoint | MIT, `LICENSE` |
| nlohmann/json | 3.12.0 vendored single header | MIT; original license/embedded notices retained |
| Python | 3.11+ interpreter supplied by system; tested with 3.12.14 | PSF terms; not bundled |
| C++ standard library/compiler | System toolchain; tested with GNU g++ 13 | Toolchain terms; not bundled as a runtime package |
| Qt6/PySide6 | Shortlisted for next desktop slice | LGPL/commercial module obligations verified; not bundled/implemented |
| PortAudio | Shortlisted for device I/O | MIT; not bundled/implemented |
| Steinberg VST3 SDK | Future native hosting dependency | Current official SDK licensing verified as MIT; SDK not yet vendored |

Pinned vendored artifacts:

```text
third_party/nlohmann/json.hpp
SHA256 aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63
third_party/nlohmann/LICENSE.MIT
SHA256 46a65cffd1ea955132d95a8dd921640714a8d6b537d2e4e482d31145ae95b603
```

Source: https://github.com/nlohmann/json/tree/v3.12.0

Reviewed official documentation:

* https://json.nlohmann.me/home/releases/
* https://github.com/nlohmann/json/blob/v3.12.0/LICENSE.MIT
* https://docs.python.org/3/license.html
* https://doc.qt.io/qtforpython-6/commercial/index.html
* https://www.qt.io/development/open-source-lgpl-obligations
* https://portaudio.com/license.html
* https://portaudio.com/docs/v19-doxydocs/writing_a_callback.html
* https://steinbergmedia.github.io/vst3_dev_portal/pages/VST%2B3%2BLicensing/VST3%2BLicense.html

No plug-ins, models, fonts, source recordings or third-party MIDI collections are
bundled. The authored synthetic bank is a development fixture, not the authorized
source-derived demonstration pack required for release. MIT application licensing
does not relicense any future dependency or imported content.
