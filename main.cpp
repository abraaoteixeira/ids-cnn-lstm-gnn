
#include <torch/script.h>
#include <iostream>
#include <memory>
#include <vector>

#include <thread>
#include <chrono>
#include <atomic>
#include <csignal>

static std::atomic<bool> running(true);

void handle_signal(int) {
    running.store(false);
}

int main(int argc, const char* argv[]) {
    if (argc != 2) {
        std::cerr << "Uso: spectre_inference <caminho_para_modelo_torchscript.pt>\n";
        return -1;
    }

    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);

    torch::jit::script::Module module;
    try {
        // Carregar o modelo exportado via TorchScript
        module = torch::jit::load(argv[1]);
        std::cout << "[✓] Modelo TorchScript carregado com sucesso.\n";
    }
    catch (const c10::Error& e) {
        std::cerr << "[!] Erro ao carregar o modelo: " << e.msg() << "\n";
        return -1;
    }

    std::cout << "[i] Iniciando loop principal do daemon (DRY-RUN - simulação). Use Ctrl+C para sair.\n";

    // Loop principal simulado — pronto para integração com NFQUEUE
    while (running.load()) {
        // Simular recepção de pacotes e construção de tensores de entrada
        // (Em produção, substitua por NFQUEUE/eBPF + pré-processador nativo)
        at::Tensor inputs = torch::randn({1, 10, 20});
        at::Tensor edge_index = torch::zeros({2, 1}, torch::kLong);

        std::vector<torch::jit::IValue> ival_inputs;
        ival_inputs.push_back(inputs);
        ival_inputs.push_back(edge_index);

        try {
            at::Tensor output = module.forward(ival_inputs).toTensor();
            float logit = output.numel() ? output[0].item<float>() : 0.0f;
            std::cout << "[daemon] Logit: " << logit << "\n";
        } catch (const c10::Error& e) {
            std::cerr << "[daemon] Erro durante inferência: " << e.msg() << "\n";
        }

        // Espera curta — em produção este timing viria do fluxo de pacotes
        std::this_thread::sleep_for(std::chrono::milliseconds(250));
    }

    std::cout << "[i] Encerrando daemon (DRY-RUN).\n";
    return 0;
}
