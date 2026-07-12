# ROADMAP: SPECTRE GRID

Este documento consolida o estado atual do projeto e o roteiro de evolução focado na integração de novos datasets e correção de anomalias arquiteturais. A arquitetura técnica do sistema encontra-se unificada no `README.md`.

## Regra de Ouro
**Toda a IA que interagir com este repositório deve ler e atualizar este ficheiro antes de sugerir novas modificações de alto impacto na infraestrutura ou datasets.**

---

## ✅ Status Atual (v1.1 Release Candidate)
- [x] Pipeline de treino validado (GPU Tesla T4) com F1-Score: 0.9856.
- [x] Criação de serviços Systemd para ambiente Enterprise (Data Plane + Control Plane isolados).
- [x] Implementação de IPC Unix Sockets (I/O em memória).
- [x] Resolvido o "Synthetic Graph Paradox" para topologias pequenas.

---

## 🎯 Integração de Datasets (DBVA-2025 e NF-UQ-NIDS-v2)

Para evoluir a capacidade de generalização e combater o *concept drift*, o roteiro inclui a integração dos seguintes datasets:

### 1. DBVA-2025 (Dataset Baseado em Vetores de Ataque)
* **Status:** Clonado em `data/DBVA/`.
* **Escopo:** 982.005 fluxos capturados em LAN com pfSense.
* **Foco:** Varreduras (Nmap), Brute Force (Hydra) e DoS (hping3).
* **Vantagem:** Utiliza CICFlowMeter, o que garante 100% de compatibilidade na engenharia de features com a nossa base atual.

### 2. NF-UQ-NIDS-v2
* **Foco:** 11,9 milhões de fluxos baseados em NetFlow v9.
* **Vantagem:** Formato idêntico à captura do eBPF/XDP, eliminando distorções estatísticas no pipeline.

---

## 🔧 Correções Críticas Pendentes (Auditoria V1)

- [ ] **Inferência Python Dinâmica:** Refatorar `inference.py` para processar dados reais do CSV usando o `preprocessor.py`, abolindo os tensores de testes randômicos.
- [ ] **Batching de Grafo em C++ (GNN):** Atualizar `ebpf/loader_fusion_v2.cpp` para parar de enviar nós isolados ($N=1$ e loop `[[0],[0]]`). O motor de fusão deve instanciar grafos relacionais baseados na janela de pacotes do Ring Buffer, habilitando o verdadeiro mecanismo de Message Passing Espaço-Temporal no LibTorch.
