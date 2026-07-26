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

## Follow-up — 2026-07-12T22:38:00Z

# Teamwork Project Prompt

O time de agentes autônomos irá consolidar todo o conhecimento gerado sobre o projeto SPECTRE GRID em um único "Livro Base" educacional. O material deve usar uma lógica pedagógica progressiva ("tijolinhos"), partindo do zero até os conceitos mais avançados.

Working directory: ~/ids-cnn-lstm-gnn
Integrity mode: development

## Requirements

### R1. Formato de Entrega
Criar um único arquivo Markdown gigante chamado `docs/SPECTRE_LIVRO_BASE.md` contendo todos os capítulos.

### R2. Lógica Progressiva ("Tijolinhos")
O conteúdo deve ser estruturado pedagogicamente. Deve iniciar assumindo conhecimento zero (explicando o básico de redes e kernel) e construir o entendimento passo a passo até chegar nas tecnologias avançadas (eBPF, Redes Neurais em Grafo Espaço-Temporais, Message Passing, Concept Drift).

### R3. Escopo de Conteúdo
O livro deve integrar e unificar os conceitos das 6 macro-areas envolvidas no projeto:
1. Engenharia de SO e Kernel (eBPF/XDP vs TCP/IP clássico).
2. Redes de Computadores Avançadas (dissecação de fluxo).
3. Cibersegurança (Movimentação Lateral, Zero-Trust).
4. Inteligência Artificial (CNN, LSTM, GATConv).
5. Engenharia de Dados (DBVA, CIC-IDS2017, Concept Drift).
6. Integração de Software (C++ e IPC Sockets).

## Acceptance Criteria

### Verificação Objetiva (Agent-as-Judge)
Um agente auditor independente deve revisar o arquivo `docs/SPECTRE_LIVRO_BASE.md` contra a seguinte rubrica:
- [ ] O arquivo foi criado no caminho correto.
- [ ] O texto segue uma progressão lógica, definindo conceitos fundamentais *antes* de utilizá-los em explicações complexas.
- [ ] As 6 macro-áreas exigidas no R3 possuem subcapítulos ou seções dedicadas e detalhadas no documento.

## Follow-up — 2026-07-15T01:01:00Z

O time de agentes autônomos irá varrer o repositório para limpar resquícios locais, criar a infraestrutura IaC (Ansible) completa para o SPECTRE GRID, e desenvolver a integração de bloqueio via API para firewall pfSense.

Working directory: c:\Users\Abraão\Documents\projects\ids-cnn-lstm-gnn

## Requirements

### R1. Limpeza e IaC (Ansible)
Varrer o projeto para limpar caminhos locais absolutos do Windows. Criar playbooks Ansible (`deploy/ansible/spectre_deploy.yml`) para instalar dependências nativas (Clang, LLVM, Node.js, Python), baixar a LibTorch, compilar o motor C++ v2 e habilitar os serviços via Systemd.

### R2. Integração pfSense (Defesa de Borda)
Criar uma integração acionável (módulo Python ou shell) para que o C++ ou o FastAPI possam bloquear IPs maliciosos diretamente no roteador pfSense (via API, SSH ou XML-RPC), não apenas no eBPF local.

### R3. Dockerização Completa
Você deve criar o `Dockerfile` para o backend FastAPI e o frontend React (usando Nginx), além do `docker-compose.yml` para orquestrar tudo. O motor C++ eBPF deve rodar no host (devido a permissões de kernel), mas deve se comunicar com os containers Docker via volumes mapeados para os Sockets Unix.

## Acceptance Criteria

### Infraestrutura
- [ ] Nenhum caminho absoluto `C:/Users/...` existe no código de inicialização.
- [ ] O playbook Ansible passa no `syntax-check`.

### Integração pfSense
- [ ] O código da integração pfSense inclui documentação e testes mockados mostrando o envio correto do IP para a blocklist do firewall.

## Follow-up — 2026-07-15T16:52:13Z

# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Create a continuous realistic traffic generator service (Bash) that runs in the background of WSL to feed the SPECTRE GRID eBPF engine during live demonstrations.

Working directory: ~/teamwork_projects/spectre_traffic_gen
Integrity mode: demo

## Requirements

### R1. Minimal Bash Traffic Generator
Crie um script Bash simples, leve e sem dependências pesadas que execute comandos básicos de rede (como `ping` e `curl`) em loop infinito. O script não deve realizar ataques reais de brute-force, apenas tráfego benigno para gerar volume de leitura na placa de rede.

### R2. Inicialização Automática Integrada
O script deve ser inicializado automaticamente sempre que o usuário ligar o motor do SPECTRE GRID (via `start_engine_real.ps1` ou `start_spectre_v2.sh`), e deve ser encerrado automaticamente (sem deixar processos zumbis) quando o servidor for desligado.

## Acceptance Criteria

### Functional
- [ ] O script principal é escrito puramente em Bash e usa apenas binários nativos do Linux (`curl`, `ping`, `sleep`).
- [ ] O script é inicializado em background sem travar o terminal principal durante a execução do motor.
- [ ] Quando o `start_engine_real.ps1` é encerrado com CTRL+C, o script de tráfego correspondente no WSL é finalizado (nenhum processo `curl` ou `bash` do gerador permanece rodando).
