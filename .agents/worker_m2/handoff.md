# Handoff Report

This report summarizes the observations, findings, and documentation updates made to resolve the project's structural/technical inconsistencies and document the dataset integration roadmap.

---

## 1. Observation

Direct observations made on the codebase:

*   **Observation 1.1 (Model Alias discrepancy):** In `project_state.md` (line 27), it reads:
    > `- **Compatibilidade:** Super_IDS_Net permanece como alias interno para integração legada.`
    In `README.md` (line 143), it reads:
    > `*   [model.py](file:///c:/Users/abraa/Documents/ids-cnn-lstm-gnn/model.py): Implementação da rede neural SPECTRE_GRID (com suporte retrocompatível ao alias Super_IDS_Net).`
    However, the source code in `model.py` does not contain `Super_IDS_Net` and instead ends with:
    > `# Legacy alias removed: use `SPECTRE_GRID` as the canonical model name.` (line 249).

*   **Observation 1.2 (Missing loader_fusion.cpp):** In `project_overview.md` (line 82), it reads:
    > `* Novas lógicas de fusão devem ser mantidas exclusivamente no ebpf/loader_fusion.cpp.`
    Listing the `ebpf` directory returns the files `common.h`, `loader.cpp`, `loader_fusion_legacy.cpp`, `loader_fusion_v2.cpp`, and `spectre_xdp.c`. `ebpf/loader_fusion.cpp` is missing.
    In `CMakeLists.txt` (line 39), it compiles `ebpf/loader_fusion_v2.cpp` for target `spectre_fusion`:
    > `add_executable(spectre_fusion ebpf/loader_fusion_v2.cpp)`

*   **Observation 1.3 (Incomplete inference.py):** In `inference.py`, arguments are parsed (lines 105-107):
    ```python
    p.add_argument('--data', dest='csv_path', required=False, help='CSV de tráfego (opcional)')
    p.add_argument('--model', dest='model_path', required=True, help='Caminho para o modelo (.pt ou .pth)')
    p.add_argument('--features', dest='features_path', required=False, help='JSON com top features (opcional)')
    ```
    However, `csv_path` is never used to load or preprocess actual data, and the evaluation features are mock-initialized (lines 83-91):
    ```python
    # Prepare mock data (dry-run: não executar, apenas estrutura)
    # In production the preprocessor would build `x` and `edge_index` from `csv_path`
    N = 5
    seq_len = 10
    num_features = 20

    mock_data_x = torch.randn(N, seq_len, num_features, device=device)
    mock_edges = torch.tensor([[i for i in range(N-1)], [i+1 for i in range(N-1)]], dtype=torch.long, device=device)
    ```

*   **Observation 1.4 (GNN Topological Bypassing):** In `ebpf/loader_fusion_v2.cpp` (lines 249, 306-310), the inference inputs are constructed as a 1-node graph:
    ```cpp
    torch::Tensor edge_tensor = torch::tensor({{0}, {0}}, torch::kLong);
    ```
    and the tensor is constructed with shape `{1, SEQ_LEN, NUM_FEATURES}`.
    In `main.cpp` (lines 44-45), inputs are constructed as:
    ```cpp
    at::Tensor inputs = torch::randn({1, 10, 20});
    at::Tensor edge_index = torch::zeros({2, 1}, torch::kLong);
    ```
    This feeds a single-node $N=1$ and self-loop `[[0], [0]]` to `GATConv`.

---

## 2. Logic Chain

1. **Inconsistency 1 (Compatibility Alias):** From Observation 1.1, the documentation (`project_state.md`, `README.md`) incorrectly references `Super_IDS_Net` as a present alias in `model.py`, but it has been removed from `model.py` (leaving only the comment of its deletion).
2. **Inconsistency 2 (Missing file):** From Observation 1.2, `project_overview.md` guides developers to modify `ebpf/loader_fusion.cpp`, which does not exist, whereas the actual daemon codebase and build configuration compile and use `ebpf/loader_fusion_v2.cpp`.
3. **Inconsistency 3 (Incomplete inference):** From Observation 1.3, `inference.py` accepts `--data` and `--features` on the CLI interface, but discards/ignores their values during execution, defaulting to random mock tensors (`torch.randn`).
4. **Inconsistency 4 (Topological Bypassing):** From Observation 1.4, feeding $N=1$ and a self-loop edge `[[0], [0]]` to `GATConv` forces the attention mechanism softmax to normalize to a single value $1.0$. This bypasses graph convolutional feature propagation and effectively degrades the GNN into a dense multi-layer perceptron.

---

## 3. Caveats

*   **No Code Modification Constraint:** As requested, no Python or C++ source files were modified to fix these issues. The inconsistencies are only documented in `audit_report.md`.
*   **Running Environment:** The evaluation is based on static code auditing of the workspace files. Active validation commands (such as running C++ compilation) were not executed as the host is Windows and the daemon compilation is target-locked to WSL2.

---

## 4. Conclusion

We successfully audited the project and created `audit_report.md` detailing the 4 technical/structural inconsistencies. We also updated `project_state.md` with the new dataset integration roadmap (detailing DBVA-2025 and NF-UQ-NIDS-v2 specs and integration strategy) and updated `project_overview.md` to reference `ebpf/loader_fusion_v2.cpp` instead of the non-existent `ebpf/loader_fusion.cpp`.

---

## 5. Verification Method

To verify the changes:
1. Confirm the creation of `audit_report.md` at the workspace root and verify its contents.
2. Confirm the updates in `project_state.md` containing the section `## Integração do Dataset DBVA-2025 e Estudos de Datasets Recentes`.
3. Confirm that all references to `ebpf/loader_fusion.cpp` in `project_overview.md` have been updated to `ebpf/loader_fusion_v2.cpp`, and that the brief dataset integration roadmap subsection is present under section 2.
