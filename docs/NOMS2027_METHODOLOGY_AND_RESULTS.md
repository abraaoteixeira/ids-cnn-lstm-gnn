# SPECTRE-GRID — Metodologia Experimental Formal e Resultados Consolidados (IEEE/IFIP NOMS 2027)

**Repositório:** `abraaoteixeira/ids-cnn-lstm-gnn`  
**Branch Científica:** `fix/leakage-free-pipeline`  
**Checksum SHA-256 do Dataset (`UNSW-NB15.csv`):** `7d851bbeabd27894ce39c8e78835c73341fc946652fb7743b9eff193b55eb511`  
**Ambientes de Execução:**
- **Dell G15 (Local/Tailscale):** NVIDIA GeForce RTX 3050 6 GB Laptop GPU, Python 3.11.9, PyTorch `2.5.1+cu121`, PyG `2.6.1`.
- **Google Colab Pro (Cloud GPU):** NVIDIA Tesla T4 (`14.56 GiB` VRAM), Python 3.13.16, PyTorch `2.11.0+cu130`, PyG `2.8.1`.

---

## 1. Metodologia do Artigo: Particionamento Cronológico, Horizonte Ativo (200k) e Validação Externa na Cauda Benigna (500k)

### 1.1. Auditoria Cronológica e Concentração Temporal dos Ataques em `UNSW-NB15.csv` (700.001 Registros)

Uma auditoria exaustiva sobre a totalidade dos `700.001` registros do arquivo original `UNSW-NB15.csv` (`UNSW-NB15_1`, `168.979.718` bytes, ordenado de forma estável `mergesort` por `Stime`) revelou uma assimetria estrutural crítica na distribuição temporal dos ataques ao longo das `7,91 horas` (`28.465 segundos`, de `Stime = 1421927377` a `1421955842`, com apenas 1 intervalo $> 60\text{ s}$ de `859 s` no decil 6):

| Decil | Intervalo de Linhas Ordenadas | Registros | `Stime` Inicial | `Stime` Final | Ataques (`Label = 1`) | Taxa de Ataque (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0** | `0 .. 70.000` | 70.000 | `1421927377` | `1421930202` | 4.948 | 7,07% |
| **1** | `70.000 .. 140.000` | 70.000 | `1421930202` | `1421932604` | 12.510 | 17,87% |
| **2** | `140.000 .. 210.000` | 70.000 | `1421932604` | `1421935434` | 4.757 | 6,80% |
| **3** | `210.000 .. 280.000` | 70.000 | `1421935434` | `1421938628` | **0** | **0,00%** |
| **4** | `280.000 .. 350.000` | 70.000 | `1421938628` | `1421941918` | **0** | **0,00%** |
| **5** | `350.000 .. 420.000` | 70.000 | `1421941918` | `1421944901` | **0** | **0,00%** |
| **6** | `420.000 .. 490.000` | 70.000 | `1421944901` | `1421945701` | **0** | **0,00%** |
| **7** | `490.000 .. 560.000` | 70.000 | `1421945701` | `1421948806` | **0** | **0,00%** |
| **8** | `560.000 .. 630.000` | 70.000 | `1421948806` | `1421951961` | **0** | **0,00%** |
| **9** | `630.000 .. 700.001` | 70.001 | `1421951961` | `1421955842` | **0** | **0,00%** |
| **Total** | **`0 .. 700.001`** | **700.001** | **`1421927377`** | **`1421955842`** | **22.215** | **3,17%** |

- **Primeiro fluxo de ataque após ordenação por `Stime`:** linha `13` (`Stime = 1421927414`).
- **Último fluxo de ataque em todo o dataset:** linha `186.807` (`Stime = 1421934448`).
- **Total de ataques entre as linhas `186.808` e `700.000` (`513.193` fluxos):** **exatamente `0` ataques**.

### 1.2. Justificativa Metodológica para o Horizonte Ativo de 200.000 Registros

Em sistemas de detecção de intrusão avaliados sob **particionamento estritamente cronológico** ($60\% / 20\% / 20\%$ sem embaralhamento aleatório para evitar *temporal data leakage*), aplicar o corte diretamente sobre as `700.001` linhas brutas aloca:
- **Treino (`0 .. 420.000`):** `22.215` ataques (`100%` dos ataques do arquivo) em `555` snapshots de `30 s`.
- **Validação (`420.000 .. 560.000`):** **`0` ataques** em `200` snapshots.
- **Teste (`560.000 .. 700.001`):** **`0` ataques** em `229` snapshots.

Com zero exemplos positivos nas partições de validação e teste, as métricas supervisionadas de detecção ($\text{Precision} = \frac{TP}{TP+FP}$, $\text{Recall} = \frac{TP}{TP+FN}$ e $\text{F1-Score}$) tornam-se matematicamente degeneradas ($0/0$), inviabilizando tanto o *Early Stopping* baseado em F1 de validação quanto a avaliação de sensibilidade a ataques.

Por conseguinte, a metodologia experimental do artigo define formalmente duas regiões complementares e disjuntas dentro da captura:

1. **Horizonte Ativo de Campanha (`Active Attack Horizon`, linhas `0 .. 200.000`, `Stime` `1421927377 .. 1421934925`):**
   Contém **100% dos `22.215` fluxos maliciosos** registrados na captura e preserva uma margem pós-campanha imediata (`linhas 186.808 .. 200.000`). Dentro deste horizonte ativo de `200.000` fluxos, o particionamento cronológico estrito $60\% / 20\% / 20\%$ produz partições causalmente disjuntas e estatisticamente representativas em janelas de $\Delta t = 30\text{ s}$:
   - **Treino (`linhas 0 .. 120.000`):** `156` snapshots, `5.910` nós (`749` nós atacantes, `5.161` nós benignos), `18.909` arestas entre hosts (`13.805` fluxos de ataque). Todos os artefatos estatísticos (vocabulário One-Hot, correlação de Pearson Top-20 e `StandardScaler` $\mu_{\text{train}}, \sigma_{\text{train}}$) são ajustados **exclusivamente** nesta partição.
   - **Validação (`linhas 120.000 .. 160.000`):** `48` snapshots, `1.793` nós (`192` nós atacantes, `1.601` nós benignos), `6.009` arestas entre hosts (`6.120` fluxos de ataque). Utilizada para seleção de hiperparâmetros, ablações arquiteturais e *Early Stopping* (`--val_only`).
   - **Teste Reservado (`linhas 160.000 .. 200.000`):** `69` snapshots, `2.388` nós (`134` nós atacantes, `2.254` nós benignos), `7.934` arestas entre hosts (`2.290` fluxos de ataque). Mantido bloqueado durante toda a seleção de modelos (`--val_only`).

2. **Validação Independente de Operação em Período Benigno (`Post-Campaign Benign Tail`, linhas `200.000 .. 700.001`, `Stime` `1421934925 .. 1421955842`):**
   Para impedir que o recorte de `200.000` linhas seja interpretado como descarte arbitrário de dados ou viés de prevalência, as **`500.001` linhas subsequentes (`linhas 200.000 .. 700.001`)** são retidas como um **conjunto de validação externa de estabilidade operacional (FPR em regime benigno prolongado)**. Este bloco compreende `667` snapshots temporais de `30 s` e `15.900` instâncias de nós benignos ao longo de mais de `5,8 horas` de tráfego pós-ataque. Crucialmente, essas `500.001` linhas são transformadas em grafos utilizando **exclusivamente** o vocabulário One-Hot, a lista `top_features` e os parâmetros `scaler_mean` / `scaler_scale` congelados da partição de treino (`linhas 0 .. 120.000`), com **`refitted_on_external = False`**.

### 1.3. Registro de Transparência sobre Acessos ao Conjunto de Teste e Protocolo `--val_only`

Em conformidade com as boas práticas de reprodutibilidade científica:
- Antes do bloqueio estrito via `--val_only`, duas execuções diagnósticas preliminares consultaram a partição de teste reservada (`linhas 160.000 .. 200.000`): (i) o smoke test inicial nas primeiras `50.000` linhas (`30s` vs. `60s`) e (ii) a primeira execução de `seed=42` em `unsw_full_ebpf_30s.pt` para as variantes `cnn_lstm_pure`, `gat_self_loop` e `cnn_lstm_gat`.
- A partir desse ponto, **todas as 18 execuções multi-seed (`6 variantes × 3 seeds: 42, 123, 1337`)**, todas as execuções da **Modalidade B (`ebpf_sensor_strict`)** e todas as escolhas arquiteturais foram conduzidas sob `--val_only`, gravando `"held_out_test_metrics": null` nos relatórios JSON.
- O arquivo complementar `UNSW-NB15_2.csv` não está presente localmente no Dell G15 nem no Google Drive (`unsw_nb15_2_present_locally: false` em `data/processed/g15_dataset_chronology_audit.json`). Quando adicionado futuramente, deverá ser processado via `preprocessor.py --reference_bundle data/processed/unsw_full_ebpf_30s.pt` (`refitted_on_external = False`) para avaliação cega adicional.

---

## 2. Investigação Controlada da Camada `GATConv`: Heterofilia, Direcionalidade e Conexão Residual

### 2.1. Estrutura Topológica e Homofilia/Heterofilia das Arestas (`unsw_full_ebpf_30s.pt`)

Como o pré-processador rotula um nó $v$ como atacante ($y_t(v) = 1$) somente quando $v$ **origina** pelo menos um fluxo malicioso (`srcip`) dentro da janela $t$, vítimas passivas (`dstip`) permanecem com rótulo $y_t(v) = 0$. A contagem exata das arestas direcionadas entre hosts distintos ($u \to v$) revela a natureza heterofílica dos ataques de rede:

| Partição | Snapshots (`30s`) | Total de Arestas ($u \to v$) | `0 -> 0` (Benigno $\to$ Benigno) | `1 -> 0` (Atacante $\to$ Vítima Benigna) | `0 -> 1` (Benigno $\to$ Atacante) | `1 -> 1` (Atacante $\to$ Atacante) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Treino (`0..120k`)** | 156 | 18.909 | 15.541 (82,19%) | **3.288 (17,39%)** | 80 (0,42%) | 0 (0,00%) |
| **Validação (`120k..160k`)** | 48 | 6.009 | 4.918 (81,84%) | **1.042 (17,34%)** | 49 (0,82%) | 0 (0,00%) |
| **Teste (`160k..200k`)** | 69 | 7.934 | 6.727 (84,79%) | **1.161 (14,63%)** | 46 (0,58%) | 0 (0,00%) |

Na partição de validação (`1.601` nós benignos e `192` nós atacantes):
- **`461` nós benignos (`28,79%`)** são **vítimas diretas** que recebem $\ge 1$ aresta de entrada oriunda de um atacante ($1 \to 0$).
- **`1.140` nós benignos (`71,21%`)** não recebem nenhuma aresta de atacantes ($0$ arestas $1 \to 0$).

### 2.2. Ablação Controlada de 6 Variantes Arquiteturais em Múltiplas Seeds (`42, 123, 1337`, `--val_only`)

Todas as 6 variantes foram treinadas até 30 épocas (`batch_size = 8`, `patience = 7`, `--val_only`, `--resume --save_every 1`) na Modalidade A (`ebpf_compatible`, `200.000` linhas, `30s`):

| Variante Arquitetural | Val F1 (Média $\pm$ DP) | Val Precision (Média $\pm$ DP) | Val Recall (Média $\pm$ DP) | Val FPR Global (Média $\pm$ DP) | FPR em Vítimas Benignas Alvo de Atacante ($N=461$) | FPR em Nós Benignos Não-Alvo ($N=1.140$) | Tempo de Treino (s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `cnn_lstm_pure` (sem `GATConv`) | $0,7516 \pm 0,0070$ | $0,6470 \pm 0,0170$ | $0,8976 \pm 0,0161$ | $5,89\% \pm 0,52\%$ | **$20,46\% \pm 1,82\%$** | **$0,00\% \pm 0,00\%$** | $6,28 \pm 2,08\text{ s}$ |
| `gat_self_loop` (auto-loops $i \to i$) | $0,7463 \pm 0,0182$ | $0,6351 \pm 0,0299$ | $0,9062 \pm 0,0113$ | $6,29\% \pm 0,82\%$ | **$21,69\% \pm 2,77\%$** | $0,06\% \pm 0,08\%$ | $9,54 \pm 2,69\text{ s}$ |
| `cnn_lstm_gat` (`src -> dst` padrão) | $0,9337 \pm 0,0128$ | $0,8874 \pm 0,0307$ | $0,9861 \pm 0,0089$ | $1,52\% \pm 0,46\%$ | **$5,13\% \pm 1,65\%$** | $0,06\% \pm 0,04\%$ | $15,01 \pm 0,97\text{ s}$ |
| `gat_reverse` (`dst -> src` invertido) | $0,9006 \pm 0,1154$ | $0,8630 \pm 0,1613$ | $0,9514 \pm 0,0514$ | $2,21\% \pm 2,73\%$ | $7,66\% \pm 9,47\%$ | $0,00\% \pm 0,00\%$ | $8,26 \pm 0,29\text{ s}$ |
| **`gat_bidir` (`src <-> dst` bidirecional)** | **$0,9609 \pm 0,0067$** | **$0,9418 \pm 0,0089$** | $0,9809 \pm 0,0107$ | **$0,73\% \pm 0,12\%$** | **$2,53\% \pm 0,41\%$** | **$0,00\% \pm 0,00\%$** | $11,18 \pm 2,88\text{ s}$ |
| **`gat_residual` (`gat(h) + W_res h`)** | **$0,9505 \pm 0,0070$** | $0,9058 \pm 0,0127$ | **$1,0000 \pm 0,0000$** | $1,25\% \pm 0,18\%$ | **$4,19\% \pm 0,51\%$** | $0,06\% \pm 0,08\%$ | $8,77 \pm 0,50\text{ s}$ |

#### Detalhamento Individual por Seed e Matriz de Confusão de Validação (`1.601` Benignos, `192` Atacantes)

| Variante | Seed | Melhor Época | Val F1 | Val Prec | Val Rec | Val FPR | `TN` | `FP` | `FN` | `TP` | `FP` em Vítimas Alvo (`/461`) | `FP` em Não-Alvo (`/1140`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `cnn_lstm_pure` | `42` | 6 | 0,7543 | 0,6434 | 0,9115 | 6,06% | 1504 | 97 | 17 | 175 | 97 (21,04%) | 0 (0,00%) |
| `cnn_lstm_pure` | `123` | 20 | 0,7585 | 0,6693 | 0,8750 | 5,18% | 1518 | 83 | 24 | 168 | 83 (18,00%) | 0 (0,00%) |
| `cnn_lstm_pure` | `1337` | 6 | 0,7420 | 0,6282 | 0,9062 | 6,43% | 1498 | 103 | 18 | 174 | 103 (22,34%) | 0 (0,00%) |
| `gat_self_loop` | `42` | 10 | 0,7284 | 0,6113 | 0,9010 | 6,87% | 1491 | 110 | 19 | 173 | 108 (23,43%) | 2 (0,18%) |
| `gat_self_loop` | `123` | 20 | 0,7713 | 0,6772 | 0,8958 | 5,12% | 1519 | 82 | 20 | 172 | 82 (17,79%) | 0 (0,00%) |
| `gat_self_loop` | `1337` | 7 | 0,7390 | 0,6167 | 0,9219 | 6,87% | 1491 | 110 | 15 | 177 | 110 (23,86%) | 0 (0,00%) |
| `cnn_lstm_gat` | `42` | 19 | 0,9227 | 0,8604 | 0,9948 | 1,94% | 1570 | 31 | 1 | 191 | 30 (6,51%) | 1 (0,09%) |
| `cnn_lstm_gat` | `123` | 28 | 0,9268 | 0,8716 | 0,9896 | 1,75% | 1573 | 28 | 2 | 190 | 28 (6,07%) | 0 (0,00%) |
| `cnn_lstm_gat` | `1337` | 29 | 0,9517 | 0,9303 | 0,9740 | 0,87% | 1587 | 14 | 5 | 187 | 13 (2,82%) | 1 (0,09%) |
| `gat_reverse` | `42` | 10 | 0,7380 | 0,6353 | 0,8802 | 6,06% | 1504 | 97 | 23 | 169 | 97 (21,04%) | 0 (0,00%) |
| `gat_reverse` | `123` | 10 | 0,9948 | 0,9897 | 1,0000 | 0,12% | 1599 | 2 | 0 | 192 | 2 (0,43%) | 0 (0,00%) |
| `gat_reverse` | `1337` | 9 | 0,9689 | 0,9639 | 0,9740 | 0,44% | 1594 | 7 | 5 | 187 | 7 (1,52%) | 0 (0,00%) |
| `gat_bidir` | `42` | 29 | 0,9646 | 0,9363 | 0,9948 | 0,81% | 1588 | 13 | 1 | 191 | 13 (2,82%) | 0 (0,00%) |
| `gat_bidir` | `123` | 16 | 0,9666 | 0,9543 | 0,9792 | 0,56% | 1592 | 9 | 4 | 188 | 9 (1,95%) | 0 (0,00%) |
| `gat_bidir` | `1337` | 9 | 0,9514 | 0,9347 | 0,9688 | 0,81% | 1588 | 13 | 6 | 186 | 13 (2,82%) | 0 (0,00%) |
| `gat_residual` | `42` | 8 | 0,9435 | 0,8930 | 1,0000 | 1,44% | 1578 | 23 | 0 | 192 | 21 (4,56%) | 2 (0,18%) |
| `gat_residual` | `123` | 9 | 0,9600 | 0,9231 | 1,0000 | 1,00% | 1585 | 16 | 0 | 192 | 16 (3,47%) | 0 (0,00%) |
| `gat_residual` | `1337` | 10 | 0,9481 | 0,9014 | 1,0000 | 1,31% | 1580 | 21 | 0 | 192 | 21 (4,56%) | 0 (0,00%) |

### 2.3. Diagnóstico Científico: Por que `CNN+LSTM` Puro Sofre Falsos Positivos em Vítimas e Como a `GATConv` Resolve

1. **Origem exata dos Falsos Positivos no modelo sem grafo (`cnn_lstm_pure`):**
   Na construção da sequência temporal local $X_t[v] \in \mathbb{R}^{L \times F}$ (`preprocessor.py`), cada nó $v$ agrega até $L=10$ fluxos incidentes nos quais $v$ participa como origem (`srcip`) **ou** destino (`dstip`). Quando um atacante $u$ dispara uma rajada de fluxos maliciosos contra um servidor benigno $v$, esses fluxos anômalos entram na série temporal $X_t[v]$. Sem a topologia direcionada do grafo (`cnn_lstm_pure` e `gat_self_loop`), o classificador observa estatísticas volumétricas anômalas em $X_t[v]$, mas é incapaz de distinguir se $v$ é o **autor (`srcip`)** ou o **alvo passivo (`dstip`)** — resultando em **$20,46\% \pm 1,82\%$ de FPR nas vítimas benignas (`461` nós)**, enquanto nos `1.140` nós benignos não atacados o FPR é **$0,00\%$**.
2. **Por que o smoke test curto de 50k linhas apresentou FPR elevado na GAT, mas o horizonte completo de 200k linhas reduziu o FPR de `5,89%` para `0,73%–1,52%`:**
   Nos primeiros estágios do treinamento (épocas 1 a 5), a agregação `GATConv` sem conexão residual sofre suavização heterofílica inicial através das arestas $1 \to 0$ (`Val FPR = 16,6%` na época 1 e `10,1%` na época 3). No smoke test de `50.000` linhas (com poucos snapshots), o *Early Stopping* interrompeu o treinamento prematuramente nessa fase transitória. Quando treinada sobre o horizonte completo de campanha (`200.000` linhas, `156` snapshots de treino), a atenção multi-head ($\text{heads}=4$) converge a partir da época 8–15 para diferenciar a assinatura de quem **envia** de quem **recebe** arestas de ataque, derrubando o FPR em vítimas benignas de **$20,46\%$ (`cnn_lstm_pure`) para $5,13\%$ (`cnn_lstm_gat`), $4,19\%$ (`gat_residual`) e $2,53\%$ (`gat_bidir`)**.
3. **Efeito estabilizador da Conexão Residual (`gat_residual`):**
   A adição da projeção linear residual $\mathbf{z}_v = \text{GAT}(\mathbf{h}, E)_v + \mathbf{W}_{\text{res}}\mathbf{h}_v$ preserva a representação temporal própria do nó $\mathbf{h}_v$ desde a época 1, acelerando a convergência para a época `8–10` (`8,77s` vs. `15,01s`) e atingindo **$\text{Recall} = 100,00\% \pm 0,00\%$ (`FN = 0` nas 3 seeds)**.

---

## 3. Resultados da Validação Independente na Cauda Benigna Pós-Campanha (`500.001` Fluxos)

Avaliação dos checkpoints congelados (`seed=42`, selecionados apenas pela validação das primeiras `200.000` linhas) sobre as **`500.001` linhas benignas subsequentes (`linhas 200.000 .. 700.001`, `667` snapshots de `30 s`, `15.900` nós benignos)** sem nenhum reajuste estatístico (`refitted_on_external = False`):

| Variante Arquitetural | Fluxos Externos Avaliados | Snapshots (`30s`) | Nós Benignos (`Label=0`) | `TN` | `FP` | **FPR Operacional Independente (%)** | Acurácia em Regime Benigno (%) | Latência Média (`ms/snapshot`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `gat_reverse` | 500.001 | 667 | 15.900 | 15.900 | **0** | **0,000%** | **100,000%** | 1,26 ms |
| `cnn_lstm_pure` | 500.001 | 667 | 15.900 | 15.893 | **7** | **0,044%** | **99,956%** | 1,02 ms |
| `gat_self_loop` | 500.001 | 667 | 15.900 | 15.876 | **24** | **0,151%** | **99,849%** | 1,27 ms |
| **`cnn_lstm_gat`** | 500.001 | 667 | 15.900 | 15.866 | **34** | **0,214%** | **99,786%** | 1,45 ms |
| `gat_bidir` | 500.001 | 667 | 15.900 | 15.809 | **91** | **0,572%** | **99,428%** | 1,25 ms |
| `gat_residual` | 500.001 | 667 | 15.900 | 15.758 | **142** | **0,893%** | **99,107%** | 1,42 ms |

> **Conclusão de Generalização Externa:** Em mais de `5,8 horas` de tráfego exclusivamente benigno pós-campanha (`15.900` avaliações de hosts em `667` janelas de `30 s`), **todas as variantes mantêm FPR abaixo de `0,90%`** (com `0,214%` na `cnn_lstm_gat` e `0,044%` na `cnn_lstm_pure`), comprovando que o treinamento no horizonte ativo de `200.000` registros **não induz alucinação de ataques em períodos de calmaria**.

---

## 4. Auditoria de Compatibilidade eBPF/XDP: Matriz das 20 Features e Modalidades A vs. B

### 4.1. Matriz Técnica Completa das 20 Features Selecionadas em `ebpf_compatible`

Confronto direto entre `preprocessor.py`, `ebpf/spectre_xdp.c`, `ebpf/common.h` (`struct flow_metrics` com apenas `{packets, bytes, start_ns, last_seen_ns, syn_count, fin_count, rst_count, psh_count, ack_count, urg_count}`) e `ebpf/loader_fusion_v2.cpp` (`derive_features()`):

| # | Feature (`ebpf_compatible`) | Significado Físico / Unidade | Coletada em `spectre_xdp.c` (XDP Ingress)? | Derivada em `loader_fusion_v2.cpp`? | Exige Fluxo Bidirecional (`dst->src`)? | Exige Estado TCP Completo (Handshake/Seq)? | Exige Janela Multi-Fluxo (100 conexões)? | Disponível no Momento Exato da Inferência XDP Ingress? |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `sttl` | Time-To-Live IPv4 de origem (`iph->ttl`, 8 bits) | Parcial (no cabeçalho IPv4 no XDP, mas ausente de `struct flow_metrics`) | Não | Não | Não | Não | **Sim (Modalidade B)** — direto do cabeçalho L3 `iph->ttl` no XDP |
| 2 | `swin` | Janela TCP anunciada pela origem (`tcph->window`) | Parcial (no cabeçalho TCP no XDP, mas ausente de `struct flow_metrics`) | Não | Não | Sim (cabeçalho TCP) | Não | **Sim (Modalidade B)** — direto do cabeçalho L4 `tcph->window` |
| 3 | `dttl` | Time-To-Live IPv4 de destino (pacotes de retorno) | **Não** (XDP atua apenas em *ingress*) | Não | **Sim** | Não | Não | **Não (Apenas Modalidade A Offline)** — exige captura simétrica de retorno |
| 4 | `proto_unas` | One-Hot protocolo IP não atribuído (`proto`) | Sim (`iph->protocol` no XDP) | Parcial (`is_tcp/udp`) | Não | Não | Não | **Sim (Modalidade B)** — campo `iph->protocol` disponível no 1º pacote |
| 5 | `Sload` | Taxa de bits de origem ($\text{bps} = 8 \cdot \text{sbytes}/\text{dur}$) | Sim (`m->bytes`, `last_seen_ns - start_ns`) | Sim (`bytes_per_sec`) | Não | Não | Não | **Sim (Modalidade B)** — calculado de `bytes` e `dur` do mapa BPF |
| 6 | `tcprtt` | Round-Trip Time do handshake TCP (`synack + ackdat`) | **Não** | Não | **Sim** | **Sim (3-way handshake)** | Não | **Não (Apenas Modalidade A Offline)** — exige observar `SYN-ACK` no sentido reverso |
| 7 | `synack` | Tempo entre `SYN` e `SYN-ACK` (segundos) | **Não** | Não | **Sim** | **Sim** | Não | **Não (Apenas Modalidade A Offline)** — exige pacote `SYN-ACK` de retorno |
| 8 | `ackdat` | Tempo entre `SYN-ACK` e `ACK` final (segundos) | **Não** | Não | **Sim** | **Sim** | Não | **Não (Apenas Modalidade A Offline)** — depende do `SYN-ACK` prévio |
| 9 | `ct_dst_src_ltm` | Nº de conexões do mesmo par `(srcip, dstip)` nas últimas 100 conexões | **Não** (mapa BPF é indexado apenas por `src_ip`) | Não | Não | Não | **Sim (buffer de 100 fluxos)** | **Não (Apenas Modalidade A Offline)** — exige tabela histórica multi-fluxo |
| 10 | `dmeansz` | Tamanho médio de pacote no sentido destino $\to$ origem | **Não** | Não | **Sim** | Não | Não | **Não (Apenas Modalidade A Offline)** — exige contagem `dbytes/Dpkts` de retorno |
| 11 | `ct_dst_sport_ltm` | Nº de conexões com mesmo `(dstip, sport)` nas últimas 100 conexões | **Não** | Não | Não | Não | **Sim (buffer de 100 fluxos)** | **Não (Apenas Modalidade A Offline)** — exige histórico global de 100 conexões |
| 12 | `dsport` | Porta de destino L4 (`ntohs(tcph->dest)` / `udph->dest`) | Parcial (lida no XDP para whitelist DNS/NTP, não salva em `flow_metrics`) | Não | Não | Não | Não | **Sim (Modalidade B)** — lida diretamente do cabeçalho L4 no XDP |
| 13 | `dwin` | Janela TCP anunciada pelo destino (retorno) | **Não** | Não | **Sim** | Sim | Não | **Não (Apenas Modalidade A Offline)** — exige cabeçalho TCP de retorno |
| 14 | `proto_tcp` | One-Hot protocolo TCP (`iph->protocol == IPPROTO_TCP`) | **Sim** (`spectre_xdp.c` linha 136) | **Sim** (`feat[12] = is_tcp`) | Não | Não | Não | **Sim (Modalidade B)** — já implementado em `spectre_xdp.c` e `loader_fusion_v2.cpp` |
| 15 | `ct_src_dport_ltm` | Nº de conexões com mesmo `(srcip, dsport)` nas últimas 100 conexões | **Não** | Não | Não | Não | **Sim (buffer de 100 fluxos)** | **Não (Apenas Modalidade A Offline)** — exige janela de 100 conexões |
| 16 | `ct_dst_ltm` | Nº de conexões para o mesmo `dstip` nas últimas 100 conexões | **Não** | Não | Não | Não | **Sim (buffer de 100 fluxos)** | **Não (Apenas Modalidade A Offline)** — exige janela de 100 conexões |
| 17 | `sport` | Porta de origem L4 (`ntohs(tcph->source)` / `udph->source`) | Parcial (lida no XDP, não salva em `flow_metrics`) | Não | Não | Não | Não | **Sim (Modalidade B)** — lida diretamente do cabeçalho L4 no XDP |
| 18 | `Dload` | Taxa de bits de destino ($\text{bps}$ no sentido reverso) | **Não** | Não | **Sim** | Não | Não | **Não (Apenas Modalidade A Offline)** — exige tráfego de retorno |
| 19 | `smeansz` | Tamanho médio de pacote de origem ($\text{sbytes}/\text{Spkts}$) | **Sim** (`m->bytes`, `m->packets`) | **Sim** (`feat[8] = avg_pkt_size`) | Não | Não | Não | **Sim (Modalidade B)** — já implementado em `spectre_xdp.c` e `loader_fusion_v2.cpp` |
| 20 | `ct_srv_dst` | Nº de conexões com mesmo `(service, dstip)` nas últimas 100 conexões | **Não** | Não | Não | Não | **Sim (buffer de 100 fluxos + L7)** | **Não (Apenas Modalidade A Offline)** — exige histórico de 100 conexões |

### 4.2. Comparação Experimental entre Modalidade A (`ebpf_compatible`) e Modalidade B (`ebpf_sensor_strict`)

Para eliminar qualquer lacuna entre o modelo avaliado e o sensor de kernel, implementamos em `preprocessor.py` o escopo `--feature_scope ebpf_sensor_strict` (**Modalidade B**), que remove todas as colunas bidirecionais (`Dpkts, dbytes, dttl, dwin, dmeansz, Dload, Djit, Dintpkt, dloss`), de RTT de handshake (`tcprtt, synack, ackdat`) e de janela histórica de 100 conexões (`ct_*`), retendo **exclusivamente métricas unidirecionais de ingress** e derivando `ebpf_log1p_sbytes`, `ebpf_log1p_spkts` e `ebpf_spkts_per_sec` exatamente como `derive_features()` em `ebpf/loader_fusion_v2.cpp`:

| Variante Arquitetural | Modalidade A (`ebpf_compatible` — Fluxo L3/L4 Bidirecional Offline) | Modalidade B (`ebpf_sensor_strict` — Sensor XDP Unidirecional Estrito, `seed=42 / 123`) |
| :--- | :---: | :---: |
| `cnn_lstm_pure` | $\text{F1} = 0,7516 \pm 0,0070$ ($\text{FPR} = 5,89\%$) | $\text{F1} = 0,7166 \text{ (s42)} / 0,7357 \text{ (s123)}$ ($\text{FPR} = 7,81\% / 6,68\%$) |
| `gat_self_loop` | $\text{F1} = 0,7463 \pm 0,0182$ ($\text{FPR} = 6,29\%$) | $\text{F1} = 0,7216 \text{ (s42)} / 0,6960 \text{ (s123)}$ ($\text{FPR} = 7,37\% / 7,43\%$) |
| `cnn_lstm_gat` | $\text{F1} = 0,9337 \pm 0,0128$ ($\text{FPR} = 1,52\%$) | $\text{F1} = 0,8087 \text{ (s42)} / 0,6853 \text{ (s123)}$ ($\text{FPR} = 5,12\% / 7,06\%$) |
| **`gat_residual`** | **$\text{F1} = 0,9505 \pm 0,0070$ ($\text{Rec} = 100\%, \text{FPR} = 1,25\%$)** | **$\text{F1} = 0,9343 \text{ (s42)} / 0,9143 \text{ (s123)}$ ($\text{Rec} = 100\%, \text{FPR} = 1,69\% / 2,25\%$)** |

> **Descoberta Científica Central da Modalidade B:** Quando restrito estritamente a features unidirecionais de ingress (`ebpf_sensor_strict`), a `cnn_lstm_gat` padrão perde estabilidade (`F1 = 0,8087 / 0,6853`), pois faltam as features de resposta (`dttl, tcprtt, dmeansz`) que diferenciavam facilmente alvos passivos. Contudo, a variante **`gat_residual`** recupera integralmente o desempenho (**`Val F1 = 0,9343` na `seed=42` e `0,9143` na `seed=123`, com `100%` de Recall e `1,69%–2,25%` de FPR**), provando que a arquitetura híbrida com conexão residual opera com alta precisão mesmo sob visibilidade estritamente unidirecional de pacotes XDP ingress.

---

## 5. Benchmark Isolado de Latência e VRAM (`benchmark_latency.py` — RTX 3050 6 GB)

Medições obtidas com `10` passagens de *GPU warmup* seguidas de `30` passagens cronometradas com `torch.cuda.synchronize()` sobre os `48` snapshots da partição de validação (`1.793` nós, `batch_size = 8`):

### 5.1. Latência Desagregada por Passagem Completa (`48` Snapshots, `1.793` Nós)

| Variante | Preparação de Batch CPU (`p50 / p95 / p99` ms) | Transferência `CPU -> GPU` (`p50 / p95 / p99` ms) | Inferência Neural Pura GPU (`p50 / p95 / p99` ms) | Pós-processamento `GPU -> CPU` (`p50 / p95 / p99` ms) | Pipeline Local Total (`p50 / p95 / p99` ms) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `cnn_lstm_pure` | `11,39 / 12,55 / 13,44` | `4,28 / 4,91 / 8,18` | `15,02 / 16,91 / 18,90` | `2,08 / 2,28 / 2,33` | `33,67 / 37,64 / 38,32` |
| `gat_self_loop` | `11,76 / 13,47 / 13,85` | `5,08 / 6,32 / 6,48` | `37,86 / 44,71 / 48,32` | `2,18 / 2,64 / 4,08` | `57,65 / 67,39 / 72,50` |
| **`cnn_lstm_gat`** | `17,94 / 22,41 / 26,40` | `8,05 / 9,04 / 10,63` | `38,81 / 47,68 / 52,18` | `2,17 / 2,63 / 4,65` | `67,55 / 82,10 / 87,75` |
| **`gat_residual`** | `17,99 / 19,64 / 22,19` | `7,94 / 9,65 / 11,50` | `39,48 / 42,39 / 45,83` | `2,17 / 2,36 / 2,51` | `68,04 / 73,54 / 79,91` |

### 5.2. Latência Streaming Unitária (`batch_size = 1`), Throughput e Consumo de VRAM

| Variante | Inferência Pura (`ms/snapshot` `p50 / p95 / p99`) | Pipeline Local (`ms/snapshot` `p50 / p95 / p99`) | Inferência Pura (`us/nó` `p50 / p95 / p99`) | Throughput Inferência Pura (`snapshots/s` / `nós/s`) | Throughput Pipeline Completo (`snapshots/s` / `nós/s`) | VRAM Alocada / Pico (`MiB`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `cnn_lstm_pure` | `2,23 / 8,23 / 8,44` | `2,94 / 8,94 / 9,13` | `61,17 / 228,09 / 239,15` | `3.356,6 / 125.384` | `1.582,9 / 59.129` | `41,61 / 66,47 MiB` |
| `gat_self_loop` | `5,05 / 5,41 / 5,89` | `5,72 / 6,15 / 6,58` | `134,56 / 153,28 / 164,72` | `1.238,0 / 46.246` | `817,5 / 30.536` | `41,77 / 66,63 MiB` |
| **`cnn_lstm_gat`** | `5,16 / 5,53 / 8,07` | `6,33 / 6,78 / 9,36` | `137,88 / 156,55 / 216,82` | `1.204,9 / 45.006` | `699,2 / 26.120` | `40,95 / 65,29 MiB` |
| **`gat_residual`** | `5,38 / 5,69 / 6,55` | `6,51 / 6,88 / 7,67` | `142,21 / 159,40 / 179,87` | `1.201,7 / 44.889` | `697,6 / 26.058` | `41,02 / 65,35 MiB` |

> **Separação Estrita de Escopo de Latência:** As medições acima referem-se exclusivamente à inferência neural em GPU e ao pipeline local de classificação (`CPU -> GPU -> Modelo -> CPU`). Elas **não** incluem latência de rede WAN nem o tempo de atualização assíncrona de mapas BPF no kernel Linux via syscall `bpf(BPF_MAP_UPDATE_ELEM)`.
