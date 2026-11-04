---
name: reproducible-training
description: Procedimentos de reprodutibilidade de treinamento em PyTorch/PyG, fixação de seeds, persistência de checkpoints e reconciliação entre hardwares heterogêneos.
---

# Skill: Reproducible Training

Esta skill padroniza os experimentos com modelos neurais no SPECTRE-GRID, garantindo que qualquer rodada de treinamento possa ser inspecionada, retomada e reproduzida de ponta a ponta.

## Quando Utilizar
- Ao treinar novas variantes da rede (CNN-LSTM, GAT, STGNN) ou explorar novos hiperparâmetros;
- Ao replicar treinamentos entre o Dell G15 (RTX 3050 Laptop) e o Google Colab Pro (Tesla T4);
- Ao salvar e versionar checkpoints (`.pth` ou `.pt`) com histórico de épocas;
- Ao investigar discrepâncias em ponto flutuante entre ambientes Windows e Linux.

## Protocolo de Reprodutibilidade Obrigatório

### 1. Fixação de Sementes e Determinismo
Todo script de treino deve invocar no início:
```python
def seed_everything(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
```

### 2. Reconhecimento de Limitações Numéricas de GPU
- Operações atômicas de agregação em grafos (`torch_geometric.nn.GATConv`, `scatter_add`, `index_add`) possuem ordem de execução de threads não-determinística na GPU.
- Por esse motivo, treinamentos com a mesma seed em hardwares diferentes (ex.: Ampere GA107 no G15 vs. Turing TU104 na T4) produzirão trajetórias de loss ligeiramente divergentes ($\Delta \text{F1} \sim \pm 0,01$).
- **Regra:** O critério de sucesso para reprodutibilidade cruzada é a invariância de convergência e a manutenção estrita do ranking arquitetural entre variantes.

### 3. Gestão de Checkpoints e Retomada
- Checkpoints de melhor época devem ser gravados isoladamente:
  `{tag_prefix}_{model_variant}_seed{seed}_{window_sec}s_best.pth`
- Nunca sobrescrever um checkpoint histórico sem criar backup prévio.
- O estado de treino deve incluir:
  ```python
  torch.save({
      "epoch": epoch,
      "model_state_dict": model.state_dict(),
      "optimizer_state_dict": optimizer.state_dict(),
      "val_f1": best_f1,
      "seed": seed,
      "variant": variant,
  }, checkpoint_path)
  ```

### 4. Manifestos de Execução em JSON
Cada execução deve salvar um relatório JSON complementar contendo:
- `git_commit`: Hash curto do commit ativo;
- `dataset_sha256`: Hash do dataset de treino;
- `gpu_name`, `torch_version`, `cuda_version`;
- `best_epoch`, `training_wall_time_sec`, `latency_ms_per_snapshot`;
- Métricas completas de validação com matriz de confusão (`tn, fp, fn, tp`).

## Comandos de Validação
```bash
# Executar treino multi-seed seguro sob modo de validação exclusiva
python train.py --variant cnn_lstm_gat --seeds 42 123 1337 --val_only --epochs 30 --batch_size 8
```
