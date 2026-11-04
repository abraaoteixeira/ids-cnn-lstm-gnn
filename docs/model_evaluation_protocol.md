# Protocolo de Retreinamento e Avaliação Científica do Modelo (SPECTRE-GRID — IEEE/IFIP NOMS 2027)

Este documento estabelece o protocolo metodológico livre de vazamento (*leakage-free*), a justificativa formal do particionamento temporal sobre o dataset **UNSW-NB15** (`700.001` registros, SHA-256 `7d851bbeabd27894ce39c8e78835c73341fc946652fb7743b9eff193b55eb511`), a avaliação cega complementar em **UNSW-NB15_2.csv** (`700.001` registros, SHA-256 `6130ad02873cc6069ae695cf2844f2e8c2e9a9a1b7532dd82ab8f202757cacf8`) e os critérios de validação para a arquitetura híbrida **CNN-1D + LSTM + GATConv**. Os resultados experimentais completos e tabelas multi-seed encontram-se consolidados em [`docs/NOMS2027_METHODOLOGY_AND_RESULTS.md`](NOMS2027_METHODOLOGY_AND_RESULTS.md).

---

## 1. Concentração Temporal dos Ataques nas 700.001 Linhas e Justificativa do Horizonte Ativo de 200.000 Registros

1. **Concentração Temporal dos Ataques em `UNSW-NB15.csv`:**
   Após ordenação cronológica estável (`mergesort`) pela coluna `Stime` (`1421927377` a `1421955842`, cobrindo `28.465 s` / `7,91 h`), a auditoria por decis demonstra que **100% dos `22.215` fluxos de ataque** ocorrem entre a linha ordenada `13` (`Stime = 1421927414`) e a linha ordenada `186.807` (`Stime = 1421934448`, Decis 0 a 2). Todo o intervalo subsequente da linha `186.808` à linha `700.000` (`513.193` registros consecutivos, Decis 3 a 9) contém **exatamente `0` ataques (`Label = 1`)**.
2. **Inviabilidade de Particionamento Cronológico Ingênuo 60%/20%/20% sobre 700.001 Linhas:**
   Sob divisão cronológica estrita ($60\% / 20\% / 20\%$) aplicada às `700.001` linhas brutas, 100% dos ataques caem na partição de treino (`0 .. 420.000`), enquanto as partições de validação (`420.000 .. 560.000`) e teste (`560.000 .. 700.001`) recebem **`0` exemplos positivos**, tornando $\text{Precision}$, $\text{Recall}$ e $\text{F1-Score}$ matematicamente indefinidos ($0/0$).
3. **Definição Formal do Horizonte Ativo (`Active Attack Horizon`, `200.000` registros):**
   O recorte das primeiras `200.000` linhas (`Stime` `1421927377 .. 1421935091`) engloba 100% dos `22.215` ataques da captura e permite um particionamento cronológico $60\% / 20\% / 20\%$ em snapshots discretos $G_t = (V_t, E_t)$ de $\Delta t = 30\text{ s}$ com presença de ataques em todas as partições:
   - **Treino (`0 .. 120.000`):** `152` snapshots, `5.724` nós (`604` atacantes, `5.120` benignos), `19.109` arestas totais (`18.909` entre hosts). Exclusivamente usado para ajuste do vocabulário One-Hot, seleção Top-20 por Pearson e `StandardScaler` ($\mu_{\text{train}}, \sigma_{\text{train}}$).
   - **Validação (`120.000 .. 160.000`):** `48` snapshots, `1.793` nós (`192` atacantes, `1.601` benignos), `6.057` arestas totais (`6.009` entre hosts). Usada para seleção de modelos, ablações e *Early Stopping* sob `--val_only`.
   - **Teste Reservado (`160.000 .. 200.000`):** `56` snapshots, `1.796` nós (`138` atacantes, `1.658` benignos), `6.651` arestas totais (`6.596` entre hosts).
4. **Registro de Transparência sobre Acessos Preliminares ao Teste:**
   O holdout de teste `160k..200k` não é descrito como intocado, pois foi acessado em testes de fumaça unitários e na primeira rodada exploratória de prototipação na seed 42. Para garantir validação rigorosamente cega e não enviesada por hipóteses prévias, os modelos congelados são avaliados em duas frentes independentes:
   - Na **cauda benigna de 500.001 registros** (`linhas 200.000 .. 700.001`, `667` snapshots, `15.900` nós benignos), avaliando estabilidade de FPR sem alarmes falsos (`FPR = 0,00% a 0,89%`);
   - Na **segunda captura independente UNSW-NB15_2.csv** (`linhas 400.000 .. 600.000`, `32.550` ataques reais, `226` snapshots, `8.598` nós), com `refitted_on_external = False`, comprovando a generalização contra *concept drift* (`F1 = 0,8733` para SPECTRE-GRID vs. `0,6773` para baselines sem grafo).

---

## 2. Regras de Isolamento Causal e Prevenção de *Data Leakage*

1. **Snapshots Temporais Causais $G_t = (V_t, E_t)$:** Arestas e sequências temporais por nó ($L=10$) são construídas estritamente dentro de cada janela $[t_0, t_0 + \Delta t)$, sem cruzar fronteiras entre treino, validação e teste.
2. **Rotulagem Direcional Estrita por Origem (`srcip`):** Um nó $v \in V_t$ recebe $y_t(v) = 1$ exclusivamente se originar ao menos um fluxo malicioso (`srcip` com `Label == 1`) na janela $t$. Vítimas passivas (`dstip`) permanecem com $y_t(v) = 0$.
3. **Duas Modalidades de Features:**
   - **Modalidade A (`--feature_scope ebpf_compatible`):** Benchmark offline L3/L4 sem inspeção profunda de pacotes (L7 DPI).
   - **Modalidade B (`--feature_scope ebpf_sensor_strict`):** Sensor eBPF/XDP estritamente unidirecional em *ingress* (compatível 1:1 com `ebpf/spectre_xdp.c` e `derive_features()` em `ebpf/loader_fusion_v2.cpp`).
