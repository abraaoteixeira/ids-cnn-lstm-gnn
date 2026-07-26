# SPECTRE GRID: Análise de Gaps Arquiteturais e Sprints

Este documento consolida a análise crítica de arquitetura (Realizada em Jul/2026), listando os gargalos críticos que separam o projeto do estágio de *Proof of Concept (PoC) / Alpha* para um sistema de produção resiliente de classe empresarial.

---

## 🛑 Os 3 Gargalos Críticos Atuais

### Gargalo 1: O Abismo dos Dados (Concept Drift)
* **O Problema:** A IA atual (STGNN) foi treinada usando o dataset **CIC-IDS2017**, que é *flow-based* (as estatísticas são geradas pelo CICFlowMeter apenas após o encerramento da conexão TCP). Em contrapartida, nosso sensor eBPF em produção coleta pacotes em tempo real (no ar). Se a IA espera ver uma métrica de um fluxo fechado e recebe dados de um fluxo recém-aberto, ocorrerá um grave caso de *Concept Drift*, resultando em alta taxa de falsos positivos/negativos na nuvem.
* **A Solução:** Retreinar o modelo de inferência utilizando datasets orientados a NetFlow ao vivo, como o **NF-UQ-NIDS-v2**, ou consolidar as métricas diretas coletadas da nossa VPS Honeypot (DBVA-2025).

### Gargalo 2: Paridade de Extração de Features (Python vs C++)
* **O Problema:** Durante o treinamento, utilizamos o script `preprocessor.py` (Python/Pandas) para limpar CSVs e extrair as "Top-20 Features de Pearson". Em produção, o Daemon de inferência escrito em C++ (`loader_fusion_v2.cpp`) lê dados crus do eBPF Ring Buffer. 
* **A Solução:** O C++ deve ser capaz de calcular matematicamente (on the fly) as exatas 20 features (como variância de tempo entre pacotes, médias de tamanho) sem atrasos. Precisamos criar testes unitários/Scripts de validação (`validate_parity.py`) para provar que o tensor que sai do C++ é idêntico ao que sairia do Python.

### Gargalo 3: Loop do IPS, Falsos Positivos e Memória
* **O Problema:** O Daemon C++ infere um ataque e bloqueia o IP escrevendo-o no `block_map` do eBPF. E se a GNN errar e bloquear IPs críticos de infraestrutura (ex: `8.8.8.8`, Cloudflare DNS, ou nosso próprio gateway WireGuard `10.0.0.1`)? Além disso, se nunca removermos IPs antigos do mapa, o kernel ficará sem memória.
* **A Solução:** 
  1. Implementar uma **Whitelist Estática** de Kernel space, garantindo que certos CIDRs nunca recebam `XDP_DROP`.
  2. Implementar um mecanismo de **Time-To-Live (TTL) / Decay** no C++, removendo bans de IPs após um período de resfriamento.

---

## 🚀 Backlog de Sprints Priorizadas

| Ordem | Sprint | Objetivo Principal | Tarefas Chave |
|---|---|---|---|
| **1** | Dados Reais & Retreino | Eliminar Concept Drift | Baixar NF-UQ-NIDS-v2, injetar dados Honeypot, rodar `train.py`, validar métricas (F1-Score). |
| **2** | Paridade Motor C++ | Garantir qualidade do Tensor | Validar se o loop do Ring Buffer no C++ gera tensores matematicamente iguais ao `preprocessor.py`. |
| **3** | Segurança Operacional | Evitar suicídio de rede | Whitelist no XDP, TTL de Ban no C++, testes de stress. |
