# CONSTITUIÇÃO OPERACIONAL E GOVERNANÇA CIENTÍFICA (SPECTRE-GRID)

> **Princípio Central Inegociável:**  
> *"Nenhuma afirmação científica sem evidência rastreável; nenhuma alteração crítica sem validação; nenhum resultado definitivo sem revisão independente."*

Este documento é a fonte de autoridade principal para qualquer agente de inteligência artificial (Antigravity, Claude Code, Cursor, Copilot ou scripts autônomos) operando no repositório `ids-cnn-lstm-gnn`. Suas regras são obrigatórias, permanentes e universais em todas as sessões.

---

## 1. Contexto do Projeto
- **Nome:** SPECTRE-GRID
- **Domínio:** Sistema de Detecção e Prevenção de Intrusão em Redes (NIDS/IPS) híbrido baseado em eBPF/XDP de alta velocidade e Redes Neurais Gráficas Espaço-Temporais (STGNN).
- **Repositório:** `abraaoteixeira/ids-cnn-lstm-gnn` | **Branch de Trabalho Atual:** `fix/leakage-free-pipeline` (a branch `main` é protegida).
- **Pesquisador Principal:** Abraão Teixeira da Silva | **Orientador:** Prof. Dr. Jackson Mallmann.

---

## 2. Os 9 Pilares da Governança Permanente

### I. Integridade Científica Absoluta
- **Proibição de Fabricação:** Jamais inventar, extrapolar ou aproximar métricas, matrizes de confusão, tempos de inferência, contagens de pacotes ou referências bibliográficas.
- **Diferenciação Ontológica Obrigatória:** O agente deve classificar explicitamente todo conteúdo técnico como:
  1. *Hipótese Teórica* (suposição a ser testada);
  2. *Evidência Observada* (dado empírico ou log de terminal verificado);
  3. *Interpretação* (análise de causa e efeito sustentada por dados);
  4. *Resultado Verificado* (comprovado por testes repetíveis e aprovados).
- **Sem Falsos Finais:** Registros legados como `VICTORY CONFIRMED` em arquivos de handoff antigos nunca devem ser assumidos como validação do estado atual sem nova verificação empírica.

### II. Rastreabilidade Extrema (Zero Métricas Órfãs)
Toda métrica, tabela ou figura apresentada em relatórios ou artigos deve conter ponteiro explícito para:
- Caminho e Checksum SHA-256 do dataset utilizado;
- Partição cronológica exata (ex.: `linhas 0 .. 120.000`);
- Semente de aleatoriedade (`seed`), número de épocas e tamanho de janela temporal ($\Delta t = 30\text{ s}$);
- Checkpoint neural versionado (ex.: `g15_cnn_lstm_gat_seed42_30s_best.pth`);
- Commit Git de referência (`git rev-parse --short HEAD`);
- Relatório JSON bruto original em `data/processed/`.

### III. Prevenção Incondicional de *Data Leakage*
- **Isolamento Causal em Snapshots:** Grafos $G_t = (V_t, E_t)$ preservam apenas eventos observados estritamente na janela $[t, t + \Delta t)$. Informações futuras jamais contaminam representações passadas.
- **Ajuste Exclusivo no Treino:** `StandardScaler` ($\mu_{\text{train}}, \sigma_{\text{train}}$), vocabulário One-Hot e seleção de atributos (Top-K Pearson) são calculados **estritamente** na partição de treino (`linhas 0 .. 120.000`). Em validação, teste ou datasets externos, aplica-se apenas `.transform()` (`refitted_on_external = False`).
- **Rotulagem Direcional Causal:** Um nó $v \in V_t$ recebe rótulo de atacante ($y_t(v) = 1$) se, e somente se, originou ao menos um fluxo malicioso na janela (`srcip`). Vítimas benignas alvejadas passivamente (`dstip`) permanecem com $y_t(v) = 0$.
- **Proteção do Teste Reservado (Holdout):** É terminantemente proibido utilizar o conjunto de teste para seleção de hiperparâmetros, escolha de variantes arquiteturais ou Early Stopping. Em fases de exploração e ablação, a opção `--val_only` é **obrigatória**. Todo acesso prévio ao teste deve ser documentado com transparência.

### IV. Reprodutibilidade e Consciência de Hardware
- **Registro de Ambiente:** Registrar sempre OS, versão do Python, PyTorch, PyG, CUDA e modelo exato de GPU.
- **Não-Determinismo de GPU Conhecido:** Reconhecer que operações atômicas paralelas na GPU (`scatter_add` em `GATConv`) e diferenças de microarquitetura CUDA (ex.: RTX 3050 Ampere vs. Tesla T4 Turing) introduzem pequenas variações em ponto flutuante ($\Delta \text{F1} \sim \pm 0,01$). O critério de reprodutibilidade é a invariância da hierarquia de modelos e convergência estável.

### V. Confiabilidade Operacional e Separação de Escopos
Não confundir nem equiparar os 5 níveis de maturidade técnica do SPECTRE-GRID:
1. *Nível 1 — Teste Unitário Sintético:* Validação de coerência lógica em dados artificiais (ex.: `tests/test_leakage_free_pipeline.py`);
2. *Nível 2 — Benchmark Offline L3/L4 (Modalidade A):* Avaliação de modelos sobre datasets rotulados estáticos (`--feature_scope ebpf_compatible`);
3. *Nível 3 — Simulação e Injeção Local:* Tráfego gerado via sockets ou scripts de replay (ex.: `continuous_flow_generator.py`);
4. *Nível 4 — Sensor Operacional eBPF/XDP Estrito (Modalidade B):* Extração unidirecional de ingresso no kernel Linux em tempo de pacote (`--feature_scope ebpf_sensor_strict`);
5. *Nível 5 — Implantação Real em Produção:* Inspeção contínua em enlace físico com mitigação em tempo real (exige ensaios reais com tráfego ao vivo).

### VI. Segurança e Preservação de Ativos
- **Proteção de Segredos:** Jamais gravar credenciais, chaves SSH, senhas ou tokens de API em arquivos commitáveis.
- **Imutabilidade Histórica:** Nunca sobrescrever checkpoints de modelos pré-existentes nem apagar dados legados sem autorização explícita do usuário. Se necessário refatorar, arquivar em `legacy/` ou com sufixo `_old`.

### VII. Controle Estrito de Alterações
- Toda nova implementação deve ser desenvolvida em branch isolada, validada pela suíte de testes automáticos e inspecionada via `git diff` antes de ser comitada.
- Commits devem seguir Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).

### VIII. Transparência nos Relatórios de Progresso
Em todo relatório de encerramento de tarefa, cada item de entrega deve ser classificado em um dos seguintes status formais:
- `IMPLEMENTADO`: Código escrito e estruturado;
- `TESTADO`: Passou por validações funcionais/unitárias automatizadas;
- `VALIDADO EXPERIMENTALMENTE`: Validado com métricas empíricas reproduzíveis e logs auditados;
- `DOCUMENTADO`: Registrado na memória científica, documentação ou artigo;
- `PENDENTE`: Planejado mas não iniciado;
- `BLOQUEADO`: Impedido por dependência externa ou restrição técnica.

### IX. Autonomia Responsável e Portões de Autorização
- **Autonomia Total:** Executar pesquisas, leituras, testes locais, cálculos estatísticos, correções de código, compilações de LaTeX/Typst e geração de figuras sem pedir confirmações redundantes.
- **Portões de Bloqueio (Exigem Autorização do Usuário):**
  1. Submeter Pull Requests ou mesclar código na branch `main`;
  2. Submeter artigos ou manuscritos a portais de conferências (EDAS, JEMS);
  3. Deletar arquivos estruturais ou dados brutos;
  4. Executar operações destrutivas de rede ou banco de dados.

---

## 3. Catálogo de Agent Skills Especializadas
O agente deve consultar e aplicar as skills disponíveis em `.agents/skills/`:
- [`scientific-integrity`](.agents/skills/scientific-integrity/SKILL.md): Princípios de validação de hipóteses, integridade de evidências e auditoria de alegações científicas.
- [`dataset-leakage-audit`](.agents/skills/dataset-leakage-audit/SKILL.md): Protocolos anti-leakage, auditoria de normalizadores congelados e isolamento causal de partições temporais.
- [`reproducible-training`](.agents/skills/reproducible-training/SKILL.md): Treinamento multi-seed PyTorch/PyG, gestão de checkpoints, recuperação de falhas e paridade de hardware.
- [`ebpf-feature-parity`](.agents/skills/ebpf-feature-parity/SKILL.md): Compatibilidade estrita entre `spectre_xdp.c`, `loader_fusion_v2.cpp`, features do dataset e inferência neural.
- [`model-evaluation`](.agents/skills/model-evaluation/SKILL.md): Avaliação estatística, ablações de topologia/direcionalidade, FPR em repouso e generalização sob concept drift.
- [`ieee-paper-writing`](.agents/skills/ieee-paper-writing/SKILL.md): Redação formal de manuscritos IEEE, formatação de tabelas rastreáveis e figuras de publicação.
- [`experiment-review`](.agents/skills/experiment-review/SKILL.md): Revisão por pares independente de execuções antes de atestar conclusões científicas.

---

## 4. Ciclo Obrigatório de Execução de Tarefas
1. **Antes da Execução:** Mapear objetivo, inspecionar estado real do código/dados, ler skills relevantes e planejar passos verificáveis.
2. **Durante a Execução:** Preservar arquivos existentes, registrar evidências no terminal, verificar logs de erro e respeitar limites de autorização.
3. **Após a Execução:** Rodar testes automáticos (`pytest tests/`), inspecionar `git diff`, atualizar a memória científica (`docs/SCIENTIFIC_MEMORY.md`) e emitir relatório taxonômico.
