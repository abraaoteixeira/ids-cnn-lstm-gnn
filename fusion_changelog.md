# SPECTRE-GRID: Changelog de Fusão (Fase 3)

## Objetivo
Documentar a transição da **Fase 2 (Componentes Isolados)** para a **Fase 3 (Fusão C++)**, onde o motor de Inteligência Artificial (LibTorch) se unirá ao interceptador de rede (eBPF) para habilitar o bloqueio autônomo e de baixa latência (XDP_DROP).

## Política de Safe Deploy
Para garantir total segurança e capacidade de *rollback* em caso de falha na compilação ou instabilidade de hardware, aplicamos a seguinte restrição:
- O arquivo original do motor de inteligência (`main.cpp`) permanecerá intocado.
- O arquivo original do orquestrador eBPF (`ebpf/loader.cpp`) permanecerá intocado.

Toda a nova arquitetura de fusão será construída em um novo arquivo independente: `ebpf/loader_fusion.cpp`.

## Modificações Adicionais
- **Build System**: O `CMakeLists.txt` foi atualizado para compilar o novo *target* `spectre_fusion`, realizando o *linking* duplo das bibliotecas `libbpf` e `LibTorch`.
- **Benchmarking**: Foi introduzido o módulo de teste isolado `test_performance_fusion.cpp` para aferição de latência real sob carga simulada de 10.000 iterações.
