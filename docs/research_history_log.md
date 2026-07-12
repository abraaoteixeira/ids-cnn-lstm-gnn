# 📜 SPECTRE_GRID: Histórico Completo de Pesquisa e Evolução (Git Log)

Este documento foi gerado a partir de uma auditoria profunda do histórico do Git (`git log`) para servir como registro oficial da evolução técnica do projeto de pesquisa **SPECTRE_GRID**, mapeando o progresso temporal, as decisões de arquitetura e os arquivos afetados em cada fase.

---

## 📅 19 de Maio de 2026: Gênese, Datasets e IPC (Fase 1)

### 1. Inicialização e Checkpoint Seguro (`ed09f46`)
* **Descrição:** Primeira consolidação massiva do código.
* **Arquivos Chave Adicionados:**
  * **IA:** `model.py`, `train.py`, `inference.py`, `export_torchscript.py`, `preprocessor.py`.
  * **Kernel/eBPF:** `ebpf/loader.cpp`, `ebpf/loader_fusion.cpp`, `ebpf/spectre_xdp.c`, `setup_ebpf_env.sh`.
  * **UI:** `static/js/app.js`, `dashboard_api.py`.
  * **Dados:** Adição massiva dos dados brutos (KDDTest, KDDTrain, UNSW-NB15 e placeholder para CIC-IDS2017).

### 2. Otimização do Pipeline de Dados (`df2dac4` e `678acc9`)
* **Descrição:** Evolução do tratamento de dados no pandas (processamento in-memory de arquivos zipados e correção de valores infinitos/NaN). Introdução formal e renomeação dos arquivos do dataset **CIC-IDS2017** (`Tuesday-WorkingHours` e `Wednesday-workingHours`).
* **Arquivos Afetados:** `inference.py`, `preprocessor.py`, renomeação em `data/raw/benchmarks/`.

### 3. Checkpoint Pré-Evolução e Simuladores (`c7ce734`)
* **Descrição:** Criação da documentação arquitetural (`project_overview.md`) e introdução dos primeiros scripts para geração contínua de tráfego de teste.
* **Arquivos Adicionados:** `scratch/continuous_flow_generator.py`, `scratch/trigger_attack.py`, `data/logs/spectre_alerts.jsonl`.

### 4. Implementação da Fase 1 - Unix Sockets IPC (`e3fd737`)
* **Descrição:** Um salto arquitetural crítico. Eliminação do I/O de disco (que usava arquivos `.jsonl`) para comunicação ultra-rápida em memória usando **Unix Domain Sockets**.
* **Arquivos Afetados:** Criação do `architecture_evolution.md`. Atualização pesada em `dashboard_api.py` e `ebpf/loader_fusion.cpp` para suportar sockets.

### 5. Estabilização e Física do Dashboard (`987b98a`, `d5ededf`, `a5c6955`)
* **Descrição:** Foco no motor gráfico HTML5 Canvas. Foram corrigidos bugs de `addColorStop`, adicionado *cache-busting* para desenvolvimento e ajustadas as constantes físicas do grafo para impedir a aglomeração severa de nós durante ataques DDoS.
* **Arquivos Afetados:** `static/js/app.js`, `static/index.html`, criação de scripts de screenshot.

---

## 📅 21 de Maio de 2026: Preparação Enterprise e Ataques Massivos

### 6. Checkpoint de Automação e Banco de Dados (`f00dbfb`)
* **Descrição:** Avanço massivo no ecossistema de testes de estresse e persistência de dados.
* **Marcos:**
  * **SQLite:** O arquivo `spectre_history.db` surge pela primeira vez, indicando que o sistema agora persiste o histórico de alertas localmente.
  * **Testes de Estresse:** Vários scripts de nível de rede foram injetados em `scratch/` para simular tráfego malicioso real, como `raw_syn_flood.py`, `udp_flood.py`, e `loopback_syn_flood.py`.
  * **Atualização no eBPF:** `ebpf/spectre_xdp.c` e `loader_fusion.cpp` receberam quase 200 linhas de modificações em conjunto com o `dashboard_api.py` para sincronizar os dados dos ataques simulados.

### 7. Deploy Enterprise com Systemd (`afc116f` e `5350765`)
* **Descrição:** Transformação do projeto em um serviço contínuo de sistema Linux (*Daemon*).
* **Marcos:**
  * Criação do diretório `deploy/systemd/` contendo arquivos `.service` para separar os 3 módulos críticos: `spectre-api`, `spectre-fusion` (eBPF) e `spectre-web`.
  * Correção imediata dos caminhos (Rule of Thumb do WSL2) para apontar estritamente para o diretório nativo Linux (`~/ids-cnn-lstm-gnn`).
  * Adição de `install_services.sh` para automação.

---

## 🎯 Conclusão da Investigação
O projeto não é apenas um "script python", mas evoluiu rapidamente de uma prova de conceito (treino em arquivos textuais) para um **Sistema Enterprise Nativo Linux**, com simulações próprias de DDoS, comunicação ultra-rápida (IPC), persistência (SQLite), backend visual refinado contra sobrecargas (anti-aglomeração no Canvas) e infraestrutura de microserviços (Systemd).
