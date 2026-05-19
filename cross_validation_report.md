# 🔬 Relatório de Validação Cruzada: PyTorch vs. LibTorch

## 1. Paridade de Arquitetura e Camadas
A transição do Python para o motor nativo LibTorch (C++) mantém a integridade estrutural através do mapeamento de camadas fundamentais:

- **CNN1D:** `torch.nn.Conv1d` (Python) ⟷ `torch::nn::Conv1d` (C++). Parâmetros de kernel, stride e padding são preservados via exportação TorchScript.
- **LSTM:** `torch.nn.LSTM` (Python) ⟷ `torch::nn::LSTM` (C++). Utiliza o mesmo backend ATen para os gates de controle temporal.
- **GAT (Topologia):** `torch_geometric.nn.GATConv` ⟷ Implementação Scripted. Operações de Message Passing e Attention Weights são vinculadas às bibliotecas `libtorch_scatter` e `libtorch_sparse` para garantir o mesmo comportamento de vizinhança gráfica.

## 2. Metodologia de Validação
Para validar a paridade, seguimos o seguinte protocolo:
1. **Serialização:** O modelo treinado é convertido para TorchScript (`torch.jit.script`).
2. **Teste Cego:** Geramos tensores de entrada determinísticos com sementes fixas (`torch.manual_seed(42)`).
3. **Comparação ponto-a-ponto:** Executamos a inferência no Python e na Engine Nativa C++, capturando os logs de saída (Logits).
4. **Cálculo de RMSE:** Calculamos o Root Mean Square Error entre os dois vetores de saída.

## 3. Critérios de Fidelidade e Tolerância
- **Limite de Erro Residual:** Definido em **1e-6**. Qualquer divergência acima deste limiar é tratada como erro de implementação na Engine Nativa.
- **Tratamento de Pesos (Weights) e Bias:** Os parâmetros são mantidos em FP32 (Full Precision). Não aplicamos quantização dinâmica para evitar ruído na validação da paridade matemática.
- **Determinismo:** Ativamos `torch.use_deterministic_algorithms(True)` para garantir reprodutibilidade em multi-threading.

## 4. Conclusão de Engenharia
A paridade matemática validada em 1e-6 assegura que o modelo SPECTRE-GRID treinado no ambiente de pesquisa possui o exato comportamento de decisão quando implantado em firewalls industriais de baixa latência.
