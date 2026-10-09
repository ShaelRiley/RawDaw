CXX ?= g++
CXXFLAGS ?= -O2 -std=c++20 -Wall -Wextra -Wpedantic -Werror
PYTHON ?= python3

.PHONY: all check demo cc-demo source-demo clean
all: build/prde1-render

build/prde1-render: native/renderer.cpp native/engine.hpp third_party/nlohmann/json.hpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -Ithird_party native/renderer.cpp -o $@

build/engine-test: native/engine_test.cpp native/engine.hpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) native/engine_test.cpp -o $@

check: all build/engine-test
	./build/engine-test
	$(PYTHON) -m unittest discover -s tests -v

demo: all
	$(PYTHON) tools/build_fixture.py --output out/demo
	$(PYTHON) -m prde1 render out/demo/synthetic.prdepack out/demo/major.prdeproj out/demo/major.wav
	$(PYTHON) -m prde1 render out/demo/synthetic.prdepack out/demo/minor.prdeproj out/demo/minor.wav

cc-demo: source-demo

source-demo: all
	$(PYTHON) tools/render_cc_demos.py

clean:
	rm -rf build out
