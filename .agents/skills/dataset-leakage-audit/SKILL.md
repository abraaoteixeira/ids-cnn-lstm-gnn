---
name: dataset-leakage-audit
description: Auditoria exaustiva e prevenção contra data leakage temporal, vazamento de normalizadores, contaminação de holdout e arestas sintéticas no SPECTRE-GRID.
---

# Skill: Dataset Leakage Audit

Esta skill estabelece o protocolo de auditoria e testes de regressão contra as 5 formas clássicas de *data leakage* em detecção de intrusão com grafos espaço-temporais.

## Quando Utilizar
- Ao adicionar ou reprocessar qualquer dataset (ex.: UNSW-NB15, CIC-IDS2017, capturas de honeypot);
- Ao modificar `preprocessor.py`, `train.py` ou a geração de `DataLoader`;
- Ao avaliar um modelo sobre dados externos ou novas partições temporais;
- Antes de consolidar tabelas experimentais para publicações.

## As 5 Formas de Data Leakage Auditadas no SPECTRE-GRID

### 1. Vazamento por Embaralhamento Temporal (*Temporal Shuffle Leakage*)
- **Risco:** Misturar pacotes de épocas futuras com o treino via `train_test_split(shuffle=True)`.
- **Regra Verificada:** Ordenação estritamente cronológica por `Stime` (`mergesort`) antes da divisão $60\% / 20\% / 20\%$. Jamais aplicar amostragem aleatória uniforme.

### 2. Vazamento de Parâmetros de Normalização e Seleção (*Preprocessor Fitting Leakage*)
- **Risco:** Executar `scaler.fit()`, `OneHotEncoder.fit()` ou cálculo de correlação de Pearson na base inteira.
- **Regra Verificada:** `fit_feature_scaler()`, `select_topk_pearson()` e o vocabulário de One-Hot são ajustados **exclusivamente** na partição de treino (`0 .. 120.000`). Em validação, teste ou cauda externa, utiliza-se apenas `scaler.transform()` com os vetores congelados `scaler_mean` e `scaler_scale` (`refitted_on_external = False`).

### 3. Vazamento de Fronteira em Snapshots (*Cross-Window Temporal Leakage*)
- **Risco:** Sequências temporais $L=10$ por nó agregando pacotes ocorridos após o fechamento da janela $[t, t + \Delta t)$ ou cruzando a fronteira de treino/validação/teste.
- **Regra Verificada:** Snapshots são indexados por `window_id = floor((t - t_min) / window_sec)` isolados dentro de cada partição. Snapshots com $\Delta t \le 0$ ou vazios são descartados com segurança.

### 4. Vazamento Topológico por Arestas Sintéticas (*Synthetic Graph Leakage*)
- **Risco:** Ligar linhas consecutivas de um arquivo CSV através de arestas artificiais $(i \to i+1)$, criando dependências topológicas inexistentes na rede física.
- **Regra Verificada:** Arestas direcionadas existem se, e somente se, houve comunicação real observada entre $IP_{\text{src}}$ e $IP_{\text{dst}}$ dentro da janela. Se não houver dados de IP, gera-se apenas auto-loops $(i \to i)$ para baselines tabulares.

### 5. Vazamento Causal de Rótulo de Nós (*Node Labeling Leakage*)
- **Risco:** Rotular um host vítima como atacante ($y=1$) pelo simples fato de receber tráfego malicioso.
- **Regra Verificada:** Apenas o emissor do fluxo (`srcip`) recebe $y_t(v) = 1$ quando emite ataque. Vítimas passivas (`dstip`) recebem $y_t(v) = 0$.

## Procedimento de Verificação Automatizada (Teste de Regressão)
Antes de aceitar qualquer modificação no pipeline, execute obrigatoriamente a suíte de testes de regressão:
```bash
pytest tests/test_leakage_free_pipeline.py tests/test_scientific_governance.py -v
```

### O que os testes verificam:
1. `test_scaler_fitted_on_train_only`: Garante que `scaler.mean_` reflete apenas a média de treino e que a aplicação no teste não altera os parâmetros.
2. `test_strict_temporal_isolation`: Garante que $\max(\text{train.Stime}) \le \min(\text{val.Stime})$ e $\max(\text{val.Stime}) \le \min(\text{test.Stime})$.
3. `test_directional_node_labeling`: Garante que um nó receptor passivo não recebe rótulo 1.
4. `test_no_cross_host_synthetic_edges`: Garante que o grafo topológico contém apenas arestas entre IPs comunicantes reais.
5. `test_frozen_external_evaluation_flag`: Garante que avaliações em datasets externos possuem `refitted_on_external == False`.

## Critérios de Aprovação
- Score de auditoria: **100% de testes aprovados (PASS)**;
- Zero avisos de `InconsistentVersionWarning` não documentados;
- Confirmação de que o conjunto de teste de holdout não foi consultado durante a calibração de hiperparâmetros (`held_out_test_metrics: null` em relatórios exploratórios).
