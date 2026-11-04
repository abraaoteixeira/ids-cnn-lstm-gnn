---
name: ieee-paper-writing
description: Diretrizes de redação, formatação em LaTeX IEEEtran, geração de figuras vetoriais e integridade bibliográfica para submissões IEEE/IFIP.
---

# Skill: IEEE Paper Writing

Esta skill orienta a produção de manuscritos científicos de alto impacto para conferências do IEEE/IFIP (como o NOMS 2027), assegurando conformidade com templates oficiais e padrões internacionais de publicação.

## Quando Utilizar
- Ao redigir ou editar arquivos `.tex` (ex.: `paper/noms2027/main.tex`);
- Ao gerar figuras e tabelas de resultados para publicação;
- Ao compilar bibliografia em `references.bib`;
- Ao auditar o manuscrito antes de submeter para revisão do orientador.

## Regras de Estrutura e Formatação
1. **Template Oficial:** Utilizar a classe `\documentclass[conference]{IEEEtran}` com duas colunas, fonte 10pt e dimensões padrão.
2. **Figuras de Qualidade Gráfica:**
   - Salvar figuras simultaneamente em PDF vetorial (`.pdf`) e bitmap de alta densidade (`.png` a 300 DPI);
   - Largura máxima para coluna simples: `3.5 in` (~`88 mm`);
   - Largura máxima para duas colunas (estendida): `7.16 in` (~`182 mm`);
   - Fontes e legendas legíveis em 8–9pt, sem serrilhamento.
3. **Tabelas Científicas Rastreáveis:**
   - Todas as tabelas devem reportar médias e desvios padrão ($\mu \pm \sigma$) entre seeds independentes;
   - Destacar em negrito os melhores resultados estatisticamente comprovados;
   - Evitar truncar casas decimais arbitrariamente (padronizar 4 casas decimais para F1/Precision/Recall e 2 para porcentagens de FPR).
4. **Integridade da Bibliografia (`references.bib`):**
   - **Tolerância Zero a Alucinação Bibliográfica:** Toda referência deve corresponder a um artigo real, indexado no IEEE Xplore, ACM DL, SpringerLink, arXiv ou USENIX;
   - Conferir autores, título, conferência/periódico, ano e DOI/URL.

## Seções Obrigatórias do Manuscrito NOMS
- **Title & Abstract:** Conciso (< 250 palavras), contextualizando o problema, a proposta, a contribuição e as evidências quantitativas.
- **I. Introduction:** Motivação, limitações dos modelos tabulares tradicionais, o desafio da heterofilia em redes e resumo das contribuições.
- **II. Related Work:** NIDS com Deep Learning, Graph Neural Networks em segurança e o estado da arte em aceleração eBPF/XDP.
- **III. SPECTRE-GRID Architecture:** Detalhamento do pipeline fim-a-fim (Kernel, Userspace, Core Neural).
- **IV. Experimental Methodology:** Formalização matemática dos snapshots $G_t=(V_t,E_t)$, causalidade estrita, horizonte ativo de 200k e rotulagem direcional.
- **V. Results and Ablation Study:** Comparação das 6 variantes arquiteturais, análise de heterofilia e benchmark de latência em GPU.
- **VI. Independent External Evaluation:** Resultados em `UNSW-NB15_2.csv` sob concept drift temporal.
- **VII. Discussion & Kernel Feasibility:** Mapeamento de atributos e viabilidade da Modalidade B em XDP ingress.
- **VIII. Threats to Validity:** Reconhecimento transparente de limitações metodológicas e operacionais.
- **IX. Conclusion & Future Work.**

## Portão de Bloqueio de Submissão
- **NUNCA submeter o manuscrito autonomamente.** A submissão via EDAS/JEMS é sempre um ato exclusivo do autor/orientador após revisão e aprovação formal.
