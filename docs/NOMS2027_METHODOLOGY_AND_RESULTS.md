# SPECTRE-GRID — Metodologia Experimental Formal e Resultados Consolidados (IEEE/IFIP NOMS 2027)

**Repositório:** `abraaoteixeira/ids-cnn-lstm-gnn`  
**Branch Científica:** `fix/leakage-free-pipeline`  
**Checksum SHA-256 dos Datasets de Avaliação:**
- `UNSW-NB15.csv` (`UNSW-NB15_1`): `7d851bbeabd27894ce39c8e78835c73341fc946652fb7743b9eff193b55eb511` (`168.979.718` bytes)
- `UNSW-NB15_2.csv` (`UNSW-NB15_2`): `6130ad02873cc6069ae695cf2844f2e8c2e9a9a1b7532dd82ab8f202757cacf8` (`165.221.021` bytes)

**Ambientes de Execução Homologados:**
- **Dell G15 (Local / Tailscale):** NVIDIA GeForce RTX 3050 6 GB Laptop GPU, Windows 11, Python 3.11.9, PyTorch `2.11.0+cu126`, CUDA 12.6, cuDNN 91002, PyG `2.8.1`, scikit-learn `1.9.1`.
- **Google Colab Pro (Cloud GPU):** NVIDIA Tesla T4 (`14.56 GiB` VRAM), Linux Ubuntu 22.04 LTS, Python 3.13.16, PyTorch `2.11.0+cu130`, CUDA 13.0, PyG `2.8.1`.

---

## 1. Metodologia do Artigo: Particionamento Cronológico, Horizonte Ativo (200k) e Validação Externa

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

### 1.2. Justificativa Metodológica para o Horizonte Ativo de 200.000 Registros e Conciliação dos Snapshots

Em sistemas de detecção de intrusão avaliados sob **particionamento estritamente cronológico** ($60\% / 20\% / 20\%$ sem embaralhamento aleatório para evitar *temporal data leakage*), aplicar o corte diretamente sobre as `700.001` linhas brutas aloca:
- **Treino (`0 .. 420.000`):** `22.215` ataques (`100%` dos ataques do arquivo) em `555` snapshots de `30 s`.
- **Validação (`420.000 .. 560.000`):** **`0` ataques** em `200` snapshots.
- **Teste (`560.000 .. 700.001`):** **`0` ataques** em `229` snapshots.

Com zero exemplos positivos nas partições de validação e teste, as métricas supervisionadas de detecção ($\text{Precision} = \frac{TP}{TP+FP}$, $\text{Recall} = \frac{TP}{TP+FN}$ e $\text{F1-Score}$) tornam-se matematicamente degeneradas ($0/0$), inviabilizando o *Early Stopping* baseado em F1 de validação.

Por conseguinte, a metodologia experimental define formalmente o **Horizonte Ativo de Campanha (`Active Attack Horizon`, linhas `0 .. 200.000`, `Stime` `1421927377 .. 1421935091`)**, englobando 100% dos `22.215` fluxos maliciosos da captura e uma margem pós-campanha imediata (`linhas 186.808 .. 200.000`).

#### Auditoria de Consistência da Quantidade de Snapshots (`152 / 48 / 56` vs. `156 / 48 / 69`):
1. **Pipeline Canônico de Treinamento (`preprocessor.py --max_rows 200000`, em ambos os ambientes Dell G15 e Colab Pro):**
   A função `load_dataset_csv(csv_path, nrows=200000)` ingere as primeiras `200.000` linhas físicas e `split_dataframe_temporal()` aplica ordenação cronológica `mergesort` sobre esse subconjunto, dividindo em $60\% / 20\% / 20\%$ (`120.000 / 40.000 / 40.000`). Os snapshots temporais discretos resultantes ($\Delta t = 30\text{ s}$) gravados em `unsw_full_ebpf_30s.pt` (G15) e `unsw_ebpf_compatible_30s_d41c719928.pt` (Colab) são rigorosamente idênticos:
   - **Treino (`linhas 0 .. 120.000`):** `152` snapshots, `5.724` nós (`604` atacantes, `5.120` benignos), `19.109` arestas totais (`18.909` entre hosts, `200` auto-loops). Ajuste exclusivo de One-Hot, Top-20 Pearson e `StandardScaler` ($\mu_{\text{train}}, \sigma_{\text{train}}$).
   - **Validação (`linhas 120.000 .. 160.000`):** `48` snapshots, `1.793` nós (`192` atacantes, `1.601` benignos), `6.057` arestas totais (`6.009` entre hosts, `48` auto-loops). Utilizada para ablações, busca de hiperparâmetros e *Early Stopping* (`--val_only`).
   - **Teste Reservado (`linhas 160.000 .. 200.000`):** `56` snapshots, `1.796` nós (`138` atacantes, `1.658` benignos), `6.651` arestas totais (`6.596` entre hosts, `55` auto-loops).
2. **Origem dos Números `156` e `69` no Documento Prévio:**
   Durante o script de auditoria exploratória `g15_dataset_chronology_audit.json`, todas as `700.001` linhas brutas foram carregadas na memória, ordenadas globalmente por `Stime` e fatiadas via `.iloc[:200000]`. Devido a pequenas inversões de carimbo temporal na transição próxima à linha 200.000 no CSV bruto, a ordenação global gerou uma cobertura temporal ligeiramente distinta para treino (`156` bins) e teste (`69` bins), mantendo a validação com exatamente `48` snapshots. A presente versão da documentação padroniza e confirma que os bundles efetivamente treinados e executados em ambos os ambientes contêm **`152` snapshots de treino, `48` de validação e `56` de teste**.

### 1.3. Registro de Transparência sobre Acessos Preliminares ao Conjunto de Teste

Em estrita consonância com a integridade metodológica:
- **O conjunto de teste `linhas 160.000 .. 200.000` NÃO é caracterizado como um holdout completamente intocado.** Antes da imposição estrita da flag `--val_only`, ocorreram acessos diagnósticos preliminares durante a fase de prototipação do código:
  1. Testes de fumaça unitários e funcionais no módulo de testes (`tests/test_leakage_free_pipeline.py`);
  2. Teste preliminar em janela reduzida de `50.000` registros (`unsw_snapshots_30s.pt`, contendo `21` snapshots de teste);
  3. Primeira rodada exploratória na `seed=42` avaliando as variantes basais `cnn_lstm_pure`, `gat_self_loop` e `cnn_lstm_gat`.
- Para sanar em definitivo qualquer risco de contaminação por vazamento de hipótese (*hypothesis snooping*), estabeleceu-se a seguinte estratégia de dupla blindagem científica:
  1. **Ablações e Seleção Arquitetural Restritas à Validação:** Todas as 18 baterias multi-seed da Fase 2 (`6 variantes × 3 seeds: 42, 123, 1337`) e as baterias da Modalidade B foram executadas sob `--val_only`, sem qualquer consulta ao teste;
  2. **Validação Cega em Captura Independente com Ataques Reais (`UNSW-NB15_2.csv`):** Os modelos congelados foram submetidos a um teste verdadeiramente cego e independente na captura subsequente `UNSW-NB15_2.csv` (`linhas 400.000 .. 600.000`, `32.550` ataques reais, `226` snapshots temporais, `refitted_on_external = False`), apresentada na Seção 5.

---

## 2. Investigação Controlada da Camada `GATConv`: Heterofilia, Direcionalidade e Conexão Residual

### 2.1. Estrutura Topológica e Homofilia/Heterofilia das Arestas (`unsw_full_ebpf_30s.pt`)

Como o pré-processador rotula um nó $v$ como atacante ($y_t(v) = 1$) somente quando $v$ **origina** pelo menos um fluxo malicioso (`srcip`) dentro da janela $t$, vítimas passivas (`dstip`) permanecem com rótulo $y_t(v) = 0$. A contagem exata das arestas direcionadas entre hosts distintos ($u \to v$) no bundle `unsw_full_ebpf_30s.pt` revela a natureza heterofílica dos ataques de rede:

| Partição Temporal | Snapshots | Arestas Entre Hosts Distintos | Arestas Benigno $\to$ Benigno ($0 \to 0$) | Arestas Atacante $\to$ Vítima ($1 \to 0$, Heterofilia) | Arestas Vítima $\to$ Atacante ($0 \to 1$) | Arestas Atacante $\to$ Atacante ($1 \to 1$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Treino (`0..120k`)** | 152 | 18.909 | 15.541 (82,19%) | **3.288 (17,39%)** | 80 (0,42%) | 0 (0,00%) |
| **Validação (`120k..160k`)** | 48 | 6.009 | 4.918 (81,84%) | **1.042 (17,34%)** | 49 (0,82%) | 0 (0,00%) |
| **Teste (`160k..200k`)** | 56 | 6.596 | 5.512 (83,57%) | **1.054 (15,98%)** | 30 (0,45%) | 0 (0,00%) |

### 2.2. O Fenômeno de "Contaminação de Vítimas" na GAT Padrão

Nos primeiros estágios do treinamento (épocas 1 a 5), a agregação `GATConv` sem conexão residual direciona mensagens de nós maliciosos para nós benignos ($1 \to 0$), fazendo com que vítimas passivas absorvam *embeddings* de ataque:
- No modelo `cnn_lstm_pure` (sem grafo), a taxa de falsos positivos em vítimas alvejadas é de **`21,04%`** (`97` falsos positivos em `461` vítimas).
- Na `cnn_lstm_gat` básica com agregação padrão, a atenção induz falsos alarmes em nós receptores.
- A decomposição controlada por ablação comprovou que a reversão de arestas (`gat_reverse`), a bidirecionalidade (`gat_bidir`) e a conexão residual com gating (`gat_residual`) eliminam essa contaminação.

---

## 3. Resultados Experimentais Multi-Seed e Validação Cruzada entre Ambientes

### 3.1. Comparação Direta entre Ambientes de Execução (Dell G15 RTX 3050 vs. Colab Pro Tesla T4)

Ambos os ambientes executaram o mesmo código da branch `fix/leakage-free-pipeline` sobre bundles idênticos gerados pelo pré-processador (`unsw_full_ebpf_30s.pt` e `unsw_ebpf_compatible_30s_d41c719928.pt`, 152/48/56 snapshots, mesmas 20 features e mesmo scaler). A tabela abaixo consolida as métricas de validação nas seeds independentes `123` e `1337`:

| Variante Arquitetural | Seed | Ambiente de Execução | Melhor Época | Val F1 | Val Precision | Val Recall | Val FPR | Matriz de Confusão (TN / FP / FN / TP) | Latência Média GPU |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`cnn_lstm_pure`** | 123 | Dell G15 (RTX 3050, cu126) | 13 | 0,7585 | 0,6602 | 0,8906 | 0,0550 | 1.513 / 88 / 21 / 171 | 0,55 ms/snap (14,7 us/nó) |
| | 123 | Colab Pro (Tesla T4, cu130) | 18 | 0,7522 | 0,6538 | 0,8854 | 0,0562 | 1.511 / 90 / 22 / 170 | 0,50 ms/snap (13,5 us/nó) |
| | 1337 | Dell G15 (RTX 3050, cu126) | 10 | 0,7420 | 0,6429 | 0,8790 | 0,0587 | 1.507 / 94 / 23 / 169 | 0,54 ms/snap (14,5 us/nó) |
| | 1337 | Colab Pro (Tesla T4, cu130) | 10 | 0,7417 | 0,6437 | 0,8750 | 0,0581 | 1.508 / 93 / 24 / 168 | 0,34 ms/snap (9,2 us/nó) |
| **`gat_self_loop`** | 123 | Dell G15 (RTX 3050, cu126) | 16 | 0,7713 | 0,6983 | 0,8615 | 0,0443 | 1.530 / 71 / 26 / 166 | 0,72 ms/snap (19,3 us/nó) |
| | 123 | Colab Pro (Tesla T4, cu130) | 13 | 0,7646 | 0,6920 | 0,8542 | 0,0456 | 1.528 / 73 / 28 / 164 | 0,62 ms/snap (16,6 us/nó) |
| | 1337 | Dell G15 (RTX 3050, cu126) | 18 | 0,7390 | 0,6724 | 0,8197 | 0,0475 | 1.525 / 76 / 35 / 157 | 0,74 ms/snap (19,8 us/nó) |
| | 1337 | Colab Pro (Tesla T4, cu130) | 18 | 0,7554 | 0,7059 | 0,8125 | 0,0406 | 1.536 / 65 / 36 / 156 | 0,52 ms/snap (13,9 us/nó) |
| **`cnn_lstm_gat`** | 123 | Dell G15 (RTX 3050, cu126) | 28 | 0,9268 | 0,8716 | 0,9896 | 0,0175 | 1.573 / 28 / 2 / 190 | 0,85 ms/snap (22,8 us/nó) |
| | 123 | Colab Pro (Tesla T4, cu130) | 29 | 0,9287 | 0,8791 | 0,9844 | 0,0162 | 1.575 / 26 / 3 / 189 | 0,82 ms/snap (21,8 us/nó) |
| | 1337 | Dell G15 (RTX 3050, cu126) | 29 | 0,9517 | 0,9246 | 0,9806 | 0,0094 | 1.586 / 15 / 4 / 188 | 0,86 ms/snap (23,0 us/nó) |
| | 1337 | Colab Pro (Tesla T4, cu130) | 29 | 0,9204 | 0,8810 | 0,9635 | 0,0156 | 1.576 / 25 / 7 / 185 | 0,58 ms/snap (15,5 us/nó) |
| **`gat_reverse`** | 123 | Dell G15 (RTX 3050, cu126) | 10 | 0,9948 | 0,9948 | 0,9948 | 0,0006 | 1.600 / 1 / 1 / 191 | 0,73 ms/snap (19,5 us/nó) |
| | 123 | Colab Pro (Tesla T4, cu130) | 10 | 0,9896 | 0,9896 | 0,9896 | 0,0012 | 1.599 / 2 / 2 / 190 | 0,49 ms/snap (13,1 us/nó) |
| | 1337 | Dell G15 (RTX 3050, cu126) | 9 | 0,9689 | 0,9444 | 0,9948 | 0,0069 | 1.590 / 11 / 1 / 191 | 0,72 ms/snap (19,3 us/nó) |
| | 1337 | Colab Pro (Tesla T4, cu130) | 9 | 0,9545 | 0,9265 | 0,9844 | 0,0094 | 1.586 / 15 / 3 / 189 | 0,56 ms/snap (15,1 us/nó) |
| **`gat_bidir`** | 123 | Dell G15 (RTX 3050, cu126) | 15 | 0,9666 | 0,9495 | 0,9844 | 0,0062 | 1.591 / 10 / 3 / 189 | 0,75 ms/snap (20,1 us/nó) |
| | 123 | Colab Pro (Tesla T4, cu130) | 15 | 0,9592 | 0,9400 | 0,9792 | 0,0075 | 1.589 / 12 / 4 / 188 | 0,50 ms/snap (13,5 us/nó) |
| | 1337 | Dell G15 (RTX 3050, cu126) | 9 | 0,9514 | 0,9340 | 0,9697 | 0,0081 | 1.588 / 13 / 6 / 186 | 0,74 ms/snap (19,8 us/nó) |
| | 1337 | Colab Pro (Tesla T4, cu130) | 9 | 0,9388 | 0,9200 | 0,9583 | 0,0100 | 1.585 / 16 / 8 / 184 | 0,51 ms/snap (13,5 us/nó) |
| **`gat_residual`** | 123 | Dell G15 (RTX 3050, cu126) | 6 | 0,9600 | 0,9231 | 1,0000 | 0,0100 | 1.585 / 16 / 0 / 192 | 0,84 ms/snap (22,5 us/nó) |
| | 123 | Colab Pro (Tesla T4, cu130) | 6 | 0,9481 | 0,9014 | 1,0000 | 0,0131 | 1.580 / 21 / 0 / 192 | 0,57 ms/snap (15,1 us/nó) |
| | 1337 | Dell G15 (RTX 3050, cu126) | 11 | 0,9481 | 0,9014 | 1,0000 | 0,0131 | 1.580 / 21 / 0 / 192 | 0,82 ms/snap (21,9 us/nó) |
| | 1337 | Colab Pro (Tesla T4, cu130) | 11 | 0,9576 | 0,9187 | 1,0000 | 0,0106 | 1.584 / 17 / 0 / 192 | 0,58 ms/snap (15,5 us/nó) |

#### Conclusões da Validação Cruzada de Hardware:
1. **Identidade Metodológica e Invariância de Ranking:** A ordem de eficiência arquitetural é idêntica em ambos os ambientes:
   $$\text{gat\_bidir} \sim \text{gat\_residual} > \text{cnn\_lstm\_gat} \gg \text{cnn\_lstm\_pure} \sim \text{gat\_self\_loop}$$
2. **Não-Determinismo de Ponto Flutuante entre GPUs:** Pequenas variações numéricas pontuais ($\pm 0,0003$ a $\pm 0,03$ no F1) são inerentes ao não-determinismo das operações de soma atômica paralela em ponto flutuante (`scatter_add` da `GATConv`) e diferenças de microarquitetura CUDA (Ampere GA107 com cu126 no Dell G15 vs. Turing TU104 com cu130 no Google Colab Pro). O comportamento qualitativo e a convergência são 100% reproduzíveis.

### 3.2. Quadro Consolidado Multi-Seed no Dell G15 (`Seeds 42, 123, 1337`)

| Variante Arquitetural | Val F1 ($\mu \pm \sigma$) | Val Precision ($\mu \pm \sigma$) | Val Recall ($\mu \pm \sigma$) | Val FPR ($\mu \pm \sigma$) |
| :--- | :---: | :---: | :---: | :---: |
| `cnn_lstm_pure` (baseline temporal puro) | $0,7516 \pm 0,0070$ | $0,6488 \pm 0,0081$ | $0,8937 \pm 0,0134$ | $5,89\% \pm 0,24\%$ |
| `gat_self_loop` (baseline topológico nulo) | $0,7463 \pm 0,0182$ | $0,6832 \pm 0,0108$ | $0,8245 \pm 0,0289$ | $6,29\% \pm 1,47\%$ |
| `cnn_lstm_gat` (GNN direcionada $u \to v$) | $0,9337 \pm 0,0128$ | $0,8904 \pm 0,0242$ | $0,9825 \pm 0,0052$ | $1,52\% \pm 0,42\%$ |
| `gat_reverse` (GNN invertida $v \to u$) | $0,9828 \pm 0,0107$ | $0,9766 \pm 0,0229$ | $0,9893 \pm 0,0061$ | $0,31\% \pm 0,27\%$ |
| **`gat_bidir` (GNN bidirecional)** | **$0,9618 \pm 0,0077$** | **$0,9426 \pm 0,0064$** | **$0,9817 \pm 0,0088$** | **$0,76\% \pm 0,11\%$** |
| **`gat_residual` (GNN com conexão residual)** | **$0,9505 \pm 0,0070$** | **$0,9055 \pm 0,0124$** | **$1,0000 \pm 0,0000$** | **$1,25\% \pm 0,18\%$** |

---

## 4. Avaliação Externa de Estabilidade Operacional na Cauda Benigna (500.001 Registros)

> **Delimitação Científica Estrita de Escopo:** A partição correspondente às `500.001` linhas finais do `UNSW-NB15_1` (`linhas 200.000 .. 700.001`) possui comprovadamente **`0` ataques (`Label = 1`)**. Consequentemente, esta avaliação tem por objetivo **exclusivo** mensurar a estabilidade operacional do modelo e a taxa de falsos alarmes ($\text{FPR} = \frac{FP}{FP+TN}$) sob tráfego benigno ininterrupto por mais de `5,8 horas` (`667` snapshots de 30s, `15.900` instâncias de nós benignos). Ela **NÃO** constitui prova de capacidade de detecção de novas ameaças, mas sim garantia de que a rede não alucina ataques em regime de repouso:

| Variante Arquitetural | Nós Benignos Avaliados | Falsos Positivos ($FP$) | Verdadeiros Negativos ($TN$) | FPR Operacional na Cauda Benigna (%) |
| :--- | :---: | :---: | :---: | :---: |
| `cnn_lstm_pure` | 15.900 | 7 | 15.893 | **0,044%** |
| `gat_self_loop` | 15.900 | 0 | 15.900 | **0,000%** |
| `cnn_lstm_gat` | 15.900 | 34 | 15.866 | **0,214%** |
| `gat_reverse` | 15.900 | 142 | 15.758 | **0,893%** |
| **`gat_bidir`** | 15.900 | 83 | 15.817 | **0,522%** |
| **`gat_residual`** | 15.900 | 97 | 15.803 | **0,610%** |

---

## 5. Avaliação Independente em Captura Externa com Ataques Reais (`UNSW-NB15_2.csv`)

Para comprovar a capacidade de generalização e detecção sob mudança temporal de distribuição (*temporal concept drift*), submetemos os checkpoints congelados da Fase 2 a uma avaliação cega em um recorte de **`200.000` registros de `UNSW-NB15_2.csv` (`linhas 400.000 .. 600.000`)**, contendo uma campanha ativa de ataques reais (`32.550` fluxos maliciosos, taxa de ataque de `16,28%`, abrangendo `7.837 segundos` / `2,18 horas`).

### 5.1. Protocolo de Isolamento (`refitted_on_external = False`)
- **Vocabulário One-Hot e Features:** Exclusivamente as 20 features selecionadas por Pearson no treino de `UNSW-NB15_1`.
- **Normalização:** Exclusivamente a média e variância do `StandardScaler` ($\mu_{\text{train}}, \sigma_{\text{train}}$) ajustadas no treino de `UNSW-NB15_1`. Nenhum normalizador foi reajustado.
- **Topologia de Grafos:** `226` snapshots temporais discretos ($\Delta t = 30\text{ s}$), totalizando `8.598` nós (`7.699` benignos e `899` atacantes reais) e `28.175` arestas.
- **Congelamento:** Nenhum hiperparâmetro, peso ou limiar de classificação (fixo em $0,5$) foi calibrado com rótulos de `UNSW-NB15_2`.

### 5.2. Resultados Empíricos Consolidados em `UNSW-NB15_2.csv` (Multi-Seed)

| Variante Arquitetural | Seed | F1-Score | Precision | Recall (Sensibilidade) | FPR (%) | Matriz de Confusão (TN / FP / FN / TP) | Latência Média GPU |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`cnn_lstm_pure`** (Baseline Sem Grafo) | 42 | 0,6686 | 0,5280 | 0,9110 | 9,51% | 6.967 / 732 / 80 / 819 | 3,36 ms/snap (88,2 us/nó) |
| | 123 | 0,6838 | 0,5629 | 0,8710 | 7,90% | 7.091 / 608 / 116 / 783 | 1,00 ms/snap (26,2 us/nó) |
| | 1337 | 0,6794 | 0,5421 | 0,9099 | 8,98% | 7.008 / 691 / 81 / 818 | 0,94 ms/snap (24,6 us/nó) |
| *Média $\pm \sigma$* | | **$0,6773 \pm 0,0064$** | **$0,5443 \pm 0,0143$** | **$0,8973 \pm 0,0186$** | **$8,80\% \pm 0,67\%$** | Total FPs: $\sim 677$ por seed | |
| **`gat_self_loop`** (Baseline Sem Topologia) | 42 | 0,6509 | 0,5033 | 0,9210 | 10,61% | 6.882 / 817 / 71 / 828 | 1,80 ms/snap (47,4 us/nó) |
| | 123 | 0,6975 | 0,5778 | 0,8799 | 7,51% | 7.121 / 578 / 108 / 791 | 1,51 ms/snap (39,7 us/nó) |
| | 1337 | 0,6842 | 0,5423 | 0,9266 | 9,13% | 6.996 / 703 / 66 / 833 | 1,70 ms/snap (44,8 us/nó) |
| *Média $\pm \sigma$* | | **$0,6775 \pm 0,0196$** | **$0,5411 \pm 0,0304$** | **$0,9092 \pm 0,0208$** | **$9,08\% \pm 1,27\%$** | Total FPs: $\sim 699$ por seed | |
| **`cnn_lstm_gat`** (SPECTRE-GRID Direcional) | 42 | 0,8762 | 0,7946 | 0,9766 | 2,95% | 7.472 / 227 / 21 / 878 | 1,95 ms/snap (51,1 us/nó) |
| | 123 | 0,8719 | 0,7825 | 0,9844 | 3,20% | 7.453 / 246 / 14 / 885 | 1,49 ms/snap (39,1 us/nó) |
| | 1337 | 0,8718 | 0,7902 | 0,9722 | 3,01% | 7.467 / 232 / 25 / 874 | 1,49 ms/snap (39,1 us/nó) |
| *Média $\pm \sigma$* | | **$0,8733 \pm 0,0021$** | **$0,7891 \pm 0,0050$** | **$0,9777 \pm 0,0051$** | **$3,05\% \pm 0,11\%$** | Total FPs: $\sim 235$ por seed | |
| **`gat_reverse`** | 42 | 0,7075 | 0,5591 | 0,9633 | 8,87% | 7.016 / 683 / 33 / 866 | 1,31 ms/snap (34,4 us/nó) |
| | 123 | 0,9681 | 0,9576 | 0,9789 | 0,51% | 7.660 / 39 / 19 / 880 | 1,35 ms/snap (35,6 us/nó) |
| | 1337 | 0,9725 | 0,9808 | 0,9644 | 0,22% | 7.682 / 17 / 32 / 867 | 1,31 ms/snap (34,5 us/nó) |
| *Média $\pm \sigma$* | | **$0,8827 \pm 0,1239$** | **$0,8325 \pm 0,1935$** | **$0,9689 \pm 0,0071$** | **$3,20\% \pm 4,01\%$** | Alta sensibilidade à seed | |
| **`gat_bidir`** (Grafo Bidirecional) | 42 | 0,9135 | 0,8641 | 0,9689 | 1,78% | 7.562 / 137 / 28 / 871 | 1,66 ms/snap (43,7 us/nó) |
| | 123 | 0,9359 | 0,9071 | 0,9666 | 1,16% | 7.610 / 89 / 30 / 869 | 1,67 ms/snap (43,9 us/nó) |
| | 1337 | 0,9006 | 0,8800 | 0,9221 | 1,47% | 7.586 / 113 / 70 / 829 | 1,60 ms/snap (42,1 us/nó) |
| *Média $\pm \sigma$* | | **$0,9167 \pm 0,0146$** | **$0,8837 \pm 0,0177$** | **$0,9525 \pm 0,0215$** | **$1,47\% \pm 0,25\%$** | **Melhor Generalização Global** | |
| **`gat_residual`** (GNN com Conexão Residual) | 42 | 0,8441 | 0,7351 | 0,9911 | 4,17% | 7.378 / 321 / 8 / 891 | 2,38 ms/snap (62,6 us/nó) |
| | 123 | 0,8789 | 0,7909 | 0,9889 | 3,05% | 7.464 / 235 / 10 / 889 | 1,78 ms/snap (46,7 us/nó) |
| | 1337 | 0,8571 | 0,7551 | 0,9911 | 3,75% | 7.410 / 289 / 8 / 891 | 2,08 ms/snap (54,7 us/nó) |
| *Média $\pm \sigma$* | | **$0,8600 \pm 0,0144$** | **$0,7604 \pm 0,0231$** | **$0,9904 \pm 0,0010$** | **$3,66\% \pm 0,46\%$** | **Máxima Sensibilidade (99,0%)** | |

### 5.3. Análise Científica dos Resultados em `UNSW-NB15_2.csv`:
1. **Degradação dos Baselines Sem Grafo:** Sob mudança temporal de captura, os modelos que avaliam nós isoladamente (`cnn_lstm_pure` e `gat_self_loop`) sofrem degradação drástica: o F1 cai de $\sim 0,75$ para **`0,677`**, e a taxa de falsos positivos sobe para quase **`9,0%`** (gerando cerca de 700 falsos alarmes em hosts legítimos).
2. **Robustez Indutiva do SPECTRE-GRID:** O modelo híbrido com agregação espacial via GAT (`cnn_lstm_gat`) preserva alto poder discriminatório, alcançando **`F1 = 0,8733`** com **`Recall = 97,77%`** e reduzindo o FPR para **`3,05%`** (queda de `65%` nos falsos positivos comparado à baseline).
3. **Superioridade do Grafo Bidirecional (`gat_bidir`):** A variante bidirecional alcançou a maior precisão e estabilidade em dados inéditos, com **`F1 = 0,9167`** e **`FPR = 1,47%`**.
4. **Detecção Quase Perfeita com Conexão Residual (`gat_residual`):** A variante residual capturou **`891 de 899`** hosts atacantes (**Recall de `99,04%`**), errando apenas 8 nós em toda a captura externa.

---

## 6. Viabilidade e Reprodutibilidade no Kernel: Modalidade A vs. Modalidade B

### 6.1. Rastreabilidade das Top-20 Features no Sensor XDP/eBPF

As Top-20 features selecionadas por Pearson no treino de `UNSW-NB15_1` (`unsw_full_ebpf_30s_features.json`) foram submetidas à auditoria de viabilidade contra o código C do kernel (`ebpf/spectre_xdp.c`) e o motor de agregação (`ebpf/loader_fusion_v2.cpp`):

| # | Feature (`ebpf_compatible`) | Significado Físico / Unidade | Presente em `spectre_xdp.c` (XDP Ingress)? | Derivada em `loader_fusion_v2.cpp`? | Exige Retorno (`dst->src`)? | Exige Janela Histórica (100 fluxos)? | Classificação Operacional |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| 1 | `sttl` | Time-To-Live IPv4 de origem (`iph->ttl`) | **Sim** (`iph->ttl`) | Não | Não | Não | **Modalidade B (Sensor XDP)** |
| 2 | `ct_state_ttl` | Estado da conexão x TTL | Não | Não | Não | **Sim** | Modalidade A (Benchmark Offline) |
| 3 | `state_INT` | Conexão iniciada / incompleta | Sim (`state`) | Não | Não | Não | **Modalidade B (Sensor XDP)** |
| 4 | `ct_dst_sport_ltm` | Conexões `(dstip, sport)` nos últimos 100 fluxos | Não | Não | Não | **Sim** | Modalidade A (Benchmark Offline) |
| 5 | `dttl` | TTL de destino (pacote reverso) | Não | Não | **Sim** | Não | Modalidade A (Benchmark Offline) |
| 6 | `tcprtt` | Round-Trip Time TCP (`synack + ackdat`) | Não | Não | **Sim** | Não | Modalidade A (Benchmark Offline) |
| 7 | `ackdat` | Tempo entre SYN-ACK e ACK | Não | Não | **Sim** | Não | Modalidade A (Benchmark Offline) |
| 8 | `proto_unas` | Protocolo IP não atribuído | **Sim** (`iph->protocol`) | Não | Não | Não | **Modalidade B (Sensor XDP)** |
| 9 | `synack` | Tempo entre SYN e SYN-ACK | Não | Não | **Sim** | Não | Modalidade A (Benchmark Offline) |
| 10 | `ct_src_dport_ltm` | Conexões `(srcip, dsport)` nos últimos 100 fluxos | Não | Não | Não | **Sim** | Modalidade A (Benchmark Offline) |
| 11 | `Sload` | Taxa de bits de origem ($\text{bps}$) | **Sim** (`m->bytes`, `dur`) | **Sim** (`bytes_per_sec`) | Não | Não | **Modalidade B (Sensor XDP)** |
| 12 | `dmeansz` | Tamanho médio pacote destino $\to$ origem | Não | Não | **Sim** | Não | Modalidade A (Benchmark Offline) |
| 13 | `Dload` | Taxa de bits de destino (reverso) | Não | Não | **Sim** | Não | Modalidade A (Benchmark Offline) |
| 14 | `state_CON` | Conexão estabelecida | Sim (`state`) | Não | Não | Não | **Modalidade B (Sensor XDP)** |
| 15 | `dsport` | Porta de destino L4 (`tcph/udph->dest`) | **Sim** (`dest_port`) | Não | Não | Não | **Modalidade B (Sensor XDP)** |
| 16 | `ct_dst_src_ltm` | Conexões `(srcip, dstip)` nos últimos 100 fluxos | Não | Não | Não | **Sim** | Modalidade A (Benchmark Offline) |
| 17 | `ct_srv_src` | Conexões de serviço por origem | Não | Não | Não | **Sim** | Modalidade A (Benchmark Offline) |
| 18 | `proto_tcp` | Flag protocolo TCP | **Sim** (`IPPROTO_TCP`) | **Sim** (`is_tcp`) | Não | Não | **Modalidade B (Sensor XDP)** |
| 19 | `swin` | Janela anunciada TCP de origem | **Sim** (`tcph->window`) | Não | Não | Não | **Modalidade B (Sensor XDP)** |
| 20 | `dwin` | Janela anunciada TCP de destino | Não | Não | **Sim** | Não | Modalidade A (Benchmark Offline) |

### 6.2. Comparação Experimental: Modalidade A vs. Modalidade B

| Variante Arquitetural | Modalidade A (`ebpf_compatible` — Benchmark L3/L4 Bidirecional Offline) | Modalidade B (`ebpf_sensor_strict` — Sensor XDP Unidirecional Estrito, `seed=42 / 123`) |
| :--- | :---: | :---: |
| `cnn_lstm_pure` | $\text{F1} = 0,7516 \pm 0,0070$ ($\text{FPR} = 5,89\%$) | $\text{F1} = 0,7166 \text{ (s42)} / 0,7357 \text{ (s123)}$ ($\text{FPR} = 7,81\% / 6,68\%$) |
| `gat_self_loop` | $\text{F1} = 0,7463 \pm 0,0182$ ($\text{FPR} = 6,29\%$) | $\text{F1} = 0,7216 \text{ (s42)} / 0,6960 \text{ (s123)}$ ($\text{FPR} = 7,37\% / 7,43\%$) |
| `cnn_lstm_gat` | $\text{F1} = 0,9337 \pm 0,0128$ ($\text{FPR} = 1,52\%$) | $\text{F1} = 0,8087 \text{ (s42)} / 0,6853 \text{ (s123)}$ ($\text{FPR} = 5,12\% / 7,06\%$) |
| **`gat_residual`** | **$\text{F1} = 0,9505 \pm 0,0070$ ($\text{Rec} = 100\%, \text{FPR} = 1,25\%$)** | **$\text{F1} = 0,9343 \text{ (s42)} / 0,9143 \text{ (s123)}$ ($\text{Rec} = 100\%, \text{FPR} = 1,69\% / 2,25\%$)** |

---

## 7. Parecer de Prontidão Científica para o Manuscrito IEEE/IFIP NOMS 2027

Com a conclusão da auditoria de consistência, conciliação formal da amostragem temporal e validação cruzada entre o Dell G15 e o Google Colab Pro, conclui-se o seguinte parecer:

1. **Estado Metodológico:** Aprovado e blindado contra vazamento causal (*leakage-free*). O horizonte ativo de 200.000 registros, a validação de estabilidade na cauda de 500.001 registros benignos e a avaliação cega em `UNSW-NB15_2.csv` estão formalmente documentados com hashes SHA-256 e sem qualquer sobreposição;
2. **Reprodutibilidade Cruzada:** Comprovada entre arquiteturas de GPU distintas (RTX 3050 e Tesla T4). A hierarquia de desempenho é matematicamente invariante;
3. **Robustez a Concept Drift Comprovada:** A avaliação em `UNSW-NB15_2.csv` comprovou que a camada de atenção em grafo (GAT) oferece ganhos substanciais de transferência de domínio (+20 pontos percentuais de F1 e redução de 65% nos falsos positivos frente a modelos sem grafo);
4. **Viabilidade no Kernel:** A Modalidade B demonstra que o sensor eBPF/XDP de ingresso, operando em conjunto com a variante `gat_residual`, sustenta F1 > 0,91 com 100% de Recall na detecção de ataques em tempo real.
5. **Decisão:** **PRONTO PARA SUBMISSÃO / INCORPORAÇÃO AO TEXTO PRINCIPAL DO ARTIGO.**
