---
name: scientific-integrity
description: Protocolo de integridade científica, auditoria de alegações, rastreabilidade de evidências e taxonomia de validação no SPECTRE-GRID.
---

# Skill: Scientific Integrity

Esta skill rege a formulação, verificação e comunicação de quaisquer resultados e alegações científicas no projeto SPECTRE-GRID.

## Quando Utilizar
- Ao redigir ou revisar seções de manuscritos científicos (IEEE/IFIP NOMS, periódicos, TCC);
- Ao sintetizar resultados de experimentos neurais ou medições de kernel;
- Ao responder perguntas sobre o estado de maturidade ou eficácia do sistema;
- Sempre que houver suspeita de sobreajuste, extrapolação de conclusões ou fabricação de métricas.

## Princípios Obrigatórios
1. **Diferenciação Ontológica de Alegações:**
   - **[HIPÓTESE]**: Suposição teórica ainda não testada (ex.: "Atenção bidirecional deve mitigar a contaminação de nós receptores").
   - **[EVIDÊNCIA OBSERVADA]**: Dado bruto auditado diretamente em logs ou arquivos JSON (ex.: "Relatório `g15_gat_bidir_seed123_30s_report.json` registrou 12 FP e 4 FN").
   - **[INTERPRETAÇÃO]**: Dedução causal baseada em evidência empírica (ex.: "A reversão da aresta reduz FP em vítimas passivas porque o gradiente não propaga embeddings de ataque ao alvo").
   - **[RESULTADO VERIFICADO]**: Comprovado por múltiplas seeds, teste de sanidade automatizado e reprodução cruzada de hardware.
2. **Tolerância Zero a Métricas Fabricadas:** Nunca aproximar, simular ou inferir um resultado numérico sem tê-lo executado efetivamente no pipeline.
3. **Ponteiro de Evidência Mandatório:**
   Toda métrica mencionada no texto deve acompanhar:
   - Dataset e SHA-256;
   - Partição exata (ex.: `linhas 0 .. 120.000` de UNSW-NB15_1 ou `linhas 400.000 .. 600.000` de UNSW-NB15_2);
   - Semente (`seed`), Época e Hiperparâmetros;
   - Arquivo de origem em `data/processed/` e Commit Git.

## Procedimento de Auditoria de Alegações
1. Localizar o arquivo JSON bruto correspondente em `data/processed/`.
2. Validar se o hash SHA-256 do dataset confere com o arquivo de dados físico em disco.
3. Comparar a matriz de confusão (`TN, FP, FN, TP`) com a Precision, Recall, F1 e FPR calculados.
4. Confirmar que o modelo avaliado foi treinado sob `--val_only` se a métrica for usada para selecionar modelos.
5. Inspecionar ameaças à validade (desbalanceamento, vazamento temporal, viés de seleção de amostragem).

## Critérios de Reprovação (Red Flags)
- Afirmar que o holdout de teste está "intocado" se houve consultas prévias na fase exploratória;
- Declarar "detecção em tempo real comprovada em produção" baseando-se apenas em benchmarks locais de GPU;
- Generalizar desempenho medido na cauda 100% benigna como se demonstrasse capacidade de detecção de ataques novos.
