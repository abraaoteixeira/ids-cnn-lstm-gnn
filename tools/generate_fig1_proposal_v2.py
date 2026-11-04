#!/usr/bin/env python3
"""
tools/generate_fig1_proposal_v2.py

Gera a proposta revisada da Figura 1 vetorial (SVG e PDF) para o manuscrito IEEE/IFIP NOMS 2027.
Apresenta formalmente a separação entre:
  1. Data Plane (eBPF/XDP Ingress no Kernel);
  2. Neural Inference Core (STGNN em Userspace);
  3. Presentation & Closed-Loop Control Plane (Dashboard e Feedback de Mitigação).

Conformidade IEEE:
- Largura: 7.16 polegadas (largura exata de duas colunas);
- Altura: 3.1 polegadas;
- Tipografia: Serifada (Times New Roman / Computer Modern);
- Convenção de linhas:
  * Linha contínua sólida: Fluxo primário de dados [Validado em Benchmark];
  * Linha ponto-traço azul: Telemetria e visualização [Protótipo Integrado];
  * Linha tracejada vermelha: Malha de mitigação autônoma no kernel [Integração de Software].
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROPOSALS_DIR = REPO_ROOT / "paper" / "noms2027" / "figures" / "proposals"
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)


def build_fig1_v2():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "Liberation Serif", "serif"],
        "font.size": 8.0,
        "axes.labelsize": 8.0,
        "text.usetex": False,
    })

    fig, ax = plt.subplots(figsize=(7.16, 3.15), dpi=300)
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(-3, 38)

    # -------------------------------------------------------------------------
    # Paleta de Cores e Estilos
    # -------------------------------------------------------------------------
    bg_p1 = "#F0F7FF"   # Kernel Data Plane (azul claro sutil)
    edge_p1 = "#2563EB"
    
    bg_p2 = "#FBF8F3"   # Neural Core (âmbar claro sutil)
    edge_p2 = "#D97706"

    bg_p3 = "#F3FAF7"   # Presentation & Control (verde claro sutil)
    edge_p3 = "#059669"

    box_fill = "#FFFFFF"
    box_edge = "#475569"

    # =========================================================================
    # PLANO 1: DATA PLANE (Linux Kernel eBPF / XDP)
    # =========================================================================
    p1_rect = patches.FancyBboxPatch(
        (1.5, 3.5), 26.5, 31.0,
        boxstyle="round,pad=0.6",
        facecolor=bg_p1,
        edgecolor=edge_p1,
        linewidth=1.2,
        linestyle="-"
    )
    ax.add_patch(p1_rect)
    ax.text(14.75, 32.5, "PLANE 1: DATA PLANE", ha="center", va="center", weight="bold", color="#1E3A8A", fontsize=8.2)
    ax.text(14.75, 30.7, "(Linux Kernel eBPF / XDP)", ha="center", va="center", color="#3B82F6", fontsize=7.2, style="italic")

    # Ingress Packet Hook
    ax.add_patch(patches.FancyBboxPatch((3.5, 23.0), 22.5, 5.8, boxstyle="square,pad=0.3", facecolor=box_fill, edgecolor=box_edge, linewidth=0.8))
    ax.text(14.75, 26.7, "spectre_xdp.c (NIC Ingress)", ha="center", va="center", weight="bold", fontsize=7.4)
    ax.text(14.75, 24.5, "L2-L4 Packet Hook & Feature Extr.", ha="center", va="center", color="#64748B", fontsize=6.5)

    # Flow Table & Filter Map
    ax.add_patch(patches.FancyBboxPatch((3.5, 14.5), 22.5, 6.8, boxstyle="square,pad=0.3", facecolor=box_fill, edgecolor=box_edge, linewidth=0.8))
    ax.text(14.75, 19.3, "BPF Maps (State & Filtering)", ha="center", va="center", weight="bold", fontsize=7.4)
    ax.text(14.75, 17.2, "• flow_table (LRU Hash Map)\n• block_map (Atomic IP Filter)", ha="center", va="center", color="#334155", fontsize=6.5)

    # RingBuffer Event Queue
    ax.add_patch(patches.FancyBboxPatch((3.5, 5.5), 22.5, 7.2, boxstyle="square,pad=0.3", facecolor=box_fill, edgecolor=box_edge, linewidth=0.8))
    ax.text(14.75, 10.3, "BPF RingBuffer Queue", ha="center", va="center", weight="bold", fontsize=7.4)
    ax.text(14.75, 8.0, "Lockless Telemetry Export\n(Kernel -> Userspace RingBuffer)", ha="center", va="center", color="#64748B", fontsize=6.5)

    # Seta interna no kernel
    ax.annotate("", xy=(14.75, 21.3), xytext=(14.75, 23.0), arrowprops=dict(arrowstyle="->", lw=1.0, color="#1E293B"))
    ax.annotate("", xy=(14.75, 12.7), xytext=(14.75, 14.5), arrowprops=dict(arrowstyle="->", lw=1.0, color="#1E293B"))

    # =========================================================================
    # PLANO 2: NEURAL INFERENCE CORE (Userspace & STGNN)
    # =========================================================================
    p2_rect = patches.FancyBboxPatch(
        (31.5, 3.5), 37.0, 31.0,
        boxstyle="round,pad=0.6",
        facecolor=bg_p2,
        edgecolor=edge_p2,
        linewidth=1.2,
        linestyle="-"
    )
    ax.add_patch(p2_rect)
    ax.text(50.0, 32.5, "PLANE 2: NEURAL INFERENCE CORE", ha="center", va="center", weight="bold", color="#92400E", fontsize=8.2)
    ax.text(50.0, 30.7, "(C++ Loader & PyTorch / PyG STGNN)", ha="center", va="center", color="#D97706", fontsize=7.2, style="italic")

    # Snapshot Slicer & Preprocessor
    ax.add_patch(patches.FancyBboxPatch((33.5, 23.0), 33.0, 5.8, boxstyle="square,pad=0.3", facecolor=box_fill, edgecolor=box_edge, linewidth=0.8))
    ax.text(50.0, 26.7, "Causal Snapshot Slicer & Frozen Scaler", ha="center", va="center", weight="bold", fontsize=7.4)
    ax.text(50.0, 24.5, "G_t = (V_t, E_t), Δt=30s | Top-20 Pearson Features", ha="center", va="center", color="#64748B", fontsize=6.5)

    # 1D-CNN + LSTM Block
    ax.add_patch(patches.FancyBboxPatch((33.5, 14.5), 33.0, 6.8, boxstyle="square,pad=0.3", facecolor=box_fill, edgecolor=box_edge, linewidth=0.8))
    ax.text(50.0, 19.3, "Spatial-Temporal Feature Extractor", ha="center", va="center", weight="bold", fontsize=7.4)
    ax.text(50.0, 17.2, "• 1D-CNN: Local Temporal Profiling\n• Unidir LSTM: L=10 Time-Series Memory", ha="center", va="center", color="#334155", fontsize=6.5)

    # GATConv + Classifier Block
    ax.add_patch(patches.FancyBboxPatch((33.5, 5.5), 33.0, 7.2, boxstyle="square,pad=0.3", facecolor=box_fill, edgecolor=box_edge, linewidth=0.8))
    ax.text(50.0, 10.3, "Graph Attention & Classification", ha="center", va="center", weight="bold", fontsize=7.4)
    ax.text(50.0, 8.0, "• GATConv (K=4 Heads, Bidir Message Passing)\n• MLP Classifier: y_t(v) in {0, 1} (Attack vs Benign)", ha="center", va="center", color="#334155", fontsize=6.5)

    # Setas internas no core neural
    ax.annotate("", xy=(50.0, 21.3), xytext=(50.0, 23.0), arrowprops=dict(arrowstyle="->", lw=1.0, color="#1E293B"))
    ax.annotate("", xy=(50.0, 12.7), xytext=(50.0, 14.5), arrowprops=dict(arrowstyle="->", lw=1.0, color="#1E293B"))

    # =========================================================================
    # PLANO 3: PRESENTATION & CLOSED-LOOP CONTROL
    # =========================================================================
    p3_rect = patches.FancyBboxPatch(
        (72.0, 3.5), 26.5, 31.0,
        boxstyle="round,pad=0.6",
        facecolor=bg_p3,
        edgecolor=edge_p3,
        linewidth=1.2,
        linestyle="-"
    )
    ax.add_patch(p3_rect)
    ax.text(85.25, 32.5, "PLANE 3: PRESENTATION & CONTROL", ha="center", va="center", weight="bold", color="#065F46", fontsize=8.2)
    ax.text(85.25, 30.7, "(FastAPI Server & React SOC Dashboard)", ha="center", va="center", color="#059669", fontsize=7.2, style="italic")

    # FastAPI WebSocket Server
    ax.add_patch(patches.FancyBboxPatch((74.0, 23.0), 22.5, 5.8, boxstyle="square,pad=0.3", facecolor=box_fill, edgecolor=box_edge, linewidth=0.8))
    ax.text(85.25, 26.7, "FastAPI Async Gateway", ha="center", va="center", weight="bold", fontsize=7.4)
    ax.text(85.25, 24.5, "WebSocket Fan-Out & aiosqlite Log", ha="center", va="center", color="#64748B", fontsize=6.5)

    # React NOC/SOC Dashboard
    ax.add_patch(patches.FancyBboxPatch((74.0, 14.5), 22.5, 6.8, boxstyle="square,pad=0.3", facecolor=box_fill, edgecolor=box_edge, linewidth=0.8))
    ax.text(85.25, 19.3, "React NOC/SOC Dashboard", ha="center", va="center", weight="bold", fontsize=7.4)
    ax.text(85.25, 17.2, "• 3D Dynamic Graph Topology\n• Live XAI Attention Weights HUD", ha="center", va="center", color="#334155", fontsize=6.5)

    # Autonomous Mitigation Policy
    ax.add_patch(patches.FancyBboxPatch((74.0, 5.5), 22.5, 7.2, boxstyle="square,pad=0.3", facecolor=box_fill, edgecolor=box_edge, linewidth=0.8))
    ax.text(85.25, 10.3, "Mitigation Policy Decision", ha="center", va="center", weight="bold", color="#B91C1C", fontsize=7.4)
    ax.text(85.25, 8.0, "If P(v) >= 0.85 -> Propose Block Rule\nAtomic bpf_map_update_elem", ha="center", va="center", color="#334155", fontsize=6.5)

    # Setas internas no presentation/control
    ax.annotate("", xy=(85.25, 21.3), xytext=(85.25, 23.0), arrowprops=dict(arrowstyle="->", lw=1.0, color="#1E293B"))
    ax.annotate("", xy=(85.25, 12.7), xytext=(85.25, 14.5), arrowprops=dict(arrowstyle="->", lw=1.0, color="#1E293B"))

    # =========================================================================
    # CONEXÕES INTER-PLANOS (CONVENÇÃO DE LINHAS FORMAL)
    # =========================================================================

    # 1. Fluxo de Dados Primário (Data Plane): Kernel RingBuffer -> Userspace Preprocessor
    # Linha Contínua Preta (1.4pt)
    ax.annotate(
        "", xy=(33.5, 25.9), xytext=(26.0, 9.1),
        arrowprops=dict(arrowstyle="->", lw=1.4, color="#0F172A", connectionstyle="arc3,rad=-0.15")
    )
    ax.text(29.5, 19.5, "Flow Events\n(Telemetry)", ha="center", va="center", fontsize=6.5, color="#0F172A", weight="bold")

    # 2. Fluxo de Telemetria e Apresentação: Neural Core -> FastAPI Gateway
    # Linha Ponto-Traço Azul (1.3pt)
    ax.annotate(
        "", xy=(74.0, 25.9), xytext=(66.5, 9.1),
        arrowprops=dict(arrowstyle="->", lw=1.3, color="#2563EB", linestyle="dashdot", connectionstyle="arc3,rad=-0.15")
    )
    ax.text(70.5, 19.5, "Predictions &\nAttn Weights", ha="center", va="center", fontsize=6.5, color="#2563EB", weight="bold")

    # 3. Fluxo de Controle e Mitigação em Malha Fechada: Decision -> BPF block_map
    # Linha Tracejada Vermelha Carmim (1.3pt)
    ax.annotate(
        "", xy=(26.0, 16.5), xytext=(74.0, 9.1),
        arrowprops=dict(arrowstyle="->", lw=1.4, color="#DC2626", linestyle="dashed", connectionstyle="arc3,rad=0.22")
    )
    ax.text(50.0, 2.0, "Autonomous Closed-Loop Mitigation: Atomic BPF Map Update (XDP_DROP)", ha="center", va="center", fontsize=7.2, color="#DC2626", weight="bold")

    # =========================================================================
    # LEGENDA CIENTÍFICA NO RODAPÉ
    # =========================================================================
    leg_y = -2.2
    # Legenda 1: Solid
    ax.plot([4.0, 9.0], [leg_y, leg_y], color="#0F172A", lw=1.5, linestyle="-")
    ax.text(9.8, leg_y, "Primary Data Plane Flow [Empirically Validated in Offline Benchmark]", ha="left", va="center", fontsize=6.5, color="#1E293B")

    # Legenda 2: Dashdot
    ax.plot([49.0, 54.0], [leg_y, leg_y], color="#2563EB", lw=1.3, linestyle="dashdot")
    ax.text(54.8, leg_y, "Telemetry & Visualization Flow [Functional Integrated Prototype]", ha="left", va="center", fontsize=6.5, color="#1E3A8A")

    # Legenda 3: Dashed Red
    ax.plot([79.0, 84.0], [leg_y, leg_y], color="#DC2626", lw=1.4, linestyle="dashed")
    ax.text(84.8, leg_y, "Closed-Loop Control Pathway*", ha="left", va="center", fontsize=6.5, color="#991B1B")

    # Salvar nos formatos vetoriais requisitados
    svg_out = PROPOSALS_DIR / "fig1_spectre_architecture_v2.svg"
    pdf_out = PROPOSALS_DIR / "fig1_spectre_architecture_v2.pdf"
    png_out = PROPOSALS_DIR / "fig1_spectre_architecture_v2.png"

    fig.savefig(svg_out, bbox_inches="tight")
    fig.savefig(pdf_out, bbox_inches="tight")
    fig.savefig(png_out, bbox_inches="tight", dpi=300)
    plt.close(fig)

    print(f"[OK] Proposta da Figura 1 gerada com sucesso:")
    print(f"  - SVG: {svg_out}")
    print(f"  - PDF: {pdf_out}")
    print(f"  - PNG: {png_out}")


if __name__ == "__main__":
    build_fig1_v2()
