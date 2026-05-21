# SPECTRE_GRID

Projeto de IDS híbrido baseado em CNN1D + LSTM + GATConv.

## Visão geral
- Codename oficial do modelo: `SPECTRE_GRID`
- A arquitetura nativa está documentada em `cross_validation_report.md`.
- O código raiz preserva o histórico de pesquisa e mantém compatibilidade com o alias `Super_IDS_Net`.
- O pipeline de dados atual (v1.1) utiliza o dataset CIC-IDS2017 para o treinamento e validação final do modelo.

## Estrutura principal
- `model.py`: implementação Python do modelo `SPECTRE_GRID`.
- `train.py`: treino do modelo usando grafo PyG salvo em `.pt`.
- `inference.py`: inferência em modo demonstrativo com dados dummy.
- `main.cpp`: wrapper C++ que carrega um modelo TorchScript.
- `CMakeLists.txt`: build do binário `spectre_inference`.
- `cross_validation_report.md`: relatório de paridade Python vs. LibTorch.
- `deploy/`: scripts e arquivos Systemd para execução de ambiente enterprise (daemon).
- `scratch/`: scripts de testes de estresse, simulações de fluxo contínuo e disparadores de ataques (ex: `real_syn_flood.py`).

## Uso
### Treino
```bash
python train.py --data_path data/processed/network_graph.pt --epochs 50
```

### Inferência Python
```bash
python inference.py
```

### Build nativo C++ (LibTorch)
```bash
mkdir -p build && cd build
cmake ..
cmake --build . --config Release
./spectre_inference ../spectre_model_scripted.pt
```

### Validação de paridade
```bash
python validate_parity.py --script-path spectre_model_scripted.pt
```

## Observações
- O `model.py` já expõe `Super_IDS_Net = SPECTRE_GRID` para compatibilidade com código legados.
- Não altere `model.py` ou `train.py` sem aprovação explícita do usuário.
- Qualquer mudança no motor nativo deve ser documentada em `cross_validation_report.md`.
