# Original User Request

## Initial Request — 2026-07-12T21:52:18Z

# Teamwork Project Prompt

Realizar uma auditoria profunda em todo o repositório (código e arquivos markdown) para identificar inconsistências, extrair informações de novos estudos (como pesquisas sobre múltiplos datasets e o DBVA), e atualizar o estado documental e arquitetural do projeto.

Working directory: ~/ids-cnn-lstm-gnn
Integrity mode: development

## Requirements

### R1. Auditoria Exaustiva de TODOS os Arquivos
O time DEVE iterar e inspecionar **absolutamente todos** os arquivos e diretórios do repositório (excluindo apenas pastas binárias/dependências padrão como `.git`, `node_modules` e `.venv_wsl`). Nenhuma pasta de código (`ebpf`, `dashboard_v2`, `docs`, `data`) ou arquivo de configuração deve ser ignorada. O cruzamento de dados deve ser exaustivo entre implementações em C++, Python, React e os arquivos Markdown.

### R2. Consolidação de Datasets
Analisar os arquivos `.md` e os arquivos no diretório `data/` (como o DBVA) e integrar as descobertas aos arquivos de controle de estado (ex: `project_state.md`, `project_overview.md`), preparando o terreno teórico para o futuro retreino do modelo.

## Acceptance Criteria

### Verificação Objetiva (Agent-as-judge e Artefatos)
- [ ] Um relatório de auditoria (`audit_report.md`) deve ser gerado na raiz detalhando ao menos 3 achados objetivos de inconsistência estrutural ou técnica.
- [ ] O arquivo `project_state.md` deve conter uma nova seção explicitando a estratégia de integração do dataset DBVA-2025 e outros datasets recentemente estudados.
- [ ] Nenhuma linha de código fonte deve ser modificada ou apagada sem estar embasada por uma falha de consistência explícita encontrada.
