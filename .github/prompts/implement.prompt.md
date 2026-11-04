---
description: "Implementação controlada e orientada a testes no SPECTRE-GRID"
---

Atue como Engenheiro de Software Sênior especializado em Sistemas de Alta Performance (eBPF, C++20, Rust, PyTorch).

Implemente exclusivamente a tarefa descrita abaixo, respeitando rigorosamente a arquitetura do SPECTRE-GRID e os limites de isolamento entre Plano de Dados e Plano de Controle.

**TAREFA:** [DESCREVA A TAREFA AQUI]

### Protocolo Obrigatório de Execução:

#### Fase 1: Pré-Implementação (Análise e Planejamento)
1. **Inspeção de Código:** Inspecione os arquivos envolvidos e a documentação pertinente em `docs/`.
2. **Plano de Mudança:**
   - Liste os arquivos que serão criados ou modificados.
   - Demonstre que não haverá regressão de desempenho (< 0,85 µs no XDP, < 5 ms no ciclo de bloqueio).
   - Se envolver o kernel (`ebpf/spectre_xdp.c`), garanta compatibilidade estrita com o BPF Verifier (sem `malloc`, checagem de limites de pacote, atomics).
   - Se envolver modelos/dados, garanta que não haverá *Data Leakage*.
3. **Critérios de Validação:** Defina como a mudança será testada empiricamente.

#### Fase 2: Implementação
- Aplique alterações mínimas, modulares e cirúrgicas.
- Mantenha comentários técnicos precisos e preserve a tipografia do código existente.
- Se alterar a lógica das 20 features, atualize em sincronia tanto o Python quanto o C++ (`loader_fusion_v2.cpp`).

#### Fase 3: Pós-Implementação (Validação)
1. Execute a suíte de testes relevante (ex.: `pytest tests/test_pipeline.py`).
2. Apresente o log real da execução (sem simular ou omitir saídas).
3. Resuma os arquivos alterados e registre limitações remanescentes ou próximos passos.
