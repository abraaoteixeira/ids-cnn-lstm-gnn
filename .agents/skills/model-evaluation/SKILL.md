---
name: model-evaluation
description: Protocolo de avaliação de modelos, estudos de ablação topológica, medição de FPR e análise de generalização sob concept drift no SPECTRE-GRID.
---

# Skill: Model Evaluation

Esta skill define as métricas, procedimentos de teste estatístico e métodos de ablação para avaliar arquiteturas neurais de detecção de intrusão no SPECTRE-GRID.

## Quando Utilizar
- Ao projetar e executar ablações entre variantes (temporal pura, topologia nula, GAT direta, reversa, bidirecional e residual);
- Ao mensurar o impacto da heterofilia e a contaminação de nós receptores;
- Ao reportar taxas de falso alarme (FPR) em tráfego de repouso (cauda benigna);
- Ao testar generalização em capturas subsequentes contendo novos ataques (`UNSW-NB15_2.csv`).

## As 6 Variantes Arquiteturais de Referência
1. `cnn_lstm_pure`: Modelo puramente temporal sem agregação espacial (ignora o grafo topológico e avalia cada nó individualmente com CNN-1D + LSTM).
2. `gat_self_loop`: Baseline com camada GAT, porém restringindo o grafo exclusivamente a auto-loops $(i \to i)$. Demonstra que a presença de parâmetros de atenção sem topologia real não melhora a generalização.
3. `cnn_lstm_gat`: Modelo híbrido com agregação direcionada padrão no sentido do fluxo ($u \to v$, do emissor para o receptor).
4. `gat_reverse`: Modelo com inversão da direção das arestas ($v \to u$, a vítima envia mensagem para o atacante).
5. `gat_bidir`: Modelo com arestas bidirecionais ($u \leftrightarrow v$).
6. `gat_residual`: Modelo com conexão residual com gating ($\mathbf{h}'_v = \mathbf{h}_v + \text{GAT}(\mathbf{h}_v, \mathcal{N}(v))$).

## Métricas Obrigatórias de Avaliação
- **Accuracy:** Taxa global de acerto.
- **Precision:** $\frac{TP}{TP + FP}$ (foco em evitar penalizar nós legítimos com falsos alarmes).
- **Recall (Sensibilidade):** $\frac{TP}{TP + FN}$ (foco em não deixar nós maliciosos passarem).
- **F1-Score:** Média harmônica entre Precisão e Recall (métrica principal de ranking).
- **FPR (False Positive Rate):** $\frac{FP}{FP + TN}$ (taxa crítica em sistemas de prevenção IPS).
- **Matriz de Confusão Completa:** Exibição explícita de `TN, FP, FN, TP`.

## Análise de Heterofilia de Arestas
Em redes de computadores, a maioria dos ataques é heterofílica ($1 \to 0$, atacante enviando para vítima).
- Uma camada GAT padrão sem conexão residual ou modulação de aresta propaga a representação latente do atacante para a vítima, provocando elevação do FPR em alvos legítimos ("contaminação de vítimas").
- A skill exige que todo relatório de ablação quantifique a distribuição de arestas entre classes ($0 \to 0, 1 \to 0, 0 \to 1, 1 \to 1$) e o FPR segmentado em nós alvejados vs. não-alvejados.

## Protocolo de Generalização sob Concept Drift
Ao avaliar modelos em novas capturas (ex.: `UNSW-NB15_2.csv`):
1. **Zero Reajuste:** Nunca recalcular média/desvio do scaler ou refazer vocabulário (`refitted_on_external = False`).
2. **Horizonte de Ataque Ativo:** Documentar e justificar a seleção de fatias temporais contendo campanhas ativas.
3. **Avaliação Pareada:** Reportar sempre a baseline sem grafo lado a lado com o SPECTRE-GRID para demonstrar ganho relativo de transferência de domínio.
