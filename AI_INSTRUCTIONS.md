# Instruções do Sistema para Inteligência Artificial (AI_INSTRUCTIONS)

## Contexto do Projeto
- **Nome:** Spectre / IDS-CNN-LSTM-GNN (Projeto de Pesquisa PVE2957-2025 - IFC Campus Brusque)
- **Natureza:** Projeto **Acadêmico de Pesquisa** (não focar em ser "nível industrial/comercial", o foco é inovação, performance técnica, experimentação e validação científica).
- **Autor/Pesquisador:** O projeto foi construído principalmente pelo autor, focado em aplicar Deep Learning e GNNs para Detecção de Intrusão em Redes (IDS).

## Regras de Comportamento e Edição de Código
1. **NUNCA DELETAR NADA:** Arquivos antigos, códigos legados ou experimentais nunca devem ser excluídos. Se precisar refatorar ou substituir algo, mova o código antigo para pastas como `legacy/`, `static_legacy/` ou adicione o sufixo `_old`.
2. **Preservar Histórico:** Manter comentários, docstrings e arquivos que mostrem a evolução do projeto (Fase 1 até Fase 4).
3. **Foco Técnico:** O sistema possui uma Arquitetura V2 avançada envolvendo:
   - Captura de pacotes: **eBPF/XDP** e Ring Buffers.
   - Processamento de alto desempenho: Daemons em **C++** (ou Rust/Go) multithreaded.
   - Inferência: **LibTorch** (C++) se comunicando via Unix Sockets (IPC) com FastAPI.
   - Frontend: Dashboard em WebGL.
4. **Ambiente:** O desenvolvimento ocorre no **Windows**, mas o alvo de implantação/execução (especialmente para eBPF/XDP e Sockets Unix) é **Linux / WSL2**. Testes e builds nativos linux exigem o ambiente WSL2.
5. **Comunicação:** Seja direto, técnico e aja como um parceiro de pair programming do pesquisador.

## Instrução para Novas Sessões da IA
Ao iniciar uma nova sessão ou um novo chat, se a IA se sentir perdida, instrua-a a ler este arquivo (`AI_INSTRUCTIONS.md`), o `README.md` e o `project_overview.md`.
