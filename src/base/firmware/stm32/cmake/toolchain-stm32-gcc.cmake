set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(CMAKE_C_COMPILER arm-none-eabi-gcc)
set(CMAKE_CXX_COMPILER arm-none-eabi-g++)
set(CMAKE_ASM_COMPILER arm-none-eabi-gcc)

set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

if(NOT DEFINED STM32_MCPU)
    set(STM32_MCPU cortex-m4)
endif()

set(CMAKE_C_FLAGS_INIT "-mcpu=${STM32_MCPU} -mthumb")
set(CMAKE_EXE_LINKER_FLAGS_INIT "-mcpu=${STM32_MCPU} -mthumb")
