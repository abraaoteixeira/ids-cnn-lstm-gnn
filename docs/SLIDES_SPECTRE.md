---
marp: true
paginate: true
style: |
  @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;700&family=Outfit:wght@300;500;800&display=swap');
  
  section {
    background-color: #0b0f19;
    color: #94a3b8;
    font-family: 'Outfit', sans-serif;
    background-image: radial-gradient(circle at 50% 0%, #1e293b 0%, transparent 70%);
    font-size: 28px;
  }
  
  h1, h2, h3 {
    color: #f8fafc;
    font-weight: 800;
    letter-spacing: -0.05em;
  }
  
  h1 {
    font-size: 2.2em;
    background: -webkit-linear-gradient(45deg, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5em;
  }
  
  h2 {
    color: #38bdf8;
    border-bottom: 1px solid #1e293b;
    padding-bottom: 10px;
  }
  
  strong {
    color: #e2e8f0;
    font-weight: 800;
  }
  
  em {
    color: #f43f5e; /* Vermelho Cybersec para destaque de ameaças */
    font-style: normal;
    font-weight: 800;
  }
  
  code {
    font-family: 'Fira Code', monospace;
    background: #0f172a;
    color: #34d399; /* Verde Neon */
    padding: 0.1em 0.3em;
    border-radius: 4px;
    border: 1px solid #1e293b;
  }
  
  pre {
    background: #05080f !important;
    border: 1px solid #334155;
    box-shadow: 0 10px 30px rgba(0,0,0,0.8);
    border-radius: 8px;
    padding: 1em;
  }
  
  blockquote {
    border-left: 4px solid #f43f5e;
    background: rgba(244, 63, 94, 0.05);
    padding: 1em;
    border-radius: 0 8px 8px 0;
    color: #cbd5e1;
    font-style: italic;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    background: #0f172a;
    border-radius: 8px;
    overflow: hidden;
  }
  
  th {
    background: #1e293b;
    color: #38bdf8;
    text-align: left;
    padding: 12px;
  }
  
  td {
    padding: 10px 12px;
    border-bottom: 1px solid #1e293b;
    color: #cbd5e1;
  }

  /* Classe Customizada para a Capa */
  section.capa {
    text-align: center;
    background-image: radial-gradient(circle at 50% 50%, #172554 0%, #0b0f19 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
  }
  section.capa h1 {
    font-size: 3.5em;
    background: -webkit-linear-gradient(45deg, #f43f5e, #818cf8, #38bdf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.1em;
  }
  section.capa h3 {
    color: #94a3b8;
    font-weight: 300;
  }
  section.capa .subtitle {
    color: #34d399;
    font-family: 'Fira Code', monospace;
    font-size: 0.8em;
    margin-top: 2em;
    letter-spacing: 0.1em;
  }
---

<!-- _class: capa -->

<h1>SPECTRE GRID</h1>
<h3>Defesa Ativa no Kernel contra Ameaças Modernas</h3>

<div class="subtitle">
> eBPF | STGNN | XDP | C++ Fusion Engine
<br>Abraão Teixeira da Silva — IFC Brusque
</div>

---

# 1. A Agonia do Firewall Tradicional
O que acontece num servidor corporativo durante um ataque de **DDoS (SYN Flood)**?

```bash
# top -d 1
%Cpu(s):  0.5 us, 99.0 sy,  0.0 ni,  0.0 id,  0.0 wa,  0.0 hi, 0.5 si
  PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND
   12 root      20   0       0      0      0 R  99.9  0.0   5:32.41 ksoftirqd/0
```

O `iptables` puxa pacote por pacote para o *User Space*.
O servidor gasta 100% da CPU apenas tentando **ler** o ataque para poder bloquear. 
> *A rede cai não porque o ataque passou, mas porque o porteiro desmaiou de exaustão.*

---

# 2. A Fundação: Cirurgia no Kernel
Nós descemos o nível. Fomos para o **Kernel Space**.

O **eBPF** (Extended Berkeley Packet Filter) nos permite injetar código C compilado *diretamente no driver da placa de rede* (NIC). 

Não há TCP/IP Stack. Não há alocação de memória do SO (sk_buff). 
Nós interceptamos a corrente elétrica no cabo de rede e tomamos a decisão.

---

# 3. O Escudo (Latência de Nanossegundos)
Este é o código real no Kernel (`spectre_xdp.c`) que derruba as ameaças:

```c
SEC("xdp")
int spectre_xdp_hook(struct xdp_md *ctx) {
    // 1. Intercepta o IP antes de existir pro Linux
    __u32 *is_blocked = bpf_map_lookup_elem(&block_map, &src_ip);
    
    if (is_blocked) {
        // 2. Drop físico imediato. Custo: ~12 nanossegundos.
        return XDP_DROP; 
    }
    return XDP_PASS;
}
```
A máquina pode receber 10 milhões de pacotes maliciosos por segundo, e a CPU continua em **1%**.

---

# 4. A Falha da IA Linear
Legal, o escudo é invencível. **Mas quem ele deve bloquear?**

IAs de cibersegurança tradicionais analisam *IP por IP*.
- **IP 192.168.1.10:** Tentou SSH. (Parece normal)
- **IP 192.168.1.11:** Tentou SMB. (Parece normal)

Mas e se esses dois IPs forem zumbis mapeando silenciosamente a rede ao mesmo tempo? Uma IA linear que olha linhas isoladas de CSV *nunca* vai detectar o padrão.

---

# 5. O Inimigo: Movimentação Lateral
Ameaças como Ransomware e *Advanced Persistent Threats* (APTs) não quebram a porta da frente. Eles entram por um phishing, infectam o PC da secretária, e começam uma **Movimentação Lateral** de fininho até o Banco de Dados.

> Como uma IA detecta um ataque que está distribuído no Tempo e no Espaço Físico da rede?
> 
> *Resposta: Trocando as linhas do Excel por um Grafo Geométrico.*

---

# 6. A Rede como um Grafo
Se o ataque é relacional, nossa matemática precisa ser relacional.
Bem-vindos à **STGNN (Space-Temporal Graph Neural Network)**.

Convertemos o tráfego de rede vivo em um grafo:
- **Nós:** Endereços IP (Atacantes e Vítimas).
- **Arestas:** Conexões ativas e métricas (Pacotes, Bytes, Flags).

*Deixamos de olhar para o indivíduo e passamos a olhar para o ecossistema.*

---

# 7. O Cérebro Híbrido (Pipeline STGNN)
Tensor de Entrada: `[Nós Ativos, Histórico 10 Segundos, 20 Features]`

1. **CNN-1D:** Varre a série temporal de 10s extraindo picos (ex: rajada de *SYN*).
2. **LSTM (Memória Longa):** Lembra o comportamento crônico do IP.
3. **GATv2Conv (Message Passing):** Onde a mágica acontece. Os IPs "conversam" entre si matematicamente, calculando *Pesos de Atenção*.

Se um nó vizinho sofre port-scan, toda a rede entra em alerta simultâneo.

---

# 8. O Paradoxo dos Dados (Concept Drift)
Treinamos a STGNN com o dataset **CIC-IDS2017**. Deu F1-Score de **99%**.
Fomos para a nuvem testar, a IA errou tudo. *Por quê?*

**Laboratório (CICFlowMeter):** Computa features apenas *após a conexão fechar*.
**Mundo Real (eBPF):** Computa features para *cada pacote no ar*.

As distribuições estatísticas eram fundamentalmente diferentes. Isso é o pesadelo da IA de produção: o *Concept Drift*.

---

# 9. O Mundo Real: Operação Honeypot
Para curar o Concept Drift, trouxemos a guerra para nós.
Subimos uma VPS na Google Cloud (`34.172.18.46`), abrimos a porta 22 e coletamos ataques ao vivo via eBPF.

| Estatística (2 dias) | Valor |
|----------------------|-------|
| Eventos Capturados | **2.939** |
| IPs Atacantes Únicos | 39 |
| Maior Ataque | 419 tentativas SSH em 30s (Brasil/SC) |
| Ameaças (Prob > 0.8) | 624 eventos |

*Nós sangramos na nuvem para coletar os dados reais de treinamento.*

---

# 10. O Motor de Fusão (A Cola C++)
Não podemos rodar o Pytorch Python tradicional lendo arquivos, seria lento demais.
Construímos um daemon nativo em **C++17**:

```cpp
// Leitura Lockless em O(1) direto da RAM do Kernel
while (ring_buffer->poll()) {
    // 1. Dynamic Graph Batching (Constrói a matriz de IPs vivos)
    auto graph = builder.build_edge_index();
    
    // 2. Welford Online Z-Score (Normaliza sem depender de disco)
    auto tensor = normalizer.process(features);
    
    // 3. LibTorch C++ Inference (Milissegundos)
    float threat_level = spectre_model.forward(tensor, graph);
}
```

---

# 11. O Dashboard: Explainable AI (XAI)
O motor C++ processa a IA e despacha um JSON via **Unix Socket** (Zero I/O de Disco) para um servidor **FastAPI / React**.

**O que o Dashboard exibe ao vivo a 60FPS:**
1. **Grafo D3-Force WebGL:** Bolinhas verdes e vermelhas se conectando dinamicamente.
2. **Globo 3D Geográfico:** Arcos cruzando o planeta das origens dos ataques.
3. **HUD de Atenção GNN:** Gráficos mostrando *exatamente* quais pesos matemáticos a GATConv usou para decidir bloquear um IP (*Explainable AI*).

---

# 12. Onde a Tropa Entra? (Próximos Passos)
O motor C++ (Fusion), o escudo (eBPF) e a IA (GNN) estão prontos e rodando.
**O que precisamos do time agora:**

1. **Retreino Urgente:** Acabar com o *Concept Drift* migrando para os datasets **DBVA-2025** e **NF-UQ-NIDS-v2**.
2. **Engenharia de Dados:** Otimizar o pré-processador (`preprocessor.py`) e expandir as *Top-20 Features*.
3. **Escrita/Pesquisa:** Gerar métricas em tabelas e ajudar a fechar as teses arquiteturais no Livro Base.

---

<!-- _class: capa -->

<h1>INICIAÇÃO</h1>
<h3>O código fonte já está aberto.</h3>

<div class="subtitle">
> GitHub: abraaoteixeira/ids-cnn-lstm-gnn <br>
> Perguntas?
</div>
