# 🎓 PLANO DE DEFESA DO TCC — SPECTRE_GRID
**Instituto Federal Catarinense (IFC) — Campus Brusque**  
**Trabalho de Conclusão de Curso em Tecnologia da Informação**  
**Orientador: [Nome do Orientador]**  
**Candidato: Abraã Oteixeira**  
**Data: Junho/2026**

---

## 1. RESUMO EXECUTIVO DA DEFESA

### Tema do Trabalho
**"SPECTRE_GRID: Sistema de Detecção de Intrusões em Tempo Real baseado em Redes Neurais Gráficas Espaço-Temporais e eBPF/XDP"**

### Contexto
Sistema de detecção de intrusões (IDS) híbrido que combina:
- **Kernel-space processing** via eBPF/XDP (latência <1μs)
- **Deep Learning** com STGNN (F1=0.9856)
- **Real-time ensemble** (STGNN + heurístico)
- **Validação em produção** (2.939 eventos reais capturados)

### Objetivo Geral
Desenvolver um sistema de detecção de intrusões de alta performance capaz de identificar movimentações laterais, varreduras de porta e ataques automatizados em tempo real, integrando processamento no kernel com inteligência artificial.

### Objetivos Específicos
1. ✅ Implementar sensor eBPF/XDP para captura de pacotes em kernel-space
2. ✅ Treinar modelo STGNN em dataset CIC-IDS2017 com F1>0.98
3. ✅ Construir ensemble heurístico para compensar limitações do modelo
4. ✅ Validar em ambiente de produção com honeypot real
5. ✅ Demonstrar detecção de ataques reais (SSH brute force, port scanning)
6. ✅ Documentar limitações (concept drift) e soluções futuras

---

## 2. CRONOGRAMA DA DEFESA

### 2.1 Preparação (Semana 1 — Próximas 5 dias)

| Data | Atividade | Responsável | Entrega |
|------|-----------|-------------|---------|
| **01/06** | Consolidar documentação completa | Candidato | ✅ FEITO |
| **02/06** | Criar gráficos honeypot (5 charts) | Candidato | Matplotlib |
| **03/06** | Exportar diagrama arquitetura (SVG) | Candidato | PowerPoint |
| **04/06** | Integrar texto "Concept Drift" no TCC | Candidato | Documento final |
| **05/06** | Ensaiar apresentação | Candidato | Feedback orientador |

### 2.2 Defesa (Data TBD)

| Horário | Atividade | Duração |
|---------|-----------|---------|
| 00:00 | Apresentação da banca | 5 min |
| 05:00 | Apresentação do candidato | 20 min |
| 25:00 | Demonstração ao vivo do sistema | 10 min |
| 35:00 | Perguntas da banca | 15 min |
| 50:00 | Respostas do candidato | 10 min |

---

## 3. ESTRUTURA DA APRESENTAÇÃO (20 minutos)

### Slide 1: Título
```
SPECTRE_GRID
Sistema de Detecção de Intrusões em Tempo Real
Baseado em Redes Neurais Gráficas Espaço-Temporais

Abraã Oteixeira | IFC Brusque | 2026
```

### Slide 2: Motivação
```
Por que este trabalho?

❌ IDSs tradicionais (Snort/Suricata) usam regras estáticas
❌ Não detectam padrões anomalias zero-day
❌ Latência alta (10-50μs)
✅ Solução: Machine Learning + Kernel Acceleration
```

### Slide 3: Arquitetura (Diagrama Mermaid SVG)
```
VPS (eBPF) → WireGuard → WSL (GNN) → FastAPI → React
  <1μs           AES-256       50-200ms    WebSocket  Real-time
```

### Slide 4: Modelo STGNN
```
Arquitetura:
- CNN1D: extrai padrões temporais
- LSTM: captura dependências de longo prazo
- GATv2Conv: message passing topológico (IP graph)
- Classificador: binary threat/benign

Resultado: F1=0.9856
```

### Slide 5: Features (20 features)
```
Tabela resumida:
- dst_port, is_SSH, is_RDP, is_scan
- packet_count, PPS, inter_arrival_time
- port_entropy, unique_ports
- is_private_ip, active_flows
... [total 20]
```

### Slide 6: Ensemble Decisor
```
Duas camadas independentes:

STGNN (Neural Network)
  ↓
max() → Probabilidade Final
  ↓
Heurístico (SSH/RDP/Scan Rules)

Se prob > 0.70 → BAN_IP no kernel
```

### Slide 7: Validação em Produção
```
Honeypot Real (31/05 - 01/06/2026)

📊 2.939 eventos capturados
🌍 39 IPs únicos de 9 países
🇧🇷 SSH Brute Force: Palhoça-SC
  (177.5.130.126, 419 tentativas/30s)
✅ Taxa de detecção: 55.2%
✅ Falsos positivos: 1.2%
```

### Slide 8: Distribuição Geográfica (Gráfico)
```
[Pie Chart]
USA: 73.9% (Google/Fastly)
Brasil: 14.3% (SSH attack)
Unknown: 10.3%
Others: <2%
```

### Slide 9: Top 10 Ataques (Gráfico)
```
[Bar Chart]
1. 74.125.69.95     (636 eventos)
2. 142.250.152.95   (565 eventos)
3. 177.5.130.126 ⚠️ (419 eventos) SSH BF
...
```

### Slide 10: Limitações & Concept Drift
```
Problema: Modelo treinou em CIC-IDS2017 (fluxo fechado)
          Sensor eBPF captura per-pacote (online)
          Resultado: distribuições divergem

Impacto: F1 lab = 98.56%, produção = 55.2%

Compensação: Ensemble heurístico (documentado)

Solução futura: Retreinar com NF-UQ-NIDS-v2
               Resultado esperado: 90%+
```

### Slide 11: Trabalhos Futuros
```
Curto Prazo (1-2 semanas):
  [ ] Retreinamento NF-UQ-NIDS-v2 (4-8h GPU)
  [ ] E2E automated tests
  [ ] WSL auto-startup

Médio Prazo (1-3 meses):
  [ ] High availability (multi-region)
  [ ] Application-level detection (WAF)
  [ ] XAI visualization

Longo Prazo:
  [ ] Production hardening
  [ ] Log rotation & backup
  [ ] Distributed sensor network
```

### Slide 12: Contribuições do Trabalho
```
✅ Primeiro IDS com STGNN + eBPF/XDP integrado
✅ Validação em produção real (honeypot)
✅ Ensemble heurístico que funciona
✅ Documentação completa de conceito drift
✅ Codebase pronto para publicação
✅ Datasets reais capturados (2939 eventos)
```

### Slide 13: Conclusão
```
Sistema em produção 24/7
Pronto para pesquisa & desenvolvimento futuro
Ferramenta open-source para comunidade de segurança
```

---

## 4. DEMONSTRAÇÃO AO VIVO (10 minutos)

### 4.1 Setup
```bash
# Terminal 1: Verificar sensor eBPF
$ sudo journalctl -u spectre-sensor -f
[Output mostrando pacotes sendo capturados]

# Terminal 2: Dashboard React
$ cd dashboard_v2
$ npm run dev
[Browser abrindo http://localhost:5173]

# Terminal 3: Simular ataque (opcional)
$ python3 stress_test.py
[Enviando pacotes maliciosos]
```

### 4.2 Demo 1: Dashboard em Tempo Real
```
Mostrar:
1. Globo 3D com arcos animados de ataques
2. Grafo de IPs (force-directed layout)
3. Tabela de top IPs atacantes
4. KPIs: total ameaças, nós ativos, latência
5. Logo IFC no header
```

### 4.3 Demo 2: Dados Reais do Honeypot
```
Abrir honeypot_real_attacks.jsonl no VS Code

Mostrar eventos reais:
- SSH brute force (177.5.130.126)
- Timestamps
- GeoIP (Brazil → Palhoça-SC)
- Probabilidade do ensemble
```

### 4.4 Demo 3: Performance
```
Mostrar metrics:
- Uptime VPS: 99.8%
- Latência kernel: <1μs (eBPF)
- Latência GNN: 50-200ms
- WebSocket: <500ms end-to-end
- Taxa detecção: 55.2%
- Falsos positivos: 1.2%
```

---

## 5. POSSÍVEIS PERGUNTAS DA BANCA

### Pergunta 1: Por que concept drift não foi resolvido?
**Resposta:**
"O concept drift é uma consequência da escolha do dataset de treinamento (CIC-IDS2017), que calcula features após o fechamento do fluxo TCP. Isso é documentado na literatura (Engelen et al. 2021). Nossa abordagem foi compensar com ensemble heurístico (1.2% false positive) enquanto mantemos produção estável. Para eliminá-lo permanentemente, o trabalho futuro é retreinar com NF-UQ-NIDS-v2, que usa NetFlow v9 — compatível com captura eBPF em tempo real. Estimamos 4-8 horas em GPU para isso."

### Pergunta 2: Qual é a inovação principal?
**Resposta:**
"A combinação STGNN + eBPF/XDP é inédita. Enquanto Snort/Suricata operam em user-space com latência 10-50μs, nosso XDP atua em kernel com <1μs. Enquanto detectores tradicionais usam regras, o STGNN aprende padrões topológicos via message passing em grafos de IP. E validamos em ambiente real (não apenas lab), capturando 2.939 eventos em 24h."

### Pergunta 3: Como você valida a efetividade?
**Resposta:**
"Usamos três métricas: (1) F1-score em lab (0.9856 em CIC-IDS2017), (2) taxa de detecção em produção (55.2% com ensemble compensando concept drift), e (3) análise dos eventos reais do honeypot (2939 eventos, 39 IPs, 9 países). O ataque mais grave foi SSH brute force origináio de Palhoça-SC (419 tentativas em 30s) — 100% detectado com confiança 0.99."

### Pergunta 4: Qual é o custo de operação?
**Resposta:**
"Zero. O sistema roda em GCP free tier (e2-micro VPS), WSL2 é grátis no Windows 11, e todas as dependências (PyTorch, FastAPI, React) são open-source. O único custo é internet. Para escalar (multi-region), estimamos ~$50/mês em GCP."

### Pergunta 5: Por que não usar Snort/Suricata ao invés de desenvolver?
**Resposta:**
"Snort/Suricata são baseados em regras (padrões conhecidos). Não detectam anomalias zero-day. Além disso, queremos demonstrar a viabilidade de integrar ML + Kernel acceleration — isso é pesquisa. O SPECTRE_GRID é prova de conceito que funciona em produção."

---

## 6. MATERIAIS DA APRESENTAÇÃO

### 6.1 Arquivos Necessários
```
apresentacao.pptx
  ├── Slide 1-13 (conforme acima)
  ├── Gráfico: honeypot distribuição geográfica
  ├── Gráfico: top 10 IPs
  ├── Gráfico: timeline de ataques
  ├── Diagrama: arquitetura STGNN
  └── Diagrama: pipeline completo (SVG)

video-demo.mp4 (opcional)
  ├── Screen recording do dashboard
  ├── Mostrando ataque em tempo real
  └── Duração: 2-3 minutos

honeypot_events.csv
  ├── Export de honeypot_real_attacks.jsonl
  ├── 2939 linhas
  └── Columns: timestamp, src_ip, country, port, prob
```

### 6.2 Documentos Impressos (opcional)
```
1. README.md (projeto)
2. project_state.md (status final)
3. MASTER_DOCUMENTATION.md (referência)
4. Seção "Concept Drift" do TCC (1-2 páginas)
```

---

## 7. CHECKLIST FINAL PRÉ-DEFESA

### 1 Dia Antes
```
[ ] Revisar todos os slides
[ ] Testar demo ao vivo (dashboard + honeypot)
[ ] Confirmar que VPS está rodando
[ ] Confirmar que WSL está funcional
[ ] Imprimir cópias da apresentação
[ ] Carregar laptop + power bank
[ ] Testar projetor (HDMI/USB-C)
[ ] Testar áudio/microfone
```

### Dia da Defesa
```
[ ] Chegar 15 min antes
[ ] Setup projetor & laptop
[ ] Fazer teste de som
[ ] Abrir slides em full-screen
[ ] Terminal SSH pronto (se precisar)
[ ] Browser com dashboard aberto (new tab)
[ ] Água & documentos em mãos
[ ] Respirar fundo
```

---

## 8. TIMELINE REAL DA EXECUÇÃO

### Cronograma Realista (Próximas 2 Semanas)

```
SEMANA 1 (Próximos 7 dias):
 MON 01/06: Consolidar docs (FEITO)
 TUE 02/06: Gerar gráficos honeypot
 WED 03/06: Exportar diagrama SVG
 THU 04/06: Integrar texto TCC
 FRI 05/06: Ensaiar apresentação
 SAT 06/06: Ajustes finais
 SUN 07/06: Descanso

SEMANA 2:
 MON 08/06: Entrega final TCC [IF REQUIRED]
 TUE-FRI: Agendamento da banca
 [Data da defesa: TBD]
```

---

**Documento Preparado: 01/06/2026 | Status: Pronto para Defesa**
