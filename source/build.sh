#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
SC4_LLVM_ROOT="${SC4_LLVM_ROOT:-/tmp/llvm-mingw}"
mkdir -p build/debug
for variant in release debug; do
  debug_flag=0
  output_dir=build
  if [[ "$variant" == debug ]]; then debug_flag=1; output_dir=build/debug; fi
  "$SC4_LLVM_ROOT/bin/clang" --target=i686-pc-windows-msvc -std=c++17 -ffreestanding -fno-exceptions -fno-rtti -fno-threadsafe-statics -fno-stack-protector -fno-builtin -O2 -Wall -Wextra -Werror -Wno-ignored-qualifiers -Wno-unused-private-field -DSC4_SPEEDING_DEBUG="$debug_flag" -Iinclude -Ishim -Isdk -c plugin.cpp -o "build/plugin-$variant.obj"
  "$SC4_LLVM_ROOT/bin/lld-link" /dll /machine:x86 /entry:DllMain@12 /nodefaultlib /safeseh:no /out:"$output_dir/SC4Speeding.dll" "build/plugin-$variant.obj" "$SC4_LLVM_ROOT/i686-w64-mingw32/lib/libkernel32.a" "$SC4_LLVM_ROOT/i686-w64-mingw32/lib/libuser32.a"
done
