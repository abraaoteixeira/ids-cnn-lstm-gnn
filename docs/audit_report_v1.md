# Relatório de Auditoria Técnica: SPECTRE GRID

Este relatório detalha as inconsistências técnicas e estruturais identificadas no repositório do projeto **SPECTRE GRID**, com base na análise estática de código e rastreamento de fluxos.

---

## 1. Divergência de Alias de Compatibilidade (Compatibility Alias Discrepancy)

### Descrição do Problema
O arquivo `project_state.md` e o `README.md` especificam o suporte retrocompatível ao alias de modelo `Super_IDS_Net` para fins de integração com sistemas legados. No entanto, a classe `Super_IDS_Net` não existe no arquivo `model.py`, que define apenas a classe canônica `SPECTRE_GRID`.

### Evidências e Referências de Arquivos

*   **`project_state.md` (Linhas 25-27):**
    ```markdown
    ## Codename e Regras Operacionais
    - **Codename do modelo:** `SPECTRE_GRID`
    - **Compatibilidade:** `Super_IDS_Net` permanece como alias interno para integração legada.
    ```

*   **`README.md` (Linha 143):**
    ```markdown
    *   [model.py](model.py): Implementação da rede neural `SPECTRE_GRID` (com suporte retrocompatível ao alias `Super_IDS_Net`).
    ```

*   **`model.py` (Linha 249):**
    A classe não consta no código-fonte, existindo apenas um comentário final indicando a sua remoção:
    ```python
    # Legacy alias removed: use `SPECTRE_GRID` as the canonical model name.
    ```

---

## 2. Ausência do Arquivo `loader_fusion.cpp` (Missing loader_fusion.cpp File)

### Descrição do Problema
A documentação de arquitetura no arquivo `project_overview.md` instrui que novas lógicas de fusão de dados e inferência devem ser mantidas no arquivo `ebpf/loader_fusion.cpp`. No entanto, este arquivo não existe na pasta `ebpf/`. Em vez dele, o arquivo `ebpf/loader_fusion_v2.cpp` é utilizado e compilado pelo CMake.

### Evidências e Referências de Arquivos

*   **`project_overview.md` (Linhas 80-82):**
    ```markdown
    1. **Arquivos Intocáveis (Safe Deploy):**
       * Os arquivos originais do motor de inteligência (`main.cpp`) e do carregador eBPF isolado (`ebpf/loader.cpp`) devem permanecer sem modificações.
       * Novas lógicas de fusão devem ser mantidas exclusivamente no `ebpf/loader_fusion.cpp`.
    ```

*   **Conteúdo do diretório `ebpf/`:**
    Os únicos arquivos presentes que lidam com fusão de dados são `loader_fusion_legacy.cpp` e `loader_fusion_v2.cpp`. O arquivo `loader_fusion.cpp` não está presente.

*   **`CMakeLists.txt` (Linhas 38-43):**
    O CMake compila a versão multithreaded utilizando o arquivo `loader_fusion_v2.cpp`:
    ```cmake
    # 4.1 FASE 3: FUSION ENGINE (Main / V2 Multi-Threaded)
    add_executable(spectre_fusion ebpf/loader_fusion_v2.cpp)
    ```

---

## 3. Implementação Incompleta de `inference.py` (Incomplete implementation of inference.py)

### Descrição do Problema
O script de CLI `inference.py` declara e processa argumentos de linha de comando para receber caminhos de dados de tráfego (`--data` para arquivos CSV) e caminhos de arquivos de mapeamento de características (`--features` para JSON). No entanto, o script ignora completamente os parâmetros informados, utilizando tensores de entrada estáticos (*mock data*) preenchidos com valores aleatórios obtidos via `torch.randn` para a simulação de inferência.

### Evidências e Referências de Arquivos

*   **`inference.py` (Linhas 72-91):**
    ```python
    def run_inference(csv_path: str | None, model_path: str, features_path: str | None, device_str: str = None):
        device = torch.device(device_str if device_str else ('cuda' if torch.cuda.is_available() else 'cpu'))

        # load top features if provided (not required for dry-run)
        top_features = None
        if features_path:
            try:
                with open(features_path, 'r') as f:
                    top_features = json.load(f)
            except Exception:
                logger.warning(f"Não foi possível carregar features de {features_path}. Seguindo com dados mock.")

        model, mode = load_model_flexible(model_path, device)

        # Prepare mock data (dry-run: não executar, apenas estrutura)
        # In production the preprocessor would build `x` and `edge_index` from `csv_path`
        N = 5
        seq_len = 10
        num_features = 20

        mock_data_x = torch.randn(N, seq_len, num_features, device=device)
        mock_edges = torch.tensor([[i for i in range(N-1)], [i+1 for i in range(N-1)]], dtype=torch.long, device=device)
    ```
    Note que a variável `csv_path` não é utilizada em nenhum momento para extrair dados ou criar o grafo, e `top_features` é carregado mas nunca repassado ou aplicado ao mapeamento de features do input.

---

## 4. Ignorância da Topologia GNN nos Daemons C++ (GNN Topological Bypassing in C++ Daemons)

### Descrição do Problema
Os executáveis nativos e de simulação (`loader_fusion_v2.cpp` e `main.cpp`) contornam a estrutura relacional do modelo GNN (`GATConv`). Ao invocar a inferência do LibTorch, eles utilizam um grafo estático com apenas 1 nó (`N=1`) e uma aresta de auto-loop `[[0], [0]]`. Em modelos de convoluição baseados em atenção como o GAT (Graph Attention Network), a aplicação de softmax sobre os vizinhos de um único nó isolado resulta em um coeficiente de atenção normalizado exatamente igual a $1.0$. Consequentemente, o mecanismo espacial de passagem de mensagens (*message passing*) é totalmente anulado, transformando a GNN em uma rede densa convencional sem contexto topológico.

### Evidências e Referências de Arquivos

*   **`ebpf/loader_fusion_v2.cpp` (Linhas 247-249 e 306-310):**
    O edge_tensor é instanciado de forma global para a thread com uma única aresta de auto-loop:
    ```cpp
    void inference_worker(torch::jit::script::Module module, int block_map_fd) {
        std::unordered_map<uint32_t, FlowContext> flow_tracker;
        torch::Tensor edge_tensor = torch::tensor({{0}, {0}}, torch::kLong);
    ```
    O tensor de características é criado com o shape `[1, SEQ_LEN, NUM_FEATURES]`, caracterizando $N=1$:
    ```cpp
    static torch::Tensor build_tensor(const FlowContext& ctx) {
        float flat[SEQ_LEN * NUM_FEATURES];
        for (int t = 0; t < SEQ_LEN; ++t) {
            int read_idx = (ctx.current_index + t) % SEQ_LEN;
            std::memcpy(&flat[t * NUM_FEATURES], ctx.ring_buffer[read_idx].data(), sizeof(float) * NUM_FEATURES);
        }
        return torch::from_blob(flat, {1, SEQ_LEN, NUM_FEATURES}, torch::kFloat32).clone();
    }
    ```
    O modelo recebe a tupla contendo o tensor de nó único e a aresta estática:
    ```cpp
    torch::Tensor input = build_tensor(ctx);
    std::vector<torch::jit::IValue> inputs;
    inputs.push_back(input); inputs.push_back(edge_tensor);
    torch::Tensor output = module.forward(inputs).toTensor();
    ```

*   **`main.cpp` (Linhas 44-52):**
    O wrapper simula a mesma entrada degenerada de $N=1$ e auto-loop `[[0], [0]]`:
    ```cpp
    at::Tensor inputs = torch::randn({1, 10, 20});
    at::Tensor edge_index = torch::zeros({2, 1}, torch::kLong);

    std::vector<torch::jit::IValue> ival_inputs;
    ival_inputs.push_back(inputs);
    ival_inputs.push_back(edge_index);

    try {
        at::Tensor output = module.forward(ival_inputs).toTensor();
    ```
