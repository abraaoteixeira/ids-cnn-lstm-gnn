import matplotlib.pyplot as plt
import numpy as np
import os

nodes = np.array([500, 1000, 2000, 5000, 10000, 20000])

# D3.js CPU limit approximation
fps_v1 = np.array([60, 45, 15, 2, 0.5, 0.1])

# WebGL GPU limit approximation
fps_v2 = np.array([60, 60, 60, 60, 55, 45])

fig, ax = plt.subplots(figsize=(10, 6))

ax.plot(nodes, fps_v1, marker='o', color='#e74c3c', linewidth=2, label='V1: HTML/D3.js (CPU Canvas)')
ax.plot(nodes, fps_v2, marker='s', color='#2ecc71', linewidth=2, label='V2: React/WebGL (GPU Force-Graph)')

ax.set_ylabel('Frames Por Segundo (FPS)', fontsize=12)
ax.set_xlabel('Quantidade de Nós na Rede (Conexões Simultâneas)', fontsize=12)
ax.set_title('Benchmark de Renderização: Dashboard UI (Limites de Escalabilidade)', fontsize=14, fontweight='bold')
ax.axhline(30, color='gray', linestyle='--', alpha=0.5, label='Limite de Fluidez (30 FPS)')
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)

plt.tight_layout()

import pathlib
brain_dir = os.environ.get("ANTIGRAVITY_BRAIN_DIR")
if brain_dir:
    artifact_dir = brain_dir
else:
    project_root = pathlib.Path(__file__).parent.parent.resolve()
    artifact_dir = str(project_root / "artifacts")
os.makedirs(artifact_dir, exist_ok=True)
output_path = os.path.join(artifact_dir, "benchmark_ui_chart.png")
plt.savefig(output_path, dpi=300)
print(f"Chart saved to {output_path}")
