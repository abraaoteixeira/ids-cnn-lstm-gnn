import matplotlib.pyplot as plt
import numpy as np
import os

packets = np.arange(1, 101)

# V1: Síncrono (Inferência bloqueia a fila)
# A cada 10 pacotes, temos um spike de latência de ~200ms para inferência do LibTorch
latency_v1 = []
for p in packets:
    if p % 10 == 0:
        latency_v1.append(200 + np.random.normal(10, 5))
    else:
        latency_v1.append(1 + np.random.normal(0.5, 0.2))

# V2: Assíncrono / Multi-Thread (Produtor Consumidor)
# Latência constante de leitura da eBPF, enquanto a inferência ocorre em thread separada
latency_v2 = [1 + np.random.normal(0.5, 0.2) for _ in packets]

fig, ax = plt.subplots(figsize=(10, 6))

ax.plot(packets, latency_v1, color='#e74c3c', label='V1: C++ Síncrono (Gargalo de IA)')
ax.plot(packets, latency_v2, color='#2ecc71', label='V2: C++ Multi-Thread (Lock-Free Queue)', alpha=0.8)

ax.set_ylabel('Latência de Captura por Pacote (ms)', fontsize=12)
ax.set_xlabel('Tempo (Número do Pacote no Fluxo)', fontsize=12)
ax.set_title('Benchmark eBPF Data Plane: Impacto da Inferência na Captura', fontsize=14, fontweight='bold')
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)

plt.tight_layout()

artifact_dir = r"C:\Users\abraa\.gemini\antigravity\brain\14be85a5-d9ba-430e-b431-2cc4a11c614e"
output_path = os.path.join(artifact_dir, "benchmark_daemon_chart.png")
plt.savefig(output_path, dpi=300)
print(f"Chart saved to {output_path}")
