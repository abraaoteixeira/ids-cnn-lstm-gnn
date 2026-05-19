# SPECTRE_GRID

Projeto de IDS híbrido baseado em CNN1D + LSTM + GATConv.

## Visão geral
- Codename oficial do modelo: `SPECTRE_GRID`
- A arquitetura nativa está documentada em `cross_validation_report.md`.

## Estrutura principal
- `model.py`: implementação Python do modelo `SPECTRE_GRID`.
- `train.py`: treino do modelo usando grafo PyG salvo em `.pt`.
- `preprocessor.py`: pipeline de engenharia de features e construção de grafo STGNN.
- `inference.py`: inferência com dados reais (via CSV) ou em modo demonstrativo (dry-run).
- `export_torchscript.py`: exportação do modelo para TorchScript (JIT Trace).
- `validate_parity.py`: validação de paridade numérica Python ⟷ LibTorch.
- `main.cpp`: daemon C++ de inferência standalone (LibTorch).
- `ebpf/loader_fusion.cpp`: motor de fusão LibTorch + eBPF/XDP com buffer rotativo.
- `dashboard_api.py`: API FastAPI + WebSocket para o Dashboard NGFW Radar.
- `CMakeLists.txt`: build system (5 targets: inference, fusion, benchmark, eBPF loader, kernel XDP).
- `cross_validation_report.md`: relatório de paridade Python vs. LibTorch.

## Uso
### Preprocessamento
```bash
python preprocessor.py --input_csv data/raw/KDDTrain_compat.csv --seq_len 10
```

### Treino
```bash
python train.py --data_path data/processed/network_graph.pt --epochs 50
```

### Inferência Python (dados reais)
```bash
python inference.py --model trained_super_ids_model.pt --data data/raw/KDDTrain_compat.csv
```

### Inferência Python (dry-run com dados mock)
```bash
python inference.py --model trained_super_ids_model.pt
```

### Dashboard (Modo Radar)
```bash
python dashboard_api.py
# Abrir http://localhost:8000 no browser
```

### Build nativo C++ (LibTorch + eBPF)
```bash
mkdir -p build && cd build
cmake ..
cmake --build . --config Release
./spectre_fusion eth0          # Motor de fusão (LibTorch + eBPF)
./spectre_inference ../spectre_model_scripted.pt  # Daemon standalone
./spectre_benchmark            # Benchmark de latência (10K iterações)
```

### Validação de paridade
```bash
python validate_parity.py --script-path spectre_model_scripted.pt
```

## Observações
- Não altere `model.py` ou `train.py` sem aprovação explícita do usuário.
- Qualquer mudança no motor nativo deve ser documentada em `cross_validation_report.md`.
- O `main.cpp` e `ebpf/loader.cpp` originais são preservados como fallback (política de Safe Deploy).
