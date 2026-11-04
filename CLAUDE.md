# CLAUDE.md — SPECTRE-GRID Project Guidelines

> **Princípio Central Inegociável:**  
> *"Nenhuma afirmação científica sem evidência rastreável; nenhuma alteração crítica sem validação; nenhum resultado definitivo sem revisão independente."*

Este repositório possui uma constituição permanente em **`AGENTS.md`**, detalhada em `docs/SCIENTIFIC_MEMORY.md` e operacionalizada pelas skills em `.agents/skills/`.

Ao operar com o Claude Code ou Claude CLI neste projeto, você **DEVE** seguir rigorosamente:

1. **Constituição Obrigatória:** Leia e adote todas as diretrizes em [`AGENTS.md`](./AGENTS.md).
2. **Branch de Trabalho:** Trabalhe exclusivamente na branch ativa (atualmente `fix/leakage-free-pipeline`). A branch `main` é estritamente protegida.
3. **Prevenção de Data Leakage:**
   - Nunca ajuste scalers ou Pearson fora da partição de treino (`refitted_on_external = False`).
   - Mantenha ordenação cronológica estrita por `Stime` (`mergesort`).
   - Rótulos de ataque pertencem exclusivamente ao nó de origem ($src$).
   - O modo `--val_only` é mandatório em qualquer fase exploratória.
4. **Skills Especializadas:**
   - `.agents/skills/scientific-integrity/SKILL.md`
   - `.agents/skills/dataset-leakage-audit/SKILL.md`
   - `.agents/skills/reproducible-training/SKILL.md`
   - `.agents/skills/ebpf-feature-parity/SKILL.md`
   - `.agents/skills/model-evaluation/SKILL.md`
   - `.agents/skills/ieee-paper-writing/SKILL.md`
   - `.agents/skills/experiment-review/SKILL.md`
5. **Decisões Arquiteturais e Memória:** Consulte sempre `docs/SCIENTIFIC_MEMORY.md` antes de propor alterações metodológicas.
