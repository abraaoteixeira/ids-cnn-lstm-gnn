cmake_minimum_required(VERSION 3.0 FATAL_ERROR)
project(spectre-grid-native)

find_package(Torch REQUIRED)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${TORCH_CXX_FLAGS}")

# 1. Inference Engine (LibTorch)
add_executable(spectre_inference main.cpp)
target_link_libraries(spectre_inference "${TORCH_LIBRARIES}" dl)
set_property(TARGET spectre_inference PROPERTY CXX_STANDARD 17)

# 2. Kernel eBPF/XDP Object
add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/spectre_xdp.o
    COMMAND clang -g -O2 -target bpf -I/usr/include/x86_64-linux-gnu -I${CMAKE_CURRENT_SOURCE_DIR}/ebpf -D__TARGET_ARCH_x86 -c ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/spectre_xdp.c -o ${CMAKE_CURRENT_BINARY_DIR}/spectre_xdp.o
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/spectre_xdp.c ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/common.h
    COMMENT "Compilando Bytecode do Kernel (eBPF)"
)
add_custom_target(ebpf_obj ALL DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/spectre_xdp.o)

# 3. User Space XDP Loader / Integrator
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBBPF REQUIRED libbpf)

add_executable(spectre_ebpf_loader ebpf/loader.cpp)
target_link_libraries(spectre_ebpf_loader ${LIBBPF_LIBRARIES} elf z)
target_include_directories(spectre_ebpf_loader PRIVATE ${LIBBPF_INCLUDE_DIRS} ebpf)
set_property(TARGET spectre_ebpf_loader PROPERTY CXX_STANDARD 17)
add_dependencies(spectre_ebpf_loader ebpf_obj)

# 4. FASE 3: FUSION ENGINE (LibTorch + eBPF)
add_executable(spectre_fusion ebpf/loader_fusion.cpp)
target_link_libraries(spectre_fusion "${TORCH_LIBRARIES}" ${LIBBPF_LIBRARIES} elf z dl)
target_include_directories(spectre_fusion PRIVATE ${LIBBPF_INCLUDE_DIRS} ebpf)
set_property(TARGET spectre_fusion PROPERTY CXX_STANDARD 17)
add_dependencies(spectre_fusion ebpf_obj)

# 5. FASE 3: BENCHMARK
add_executable(spectre_benchmark test_performance_fusion.cpp)
target_link_libraries(spectre_benchmark "${TORCH_LIBRARIES}" dl)
set_property(TARGET spectre_benchmark PROPERTY CXX_STANDARD 17)
