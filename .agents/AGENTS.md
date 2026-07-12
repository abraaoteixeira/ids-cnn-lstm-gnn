# Regras e Contexto do Projeto (SPECTRE GRID)

## Contexto do Projeto
- **Nome:** SPECTRE GRID
- **Descrição:** Sistema de Detecção e Prevenção de Intrusão (IDS/IPS) híbrido baseado em eBPF/XDP e Inteligência Artificial Gráfica Espaço-Temporal (STGNN).
- **Tecnologias:** eBPF/XDP (C), Motor de Fusão (C++/Rust), STGNN (PyTorch/Python), Painel de Controle (React/Vite, FastAPI).
- **Autor/Pesquisador:** Abraão Teixeira da Silva.
- **Orientador:** Prof. Dr. Jackson Mallmann.

## Geração de Documentos ABNT
- A conversão de Markdown para PDF usando pacotes Node tradicionais (como `md-to-pdf`) pode travar no ambiente Windows/PowerShell deste projeto devido a dependências mal resolvidas do Chromium.
- **Estratégia Definitiva:** Sempre gerar documentos TCC formatados em ABNT criando um arquivo HTML customizado com CSS específico para paginação e formatação (`@page { margin: 3cm 2cm 2cm 3cm; }`). 
- Os diagramas Mermaid devem ser incluídos importando o script nativo no `<head>`.
- Para compilar o PDF final, utilize um script Node puro (`build_pdf_abnt.js`) instanciando o `puppeteer` de forma programática (sempre usando a flag `--no-sandbox` nas opções de *launch*).
