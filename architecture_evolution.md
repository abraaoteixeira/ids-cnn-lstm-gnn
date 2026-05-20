# 🚀 Evolução Arquitetural SPECTRE_GRID

Este documento descreve as quatro fases de evolução arquitetural projetadas para levar o SPECTRE_GRID aos padrões de sistemas críticos de nível corporativo (equivalente às arquiteturas da Cloudflare e Fortinet).

---

## 📋 Matriz de Evolução Arquitetural

| Fase | Tecnologia Central | Foco de Melhoria | Status |
| :--- | :--- | :--- | :--- |
| **Fase 1** | Unix Domain Sockets (IPC) | Eliminação de I/O de disco no fluxo crítico em tempo real. | **EM EXECUÇÃO** |
| **Fase 2** | eBPF Ring Buffer (`BPF_MAP_TYPE_RINGBUF`) | Eliminar CPU Polling (transição para modelo orientado a eventos). | *Planejado* |
| **Fase 3** | Multi-Threading C++ (Data/Control Planes) | Isolar o loop de captura de pacotes da inferência de IA. | *Planejado* |
| **Fase 4** | D3-Force / WebGL Rendering (PixiJS) | Descarregar e otimizar a visualização de grafos sob estresse. | *Planejado* |

---

## 🔍 Detalhamento das Fases

### 1. Fase 1: Ingestão por Socket IPC em Memória (Fase Atual)
* **Como funciona hoje (Antes):**
  O motor C++ (`spectre_fusion`) grava as detecções em disco no arquivo `data/logs/spectre_alerts.jsonl`. A API FastAPI (`dashboard_api.py`) lê esse arquivo continuamente em loop usando `f.readline()` e `asyncio.sleep(0.1)`.
* **Como funcionará (Depois):**
  O arquivo físico de logs é removido do caminho crítico. O FastAPI cria um **Unix Domain Socket** em `/tmp/spectre.sock` e roda um servidor assíncrono. O C++ conecta-se a este socket Unix e transmite os alertas formatados em JSON diretamente na memória RAM.
* **Benefício Técnico (Porquê):**
  Elimina a latência física do disco rígido/SSD (queda de milissegundos para nanossegundos). Evita concorrência de leitura/escrita no arquivo e previne o buffering de escrita do SO, fazendo com que o dashboard reaja instantaneamente sem atraso ou "engasgos".

---

### 2. Fase 2: eBPF Ring Buffer
* **Como funciona hoje (Antes):**
  O espaço de usuário em C++ executa um loop de polling ativo (`sleep(1)`) chamando as funções do Libbpf (`bpf_map_get_next_key` e `bpf_map_lookup_elem`) para varrer todos os fluxos ativos registrados no kernel space.
* **Como funcionará (Depois):**
  Transição do mapa hash eBPF para um **BPF Ring Buffer** (`BPF_MAP_TYPE_RINGBUF`). Quando o kernel space intercepta uma anomalia ou fim de janela de pacotes, ele escreve um evento no Ring Buffer usando `bpf_ringbuf_output()`. O C++ fica em modo passivo escutando via `bpf_buffer__poll()`.
* **Benefício Técnico (Porquê):**
  Transição de um modelo de "Pull" (varredura ativa periódica) para "Push" (orientado a eventos em tempo real). Zera o uso desnecessário de CPU do daemon C++ quando a rede está silenciosa e responde no nanossegundo exato do disparo do alerta no driver de rede.

---

### 3. Fase 3: Multi-Threading no C++ (Separação de Planos)
* **Como funciona hoje (Antes):**
  O programa C++ roda de forma síncrona e sequencial em uma única thread principal: ler do eBPF ──► montar features ──► rodar IA (LibTorch) ──► atualizar bloqueio no kernel. A inferência de IA consome recursos de CPU/GPU e atrasa a leitura dos pacotes do eBPF.
* **Como funcionará (Depois):**
  Divisão estrita do motor em duas threads de execução:
  * **Thread A (Data Plane):** Apenas lê dados do kernel (ring buffer) e os empilha em uma fila segura em memória (`std::queue`).
  * **Thread B (Control Plane / IA):** Consome a fila assintoticamente, executa a inferência LibTorch (GNN) e injeta o IP bloqueado no `block_map` do kernel.
* **Benefício Técnico (Porquê):**
  Isola a coleta do tráfego de rede da latência de computação do modelo de IA (Deep Learning). Garante que nenhuma métrica de pacote seja perdida mesmo se a inferência sofrer latências temporárias.

---

### 4. Fase 4: Otimização do Grafo (D3-Force / WebGL)
* **Como funciona hoje (Antes):**
  A física do grafo (atração, repulsão de nós e gravidade) é calculada na thread principal do navegador usando código JavaScript puro em Canvas 2D. Quando há varreduras de portas rápidas (nmap), a quantidade de IPs/arestas cresce, derrubando o frame-rate (FPS) do navegador.
* **Como funcionará (Depois):**
  Substituir os loops manuais do `app.js` pela biblioteca matemática otimizada **D3-Force** (executando cálculos de layout em Web Workers paralelos) e usar um motor gráfico acelerado por GPU via WebGL (ex: **PixiJS** ou **Cytoscape.js**).
* **Benefício Técnico (Porquê):**
  Estabilidade geométrica do grafo (nós não sofrem *jittering* ou oscilação infinita) e renderização suave a 60 FPS estáveis mesmo com centenas de conexões simultâneas piscando no painel.
