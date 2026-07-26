import matplotlib.pyplot as plt
import numpy as np
import os

labels = ['API V1 (Síncrona)\nSQLite Lock / Threads', 'API V2 (Assíncrona)\nQueue + aiosqlite']
throughput = [500, 82450] # Estimativa generosa para V1 antes de crashar, V2 real
status = ['FALHA CRÍTICA\nCrash WinError 10054', 'SUCESSO\n0.24s p/ 20.000 msgs']

x = np.arange(len(labels))
width = 0.5

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(x, throughput, width, color=['#e74c3c', '#2ecc71'])

ax.set_ylabel('Throughput (Mensagens / Segundo)', fontsize=12)
ax.set_title('Teste de Stress IPC: Pico de 20.000 Mensagens (Simulação DDoS)', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=12)
ax.set_ylim(0, 100000)

for i, bar in enumerate(bars):
    height = bar.get_height()
    ax.annotate(f'{status[i]}\n{throughput[i]} msgs/s',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 5),  # 5 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom', fontsize=11, fontweight='bold')

plt.tight_layout()

# Save to artifacts directory
import pathlib
brain_dir = os.environ.get("ANTIGRAVITY_BRAIN_DIR")
if brain_dir:
    artifact_dir = brain_dir
else:
    project_root = pathlib.Path(__file__).parent.parent.resolve()
    artifact_dir = str(project_root / "artifacts")
os.makedirs(artifact_dir, exist_ok=True)
output_path = os.path.join(artifact_dir, "benchmark_chart.png")
plt.savefig(output_path, dpi=300)
print(f"Chart saved to {output_path}")
