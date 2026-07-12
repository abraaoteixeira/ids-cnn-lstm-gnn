# Handoff Report: Deep Repository Audit and Dataset Integration Strategy

This report presents the findings of a deep structural and logical audit of the SPECTRE GRID repository, extracts key parameters of the DBVA-2025 and other studied datasets, and details a clear roadmap for integrating them into the STGNN framework.

---

## 1. Observation

During the read-only exploration, the following files and directories were inspected:
- `/` (project root files: `model.py`, `train.py`, `preprocessor.py`, `inference.py`, `validate_parity.py`)
- `ebpf/` (`spectre_xdp.c`, `loader.cpp`, `loader_fusion_v2.cpp`, `loader_fusion_legacy.cpp`)
- `data/DBVA/` (`README.md`, `vetores.md`, `3-ml.py`, `5-adaptador_cic.py`)
- `docs/` (`model_evaluation_protocol.md`, `project_overview.md`, `wsl_deployment_guide.md`)
- `project_state.md`

### Observation A: Objective Technical & Structural Inconsistencies

1. **Compatibility Alias Discrepancy**
   - **File `project_state.md` (lines 25-27):**
     ```markdown
     ## Codename e Regras Operacionais
     - **Codename do modelo:** `SPECTRE_GRID`
     - **Compatibilidade:** `Super_IDS_Net` permanece como alias interno para integração legada.
     ```
   - **File `README.md` (line 143):**
     ```markdown
     *   [model.py](...): Implementação da rede neural `SPECTRE_GRID` (com suporte retrocompatível ao alias `Super_IDS_Net`).
     ```
   - **File `model.py` (line 249):**
     ```python
     # Legacy alias removed: use `SPECTRE_GRID` as the canonical model name.
     ```
     *Verification:* There is no definition of `Super_IDS_Net` anywhere in `model.py`.

2. **Missing `loader_fusion.cpp` File**
   - **File `project_overview.md` (lines 80-82):**
     ```markdown
     1. **Arquivos Intocáveis (Safe Deploy):**
        * Os arquivos originais do motor de inteligência (`main.cpp`) e do carregador eBPF isolado (`ebpf/loader.cpp`) devem permanecer sem modificações.
        * Novas lógicas de fusão devem ser mantidas exclusivamente no `ebpf/loader_fusion.cpp`.
     ```
   - **Directory `ebpf/` file list:** Only contains `common.h`, `loader.cpp`, `loader_fusion_legacy.cpp`, `loader_fusion_v2.cpp`, and `spectre_xdp.c`. There is no file named `loader_fusion.cpp`.
   - **File `CMakeLists.txt` (lines 38-40):**
     ```cmake
     # 4.1 FASE 3: FUSION ENGINE (Main / V2 Multi-Threaded)
     add_executable(spectre_fusion ebpf/loader_fusion_v2.cpp)
     ```

3. **Incomplete implementation of `inference.py`**
   - The CLI parser defines `--data` (for passing a traffic CSV) and `--features` (for features JSON):
     **File `inference.py` (lines 103-109):**
     ```python
     def parse_args():
         p = argparse.ArgumentParser(...)
         p.add_argument('--data', dest='csv_path', required=False, help='CSV de tráfego (opcional)')
         p.add_argument('--model', dest='model_path', required=True, help='Caminho para o modelo (.pt ou .pth)')
         p.add_argument('--features', dest='features_path', required=False, help='JSON com top features (opcional)')
         ...
     ```
   - However, the inference execution hardcodes a random mock tensor and completely ignores the CSV data:
     **File `inference.py` (lines 83-97):**
     ```python
     # Prepare mock data (dry-run: não executar, apenas estrutura)
     # In production the preprocessor would build `x` and `edge_index` from `csv_path`
     N = 5
     seq_len = 10
     num_features = 20

     mock_data_x = torch.randn(N, seq_len, num_features, device=device)
     mock_edges = torch.tensor([[i for i in range(N-1)], [i+1 for i in range(N-1)]], dtype=torch.long, device=device)
     ```

4. **GNN Topological Bypassing in C++ Daemons**
   - **File `ebpf/loader_fusion_v2.cpp` (lines 249, 306-310):**
     ```cpp
     torch::Tensor edge_tensor = torch::tensor({{0}, {0}}, torch::kLong);
     ...
     torch::Tensor input = build_tensor(ctx); // shape [1, 10, 20]
     std::vector<torch::jit::IValue> inputs;
     inputs.push_back(input); inputs.push_back(edge_tensor);
     torch::Tensor output = module.forward(inputs).toTensor();
     ```
   - **File `main.cpp` (lines 44-49):**
     ```cpp
     at::Tensor inputs = torch::randn({1, 10, 20});
     at::Tensor edge_index = torch::zeros({2, 1}, torch::kLong);
     ```
     *Verification:* The model is evaluated on a per-node level (`N = 1`) using a static, dummy self-loop edge.

---

### Observation B: Dataset Studies and Extracted Specifications

1. **DBVA-2025 (Dataset Baseado em Vetores de Ataque - 2025)**
   - **Scale:** 982,005 flows derived from a 5 GB raw PCAP file representing 33.5 hours of LAN capture. Exported to a 409 MB CSV file.
   - **Capture Period:** 07/11 (23:00) to 09/11 (08:30) of 2025.
   - **Topology:** Controlled virtual network (VirtualBox) with pfSense firewall gateway (`192.168.1.1`), Kali Linux attacker (`192.168.1.10`), and Mint/Debian/Windows target machines.
   - **Attack Tooling:** Nmap (scanning), Gobuster (directory bruteforce), Hydra (FTP/SSH credential cracking), and hping3 (SYN flood DoS).
   - **Feature Extraction:** CICFlowMeter (84 features).
   - **Class Distribution:**
     * `Benign`: 60,791 flows
     * `Recon_PortScan`: 123,504 flows
     * `Discovery_DirBruteforce`: 13,535 flows
     * `Credential_BruteForce_FTP`: 666 flows
     * `Credential_BruteForce_SSH`: 57 flows
     * `Impact_DoS`: 784,452 flows
   - **Associated Scripts:**
     * `1-limpeza.py`: Handles NaN/Inf values, strips column whitespace.
     * `2-rotulagem.py`: Rules-based labeling matching attacker source IPs and attack schedules.
     * `3-ml.py`: Balance training data via SMOTE and undersampling, then train multi-class RandomForest and unsupervised IsolationForest.
     * `5-adaptador_cic.py`: Tool for schema mapping and column consolidation (combines/adapts CIC-IDS formats).

2. **NF-UQ-NIDS-v2**
   - **Source/Justification:** Documented in `docs/model_evaluation_protocol.md` and `README.md` (lines 250, 309).
   - **Scale/Format:** 11.99 million flows in native NetFlow v9 / IPFIX format.
   - **Purpose:** Eliminating structural *concept drift* between the offline dataset format (CICFlowMeter PCAP-based flow closure) and live eBPF/XDP real-time capture features. NetFlow features map 1:1 to metrics easily computed in eBPF.

3. **Other Studied Datasets**
   - **CIC-IDS2017 Full Processed:** Current baseline model training set (v1.1 final build).
   - **UNSW-NB15:** Stored in raw benchmarks (`data/raw/benchmarks/UNSW-NB15.csv`, 700,001 entries) and referenced in history logs.
   - **CICIoT2023:** Stored as real-time IoT attack benchmark study.

---

## 2. Logic Chain

The step-by-step reasoning linking the observations to the strategic conclusions:

1. **GNN Topology Disconnection:** 
   - *Observation B4* shows that C++ inference inputs have shape `[1, 10, 20]` (single node `N=1`) and a static self-loop edge `[[0], [0]]`.
   - *Reasoning:* A Graph Attention Network (GATConv) utilizes edge connections to aggregate features from neighbors. When `N = 1` and `edge_index` has only a self-loop, the attention coefficients normalize to 1 and no message passing occurs. This effectively disables the spatial component of the GNN, reducing the model to a standard CNN-LSTM sequence classifier.
   - *Conclusion:* To achieve true GNN capability, the C++ runtime must collect and batch multiple active flows, constructing a real graph topology before calling LibTorch.

2. **Concept Drift & Feature Incompatibility:**
   - *Observation B1* indicates DBVA-2025 is extracted using CICFlowMeter (84 features). *Observation B2* points out that eBPF captures NetFlow (v9) records.
   - *Reasoning:* Running the model on eBPF data requires the model to receive features that are measurable on-the-fly. CICFlowMeter features depend on post-facto calculation of bidirectional connection stats (e.g. packet inter-arrival times across the entire connection). NetFlow features (like those in NF-UQ-NIDS-v2) are computed incrementally.
   - *Conclusion:* Integrating DBVA-2025 directly without feature translation will lead to severe performance degradation due to mismatched feature distributions.

3. **Dynamic vs. Hardcoded Features:**
   - *Observation A3* shows `preprocessor.py` selects the Top-20 features dynamically using Pearson correlation, saving them to a JSON mapping.
   - *Observation B1/B2* shows `loader_fusion_v2.cpp` has a statically hardcoded `MODEL_FEATURE_MAPPING` array mapping 20 derived features.
   - *Reasoning:* If a retrained model is loaded without updating the C++ feature mapping array, the model will receive incorrect input variables, breaking the inference pipeline.
   - *Conclusion:* Feature order and normalization logic must be synchronized between the Python preprocessor and the C++ daemon runtime.

---

## 3. Caveats

- **WSL Performance Limitations:** The local Windows host lacks native Python PyTorch GPU dependencies, so training must be performed within WSL2 (using the virtual environment `/home/abras/ids-cnn-lstm-gnn/.venv_fast`) or via Google Colab (`Colab_Training_NF_UQ_NIDS.ipynb`).
- **Simplification to Binary Classification:** The DBVA-2025 labels are multi-class (6 types), while the current SPECTRE GRID model uses a binary classifier (logit per node). A preprocessing layer must map the 5 attack categories to target class `1` and `Benign` to `0`.

---

## 4. Conclusion

The audit shows that the SPECTRE GRID codebase compiles and works correctly on isolated node inference, but suffers from a disconnect where the GNN features are bypassed during C++ deployment. Furthermore, retraining on new datasets like DBVA-2025 requires strict feature mapping and dynamic alignment.

### Strategic Roadmap for Dataset Integration

1. **Step 1: Standardized NetFlow Schema Mapping**
   - Align DBVA-2025 features (CICFlowMeter-derived) with the NetFlow features of NF-UQ-NIDS-v2 and the metrics extracted by the C++ engine (`derive_features` in `loader_fusion_v2.cpp`).
   - Create a feature mapping adapter (extending `data/DBVA/5-adaptador_cic.py`) that exports exactly 20 aligned metrics.

2. **Step 2: Binary Graph Construction**
   - Adapt `preprocessor.py` to ingest the cleaned DBVA-2025 dataset.
   - Group flows by IP addresses (`Src IP` and `Dst IP` as nodes, timestamps defining edges).
   - Generate Graph objects (`network_graph.pt`) using a binary target mapping (`1` for attack labels, `0` for benign).

3. **Step 3: Joint Training & Fine-Tuning**
   - Retrain the GNN model using the Jupyter notebook/script `Colab_Training_NF_UQ_NIDS.ipynb` modified to support mixed-batch training (combining NF-UQ-NIDS-v2 for base NetFlow v9 knowledge, and DBVA-2025 graphs to specialize on local modern exploits).
   - Enforce fixed seed `42` to maintain structural parity.

4. **Step 4: Real GNN Batching in C++ Daemon**
   - Modify the C++ inference engine (`loader_fusion_v2.cpp`) to accumulate flows across a window of time (e.g., 2-5 seconds).
   - Build a local adjacency matrix (IP-to-IP relationships) for active hosts in memory, exporting a dynamic batch size `N > 1` and a populated `edge_index` to the LibTorch model, enabling true message passing.

5. **Step 5: Code & Doc Parity Clean-up**
   - Restore the compatibility alias `Super_IDS_Net` in `model.py` to prevent import issues in legacy scripts.
   - Rename/update references to `ebpf/loader_fusion.cpp` in `project_overview.md` to target `ebpf/loader_fusion_v2.cpp`.
   - Update `inference.py` to read real CSV data if provided.

---

## 5. Verification Method

To verify these observations and validate the model pipeline, execute the following commands in the WSL system:

1. **Verify Python/C++ Parity:**
   Run the parity checking script inside the WSL environment to confirm that the `state_dict` and the traced TorchScript export yield identical logits:
   ```bash
   wsl /home/abras/ids-cnn-lstm-gnn/.venv_fast/bin/python3 /home/abras/ids-cnn-lstm-gnn/validate_parity.py --checkpoint /home/abras/ids-cnn-lstm-gnn/trained_super_ids_model.pt
   ```
   *Expected Output:*
   ```text
   [INFO] Carregando pesos do checkpoint para o modelo Python: trained_super_ids_model.pt
   === Validação de Paridade ===
   Batch size: 4
   Shape: torch.Size([4])
   Max abs diff: 0.000000e+00
   Mean abs diff: 0.000000e+00
   Passou: SIM
   ```

2. **Verify Missing File:**
   Confirm the absence of the documentation-mandated `loader_fusion.cpp`:
   ```bash
   wsl ls -l /home/abras/ids-cnn-lstm-gnn/ebpf/loader_fusion.cpp
   ```
   *Expected Output:* `ls: cannot access ...: No such file or directory`

3. **Inspect Selected Features:**
   Inspect `data/processed/top20_features.json` to verify the active features generated by the preprocessor:
   ```bash
   cat c:\Users\Abraão\Documents\projects\ids-cnn-lstm-gnn\data\processed\top20_features.json
   ```
