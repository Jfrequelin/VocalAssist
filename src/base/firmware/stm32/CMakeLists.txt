cmake_minimum_required(VERSION 3.20)
project(edge_base_stm32 C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

option(EDGE_BUILD_EXAMPLE "Build runtime example binary" ON)
set(EDGE_TARGET_ARCH "host" CACHE STRING "Target architecture: host or stm32")
set_property(CACHE EDGE_TARGET_ARCH PROPERTY STRINGS host stm32)

add_library(edge_base_core STATIC
    src/base_runtime.c
)

target_include_directories(edge_base_core
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_options(edge_base_core
    PRIVATE
        -Wall
        -Wextra
        -Wpedantic
)

if(EDGE_TARGET_ARCH STREQUAL "stm32")
    if(NOT DEFINED STM32_MCPU)
        set(STM32_MCPU cortex-m4)
    endif()

    target_compile_definitions(edge_base_core PRIVATE EDGE_TARGET_STM32=1)
    target_compile_options(edge_base_core PRIVATE
        -mcpu=${STM32_MCPU}
        -mthumb
        -ffreestanding
        -fno-builtin
    )
    target_link_options(edge_base_core INTERFACE
        -mcpu=${STM32_MCPU}
        -mthumb
    )
endif()

if(EDGE_BUILD_EXAMPLE)
    add_executable(edge_base_example
        src/main_example.c
    )
    target_link_libraries(edge_base_example PRIVATE edge_base_core)

    if(EDGE_TARGET_ARCH STREQUAL "stm32")
        target_compile_options(edge_base_example PRIVATE
            -mcpu=${STM32_MCPU}
            -mthumb
            -ffreestanding
            -fno-builtin
        )
        target_link_options(edge_base_example PRIVATE
            -mcpu=${STM32_MCPU}
            -mthumb
        )
    endif()
endif()
