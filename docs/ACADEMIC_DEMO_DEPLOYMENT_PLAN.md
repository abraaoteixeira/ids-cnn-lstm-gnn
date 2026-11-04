# SPECTRE-GRID — PLANO DE IMPLANTAÇÃO E DEMONSTRAÇÃO ACADÊMICA REPRODUZÍVEL

> **Autor:** Abraão Teixeira da Silva  
> **Orientador:** Prof. Dr. Jackson Mallmann  
> **Projeto:** SPECTRE-GRID (NIDS/IPS Espaço-Temporal com eBPF/XDP e STGNN)  
> **Data:** Novembro de 2026  
> **Status:** Documento Estratégico de Engenharia e Demonstração Científica  

---

## 1. Visão Geral e Princípios Norteadores

O projeto SPECTRE-GRID concluiu com êxito a fase de consolidação científica, alcançando aprovação integral em esteiras automatizadas de auditoria anti-vazamento (*data leakage*), conciliação estrita de métricas multi-seed e sincronização do manuscrito para o **IEEE/IFIP NOMS 2027**.

O objetivo desta nova fase é **transformar os artefatos experimentais validados em uma demonstração acadêmica viva, tangível e cientificamente defensável**, permitindo que o orientador (Prof. Dr. Jackson Mallmann), bancas de avaliação (TCC/MICTI) e revisores de conferências internacionais inspecionem a inferência neural, a topologia gráfica dinâmica e a telemetria do sistema sem atritos de instalação.

### Princípios Inegociáveis da Demonstração:
1. **Verdade Científica e Transparência Ontológica:** Não caracterizar tráfego reproduzido ou injetado como se fosse captura física ao vivo; não afirmar descarte de pacotes no kernel (*line-rate drop*) quando o ambiente operacional não estiver instrumentado fisicamente em hardware de rede.
2. **Separação Categórica de Modos:** Diferenciação formal e visual na interface entre o **Modo A (Academic Replay)** e o **Modo B (Experimental Live)**.
3. **Acessibilidade Universal e Rigor de Infraestrutura:** Avaliação realista das opções de hospedagem, diferenciando plataformas estáticas gratuitas, requisitos de faturamento para contêineres dinâmicos, doações acadêmicas (grants), infraestrutura institucional e túneis efêmeros locais.

---

## 2. Estudo de Viabilidade de Infraestrutura e Plataformas de Hospedagem

Com base na documentação oficial atual do ecossistema de computação (em particular [Hugging Face Spaces Overview](https://huggingface.co/docs/hub/spaces-overview)), a viabilidade de cada ambiente é classificada abaixo:

| Plataforma / Ambiente | Modelo de Custo & Requisitos de Acesso | Requisitos de Hardware | Suporte ao Modo A (Replay) | Suporte ao Modo B (Live) | Veredito Estratégico |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Hugging Face Static Spaces** | **Gratuito e Público** (sem cartão de crédito) | Recursos de CDN estático (HTML/JS/WASM) | **Incompatível** (sem backend Python/PyTorch) | **Incompatível** (sem kernel/XDP) | **Apenas Frontend Estático:** Permite hospedar telas HTML/JS compiladas, mas é incapaz de executar inferência PyTorch ou manter websockets dinâmicos sem servidor externo. |
| **Hugging Face Docker / Gradio Spaces** | **Exige Verificação de Faturamento / Assinatura** (conforme política atual da HF para instanciar contêineres e alocar hardware CPU Basic) | 2 vCPUs, 16 GB RAM, 50 GB disco efêmero | **100% Compatível** (caso conta verificada) | **Incompatível** (sem kernel Linux/XDP nativo) | **Viabilidade Condicional:** A criação de novos Docker Spaces requer conta com verificação de método de pagamento ou subscrição ativa. Não deve ser anunciada como '100% gratuita permanente sem cartão'. |
| **Hugging Face Community Grants** | **Gratuito sob Concessão Acadêmica** (mediante formulário de submissão e aprovação manual por comitê da HF) | Instâncias de CPU ou GPU para pesquisa aberta | **100% Compatível** | **Incompatível** (sem kernel/XDP) | **Alternativa para Manuscrito/Paper:** Excelente para submissão formal de pesquisa aberta, porém sem garantia imediata de ativação para testes locais prévios. |
| **Infraestrutura Institucional (IFC Brusque / RNP)** | **Gratuito Institucional** (requer projeto e aprovação administrativa prévia) | Servidor Linux bare-metal ou VM KVM com interface de rede física | **100% Compatível** | **100% Compatível** (sob agendamento) | **Ambiente Recomendado para Validação com Orientador:** Ambiente controlado e definitivo para ensaios do Modo B com privilégios de kernel (`CAP_BPF`, `CAP_NET_ADMIN`) e acoplamento do XDP. |
| **Host Local + Túnel Seguro (Cloudflare Tunnel / ngrok)** | **100% Gratuito e Imediato** (instalação pontual de `cloudflared`) | Dell G15 ou estação de trabalho local com Python/Node | **100% Compatível** | **Parcialmente Compatível** (WSL2 veth / loopback) | **Solução Ideal para Apresentações Síncronas (Banca/Reuniões):** Gera URL temporária e segura via HTTPS (`*.trycloudflare.com`) durante a sessão de avaliação sem expor portas no roteador, mas dependente da máquina local ligada (não é hospedagem web 24/7 permanente). |
| **Testbeds Científicos Internacionais (Chameleon / CloudLab)** | **Gratuito para Pesquisa** (requer projeto aprovado) | Servidores bare-metal com SmartNICs (100G) | **Compatível** | **100% Compatível (Nível 5)** | **Mapeado como Trabalho Futuro:** Plataforma para ensaios de saturação de taxa de linha em periódico (IEEE TNSM). |

---

## 3. Especificação Técnica dos Modos de Demonstração

```
┌────────────────────────────────────────────────────────────────────────┐
│             ARQUITETURA DUAL-MODE DO SPECTRE-GRID                     │
├───────────────────────────────────┬────────────────────────────────────┤
│ MODO A — ACADEMIC REPLAY          │ MODO B — EXPERIMENTAL LIVE         │
│ (Web Pública / Avaliadores / NOMS)│ (Laboratório Linux / Banca TCC)    │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Dados: Snapshots auditados de   │ • Dados: Pacotes reais na placa    │
│   UNSW-NB15 (linhas 400k..600k)   │   de rede física (NIC driver)      │
│ • Motor: PyTorch CPU nativo       │ • Motor: Sensor C eBPF/XDP +       │
│   (modelo SPECTRE_GRID real)      │   Loader Fusion + PyTorch GPU/CPU  │
│ • IPC: Leitor de snapshots via    │ • IPC: RingBuffer de kernel e      │
│   Async Queue / TCP Socket        │   Unix Domain Socket (/tmp/sock)   │
│ • Mitigação: Simulação causal e   │ • Mitigação: Atualização de mapa   │
│   projeção de bloqueio na UI      │   BPF block_map com XDP_DROP real  │
│ • Banner na UI: SINALIZAÇÃO CLARA │ • Banner na UI: SINALIZAÇÃO LIVE   │
│   DE EVENTOS REPRODUZIDOS         │   COM CONTADORES DE KERNEL ATIVOS  │
└───────────────────────────────────┴────────────────────────────────────┘
```

### 3.1. Modo A — Academic Replay (Recomendado para Demonstração Web)
- **Fonte Canônica de Dados:** Recorte auditado de `UNSW-NB15_2.csv` (`linhas 400.000 .. 600.000`), contendo exatamente **32.550 ataques reais distribuídos em 226 snapshots temporais** ($\Delta t = 30\text{ s}$) e **8.598 nós comunicantes**.
- **Mecanismo Operacional:**
  1. O script `tools/academic_replay_player.py` carrega os dados pré-processados;
  2. A cada intervalo de reprodução (configurável entre 1s e 3s por snapshot temporal de 30s), o fatiador extrai o subgrafo $G_t = (V_t, E_t)$ e a matriz de atributos $X_t \in \mathbb{R}^{N_t \times 10 \times 20}$;
  3. Aplica o `StandardScaler` ajustado estritamente no treino de `UNSW-NB15_1` (`refitted_on_external = False`);
  4. Executa a inferência direta no modelo neural `SPECTRE_GRID` (checkpoint congelado `g15_cnn_lstm_gat_seed42_30s_best.pth` ou variante bidirecional);
  5. Extrai as probabilidades de intrusão e os coeficientes de atenção do `GATConv` via `forward_xai()`;
  6. Envia os eventos para a `dashboard_api_v2.py`, que os transmite via WebSocket para o frontend React;
  7. **Destaque Visual Transparente:** Um banner fixo no cabeçalho informa:  
     `MODO REPLAY ACADÊMICO: TRÁFEGO AUDITADO (UNSW-NB15) COM INFERÊNCIA NEURAL REAL EM CPU`.

### 3.2. Modo B — Experimental Live (Laboratório Físico / IFC)
- **Pré-requisitos Mandatórios:**
  - Sistema operacional Linux nativo com Kernel $\ge 5.15$;
  - Pacotes `clang`, `llvm`, `libbpf-dev`, `linux-headers-$(uname -r)`;
  - Placa de rede compatível com driver XDP (ou modo fallback `xdpgeneric`);
  - Privilégios administrativos de root (`sudo`).
- **Mecanismo Operacional:**
  1. O programa `ebpf/spectre_xdp.c` é compilado para bytecode BPF (`spectre_xdp.o`) e acoplado à interface física ativa;
  2. O motor `spectre_fusion` lê os eventos do `ringbuf` e exporta fluxos normalizados para o Unix Socket `/tmp/spectre.sock`;
  3. A inferência em tempo real processa os grafos e, detectado um nó atacante com probabilidade $p > 0,85$, executa chamada atômica `bpf_map_update_elem` na `block_map`;
  4. O filtro XDP passa a descartar fisicamente os pacotes subsequentes (`XDP_DROP`) no driver de rede;
  5. Contadores de hardware (`ethtool -S` e `bpftool map dump`) comprovam o descarte físico em tempo real.

---

## 4. Estratégia de Redesenho da Apresentação Científica Visual

### 4.1. Diagnóstico da Figura 1 Atual (`paper/noms2027/figures/fig1_spectre_architecture.pdf`)
A inspeção da versão preliminar gerada via Matplotlib identificou três vulnerabilidades metodológicas que exigem correção prévia à submissão definitiva:
1. **Ambiguidade na Seta de Mitigação:** A seta inferior rotulada *"Autonomous Mitigation: Dynamic XDP Drop via BPF Map Update"* conecta a saída do classificador neural diretamente ao bloco de kernel, sugerindo que o descarte físico foi medido em malha fechada durante os benchmarks offline (quando, na verdade, os benchmarks avaliaram a acurácia offline das Modalidades A e B).
2. **Falta de Diferenciação de Fluxos:** O diagrama atual não distingue graficamente o **Fluxo de Dados Primário** (pacotes $\to$ grafos $\to$ inferência), o **Fluxo de Apresentação/Telemetria** (eventos $\to$ WebSocket $\to$ Dashboard) e o **Fluxo de Controle de Mitigação** (bloqueio atômico em BPF map).
3. **Inconsistência de Tipografia Vetorial:** A renderização por retângulos simples do Matplotlib destoa dos padrões estéticos de publicações IEEE de alto impacto.

### 4.2. Especificação do Novo Modelo Vetorial (TikZ / SVG Programático)
Propõe-se a reconstrução integral da figura utilizando código vetorial estrito (TikZ ou SVG de alta precisão convertido para PDF vetorial), com largura exata de duas colunas (**$7,16\text{ polegadas} \approx 181,8\text{ mm}$**) e altura máxima de **$3,2\text{ polegadas}$**:

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                   FIGURA 1 REVISADA — ESPECIFICAÇÃO DE DESIGN IEEE                      │
├──────────────────────────┬─────────────────────────────┬─────────────────────────────────┤
│ PLANO 1: KERNEL INGRESS  │ PLANO 2: USERSPACE & STGNN │ PLANO 3: APRESENTAÇÃO & CONTROLE│
│ (eBPF / XDP Data Plane)  │ (Neural Inference Core)     │ (Dashboard & Closed-Loop IPS)   │
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────┤
│ • Ingress Packet Hook    │ • Causal Snapshot Slicer    │ • WebSocket Broadcast           │
│   (spectre_xdp.c)        │   G_t = (V_t, E_t), Δt=30s  │   (FastAPI Async Server)        │
│ • Flow Tracking Table    │ • Frozen Scaler (μ, σ)      │ • React NOC/SOC Dashboard       │
│   (BPF LRU Hash Map)     │ • 1D-CNN + Unidir LSTM (L10)│   (3D Graph Topology & XAI)     │
│ • RingBuffer Event Queue │ • GATConv (Bidir / Residual)│ • Mitigation Control Pathway    │
│ • Block Filter Map       │ • MLP Node Classifier       │   [DASHED LINE / PROPOSED LOOP] │
│   (BPF Hash Map)         │   y_t(v) ∈ {0, 1}           │   bpf_map_update_elem -> DROP   │
└──────────────────────────┴─────────────────────────────┴─────────────────────────────────┘
```

#### Convenções Gráficas Obrigatórias na Nova Figura:
1. **Linha Contínua Sólida (Preto/Cinza Escuro, 1.5pt):** *Fluxo de Dados Primário (Data Plane)* — Transmissão de pacotes, extração de features, montagem de snapshots $G_t$ e propagação direta na STGNN. Classificação ontológica: **`[COMPROVADO EXPERIMENTALMENTE EM BENCHMARK]`**.
2. **Linha Ponto-Traço Azul (Azul Escuro, 1.2pt):** *Fluxo de Telemetria e Monitoramento* — Exportação de tensores, predições e pesos de atenção para a interface web via WebSocket. Classificação ontológica: **`[PROTÓTIPO INTEGRADO FUNCIONAL]`**.
3. **Linha Tracejada Vermelha (Vermelho Carmim, 1.2pt, com rótulo explícito):** *Fluxo de Controle e Mitigação Ativa* — Atualização de mapas BPF para descarte no kernel. A legenda deverá declarar textualmente: *"Control pathway for autonomous in-kernel mitigation (validated in software integration; physical line-rate hardware evaluation subject to live testbed deployment)"*.
4. **Alinhamento Tipográfico IEEE:** Todas as fontes da figura serão configuradas em *Times New Roman* ou *Computer Modern*, em tamanhos 8pt a 9pt, garantindo perfeita harmonia com o texto corrido do manuscrito.

---

## 5. Roteiro de Demonstração Acadêmica (Script para Orientador e Bancas)

Tempo estimado total: **12 a 15 minutos**.

```
[00:00 - 03:00] ──> 1. Abertura e Regime de Repouso (Benign Tail: FPR < 0,6%)
[03:00 - 07:00] ──> 2. Injeção de Ataque Real (UNSW-NB15_2: Detecção Causal GAT)
[07:00 - 10:00] ──> 3. Mitigação Topológica e Proteção de Vítimas Passivas
[10:00 - 13:00] ──> 4. Transparência Científica, Auditoria de JSONs e eBPF
[13:00 - 15:00] ──> 5. Conclusões e Arguição da Banca
```

### Passo 1: Abertura e Estabilidade Operacional em Repouso (00:00 - 03:00)
- **Ação:** Abrir a dashboard no navegador (via host local ou túnel seguro);
- **Evidência Visual:** Apontar para o banner no topo confirmando:  
  `ACADEMIC REPLAY — INFERÊNCIA REAL SOBRE TRÁFEGO HISTÓRICO, SEM CAPTURA OU MITIGAÇÃO AO VIVO`;
- **Demonstração:** Executar a reprodução da cauda benigna auditada (667 snapshots temporais, 15.900 nós). Mostrar nos contadores e gráficos que o classificador opera em regime de repouso com baixa taxa de falsos positivos (FPR canônico de **$0,5723\%$**, correspondendo a exatamente **91 falsos positivos em 15.900 nós benignos**, com **15.809 verdadeiros negativos**). Deixar explícito que não se trata de ausência absoluta de falsos positivos, mas de uma taxa de falso alarme operacionalmente contida;
- **Argumento:** *"O SPECTRE-GRID demonstra estabilidade em tráfego puramente benigno, evitando o disparo massivo de alertas espúrios que tipicamente sobrecarregam operadores de SOC."*

### Passo 2: Detecção de Campanha Ativa e Mudança de Distribuição (03:00 - 07:00)
- **Ação:** Iniciar o recorte de linhas 400.000..600.000 de `UNSW-NB15_2.csv` (campanha real com 32.550 ataques);
- **Evidência Visual:** Observar na topologia gráfica os nós atacantes reais identificados em vermelho, com escore de atenção e probabilidade neural emitida pelo modelo;
- **Demonstração:** Clicar em um nó agressor real do dataset (ex.: `175.45.176.0` ou `175.45.176.2`, endereços confirmados do pool de ataque do UNSW-NB15) e exibir no painel lateral o volume de bytes, os fluxos correlacionados e a probabilidade calculada pela STGNN;
- **Argumento:** *"Mesmo sob severo concept drift temporal em uma captura de rede independente, a camada GAT bidirecional preserva F1 de $0,9167$, enquanto modelos sem grafo colapsam para $0,6773$."*

### Passo 3: O Ponto Crítico da Tese — Proteção de Vítimas Passivas (07:00 - 10:00)
- **Ação:** Selecionar um nó servidor/vítima passiva da rede interna (ex.: `149.171.126.1` ou `10.40.182.1`) que está recebendo múltiplos ataques direcionados na janela temporal;
- **Evidência Visual:** Mostrar que o nó da vítima permanece classificado como seguro/permitido (rótulo $y=0$, atenção de agressão contida), enquanto apenas o nó de origem malicioso recebe proposição de bloqueio;
- **Argumento Científico:** *"Aqui comprovamos empiricamente a tese central do SPECTRE-GRID: ao adotar rotulagem causal restrita à origem ($srcip$) combinada com passagem de mensagens bidirecional, evitamos que alvos benignos sofram contaminação de vizinhança. Em modelos direcionados tradicionais, o FPR dessas vítimas saltava para $6,51\%$; no SPECTRE-GRID com GAT bidirecional, o nó protegido permanece livre de bloqueio indevido."*

### Passo 4: Transparência Metodológica e Código do Sensor (10:00 - 13:00)
- **Ação:** Apresentar a separação ontológica entre a inferência neural da dashboard e o código do driver eBPF (`spectre_xdp.c`);
- **Evidência:** Demonstrar que o sistema não utiliza números simulados nem maquiados; abrir o arquivo JSON correspondente na pasta `data/processed/` comprovando a paridade exata de cada métrica exibida na tela com a auditoria de governança;
- **Argumento:** *"Toda e qualquer estatística visualizada nesta demonstração é estritamente rastreável a um checksum SHA-256 e a um relatório auditado no repositório público do projeto."*

---

## 6. Arquitetura de Implementação da Aplicação Web

Para viabilizar a implantação conteinerizada (Hugging Face Spaces ou servidor Docker Linux), o repositório adotará as seguintes melhorias técnicas prévias:

1. **Correção do Endpoint WebSocket no Frontend (`dashboard_v2/src/App.jsx`):**  
   Substituir a URL estática `ws://localhost:8001/ws/threats` por resolução dinâmica baseada no protocolo e host do navegador:
   ```javascript
   const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
   const wsUrl = `${protocol}//${window.location.host}/ws/threats`;
   const ws = new WebSocket(wsUrl);
   ```
2. **Build Estático Pré-Compilado (`dashboard_v2/dist/`):**  
   Executar `npm run build` para empacotar o bundle JS/CSS otimizado de produção, permitindo que a `dashboard_api_v2.py` o sirva diretamente via `StaticFiles` sem necessidade de Node.js em tempo de execução.
3. **Player Acadêmico Dedicado (`tools/academic_replay_player.py`):**  
   Implementar um script desacoplado que carrega snapshots pré-processados reais do `UNSW-NB15`, executa a inferência neural em CPU nativa e publica os registros no socket IPC da API em taxa ajustável.
4. **Dockerfile Otimizado para CPU Basic (Hugging Face Spaces):**  
   Container baseado em `python:3.11-slim`, instalando dependências mínimas (PyTorch CPU wheel, torch_geometric, pandas, fastapi, uvicorn), sem necessidade de CUDA ou compilação de bibliotecas de kernel.

---

## 7. Próximos Passos e Portão de Autorização

Conforme as diretrizes de governança permanente, as seguintes etapas dependem de aprovação explícita do usuário antes da execução:

- [ ] **Aprovação do Design da Figura 1:** Homologar a separação em 3 planos vetoriais antes de regenerar `fig1_spectre_architecture.pdf` e alterar o manuscrito LaTeX;
- [ ] **Autorização para Build do Frontend:** Executar a compilação do React 19 (`npm run build`) para gerar `dashboard_v2/dist/`;
- [ ] **Autorização para Publicação de Demonstração Web:** Criar o Space no Hugging Face (ou configurar o contêiner institucional) quando requisitado.

---
*Documento homologado em conformidade com o Quality Gate Permanente do SPECTRE-GRID.*  
*Branch de Trabalho:* `fix/leakage-free-pipeline`.
