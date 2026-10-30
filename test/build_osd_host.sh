#!/bin/sh
# Build the F12 panel (crtemu_osd.cpp + Dear ImGui) as a Linux shared library for test/osd_test.py.
#   sh test/build_osd_host.sh <cnc-ddraw checkout> <out dir>
# Needs clang++ (or g++) and the Mesa EGL/GL libraries; the panel loads GL through ImGui's own loader.
set -e
SRC=${1:-third_party/cnc-ddraw}
OUT=${2:-out/osdhost}
CXX=${CXX:-clang++}
mkdir -p "$OUT"
for f in src/imgui/imgui.cpp src/imgui/imgui_draw.cpp src/imgui/imgui_tables.cpp src/imgui/imgui_widgets.cpp \
         src/imgui/backends/imgui_impl_opengl3.cpp src/crtemu/crtemu_osd.cpp; do
  $CXX -std=c++11 -O1 -g -fPIC -fno-exceptions -fno-rtti -fno-threadsafe-statics -DIMGUI_DISABLE_DEMO_WINDOWS \
       -DCRTEMU_OSD_TEST -I"$SRC/src/imgui" -I"$SRC/inc" -c "$SRC/$f" -o "$OUT/$(basename "$f").o"
done
$CXX -shared -o "$OUT/libosd.so" "$OUT"/*.o -ldl
echo "built $OUT/libosd.so  (run: CRTEMU_OSD_SCALE=2 python test/osd_test.py $OUT/libosd.so <shader.glsl> <bg.png> out.png 2560 1440)"
