# Build firmware base pour STM32

Note: le message utilisateur mentionne "st32"; ce guide cible STM32.

## Prerequis

- CMake >= 3.20
- GCC ARM Embedded dans le PATH (`arm-none-eabi-gcc`)

## Build host (verification rapide)

```bash
cmake -S src/base/firmware/stm32 -B build/stm32-host -DEDGE_TARGET_ARCH=host
cmake --build build/stm32-host -j
./build/stm32-host/edge_base_example
```

## Build cross-compile STM32

```bash
cmake -S src/base/firmware/stm32 \
  -B build/stm32 \
  -DCMAKE_TOOLCHAIN_FILE=src/base/firmware/stm32/cmake/toolchain-stm32-gcc.cmake \
  -DEDGE_TARGET_ARCH=stm32 \
  -DSTM32_MCPU=cortex-m4

cmake --build build/stm32 -j
```

Pour un autre MCU, changer `STM32_MCPU` (ex: `cortex-m7`, `cortex-m33`).

## Integration avec STM32CubeIDE

- Importer `edge_base_core` (fichiers de `include/` et `src/`) dans le projet CubeIDE.
- Garder la meme API C (`base_runtime_init`, `base_runtime_set_mute`, `base_runtime_process_transcript`).
- Connecter la capture micro, le transport reseau et le playback autour de cette API.

## Fichiers cles

- `src/base/firmware/stm32/include/base_runtime.h`
- `src/base/firmware/stm32/src/base_runtime.c`
- `src/base/firmware/stm32/CMakeLists.txt`
- `src/base/firmware/stm32/cmake/toolchain-stm32-gcc.cmake`
