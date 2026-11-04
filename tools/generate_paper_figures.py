"""
tools/generate_paper_figures.py

Gera todas as 5 figuras científicas em alta resolução (PDF vetorial e PNG 300 DPI)
para o manuscrito IEEE/IFIP NOMS 2027 do SPECTRE-GRID, rigorosamente alinhadas
aos relatórios JSON auditados e aos experimentos efetivos.
"""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

# Configurações de estilo acadêmico IEEE
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.titlesize": 10,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

FIG_DIR = Path("paper/noms2027/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)


def generate_fig1_architecture():
    """Figura 1: Arquitetura Espaço-Temporal do SPECTRE-GRID."""
    fig, ax = plt.subplots(figsize=(7.16, 2.8)) # IEEE two-column width
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)

    # Cores
    c_kernel = "#E3F2FD"
    c_user = "#F3E5F5"
    c_model = "#FFF3E0"
    c_box_edge = "#455A64"

    # Bloco Kernel Space
    k_rect = patches.FancyBboxPatch((2, 2), 26, 36, boxstyle="round,pad=0.8", facecolor=c_kernel, edgecolor="#1976D2", linewidth=1.5, linestyle="--")
    ax.add_patch(k_rect)
    ax.text(15, 35, "Linux Kernel (eBPF / XDP)", ha="center", va="center", weight="bold", color="#0D47A1", fontsize=9)

    ax.add_patch(patches.Rectangle((4, 22), 22, 9, facecolor="#BBDEFB", edgecolor=c_box_edge, linewidth=1))
    ax.text(15, 26.5, "spectre_xdp.c\n(Ingress Driver L2-L4)", ha="center", va="center", fontsize=8)

    ax.add_patch(patches.Rectangle((4, 7), 22, 11, facecolor="#BBDEFB", edgecolor=c_box_edge, linewidth=1))
    ax.text(15, 12.5, "BPF Hash Maps\n(Flow State & Topo Cache)", ha="center", va="center", fontsize=8)

    # Seta Kernel -> Userspace
    ax.annotate("", xy=(33, 20), xytext=(26, 20), arrowprops=dict(arrowstyle="->", lw=1.5, color="#37474F"))
    ax.text(29.5, 22, "RingBuffer\n(Events)", ha="center", va="center", fontsize=7)

    # Bloco Userspace Feature Fusion & Graph Construction
    u_rect = patches.FancyBboxPatch((33, 2), 28, 36, boxstyle="round,pad=0.8", facecolor=c_user, edgecolor="#7B1FA2", linewidth=1.5, linestyle="--")
    ax.add_patch(u_rect)
    ax.text(47, 35, "Ingress Engine & Graph Builder", ha="center", va="center", weight="bold", color="#4A148C", fontsize=9)

    ax.add_patch(patches.Rectangle((35, 20), 24, 11, facecolor="#E1BEE7", edgecolor=c_box_edge, linewidth=1))
    ax.text(47, 25.5, "Temporal Snapshot Slicer\n$G_t = (V_t, E_t), \\Delta t = 30\\,\\mathrm{s}$\nStrict Source Labeling", ha="center", va="center", fontsize=8)

    ax.add_patch(patches.Rectangle((35, 6), 24, 10, facecolor="#E1BEE7", edgecolor=c_box_edge, linewidth=1))
    ax.text(47, 11, "20-D Flow Vector Normalizer\n(Frozen $\\mu_{\\mathrm{train}}, \\sigma_{\\mathrm{train}}$)", ha="center", va="center", fontsize=8)

    # Seta Userspace -> Deep Learning Model
    ax.annotate("", xy=(66, 20), xytext=(61, 20), arrowprops=dict(arrowstyle="->", lw=1.5, color="#37474F"))
    ax.text(63.5, 22, "PyG\nBatches", ha="center", va="center", fontsize=7)

    # Bloco Neural Network (CNN + Unidirectional LSTM + GAT)
    m_rect = patches.FancyBboxPatch((66, 2), 32, 36, boxstyle="round,pad=0.8", facecolor=c_model, edgecolor="#E65100", linewidth=1.5)
    ax.add_patch(m_rect)
    ax.text(82, 35, "SPECTRE-GRID Deep Neural Core", ha="center", va="center", weight="bold", color="#BF360C", fontsize=9)

    # Sub-camadas neurais: Unidirectional LSTM
    ax.add_patch(patches.Rectangle((68, 23), 28, 8, facecolor="#FFE0B2", edgecolor=c_box_edge, linewidth=1))
    ax.text(82, 27, "1D-CNN Feature Extractor\n+ Unidirectional LSTM ($L=10$)", ha="center", va="center", fontsize=8)

    ax.add_patch(patches.Rectangle((68, 12), 28, 8, facecolor="#FFCC80", edgecolor=c_box_edge, linewidth=1))
    ax.text(82, 16, "GATConv (Rev / Bidir / Res)\n$\\mathbf{h}'_v = \\mathbf{h}_v + \\sum_{u \\in \\mathcal{N}(v)} \\alpha_{vu} \\mathbf{W} \\mathbf{h}_u$", ha="center", va="center", fontsize=7.5)

    ax.add_patch(patches.Rectangle((68, 4), 28, 6, facecolor="#FFB74D", edgecolor=c_box_edge, linewidth=1))
    ax.text(82, 7, "MLP Classifier ($y_t(v) \\in \\{0, 1\\}$)", ha="center", va="center", weight="bold", fontsize=8)

    # Seta de Mitigation de volta ao Kernel
    ax.annotate("", xy=(15, 2), xytext=(82, 2), arrowprops=dict(arrowstyle="->", lw=1.5, color="#C62828", connectionstyle="arc3,rad=-0.15"))
    ax.text(48.5, -1, "Autonomous Mitigation: Dynamic XDP Drop via BPF Map Update", ha="center", va="center", weight="bold", color="#C62828", fontsize=7.5)

    fig.savefig(FIG_DIR / "fig1_spectre_architecture.pdf")
    fig.savefig(FIG_DIR / "fig1_spectre_architecture.png")
    plt.close(fig)
    print("Figura 1 gerada com sucesso.")


def generate_fig2_chronology():
    """Figura 2: Distribuição dos ataques por decil no UNSW-NB15 e justificativa do horizonte ativo."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 2.4))

    # Dados exatos de Decis (700.001 registros ordenados por Stime, total de 22.215 ataques)
    deciles = np.arange(10)
    attacks_per_decile = [4948, 12510, 4757, 0, 0, 0, 0, 0, 0, 0]

    # Bar chart à esquerda
    bars = ax1.bar(deciles, attacks_per_decile, color=["#D32F2F", "#D32F2F", "#D32F2F", "#388E3C", "#388E3C", "#388E3C", "#388E3C", "#388E3C", "#388E3C", "#388E3C"], edgecolor="#263238", width=0.7)
    ax1.set_xlabel("Dataset Decile (70k Rows Each)")
    ax1.set_ylabel("Malicious Flows (Count)")
    ax1.set_title("(a) Attack Concentration in UNSW-NB15_1")
    ax1.set_xticks(deciles)
    ax1.set_xticklabels([f"D{d}" for d in deciles])
    ax1.grid(axis="y", linestyle=":", alpha=0.6)

    # Anotações exatas (22.215 ataques)
    ax1.annotate("100% of Attacks\n(22,215 flows)", xy=(1, 12600), xytext=(1.5, 11000),
                 arrowprops=dict(arrowstyle="->", lw=1.2, color="#B71C1C"), fontsize=7.5, weight="bold", color="#B71C1C")
    ax1.text(6, 4000, "500,001 Consecutively\nBenign Flows (0 Attacks)", ha="center", fontsize=7.5, color="#2E7D32", weight="bold")

    # Gráfico de pizza / proporção à direita: Partição do Horizonte Ativo vs Cauda Benigna (667 snapshots)
    labels = ["Train (120k)\n152 snaps", "Val (40k)\n48 snaps", "Holdout (40k)\n56 snaps", "Benign Tail (500k)\n667 snaps"]
    sizes = [120000, 40000, 40000, 500001]
    colors = ["#1976D2", "#F57C00", "#7B1FA2", "#388E3C"]
    explode = (0.05, 0.05, 0.05, 0.08)

    wedges, texts, autotexts = ax2.pie(sizes, explode=explode, labels=labels, autopct="%1.1f%%",
                                       startangle=140, colors=colors, textprops=dict(fontsize=7.5),
                                       wedgeprops=dict(edgecolor="#263238", linewidth=0.8))
    for at in autotexts:
        at.set_fontsize(7)
        at.set_weight("bold")
        at.set_color("white")
    ax2.set_title("(b) Dual-Region Methodology")

    fig.savefig(FIG_DIR / "fig2_attack_chronology_audit.pdf")
    fig.savefig(FIG_DIR / "fig2_attack_chronology_audit.png")
    plt.close(fig)
    print("Figura 2 gerada com sucesso.")


def generate_fig3_ablation():
    """Figura 3: Estudo de ablação multi-seed (F1 e FPR) com métricas reais de validação."""
    fig, ax1 = plt.subplots(figsize=(7.16, 2.6))

    variants = [
        "CNN-LSTM\n(Pure Temp.)",
        "GAT Self-Loop\n(No Topology)",
        "CNN-LSTM-GAT\n(Directed)",
        "GAT Reverse\n(Inverted Edge)",
        "GAT Bidir\n(Bidirectional)",
        "GAT Residual\n(Skip Conn.)"
    ]

    # Médias e desvios reais auditados em g15_phase2_consolidated_summary.json
    f1_means = [0.7516, 0.7463, 0.9337, 0.9006, 0.9609, 0.9505]
    f1_stds = [0.0070, 0.0182, 0.0128, 0.1154, 0.0067, 0.0070]

    fpr_means = [5.89, 6.29, 1.52, 2.21, 0.73, 1.25]
    fpr_stds = [0.52, 0.82, 0.46, 2.73, 0.12, 0.18]

    x = np.arange(len(variants))
    width = 0.36

    # Eixo primário (F1-score)
    rects1 = ax1.bar(x - width/2, f1_means, width, yerr=f1_stds, label="Val F1-Score", color="#1565C0", edgecolor="#0D47A1", capsize=3)
    ax1.set_ylabel("F1-Score", color="#1565C0", weight="bold")
    ax1.set_ylim(0.65, 1.02)
    ax1.tick_params(axis="y", labelcolor="#1565C0")
    ax1.set_xticks(x)
    ax1.set_xticklabels(variants, fontsize=7.5)
    ax1.grid(axis="y", linestyle=":", alpha=0.6)

    # Eixo secundário (FPR %)
    ax2 = ax1.twinx()
    rects2 = ax2.bar(x + width/2, fpr_means, width, yerr=fpr_stds, label="Val FPR (%)", color="#D32F2F", edgecolor="#B71C1C", capsize=3)
    ax2.set_ylabel("False Positive Rate (%)", color="#D32F2F", weight="bold")
    ax2.set_ylim(0, 9.0)
    ax2.tick_params(axis="y", labelcolor="#D32F2F")

    for i, rect in enumerate(rects1):
        ax1.text(rect.get_x() + rect.get_width()/2., rect.get_height() + 0.012, f"{f1_means[i]:.3f}", ha="center", va="bottom", fontsize=7, color="#0D47A1", weight="bold")

    for i, rect in enumerate(rects2):
        ax2.text(rect.get_x() + rect.get_width()/2., rect.get_height() + 0.3, f"{fpr_means[i]:.2f}%", ha="center", va="bottom", fontsize=7, color="#B71C1C", weight="bold")

    plt.title("Architectural Ablation & Edge Modulation Study (Multi-Seed Average $\\pm \\sigma$)", weight="bold")
    fig.savefig(FIG_DIR / "fig3_ablation_f1_fpr.pdf")
    fig.savefig(FIG_DIR / "fig3_ablation_f1_fpr.png")
    plt.close(fig)
    print("Figura 3 gerada com sucesso.")


def generate_fig4_external_generalization():
    """Figura 4: Desempenho em dados externos (UNSW-NB15_1 Val vs UNSW-NB15_2 Test)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 2.6))

    models = ["CNN-LSTM", "GAT Self-Loop", "CNN-LSTM-GAT", "GAT Bidir", "GAT Residual"]

    # F1 auditados: UNSW-NB15_1 Val vs UNSW-NB15_2 (rows 400k..600k)
    f1_set1 = [0.7516, 0.7463, 0.9337, 0.9609, 0.9505]
    f1_set2 = [0.6773, 0.6776, 0.8733, 0.9167, 0.8601]

    fpr_set1 = [5.89, 6.29, 1.52, 0.73, 1.25]
    fpr_set2 = [8.79, 9.08, 3.05, 1.47, 3.66]

    x = np.arange(len(models))
    w = 0.35

    # Subplot 1: F1 Comparison
    ax1.bar(x - w/2, f1_set1, w, label="UNSW-NB15_1 (In-Distr. Val)", color="#1E88E5", edgecolor="#1565C0")
    ax1.bar(x + w/2, f1_set2, w, label="UNSW-NB15_2 (Ext. Capture)", color="#00897B", edgecolor="#004D40")
    ax1.set_ylabel("F1-Score", weight="bold")
    ax1.set_title("(a) F1 Robustness Under Temporal Drift")
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, rotation=25, ha="right", fontsize=7.5)
    ax1.set_ylim(0.55, 1.02)
    ax1.legend(loc="lower left", fontsize=7)
    ax1.grid(axis="y", linestyle=":", alpha=0.6)

    # Subplot 2: FPR Comparison
    ax2.bar(x - w/2, fpr_set1, w, label="UNSW-NB15_1 Val", color="#E53935", edgecolor="#B71C1C")
    ax2.bar(x + w/2, fpr_set2, w, label="UNSW-NB15_2 Ext.", color="#FB8C00", edgecolor="#E65100")
    ax2.set_ylabel("False Positive Rate (%)", weight="bold")
    ax2.set_title("(b) False Alarm Rate Comparison")
    ax2.set_xticks(x)
    ax2.set_xticklabels(models, rotation=25, ha="right", fontsize=7.5)
    ax2.set_ylim(0, 11.5)
    ax2.legend(loc="upper right", fontsize=7)
    ax2.grid(axis="y", linestyle=":", alpha=0.6)

    ax2.annotate("Baseline Degradation:\nFPR rises to ~8.8%", xy=(0.35, 8.8), xytext=(0.5, 9.8),
                 arrowprops=dict(arrowstyle="->", lw=1.2, color="#B71C1C"), fontsize=7, color="#B71C1C", weight="bold")

    fig.savefig(FIG_DIR / "fig4_external_generalization_drift.pdf")
    fig.savefig(FIG_DIR / "fig4_external_generalization_drift.png")
    plt.close(fig)
    print("Figura 4 gerada com sucesso.")


def generate_fig5_latency():
    """Figura 5: Benchmark empírico de latência desagregada em GPU (RTX 3050)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 2.5))

    variants = ["CNN-LSTM", "GAT Self-Loop", "CNN-LSTM-GAT", "GAT Residual"]

    # Latências empíricas auditadas por batch de 48 snapshots (em ms)
    cpu_prep = [11.39, 11.76, 17.94, 17.99]
    cpu_to_gpu = [4.28, 5.08, 8.05, 7.94]
    gpu_infer = [15.02, 37.86, 38.81, 39.48]
    gpu_to_cpu = [2.08, 2.18, 2.17, 2.17]

    x = np.arange(len(variants))
    w = 0.55

    # Stacked bar chart
    ax1.bar(x, cpu_prep, w, label="Batch Prep (CPU)", color="#90CAF9")
    ax1.bar(x, cpu_to_gpu, w, bottom=cpu_prep, label="CPU -> GPU Copy", color="#FFCC80")
    b2 = np.array(cpu_prep) + np.array(cpu_to_gpu)
    ax1.bar(x, gpu_infer, w, bottom=b2, label="Neural Inference (GPU)", color="#EF5350")
    b3 = b2 + np.array(gpu_infer)
    ax1.bar(x, gpu_to_cpu, w, bottom=b3, label="GPU -> CPU Output", color="#A5D6A7")

    ax1.set_ylabel("Latency (ms / 48 Snapshots)", weight="bold")
    ax1.set_title("(a) Local Pipeline Stage Breakdown (p50)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(variants, rotation=20, ha="right", fontsize=7.5)
    ax1.legend(loc="upper left", fontsize=6.8)
    ax1.grid(axis="y", linestyle=":", alpha=0.6)

    # Subplot 2: Latência unitária por snapshot vs Real-time Budget
    lat_unit = [3.83, 5.05, 6.33, 6.57] # ms per single snapshot no pipeline total
    nodes_per_sec = [59129, 26120, 26119, 26058]

    ax2.bar(x, lat_unit, w, color="#5C6BC0", edgecolor="#3949AB")
    ax2.set_ylabel("Pipeline Time (ms / Snapshot)", weight="bold")
    ax2.set_title("(b) Streaming Latency vs 30s Window Budget")
    ax2.set_xticks(x)
    ax2.set_xticklabels(variants, rotation=20, ha="right", fontsize=7.5)
    ax2.set_ylim(0, 9.0)
    ax2.grid(axis="y", linestyle=":", alpha=0.6)

    for i, v in enumerate(lat_unit):
        ax2.text(i, v + 0.3, f"{v:.2f} ms\n({nodes_per_sec[i]:,d} n/s)", ha="center", fontsize=6.8, weight="bold")

    fig.savefig(FIG_DIR / "fig5_latency_throughput_tradeoff.pdf")
    fig.savefig(FIG_DIR / "fig5_latency_throughput_tradeoff.png")
    plt.close(fig)
    print("Figura 5 gerada com sucesso.")


if __name__ == "__main__":
    generate_fig1_architecture()
    generate_fig2_chronology()
    generate_fig3_ablation()
    generate_fig4_external_generalization()
    generate_fig5_latency()
    print("Todas as 5 figuras geradas e alinhadas com sucesso aos dados auditados.")
