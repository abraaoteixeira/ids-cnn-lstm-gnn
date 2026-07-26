#include <iostream>
#include <chrono>
#include <vector>
#include <torch/script.h>
#include <torch/torch.h>
#include <dlfcn.h> // Para carregar operacoes customizadas (torch_scatter)

int main(int argc, char **argv) {
    std::cout << "===============================================" << std::endl;
    std::cout << "[MOCK] Teste de Performance: Fusão LibTorch" << std::endl;
    std::cout << "===============================================" << std::endl;

    // --- EXTENSOES DE GRAFO (GNN) ---
    // O modelo SPECTRE-GRID foi salvo usando torch_scatter e torch_sparse. 
    // Para o LibTorch C++ reconhecer essas operacoes (ex: torch_scatter::segment_sum_csr),
    // precisamos carregar as bibliotecas compartilhadas (.so) dessas extensoes python.
    // Antes de carregar as extensoes, precisamos carregar a biblioteca de vinculo do proprio Python
    // de forma global (RTLD_GLOBAL), para que simbolos como 'PyInstanceMethod_Type' fiquem disponiveis!
    std::cout << "[INFO] Tentando carregar libpython3.12.so para simbolos globais..." << std::endl;
    void* py_handle = dlopen("/usr/lib/x86_64-linux-gnu/libpython3.12.so", RTLD_NOW | RTLD_GLOBAL);
    if (!py_handle) {
        py_handle = dlopen("libpython3.12.so", RTLD_NOW | RTLD_GLOBAL);
    }
    if (!py_handle) {
        std::cerr << "[AVISO] Nao foi possivel carregar libpython3.12.so: " << dlerror() << std::endl;
    } else {
        std::cout << "[OK] Símbolos do Python carregados com sucesso." << std::endl;
    }

    std::cout << "[INFO] Tentando carregar extensoes do torch_scatter e torch_sparse..." << std::endl;
    std::vector<std::string> sos = {
        // torch_scatter
        "../.venv_wsl/lib/python3.12/site-packages/torch_scatter/_version_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_scatter/_scatter_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_scatter/_segment_coo_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_scatter/_segment_csr_cpu.so",
        // torch_sparse
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_version_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_convert_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_diag_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_ego_sample_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_hgt_sample_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_metis_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_neighbor_sample_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_relabel_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_rw_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_saint_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_sample_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_sparse/_spmm_cpu.so"
    };
    for (const auto& path : sos) {
        void* handle = dlopen(path.c_str(), RTLD_LAZY | RTLD_GLOBAL);
        if (!handle) {
            std::cerr << "[AVISO] Nao foi possivel carregar: " << path << " Erro: " << dlerror() << std::endl;
        } else {
            std::cout << "[OK] Carregado: " << path << std::endl;
        }
    }

    // Carregar Modelo
    torch::jit::script::Module module;
    try {
        module = torch::jit::load("spectre_model_scripted.pt");
        module.eval();
        std::cout << "[OK] Modelo carregado com sucesso." << std::endl;
    } catch (const c10::Error& e) {
        std::cerr << "[ERRO] Falha ao carregar o modelo: " << e.what() << std::endl;
        return -1;
    }

    const int ITERATIONS = 10000;
    const int SEQ_LEN = 10;
    const int NUM_FEATURES = 20;

    std::cout << "\nIniciando " << ITERATIONS << " inferencias simuladas (Tensor Shape: [1, " << SEQ_LEN << ", " << NUM_FEATURES << "])..." << std::endl;

    // Gerar um tensor pre-alocado de lixo para evitar overhead de alocacao dinamica no loop
    auto options = torch::TensorOptions().dtype(torch::kFloat32);
    torch::Tensor mock_tensor = torch::rand({1, SEQ_LEN, NUM_FEATURES}, options);
    
    // O modelo GATConv necessita de um tensor edge_index como segundo argumento de tamanho [2, E]
    auto edge_options = torch::TensorOptions().dtype(torch::kLong);
    torch::Tensor mock_edge_index = torch::tensor({{0}, {0}}, edge_options); // self-loop no nó 0

    std::vector<torch::jit::IValue> inputs;
    inputs.push_back(mock_tensor);
    inputs.push_back(mock_edge_index);

    std::cout << "[DEBUG] Tamanho do vetor inputs: " << inputs.size() << std::endl;
    std::cout << "[DEBUG] Elemento 0 tipo: " << inputs[0].tagKind() << " shape: " << inputs[0].toTensor().sizes() << std::endl;
    std::cout << "[DEBUG] Elemento 1 tipo: " << inputs[1].tagKind() << " shape: " << inputs[1].toTensor().sizes() << std::endl;

    // Warm-up do modelo (compilacao lazy inicial)
    for (int i = 0; i < 5; ++i) {
        module.forward(inputs).toTensor();
    }

    auto start_time = std::chrono::high_resolution_clock::now();

    // Loop de stress
    for (int i = 0; i < ITERATIONS; ++i) {
        torch::Tensor output = module.forward(inputs).toTensor();
        float prob = torch::sigmoid(output).item<float>();
        
        // Simular logica de drop (previne otimizacao agressiva do compilador)
        if (prob > 0.999f) {
            volatile int drop = 1;
        }
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    auto total_duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
    auto avg_latency_us = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time).count() / ITERATIONS;

    std::cout << "\n===============================================" << std::endl;
    std::cout << "Resultado do Benchmark:" << std::endl;
    std::cout << "Tempo Total (" << ITERATIONS << " runs): " << total_duration << " ms" << std::endl;
    std::cout << "Latência Média por Inferencia: " << avg_latency_us << " microsegundos (us)" << std::endl;
    std::cout << "===============================================" << std::endl;

    return 0;
}
