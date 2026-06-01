# Protocolo de Retreinamento e Avaliação de Modelo (SPECTRE_GRID)

Este documento define o rigor acadêmico e as métricas padrão para o processo de retreinamento da arquitetura Híbrida (CNN-1D + LSTM + GATConv) utilizando o dataset **NF-UQ-NIDS-v2**.

## 1. Justificativa de Eliminação do *Concept Drift*
O modelo original foi treinado sobre o **CIC-IDS2017** (baseado em pacotes puros/PCAP com 78 features do CICFlowMeter). No entanto, o sensor de produção (`sensor_ebpf.py`) atua na camada XDP coletando dados em formato de fluxo puro (NetFlow/IPFIX). Essa discrepância de domínio gera um *concept drift* estrutural.
A substituição para o **NF-UQ-NIDS-v2** corrige isso, pois este dataset contém 11.99 milhões de fluxos no padrão estrito do NetFlow V9, mapeando 1:1 com as métricas extraíveis via eBPF.

## 2. Pipeline de Dados
- **Pré-processamento:** One-Hot Encoding das *TCP Flags* e portas.
- **Seleção de Atributos:** Seleção das Top-20 features via Correlação de Pearson com a variável *target* (Label).
- **Mapeamento Topológico (GNN):** O dataset é convertido para grafos direcionados temporais, onde os nós representam endereços IPv4 (`IPV4_SRC_ADDR`, `IPV4_DST_ADDR`) e as arestas representam a cronologia do fluxo.

## 3. Métricas de Desempenho (Padrão Acadêmico)
Durante o retreinamento no Google Colab (GPU T4), as seguintes métricas devem ser obrigatoriamente reportadas por *epoch* e na validação final:

1. **Loss Function:** `CrossEntropyLoss` (com pesos balanceados caso haja desbalanço grave de classes no batch).
2. **Accuracy (Acurácia):** Taxa global de acertos.
3. **Precision (Precisão):** Foco em minimizar Falsos Positivos (essencial em IPS para não derrubar tráfego benigno).
4. **Recall (Sensibilidade):** Foco em minimizar Falsos Negativos (capacidade de não deixar ataques passarem).
5. **F1-Score (Harmônico):** A métrica definitiva de validação do paper, ponderando Precisão e Recall.
6. **Matriz de Confusão:** Para avaliar a dissipação de predições sobre as classes benignas vs. ataques DDoS/Brute Force.

## 4. Hardware e Replicação
O retreinamento está isolado no script `Colab_Training_NF_UQ_NIDS.ipynb` para garantir 100% de reproducibilidade em instâncias homogêneas (Google Colab, NVIDIA Tesla T4 16GB). Sementes de aleatoriedade (seeds) do PyTorch são fixadas em `42`.
