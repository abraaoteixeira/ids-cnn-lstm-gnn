#include <iostream>
#include <unistd.h>
#include <bpf/libbpf.h>
#include <bpf/bpf.h>
#include <net/if.h>
#include <arpa/inet.h>
#include <vector>
#include <csignal>

#include "common.h"

static bool exiting = false;

static void sig_handler(int sig) {
    exiting = true;
}

// Helper to format IPs
std::string format_ip(__u32 ip) {
    struct in_addr ip_addr;
    ip_addr.s_addr = ip;
    return std::string(inet_ntoa(ip_addr));
}

int main(int argc, char **argv) {
    if (argc < 2) {
        std::cerr << "Uso: " << argv[0] << " <interface_de_rede> (ex: eth0)" << std::endl;
        return 1;
    }

    const char *iface = argv[1];
    int ifindex = if_nametoindex(iface);
    if (ifindex == 0) {
        std::cerr << "Erro: Interface " << iface << " nao encontrada." << std::endl;
        return 1;
    }

    // 1. Carregar o arquivo compilado do eBPF
    struct bpf_object *obj = bpf_object__open_file("spectre_xdp.o", NULL);
    if (libbpf_get_error(obj)) {
        std::cerr << "Erro ao abrir spectre_xdp.o" << std::endl;
        return 1;
    }

    if (bpf_object__load(obj)) {
        std::cerr << "Erro ao carregar o objeto BPF no kernel." << std::endl;
        return 1;
    }

    // 2. Localizar o programa XDP
    struct bpf_program *prog = bpf_object__find_program_by_name(obj, "spectre_xdp_prog");
    if (!prog) {
        std::cerr << "Erro ao achar o programa XDP 'spectre_xdp_prog'" << std::endl;
        return 1;
    }

    // 3. Anexar o programa a interface de rede
    struct bpf_link *link = bpf_program__attach_xdp(prog, ifindex);
    if (libbpf_get_error(link)) {
        std::cerr << "Erro ao anexar o programa XDP a interface " << iface << std::endl;
        return 1;
    }

    std::cout << "[SPECTRE-GRID] XDP Hook anexado com sucesso na interface " << iface << std::endl;

    // 4. Localizar os mapas
    struct bpf_map *flow_map = bpf_object__find_map_by_name(obj, "flow_map");
    struct bpf_map *block_map = bpf_object__find_map_by_name(obj, "block_map");
    
    int flow_map_fd = bpf_map__fd(flow_map);
    int block_map_fd = bpf_map__fd(block_map);

    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    // Loop de Integracao Kernel -> User Space
    std::cout << "Monitorando fluxos e aguardando inferencia... (Ctrl+C para sair)" << std::endl;
    
    while (!exiting) {
        struct flow_key_t key = {}, next_key;
        struct flow_metrics_t metrics;
        
        int flow_count = 0;
        
        // Iterar pelos fluxos capturados no kernel
        while (bpf_map_get_next_key(flow_map_fd, &key, &next_key) == 0) {
            if (bpf_map_lookup_elem(flow_map_fd, &next_key, &metrics) == 0) {
                flow_count++;
                
                // --- INTEGRACAO LIBTORCH AQUI ---
                // No motor nativo (main.cpp), transformariamos metrics em tensores.
                // auto features = torch::tensor({ metrics.bytes, metrics.packets, metrics.syn_count, ... });
                // auto prediction = module.forward({ features }).toTensor();
                // if (prediction.item<float>() > 0.8) { bloqueia IP }
                
                // Para exemplo, se detectarmos pacotes suspeitamente altos de um mesmo IP:
                if (metrics.syn_count > 1000) {
                    std::cout << "[ALERTA] SYN Flood detectado de " << format_ip(next_key.src_ip) << "! Aplicando bloqueio." << std::endl;
                    
                    struct block_info_t binfo = {};
                    binfo.block_time_ns = 0; // Usariamos time actual
                    binfo.blocked_packets = 0;
                    bpf_map_update_elem(block_map_fd, &next_key.src_ip, &binfo, BPF_ANY);
                }
            }
            key = next_key;
        }

        if (flow_count > 0) {
            std::cout << "[INFO] " << flow_count << " fluxos ativos processados na ultima janela." << std::endl;
        }
        
        sleep(1); // Janela temporal de 1 segundo (Batch de Inferencia)
    }

    std::cout << "Encerrando SPECTRE-GRID e removendo ganchos XDP..." << std::endl;
    bpf_link__destroy(link);
    bpf_object__close(obj);

    return 0;
}
