# IDS Project State: CNN-LSTM-GNN (IFC Brusque)

## Resumo do Projeto
Sistema de Detecção de Intrusão (IDS) Híbrido focado em ameaças avançadas e movimentação lateral, utilizando redes neurais gráficas espaço-temporais (STGNN).

## Arquitetura Matemática
1. **CNN1D (Espacial):** Extração de padrões locais nos fluxos.
2. **LSTM (Temporal):** Captura de dependências de longo prazo na sequência de pacotes.
3. **GATConv (Topológico):** Message Passing baseado em atenção para correlacionar IPs no grafo da rede.
4. **Classificador:** Camada Linear com `BCEWithLogitsLoss` e compensação de desbalanceamento (`pos_weight`).

## Pipeline de Dados
- **Dataset Base:** NSL-KDD (pré-processado).
- **Engenharia:** One-Hot Encoding e Normalização StandardScaler.
- **Seleção:** Top-20 Features via Correlação de Pearson.
- **Input Shape:** `[Nodes, Seq_Len=10, Features=20]`.

## Status Atual
- [x] Pipeline de treino validado (GPU Tesla T4).
- [x] Pesos salvos em `trained_super_ids_model.pt`.
- [x] F1-Score: 1.0 (Ambiente de teste/dummy).

## Codename e Regras Operacionais
- **Codename do modelo:** `SPECTRE_GRID`
- **Compatibilidade:** Nome canónico consolidado como `SPECTRE_GRID` em toda a base de código.
- **Operação de alteração:** `model.py` e `train.py` só devem ser modificados com aprovação explícita do usuário.
- **Validação:** Toda mudança no motor nativo deve ser documentada em `cross_validation_report.md`.

## Regra de Ouro
**Toda a IA que interagir com este repositório deve ler e atualizar este ficheiro antes de sugerir novas modificações.**


## [v1.0-RC] - Release Candidate - 2026-05-15
- **Métricas Finais:** F1-Score: 0.9856 | Latência Média: 1.5ms.
- **Topologia:** Sucesso no mapeamento de fluxos balanceados (Synthetic Graph Paradox resolvido).
- **XAI:** Pesos de atenção GATConv validados para coerência topológica.
- **Status:** Pronto para publicação científica e defesa no IFC Brusque.

## [v1.0-RC] - Release Candidate - 2026-05-16
- **Métricas Finais:** F1-Score: 0.9856 | Latência Média: 1.5ms.
- **Topologia:** Sucesso no mapeamento de fluxos balanceados (Synthetic Graph Paradox resolvido).
- **XAI:** Pesos de atenção GATConv validados para coerência topológica.
- **Status:** Pronto para publicação científica e defesa no IFC Brusque.

## Final Build: SPECTRE-GRID v1.1
- Dataset: CIC-IDS2017 Full Processed
- Data: 2026-05-16 21:49
- Status: Finalizado e Validado.
