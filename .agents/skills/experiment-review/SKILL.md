---
name: experiment-review
description: Protocolo de revisão por pares e auditoria de lotes experimentais antes da incorporação em manuscritos, teses ou relatórios do SPECTRE-GRID.
---

# Skill: Experiment Review

Esta skill estabelece o protocolo formal de auditoria técnica e revisão por pares de baterias de experimentos neurais antes de quaisquer dados serem considerados definitivos ou inseridos em artigos científicos e relatórios acadêmicos.

## Quando Utilizar
- Antes de consolidar tabelas de resultados para artigos (IEEE NOMS, periódicos, TCC);
- Ao concluir rodadas de treinamento multi-seed (Dell G15 ou Google Colab Pro);
- Ao receber novas capturas ou bundles de avaliação externa (ex.: UNSW-NB15_2);
- Sempre que houver divergência entre métricas de ambientes distintos.

## Checklist de Revisão Experimental (6 Portões de Aceite)

### 1. Portão de Identificação e Rastreabilidade
- [ ] O hash SHA-256 do dataset bruto e do bundle de snapshots está documentado no manifesto JSON?
- [ ] O commit Git exato do código de treinamento foi registrado no log de execução?
- [ ] O hardware (GPU, vRAM, arquitetura GA107/TU104), versão de driver e runtime CUDA/PyTorch foram anotados?
- [ ] O script de execução preservou os argumentos (`--epochs`, `--batch_size`, `--lr`, `--window_size`, `--feature_set`, `--seed`)?

### 2. Portão de Isolamento Temporal e Ausência de Vazamento
- [ ] A ordenação cronológica (`mergesort` em `Stime`) foi respeitada rigorosamente?
- [ ] O normalizador `StandardScaler` e a matriz de Pearson foram ajustados **exclusivamente** na partição de treino (`refitted_on_external = False` em testes externos)?
- [ ] Os snapshots de validação e teste não compartilham transições temporais ou janelas sobrepostas com o treino?
- [ ] O modo `--val_only` esteve ativado durante toda a fase de seleção de hiperparâmetros e topologias?

### 3. Portão de Consistência Aritmética
- [ ] A matriz de confusão confere com os totais de nós?
  $$ \text{Total} = TN + FP + FN + TP $$
- [ ] As métricas derivadas estão matematicamente corretas:
  $$ \text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN} $$
  $$ \text{F1} = \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}, \quad \text{FPR} = \frac{FP}{FP + TN} $$
- [ ] A taxa de falsos positivos (FPR) foi calculada sobre o universo real de benignos ($FP + TN$), e não sobre o total geral de amostras?

### 4. Portão de Avaliação Estrutural e Topológica
- [ ] Foi verificado o impacto da direção de message passing na topologia (Pure, Self-loop, Forward, Reverse, Bidirectional, Residual)?
- [ ] As métricas de vítimas benignas foram separadas das métricas de atacantes para auditar a contaminação por vizinhança (heterofilia)?
- [ ] O conjunto de features empregado é estritamente aderente ao conjunto `ebpf_compatible` (20 atributos)?

### 5. Portão de Reprodutibilidade Multi-Seed e Cross-Hardware
- [ ] Foram executadas pelo menos 3 sementes independentes (ex.: 42, 123, 1337) antes de afirmar superioridade de uma arquitetura?
- [ ] A média e desvio-padrão ($\mu \pm \sigma$) foram reportados em vez de selecionar apenas a melhor semente (cherry-picking)?
- [ ] A divergência cross-hardware (ex.: Ampere RTX 3050 vs Turing Tesla T4) está dentro da margem de não-determinismo esperada para operações atômicas em ponto flutuante ($\Delta \text{F1} \le 0.015$)?
- [ ] O ranking relativo das arquiteturas permaneceu 100% invariante entre os ambientes?

### 6. Portão de Generalização e Cauda Benigna
- [ ] Se o teste foi realizado em períodos com 100% de tráfego benigno, o resultado foi reportado exclusivamente como auditoria de FPR (estabilidade operacional), sem alegar "detecção de novos ataques"?
- [ ] Para aferir robustez contra concept drift, foi realizada avaliação em captura independente contendo ataques (ex.: UNSW-NB15_2) com normalizador estritamente congelado?

## Critérios de Rejeição Imediata
1. **Normalizador Reajustado em Teste:** Qualquer script que execute `scaler.fit()` ou `scaler.fit_transform()` fora da partição de treino torna o experimento nulo.
2. **Cherry-Picking de Semente:** Publicar apenas a semente de pico sem reportar o desvio e as demais sementes executadas.
3. **Holdout Contaminado:** Selecionar o melhor modelo com base nas métricas do conjunto de teste reservado.
