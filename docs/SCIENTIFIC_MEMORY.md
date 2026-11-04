# SPECTRE-GRID — Livro de Memória Científica (Architectural & Scientific Decision Records)

Este documento registra formalmente as decisões de projeto, metodologia científica e governança arquitetural do SPECTRE-GRID. Todas as decisões aqui contidas são vinculantes para o repositório e suas branches.

---

## Índice de Decisões Científicas

| ID | Data | Título | Status | Commit / Ref |
|---|---|---|---|---|
| [ADR-001](#adr-001-particionamento-temporal-estrito-vs-k-fold-aleatório) | 2026-10-15 | Particionamento Temporal Estrito vs K-Fold Aleatório | VIGENTE | `860221f` |
| [ADR-002](#adr-002-congelamento-do-pré-processador-no-treino-scaler-e-pearson) | 2026-10-20 | Congelamento do Pré-processador no Treino (Scaler e Pearson) | VIGENTE | `860221f` |
| [ADR-003](#adr-003-subconjunto-de-features-compatíveis-com-ebpf-20-atributos) | 2026-10-22 | Subconjunto de Features Compatíveis com eBPF (20 atributos) | VIGENTE | `860221f` |
| [ADR-004](#adr-004-horizonte-ativo-de-200k-registros-e-auditoria-da-cauda-benigna) | 2026-10-28 | Horizonte Ativo de 200k Registros e Auditoria da Cauda Benigna | VIGENTE | `860221f` |
| [ADR-005](#adr-005-modelagem-da-direção-das-arestas-no-message-passing-heterofilia) | 2026-11-01 | Modelagem da Direção das Arestas no Message Passing (Heterofilia) | VIGENTE | `e171cfb` |
| [ADR-006](#adr-006-atribuição-estrita-de-rótulo-ao-ip-de-origem-src---dst) | 2026-11-01 | Atribuição Estrita de Rótulo ao IP de Origem ($src \to dst$) | VIGENTE | `e171cfb` |
| [ADR-007](#adr-007-avaliação-independente-em-captura-externa-unsw-nb15_2-para-concept-drift) | 2026-11-02 | Avaliação Independente em Captura Externa (UNSW-NB15_2) para Concept Drift | VIGENTE | `e171cfb` |
| [ADR-008](#adr-008-protocolo-de-avaliação-holdout-e-governança-multi-hardware) | 2026-11-03 | Protocolo de Avaliação Holdout e Governança Multi-Hardware | VIGENTE | `e171cfb` |

---

### ADR-001: Particionamento Temporal Estrito vs K-Fold Aleatório
- **Data:** 2026-10-15
- **Status:** VIGENTE
- **Contexto:** Em detecção de intrusão em redes, a amostragem aleatória (Shuffle / K-Fold aleatório) mistura fluxos de uma mesma conexão ou sessão em partições de treino e teste. Isso gera vazamento de dados (*data leakage*) temporal, inflacionando artificialmente as métricas de acurácia e F1-score para patamares superiores a 99%, mas colapsando quando o modelo enfrenta tráfego futuro real.
- **Decisão:** Proibir qualquer particionamento aleatório no pipeline do SPECTRE-GRID. Os fluxos devem ser ordenados estritamente pelo carimbo temporal de início (`Stime`) utilizando algoritmo de ordenação estável (`mergesort`), dividindo as partições em 60% Treino, 20% Validação e 20% Teste.
- **Evidência:** Auditoria empírica no UNSW-NB15 demonstrou que splits aleatórios permitiam que nós e fluxos de scanners de porta (port scan) fossem observados simultaneamente no treino e no teste. Com o particionamento temporal estrito, o F1-score real inicial cai para níveis realistas (~0.75 - 0.88), eliminando o viés retrospectivo.
- **Impacto:** Nenhuma métrica gerada com k-fold ou amostragem aleatória é aceita no projeto. Todos os bundles são gerados via `preprocessor.py` cronológico.

---

### ADR-002: Congelamento do Pré-processador no Treino (Scaler e Pearson)
- **Data:** 2026-10-20
- **Status:** VIGENTE
- **Contexto:** O pré-processamento inclui a seleção de atributos via correlação de Pearson e a normalização de variáveis contínuas via `StandardScaler`. Executar `fit()` no dataset completo vaza a média, variância e estrutura de correlação da partição de teste para a fase de treinamento.
- **Decisão:** O normalizador `StandardScaler` e a matriz de Pearson devem ser ajustados **exclusivamente** sobre a partição de treino ($D_{train}$). Em validação, teste e inferência, utiliza-se exclusivamente `transform()` com os parâmetros congelados ($\mu_{train}, \sigma_{train}$). Em conjuntos externos (ex.: UNSW-NB15_2), é expressamente vedado qualquer `refit` (`refitted_on_external = False`).
- **Evidência:** O pipeline serializa os parâmetros do scaler no bundle de snapshots (`scaler_mean_`, `scaler_scale_`), garantindo verificação determinística de que as partições subsequentes são normalizadas de forma causal.
- **Impacto:** Garante estrita causalidade temporal em tempo de execução real do sensor eBPF.

---

### ADR-003: Subconjunto de Features Compatíveis com eBPF (20 atributos)
- **Data:** 2026-10-22
- **Status:** VIGENTE
- **Contexto:** Datasets acadêmicos (como UNSW-NB15 e CIC-IDS) contêm dezenas de features complexas que exigem reconstrução de estado de camada de aplicação de longo prazo ou são calculadas em pós-processamento bidirecional offline. Tentar extrair tais atributos no plano de dados do Linux (eBPF/XDP) estoura o limite de instruções do BPF verifier ou introduz latência proibitiva.
- **Decisão:** Restringir o espaço de entrada neural do SPECTRE-GRID a um subconjunto estrito de **20 atributos** (`ebpf_compatible`), viáveis de serem computados no ring buffer do kernel (Modalidade A) ou no daemon de agregação de usuários em C++ (Modalidade B), respeitando as restrições de memória de XDP maps.
- **Evidência:** Mapeamento formal entre os campos de `ebpf/sensor.c`, a estrutura de agregação em `engine/flow_tracker.cpp` e o tensor de entrada PyTorch em `models/neural_ids.py`.
- **Impacto:** O modelo opera exclusivamente com features factíveis em produção, eliminando a discrepância laboratório-mundo real.

---

### ADR-004: Horizonte Ativo de 200k Registros e Auditoria da Cauda Benigna
- **Data:** 2026-10-28
- **Status:** VIGENTE
- **Contexto:** O primeiro arquivo do UNSW-NB15 (`UNSW-NB15_1.csv`, 700.001 registros) apresenta uma distribuição bimodal anômala: as primeiras 200.000 linhas contêm 25.176 ataques multivariados (Scans, Exploits, DoS, Fuzzers) distribuídos ao longo de horas; as 500.001 linhas subsequentes são 100% tráfego benigno sintético (sem nenhum ataque). Avaliar o dataset completo agregando métricas mascara o desempenho em ataques e produz métricas de recall ilusórias.
- **Decisão:** Adotar as primeiras **200.000 linhas** como o **Horizonte Ativo** para treinamento, validação e teste sob presença de ataques, gerando 152 snapshots de treino, 48 de validação e 56 de teste. Utilizar as 500.001 linhas restantes (a "cauda benigna") exclusivamente como um **teste de robustez operacional e estresse de FPR**, nunca como métrica de capacidade de generalização de ataques.
- **Evidência:** Nos 1.488 snapshots da cauda benigna, foram auditados 0 ataques reais. Modelos que operavam nessa faixa sem monitoramento de FPR apresentavam falsos alarmes cumulativos inaceitáveis.
- **Impacto:** Transparência total na metodologia do artigo NOMS 2027, justificando o particionamento temporal com rigor inquestionável.

---

### ADR-005: Modelagem da Direção das Arestas no Message Passing (Heterofilia)
- **Data:** 2026-11-01
- **Status:** VIGENTE
- **Contexto:** Na formulação de grafos de tráfego, as arestas representam fluxos de comunicação direcionados ($src \to dst$). Quando camadas tradicionais de GAT (Graph Attention Network) propagam mensagens ao longo da direção natural do fluxo ($src \to dst$), os embeddings dos nós vítimas benignos (servidores e alvos de scan) recebem e agregam os sinais agressivos dos nós atacantes. Isso gera heterofilia severa na vizinhança, fazendo com que vítimas inofensivas sejam classificadas erroneamente como atacantes, elevando a taxa de falsos positivos (FPR) para até 16.5% na GAT padrão com self-loop.
- **Decisão:** Implementar e comparar sistematicamente variantes topológicas de message passing:
  1. `gat_reverse`: Inversão da direção das mensagens ($dst \to src$), onde o atacante agrega contexto da vítima sem contaminá-la;
  2. `gat_bidir`: Grafos bidirecionais onde mensagens trafegam em ambos os sentidos com parâmetros de atenção diferenciados;
  3. `gat_residual`: Conexões residuais ponderadas que preservam a identidade do nó antes da agregação espacial.
- **Evidência:** Experimentos multi-seed (Dell G15 e Google Colab Pro) comprovaram que a reversão e bidirecionalidade derrubam o FPR de 16.50% para menos de 1.50%, mantendo o Recall acima de 98%.
- **Impacto:** Esta descoberta constitui a **contribuição científica central** do manuscrito para o IEEE/IFIP NOMS 2027.

---

### ADR-006: Atribuição Estrita de Rótulo ao IP de Origem ($src \to dst$)
- **Data:** 2026-11-01
- **Status:** VIGENTE
- **Contexto:** Um fluxo malicioso no UNSW-NB15 possui `Label = 1`. Se o grafo associar esse rótulo indiscriminadamente a ambos os nós da extremidade ($src$ e $dst$), os servidores benignos atacados seriam forçados a assumir rótulo de classe positiva durante a retropropagação (*backpropagation*), corrompendo a função de perda.
- **Decisão:** Na construção dos grafos temporais ($G_t = (V_t, E_t)$), o rótulo de ataque é atribuído **estritamente ao nó de origem ($src$)**, que efetivamente disparou o fluxo malicioso. O nó de destino ($dst$) preserva o rótulo 0 (benigno), exceto se ele próprio tiver emitido fluxos maliciosos como origem no mesmo snapshot.
- **Evidência:** Elimina o viés de rotulagem bilateral e permite que o módulo de atenção aprenda a distinguir o agente agressor do receptor passivo.
- **Impacto:** Formalizado no algoritmo de construção de grafos do preprocessor e auditado por testes unitários.

---

### ADR-007: Avaliação Independente em Captura Externa (UNSW-NB15_2) para Concept Drift
- **Data:** 2026-11-02
- **Status:** VIGENTE
- **Contexto:** Avaliações no mesmo arquivo de captura (mesmo com separação cronológica estrita) podem compartilhar padrões específicos de distribuição IP, topologia de rede local e faixas horárias contíguas. Para comprovar robustez contra deriva de conceito (*concept drift*) e generalização topológica real, é indispensável avaliar o modelo em uma captura independente.
- **Decisão:** Avaliar os modelos treinados no bundle 1 sobre uma fatia de 200.000 linhas da captura subsequente (`UNSW-NB15_2.csv`, linhas 400.000 a 600.000, 32.550 ataques, 226 snapshots), mantendo o normalizador estritamente congelado (`refitted_on_external = False`). É terminantemente vedado usar os resultados de `UNSW-NB15_2` para ajustar hiperparâmetros ou arquiteturas.
- **Evidência:** No conjunto externo, a CNN-LSTM pura sofreu degradação severa ($F1 = 0.6773, FPR = 8.80\%$). Em contrapartida, as variantes GAT com modelagem relacional preservaram alta resiliência: `gat_bidir` atingiu $F1 = 0.9167, FPR = 1.47\%$ e `gat_residual` alcançou $Recall = 99.04\%$.
- **Impacto:** Prova empírica irrefutável de que a modelagem espacial em grafos fornece representações invariantes a mudanças de distribuição em relação a classificadores puramente temporais.

---

### ADR-008: Protocolo de Avaliação Holdout e Governança Multi-Hardware
- **Data:** 2026-11-03
- **Status:** VIGENTE
- **Contexto:** A execução de experimentos científicos em múltiplos ambientes de computação (GPU móvel Ampere RTX 3050 com CUDA 12.6 vs GPU de datacenter Turing Tesla T4 com CUDA 13.0) expõe o pipeline a variações de ponto flutuante em operações atômicas não-determinísticas (`atomicAdd` no scatter de adjacência de GNNs). Além disso, acessos prévios à partição de teste devem ser documentados com transparência.
- **Decisão:**
  1. Manter o modo `--val_only` ativo durante toda a pesquisa e desenvolvimento;
  2. Documentar de forma transparente na metodologia que a partição de teste do bundle 1 serviu como teste de sanidade preliminar, complementado pela avaliação externa cega no bundle 2;
  3. Estabelecer que a consistência cruzada entre hardware é dada pela invariância estrita do ranking de desempenho das arquiteturas e tolerância de variação $\Delta F1 \le 0.015$, não exigindo igualdade bit a bit;
  4. Instituir a governança permanente com auditoria automatizada em CI.
- **Evidência:** Relatórios de execução nos dois nós de hardware (`g15_*` e `colab_*`) apresentaram exatamente o mesmo ranking de 6 arquiteturas, provando que as conclusões científicas são independentes da plataforma de aceleração.
- **Impacto:** Rastreabilidade e conformidade total com os padrões éticos e metodológicos do IEEE/IFIP.
