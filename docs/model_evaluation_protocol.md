# Protocolo de Retreinamento e Avaliação Científica do Modelo (SPECTRE-GRID — IEEE/IFIP NOMS 2027)

Este documento estabelece o protocolo metodológico livre de vazamento (*leakage-free*), a justificativa formal do particionamento temporal sobre o dataset **UNSW-NB15** (`700.001` registros, SHA-256 `7d851bbeabd27894ce39c8e78835c73341fc946652fb7743b9eff193b55eb511`) e os critérios de validação para a arquitetura híbrida **CNN-1D + LSTM + GATConv**. Os resultados experimentais completos e tabelas multi-seed encontram-se consolidados em [`docs/NOMS2027_METHODOLOGY_AND_RESULTS.md`](NOMS2027_METHODOLOGY_AND_RESULTS.md).

---

## 1. Concentração Temporal dos Ataques nas 700.001 Linhas e Justificativa do Horizonte Ativo de 200.000 Registros

1. **Concentração Temporal dos Ataques em `UNSW-NB15.csv`:**
   Após ordenação cronológica estável (`mergesort`) pela coluna `Stime` (`1421927377` a `1421955842`, cobrindo `28.465 s` / `7,91 h`), a auditoria por decis demonstra que **100% dos `22.215` fluxos de ataque** ocorrem entre a linha ordenada `13` (`Stime = 1421927414`) e a linha ordenada `186.807` (`Stime = 1421934448`, Decis 0 a 2). Todo o intervalo subsequente da linha `186.808` à linha `700.000` (`513.193` registros consecutivos, Decis 3 a 9) contém **exatamente `0` ataques (`Label = 1`)**.
2. **Inviabilidade de Particionamento Cronológico Ingênuo 60%/20%/20% sobre 700.001 Linhas:**
   Sob divisão cronológica estrita ($60\% / 20\% / 20\%$) aplicada às `700.001` linhas brutas, 100% dos ataques caem na partição de treino (`0 .. 420.000`), enquanto as partições de validação (`420.000 .. 560.000`) e teste (`560.000 .. 700.001`) recebem **`0` exemplos positivos**, tornando $\text{Precision}$, $\text{Recall}$ e $\text{F1-Score}$ matematicamente indefinidos ($0/0$).
3. **Definição Formal do Horizonte Ativo (`Active Attack Horizon`, `200.000` registros):**
   O recorte das primeiras `200.000` linhas ordenadas (`Stime` `1421927377 .. 1421934925`) engloba 100% dos `22.215` ataques da captura e permite um particionamento cronológico $60\% / 20\% / 20\%$ em snapshots discretos $G_t = (V_t, E_t)$ de $\Delta t = 30\text{ s}$ com presença balanceada de ataques em todas as partições:
   - **Treino (`0 .. 120.000`):** `156` snapshots, `5.910` nós (`749` atacantes, `5.161` benignos), `13.805` fluxos maliciosos. Exclusivamente usado para ajuste do vocabulário One-Hot, seleção Top-20 por Pearson e `StandardScaler` ($\mu_{\text{train}}, \sigma_{\text{train}}$).
   - **Validação (`120.000 .. 160.000`):** `48` snapshots, `1.793` nós (`192` atacantes, `1.601` benignos), `6.120` fluxos maliciosos. Usada para seleção de modelos, ablações e *Early Stopping* sob `--val_only`.
   - **Teste Reservado (`160.000 .. 200.000`):** `69` snapshots, `2.388` nós (`134` atacantes, `2.254` benignos), `2.290` fluxos maliciosos. Mantido bloqueado durante a escolha arquitetural (`--val_only`).
4. **Validação Independente Obrigatória no Período Benigno Pós-Campanha (`500.001` registros, `200.000 .. 700.001`):**
   Para garantir que o treinamento no horizonte ativo de `200.000` linhas não eleve a taxa de falsos alarmes em operação normal, os modelos congelados são obrigatoriamente avaliados nas **`500.001` linhas benignas subsequentes (`linhas 200.000 .. 700.001`, `667` snapshots de `30 s`, `15.900` nós benignos)**. Essa cauda externa é transformada usando **estritamente** o `StandardScaler`, o vocabulário One-Hot e as `top_features` ajustados no treino (`0 .. 120.000`), sem reajuste (`refitted_on_external = False`). Os resultados empíricos confirmam FPR operacional entre **`0,000%` e `0,893%`** (`0,214%` para `cnn_lstm_gat` e `0,044%` para `cnn_lstm_pure`).

---

## 2. Regras de Isolamento Causal e Prevenção de *Data Leakage*

1. **Snapshots Temporais Causais $G_t = (V_t, E_t)$:** Arestas e sequências temporais por nó ($L=10$) são construídas estritamente dentro de cada janela $[t_0, t_0 + \Delta t)$, sem cruzar fronteiras entre treino, validação e teste.
2. **Rotulagem Direcional Estrita por Origem (`srcip`):** Um nó $v \in V_t$ recebe $y_t(v) = 1$ exclusivamente se originar ao menos um fluxo malicioso (`srcip` com `Label == 1`) na janela $t$. Vítimas passivas (`dstip`) permanecem com $y_t(v) = 0$.
3. **Duas Modalidades de Features:**
   - **Modalidade A (`--feature_scope ebpf_compatible`):** Benchmark offline L3/L4 sem inspeção profunda de pacotes (L7 DPI).
   - **Modalidade B (`--feature_scope ebpf_sensor_strict`):** Sensor eBPF/XDP estritamente unidirecional em *ingress* (compatível 1:1 com `ebpf/spectre_xdp.c` e `derive_features()` em `ebpf/loader_fusion_v2.cpp`).
