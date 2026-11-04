---
name: ebpf-feature-parity
description: Protocolo de paridade e verificação estrita entre o extrator eBPF/XDP no kernel C, o loader C++/Rust em userspace e as entradas da rede neural no SPECTRE-GRID.
---

# Skill: eBPF Feature Parity

Esta skill define as regras de consistência entre a observabilidade física de pacotes no kernel Linux (`ebpf/spectre_xdp.c`), a agregação de fluxos em userspace (`ebpf/loader_fusion_v2.cpp` / `loader_fusion_rs`) e o pré-processamento de datasets de benchmark (`preprocessor.py`).

## Quando Utilizar
- Ao adicionar novas features ao modelo ou avaliar compatibilidade com o sensor eBPF;
- Ao comparar resultados entre a **Modalidade A** (Benchmark Offline) e a **Modalidade B** (Sensor Estrito);
- Ao modificar `struct flow_metrics` em `ebpf/common.h` ou `derive_features()` em `loader_fusion_v2.cpp`;
- Ao redigir discussões sobre viabilidade de implantação em tempo real.

## As Duas Modalidades de Observação

### Modalidade A: `--feature_scope ebpf_compatible` (Benchmark Offline L3/L4)
- **Objetivo:** Estabelecer o limite superior de capacidade do modelo em dados de fluxo sem inspeção profunda de pacotes (DPI / L7).
- **Características:** Remove atributos de payload HTTP/FTP, mas permite métricas de fluxo bidirecional (`dttl`, `dwin`, `tcprtt`, `synack`, `ackdat`, `dmeansz`, `Dload`) e contadores históricos de 100 conexões (`ct_*`).
- **Limitação Conhecida:** Não pode ser calculada instantaneamente no primeiro pacote de ingresso no XDP, pois depende de pacotes de retorno da vítima para o atacante.

### Modalidade B: `--feature_scope ebpf_sensor_strict` (Sensor Operacional eBPF/XDP Unidirecional)
- **Objetivo:** Reproduzir com fidelidade 1:1 o que o hook XDP em *driver mode* consegue extrair de pacotes de ingresso (*ingress-only*).
- **Características:**
  - Remove **todas** as colunas de retorno reverso (`dst -> src`) e janelas de 100 conexões;
  - Utiliza apenas atributos de cabeçalho L3/L4 de entrada: `sttl`, `swin`, `sport`, `dsport`, `proto_tcp`, `proto_unas`, `state_INT`, `state_CON`;
  - Deriva taxas e contadores logarítmicos instantâneos exatamente como `loader_fusion_v2.cpp`:
    - `ebpf_log1p_sbytes = log1p(sbytes)`
    - `ebpf_log1p_spkts = log1p(Spkts)`
    - `ebpf_spkts_per_sec = Spkts / max(dur, 1e-6)`
- **Descoberta Científica:** A variante `cnn_lstm_gat` básica perde sensibilidade na Modalidade B, mas a variante **`gat_residual`** sustenta F1 > 0,91 com 100% de Recall e FPR de ~1,69%–2,25%, provando que conexões residuais compensam a ausência de atributos de retorno.

## Tabela de Mapeamento Kernel <-> Userspace <-> Modelo

| Feature | Campo em `spectre_xdp.c` | Campo em `loader_fusion_v2.cpp` | Normalização no Modelo |
| :--- | :--- | :--- | :--- |
| `sttl` | `iph->ttl` | `m.sttl = iph->ttl` | `StandardScaler` (treino) |
| `swin` | `tcph->window` | `m.swin = ntohs(tcph->window)` | `StandardScaler` (treino) |
| `sport` | `tcph/udph->source` | `m.sport = ntohs(...)` | `StandardScaler` (treino) |
| `dsport` | `tcph/udph->dest` | `m.dsport = ntohs(...)` | `StandardScaler` (treino) |
| `proto_tcp` | `iph->protocol == IPPROTO_TCP` | `feat[12] = is_tcp` | Binário One-Hot $\{0, 1\}$ |
| `sbytes` | Atômico `m->bytes += len` | `log1p(bytes)` | `StandardScaler` (treino) |
| `Spkts` | Atômico `m->packets++` | `log1p(packets)` | `StandardScaler` (treino) |

## Comandos de Verificação
```bash
# Verificar compilação do loader C++ e equivalência de features
python -c "from preprocessor import filter_features_by_observation_scope; import pandas as pd; df = pd.DataFrame({'sbytes': [100], 'Spkts': [5]}); df_b, _ = filter_features_by_observation_scope(df, 'ebpf_sensor_strict'); assert 'ebpf_log1p_sbytes' in df_b.columns"
```
