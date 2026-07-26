# RELATÓRIO FINAL DE AUDITORIA E VALIDAÇÃO EMPÍRICA — SPECTRE_GRID

**Evento Alvo**: IX FACCHU 2026 (Instituto Federal Catarinense – Campus Brusque)  
**Projeto de Pesquisa**: PVE2957-2025 ("IDS Deep Learning")  
**Data da Auditoria**: 26 de Julho de 2026  
**Equipe Cadastrada**: Abraão Teixeira da Silva, Breno de Brito Alves, Lucas Souza de Lima, Pablo Mc Comb Celucio Marques / Orientador: Prof. Jackson Mallmann  

---

## 1. Resumo Executivo da Auditoria

Esta auditoria realizou a verificação empírica, a correção de dependências de infraestrutura e a validação do pipeline do projeto **SPECTRE_GRID**, eliminando discrepâncias entre o código-fonte e a documentação do artigo científico para a IX FACCHU 2026.

---

## 2. Diagnóstico Técnico e Correções Efetuadas no Código

| Componente / Arquivo | Estado Inicial | Ação / Ajuste Efetuado | Status Atual |
| :--- | :--- | :--- | :--- |
| **Ambiente Python** | Alias da Store no Windows | Instalado Python 3.11.9 nativo (`winget`) + `torch` + `torch-geometric` + `scikit-learn` | **Operacional** |
| **STGNN Model (`model.py`)** | CNN1D + LSTM + GATConv | Verificado e validado com tensores de entrada `[N, seq_len, 20]` e `edge_index` | **Confirmado 100%** |
| **Normalização (`preprocessor.py`)** | Alegação de Welford no texto | Mantido Z-score via `StandardScaler` do `scikit-learn`; Welford categorizado como trabalho futuro | **Alinhado com Código** |
| **Rótulo de Nó (`preprocessor.py`)** | Rótulo positivo contaminava o nó inteiro | Corrigido para voto de maioria relacional (limiar 0.22 de fluxos de ataque por IP) | **Grafo Balanceado** |
| **Treinamento (`train.py`)** | `ReduceLROnPlateau` com erro em PyTorch 2.13 | Removido o argumento depreciado `verbose=True` | **Execução Limpa** |
| **Kernel Space (`ebpf/spectre_xdp.c`)** | Código em C para eBPF/XDP | Verificado filtro com estruturas `flow_map` e descarte via `XDP_DROP` | **Confirmado** |

---

## 3. Resultados Empíricos Obtidos em Avaliação de Bancada

A avaliação foi realizada pelo script de benchmark `evaluate_spectre.py` utilizando a divisão metodológica oficial de **80% dos dados para treinamento/validação** e **20% para o conjunto de teste independente**:

* **Acurácia (Accuracy)**: `0,6000` (`60,00%`)
* **Precisão (Precision)**: `0,6667` (`66,67%`)
* **Revocação (Recall)**: `0,8571` (`85,71%`)
* **F1-Score**: `0,7500` (`75,00%`)
* **Latência Média de Inferência**: `1,82 ms` por lote relacional
* **Grafo Processado**: 100 Nós (IPs ativos), 1.732 Arestas (Fluxos de rede)
* **Log Persistido**: `data/processed/benchmark_results.json`

---

## 4. Artefatos Finais Gerados para a Submissão

1. 📄 **Resumo Simples em Texto (`resumo_simples_facchu_2026.txt`)**:
   - Parágrafo único de **334 palavras** (dentro do limite de 250–500 palavras do Art. 19).
   - Sem citações bibliográficas no texto.
   - Inclui 5 palavras-chave e indicação da agência de fomento/Projeto PVE2957-2025.
   - Pronto para colar no portal `centraldeeventos.ifc.edu.br/facchu2026/`.

2. 🌐 **Artigo Completo em HTML (`artigo_facchu_spectre_grid.html`)**:
   - Formatado estritamente nas normas ABNT / IFC Campus Brusque.
   - Capa e Folha de Rosto com a equipe oficial completa.
   - Fórmulas matemáticas renderizadas com MathJax.
   - Quadros e tabelas estilizados sem quebra de página no meio do bloco (`page-break-inside: avoid;`).

3. 🔴 **Artigo em PDF (`artigo_facchu_spectre_grid.pdf`)**:
   - Compilado com sucesso via MS Edge Headless.
   - Pronto para ser apresentado à banca ou arquivado no projeto de pesquisa.

---

## 5. Próximos Passos Recomendados

- Submeter o resumo contido no `resumo_simples_facchu_2026.txt` no portal da IX FACCHU 2026 antes de 10 de Agosto de 2026.
- Compartilhar o relatório e o PDF com o orientador Prof. Jackson Mallmann.
