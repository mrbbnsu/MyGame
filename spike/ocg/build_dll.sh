#!/usr/bin/env bash
# WO-005 P1 探针构建脚本：把 ygopro-core（含捆绑 Lua）编成 ocgcore.dll
# 工具链：pip install ziglang（zig c++ = clang 前端 + mingw-w64 静态运行时）
# 用法：bash spike/ocg/build_dll.sh
set -e
ROOT=/e/Game
CORE=$ROOT/vendor/repos/ygopro-core
OUT=$ROOT/spike/ocg/out
mkdir -p "$OUT"

cd "$CORE"

# 与 premake5.lua 的 ocgcoreshared 目标保持一致：
#   根目录 *.cpp + RNG/*.hpp（头）+ lua/src/*.c（剔除 premake removefiles 清单，按 C++ 编译）
CPPS=$(ls *.cpp)
LUA_EXCLUDE_RE='(lbitlib|lcorolib|ldblib|linit|loadlib|loslib|ltests|lutf8lib|onelua)\.c$|/(lua|luac)\.c$'
LUACS=$(ls lua/src/*.c | grep -vE "$LUA_EXCLUDE_RE")

python -m ziglang c++ -shared -std=c++17 -O2 -DNDEBUG \
  -DOCGCORE_EXPORT_FUNCTIONS \
  -DWIN32 -D_WIN32 -DNOMINMAX -DUNICODE -D_UNICODE \
  -fno-rtti \
  -I. -Ilua/src -Ilua \
  -include luaconf-customize.h \
  $CPPS -x c++ $LUACS -x none \
  -static-libgcc -static-libstdc++ \
  -o "$OUT/ocgcore.dll"

echo "OK: $OUT/ocgcore.dll"
ls -la "$OUT/ocgcore.dll"
