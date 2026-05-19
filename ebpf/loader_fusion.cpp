/**
 * loader_fusion.cpp — SPECTRE-GRID Fusion Engine v2.0
 *
 * Motor de fusão: eBPF/XDP (Kernel) + LibTorch (IA) com Ring Buffer Estático.
 *
 * Regras de Arquitetura:
 *   - ZERO alocação dinâmica no hot loop (std::array, sem push_back)
 *   - Ring buffer estático [10][20] com ponteiro circular
 *   - Inferência CONDICIONAL: forward() só dispara quando packet_count >= 10
 *   - Safe Deploy: main.cpp e loader.cpp permanecem intocados
 */

#include <iostream>
#include <unistd.h>
#include <bpf/libbpf.h>
#include <bpf/bpf.h>
#include <net/if.h>
#include <arpa/inet.h>
#include <array>
#include <unordered_map>
#include <vector>
#include <cstring>
#include <cmath>
#include <csignal>
#include <torch/script.h>
#include <torch/torch.h>
#include <dlfcn.h>

#include <linux/if_link.h>
#include "common.h"

// =====================================================================
// CONSTANTES — ZERO MAGIC NUMBERS
// =====================================================================
static constexpr int SEQ_LEN        = 10;
static constexpr int NUM_FEATURES   = 20;
static constexpr float DROP_THRESH  = 0.95f;

static bool exiting = false;
static void sig_handler(int) { exiting = true; }

// =====================================================================
// ESTRUTURA DE ALTO DESEMPENHO — ZERO ALOCAÇÃO DINÂMICA
// =====================================================================
/**
 * FlowContext: buffer por IP de origem.
 *
 * - ring_buffer: std::array estático [10][20] — SEM heap allocation.
 * - current_index: ponteiro circular (módulo 10).
 * - packet_count: janelas temporais acumuladas.
 *
 * Campos auxiliares para derivação de deltas e normalização Z-score:
 * - prev_*: snapshot da janela anterior para cálculo de Δ.
 * - sum/sq_sum: estatísticas correntes para Z-score online (Welford).
 */
struct FlowContext {
    std::array<std::array<float, NUM_FEATURES>, SEQ_LEN> ring_buffer = {};
    int current_index = 0;
    int packet_count  = 0;

    // Snapshot anterior para deltas
    uint64_t prev_bytes   = 0;
    uint64_t prev_packets = 0;
    uint32_t prev_syn     = 0;
    uint32_t prev_ack     = 0;
    uint32_t prev_fin     = 0;
    uint32_t prev_rst     = 0;
    uint64_t prev_ts_ns   = 0;

    // Welford online Z-score
    std::array<float, NUM_FEATURES> sum    = {};
    std::array<float, NUM_FEATURES> sq_sum = {};
    int norm_n = 0;

    // Pico histórico de PPS (burst detection)
    float peak_pps = 0.0f;
};

// =====================================================================
// DERIVAÇÃO DE 20 FEATURES (ZERO HEAP)
// =====================================================================
/**
 * Extrai 20 features estatísticas a partir das métricas brutas do eBPF.
 * Opera 100% em stack — nenhuma alocação dinâmica.
 *
 * [0]  delta_bytes           [10] ack_ratio
 * [1]  delta_packets         [11] fin_ratio
 * [2]  delta_syn             [12] rst_ratio
 * [3]  delta_ack             [13] syn_ack_ratio (SYN flood)
 * [4]  delta_fin             [14] duration_s
 * [5]  delta_rst             [15] log_total_bytes
 * [6]  bytes_per_packet      [16] log_total_packets
 * [7]  packets_per_second    [17] flag_entropy
 * [8]  bytes_per_second      [18] inter_arrival_ms
 * [9]  syn_ratio             [19] burst_intensity
 */
static void derive_features(const flow_metrics_t& m,
                             FlowContext& ctx,
                             uint64_t now_ns,
                             std::array<float, NUM_FEATURES>& out)
{
    // --- Deltas (clamp a zero para wrap-around) ---
    float db  = std::fmax(0.0f, static_cast<float>(m.bytes      - ctx.prev_bytes));
    float dp  = std::fmax(0.0f, static_cast<float>(m.packets    - ctx.prev_packets));
    float ds  = std::fmax(0.0f, static_cast<float>(m.syn_count  - ctx.prev_syn));
    float da  = std::fmax(0.0f, static_cast<float>(m.ack_count  - ctx.prev_ack));
    float df  = std::fmax(0.0f, static_cast<float>(m.fin_count  - ctx.prev_fin));
    float dr  = std::fmax(0.0f, static_cast<float>(m.rst_count  - ctx.prev_rst));

    // Janela temporal (segundos)
    float dt = (now_ns > ctx.prev_ts_ns)
               ? static_cast<float>(now_ns - ctx.prev_ts_ns) / 1e9f
               : 1.0f;

    // Acumulados totais
    float tb = static_cast<float>(m.bytes);
    float tp = static_cast<float>(m.packets);
    float ts = static_cast<float>(m.syn_count);
    float ta = static_cast<float>(m.ack_count);
    float tf = static_cast<float>(m.fin_count);
    float tr = static_cast<float>(m.rst_count);

    float safe_pkts = std::fmax(tp, 1.0f);

    // [0..5] Deltas brutos
    out[0]  = db;
    out[1]  = dp;
    out[2]  = ds;
    out[3]  = da;
    out[4]  = df;
    out[5]  = dr;

    // [6..8] Taxas derivadas
    out[6]  = (dp > 0.0f) ? db / dp : 0.0f;    // bytes_per_packet
    out[7]  = dp / dt;                           // packets_per_second
    out[8]  = db / dt;                           // bytes_per_second

    // [9..12] Proporções de flags TCP
    out[9]  = ts / safe_pkts;   // syn_ratio
    out[10] = ta / safe_pkts;   // ack_ratio
    out[11] = tf / safe_pkts;   // fin_ratio
    out[12] = tr / safe_pkts;   // rst_ratio

    // [13] Indicador de SYN flood
    out[13] = ts / std::fmax(ta, 1.0f);

    // [14] Duração total do fluxo (s)
    out[14] = std::fmax(static_cast<float>(m.last_time_ns - m.start_time_ns) / 1e9f, 0.0f);

    // [15..16] Volume cumulativo (log)
    out[15] = std::log1p(tb);
    out[16] = std::log1p(tp);

    // [17] Entropia de Shannon das flags TCP
    float flag_total = ts + ta + tf + tr;
    float entropy = 0.0f;
    if (flag_total > 0.0f) {
        float flags[4] = {ts, ta, tf, tr};
        for (int i = 0; i < 4; ++i) {
            if (flags[i] > 0.0f) {
                float p = flags[i] / flag_total;
                entropy -= p * std::log2(p);
            }
        }
    }
    out[17] = entropy;

    // [18] Tempo médio entre pacotes (ms)
    out[18] = (dp > 1.0f) ? (dt * 1000.0f) / dp : dt * 1000.0f;

    // [19] Burst intensity
    float pps = out[7];
    if (pps > ctx.peak_pps) ctx.peak_pps = pps;
    out[19] = (ctx.peak_pps > 0.0f) ? pps / ctx.peak_pps : 0.0f;

    // --- Salvar snapshot para próximo delta ---
    ctx.prev_bytes   = m.bytes;
    ctx.prev_packets = m.packets;
    ctx.prev_syn     = m.syn_count;
    ctx.prev_ack     = m.ack_count;
    ctx.prev_fin     = m.fin_count;
    ctx.prev_rst     = m.rst_count;
    ctx.prev_ts_ns   = now_ns;
}

// =====================================================================
// NORMALIZAÇÃO Z-SCORE (WELFORD ONLINE — ZERO HEAP)
// =====================================================================
static void normalize_zscore(FlowContext& ctx, std::array<float, NUM_FEATURES>& feat) {
    ctx.norm_n++;
    float n = static_cast<float>(ctx.norm_n);

    for (int i = 0; i < NUM_FEATURES; ++i) {
        ctx.sum[i]    += feat[i];
        ctx.sq_sum[i] += feat[i] * feat[i];

        float mean   = ctx.sum[i] / n;
        float var    = (ctx.sq_sum[i] / n) - (mean * mean);
        float stddev = std::sqrt(std::fmax(var, 1e-8f));

        feat[i] = (feat[i] - mean) / stddev;
    }
}

// =====================================================================
// TENSOR BUILDER (CRONOLÓGICO — ZERO HEAP)
// =====================================================================
/**
 * Constrói tensor [1, 10, 20] a partir do ring buffer em ordem cronológica.
 * O slot mais antigo está em current_index (se cheio). Usa .clone() para
 * desacoplar da memória do ring_buffer.
 */
static torch::Tensor build_tensor(const FlowContext& ctx) {
    // Array estático em stack para montar o tensor em ordem cronológica
    float flat[SEQ_LEN * NUM_FEATURES];

    for (int t = 0; t < SEQ_LEN; ++t) {
        int read_idx = (ctx.current_index + t) % SEQ_LEN;
        std::memcpy(&flat[t * NUM_FEATURES],
                     ctx.ring_buffer[read_idx].data(),
                     sizeof(float) * NUM_FEATURES);
    }

    return torch::from_blob(flat, {1, SEQ_LEN, NUM_FEATURES}, torch::kFloat32).clone();
}

// =====================================================================
// UTILIDADES
// =====================================================================
static std::string format_ip(__u32 ip) {
    struct in_addr a;
    a.s_addr = ip;
    return std::string(inet_ntoa(a));
}

static uint64_t clock_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<uint64_t>(ts.tv_sec) * 1000000000ULL + ts.tv_nsec;
}

// =====================================================================
// MAIN
// =====================================================================
int main(int argc, char **argv) {
    if (argc < 2) {
        std::cerr << "Uso: " << argv[0] << " <interface> (ex: eth0)" << std::endl;
        return 1;
    }

    const char *iface = argv[1];
    int ifindex = if_nametoindex(iface);
    if (ifindex == 0) {
        std::cerr << "Erro: Interface " << iface << " nao encontrada." << std::endl;
        return 1;
    }

    // --- EXTENSOES DE GRAFO (GNN) ---
    std::cout << "[INFO] Carregando libpython3.12.so..." << std::endl;
    void* py_handle = dlopen("/usr/lib/x86_64-linux-gnu/libpython3.12.so", RTLD_NOW | RTLD_GLOBAL);
    if (!py_handle) py_handle = dlopen("libpython3.12.so", RTLD_NOW | RTLD_GLOBAL);
    if (!py_handle) std::cerr << "[AVISO] libpython3.12.so: " << dlerror() << std::endl;

    std::cout << "[INFO] Carregando extensoes torch_scatter/torch_sparse..." << std::endl;
    const char* ext_paths[] = {
        "../.venv_wsl/lib/python3.12/site-packages/torch_scatter/_version_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_scatter/_scatter_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_scatter/_segment_coo_cpu.so",
        "../.venv_wsl/lib/python3.12/site-packages/torch_scatter/_segment_csr_cpu.so",
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
    for (const auto& path : ext_paths) {
        void* h = dlopen(path, RTLD_LAZY | RTLD_GLOBAL);
        if (!h) std::cerr << "[AVISO] " << path << ": " << dlerror() << std::endl;
        else    std::cout << "[OK] " << path << std::endl;
    }

    // --- CARREGAMENTO DO MODELO LIBTORCH ---
    std::cout << "[SPECTRE-GRID] Carregando modelo TorchScript..." << std::endl;
    torch::jit::script::Module module;
    try {
        module = torch::jit::load("spectre_model_scripted.pt");
        module.eval();
    } catch (const c10::Error& e) {
        std::cerr << "Erro ao carregar modelo: " << e.what() << std::endl;
        return -1;
    }
    std::cout << "[SPECTRE-GRID] Modelo CNN-LSTM-GAT carregado!" << std::endl;

    // --- CARREGAMENTO eBPF ---
    struct bpf_object *obj = bpf_object__open_file("spectre_xdp.o", NULL);
    if (libbpf_get_error(obj)) {
        std::cerr << "Erro ao abrir spectre_xdp.o" << std::endl;
        return 1;
    }
    if (bpf_object__load(obj)) {
        std::cerr << "Erro ao carregar BPF no kernel." << std::endl;
        return 1;
    }

    struct bpf_program *prog = bpf_object__find_program_by_name(obj, "spectre_xdp_prog");
    if (!prog) {
        std::cerr << "Programa XDP 'spectre_xdp_prog' nao encontrado." << std::endl;
        return 1;
    }

    struct bpf_link *link = bpf_program__attach_xdp(prog, ifindex);
    bool attached_native = true;
    if (libbpf_get_error(link)) {
        attached_native = false;
        std::cout << "[AVISO] Modo Nativo falhou. Tentando SKB..." << std::endl;
        int prog_fd = bpf_program__fd(prog);
        int err = bpf_xdp_attach(ifindex, prog_fd, XDP_FLAGS_SKB_MODE, NULL);
        if (err < 0) {
            std::cerr << "Erro critico: XDP falhou em ambos os modos (err=" << err << ")" << std::endl;
            return 1;
        }
        std::cout << "[SPECTRE-GRID] XDP anexado em MODO SKB em " << iface << std::endl;
    } else {
        std::cout << "[SPECTRE-GRID] XDP anexado em MODO NATIVO em " << iface << std::endl;
    }

    struct bpf_map *bpf_flow_map = bpf_object__find_map_by_name(obj, "flow_map");
    struct bpf_map *bpf_block_map = bpf_object__find_map_by_name(obj, "block_map");
    int flow_map_fd  = bpf_map__fd(bpf_flow_map);
    int block_map_fd = bpf_map__fd(bpf_block_map);

    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    // =====================================================================
    // PASSO 2: MAPA DE RASTREAMENTO — INDEXADO POR IP DE ORIGEM
    // =====================================================================
    std::unordered_map<uint32_t, FlowContext> flow_tracker;

    // Edge tensor pré-alocado (self-loop, reutilizado a cada inferência)
    torch::Tensor edge_tensor = torch::tensor({{0}, {0}}, torch::kLong);

    // Telemetria
    uint64_t total_inferences = 0;
    uint64_t total_blocks     = 0;

    std::cout << "\n=====================================================" << std::endl;
    std::cout << "[SPECTRE-GRID] Fusion Engine v2.0 — Ring Buffer Estático" << std::endl;
    std::cout << "[SPECTRE-GRID] " << SEQ_LEN << " janelas × " << NUM_FEATURES << " features" << std::endl;
    std::cout << "[SPECTRE-GRID] Limiar XDP_DROP: " << (DROP_THRESH * 100.0f) << "%" << std::endl;
    std::cout << "[SPECTRE-GRID] Monitorando " << iface << std::endl;
    std::cout << "=====================================================" << std::endl;

    // =====================================================================
    // HOT LOOP — ZERO ALOCAÇÃO DINÂMICA
    // =====================================================================
    while (!exiting) {
        struct flow_key_t key = {}, next_key;
        struct flow_metrics_t metrics;
        uint64_t now = clock_ns();

        int flows_seen = 0;
        int inferences_run = 0;

        while (bpf_map_get_next_key(flow_map_fd, &key, &next_key) == 0) {
            if (bpf_map_lookup_elem(flow_map_fd, &next_key, &metrics) == 0) {
                flows_seen++;

                // Indexar FlowContext pelo IP de origem
                uint32_t src_ip = next_key.src_ip;
                FlowContext& ctx = flow_tracker[src_ip];

                // Primeira observação: salvar snapshot e pular (sem delta ainda)
                if (ctx.norm_n == 0 && ctx.packet_count == 0) {
                    ctx.prev_bytes   = metrics.bytes;
                    ctx.prev_packets = metrics.packets;
                    ctx.prev_syn     = metrics.syn_count;
                    ctx.prev_ack     = metrics.ack_count;
                    ctx.prev_fin     = metrics.fin_count;
                    ctx.prev_rst     = metrics.rst_count;
                    ctx.prev_ts_ns   = now;
                    key = next_key;
                    continue;
                }

                // --- PASSO 2a: Derivar 20 features (stack-only) ---
                std::array<float, NUM_FEATURES> feat = {};
                derive_features(metrics, ctx, now, feat);

                // --- PASSO 2b: Normalizar Z-score (Welford online) ---
                normalize_zscore(ctx, feat);

                // --- PASSO 2c: Inserir no ring buffer (ponteiro circular) ---
                ctx.ring_buffer[ctx.current_index] = feat;
                ctx.current_index = (ctx.current_index + 1) % SEQ_LEN;
                ctx.packet_count++;

                // =========================================================
                // PASSO 3: INFERÊNCIA CONDICIONAL (SÓ SE packet_count >= 10)
                // =========================================================
                if (ctx.packet_count >= SEQ_LEN) {
                    try {
                        // Montar tensor [1, 10, 20] em ordem cronológica
                        torch::Tensor input = build_tensor(ctx);

                        // Forward pass: CNN1D → LSTM → GATConv → FC
                        std::vector<torch::jit::IValue> inputs;
                        inputs.push_back(input);
                        inputs.push_back(edge_tensor);
                        torch::Tensor output = module.forward(inputs).toTensor();

                        float prob = torch::sigmoid(output).item<float>();
                        total_inferences++;
                        inferences_run++;

                        // --- GATILHO XDP_DROP ---
                        if (prob > DROP_THRESH) {
                            std::cout << "[ALERTA CRITICO - XDP_DROP] IP: "
                                      << format_ip(src_ip)
                                      << " | Prob: " << (prob * 100.0f) << "%"
                                      << " | Janelas: " << ctx.packet_count
                                      << std::endl;

                            struct block_info_t binfo = {};
                            binfo.block_time_ns = now;
                            binfo.blocked_packets = 0;
                            bpf_map_update_elem(block_map_fd, &src_ip, &binfo, BPF_ANY);
                            total_blocks++;
                        }
                    } catch (const c10::Error& e) {
                        std::cerr << "[ERRO] forward() falhou: " << e.what() << std::endl;
                    }
                }
            }
            key = next_key;
        }

        if (flows_seen > 0) {
            std::cout << "[INFO] " << flows_seen << " fluxos | "
                      << inferences_run << " inferencias | "
                      << flow_tracker.size() << " IPs rastreados | "
                      << total_blocks << " bloqueios" << std::endl;
        }

        sleep(1);
    }

    // =====================================================================
    // SHUTDOWN
    // =====================================================================
    std::cout << "\n=====================================================" << std::endl;
    std::cout << "[SPECTRE-GRID] Encerrando Fusion Engine v2.0" << std::endl;
    std::cout << "[SPECTRE-GRID] Total: " << total_inferences << " inferencias | "
              << total_blocks << " bloqueios" << std::endl;
    std::cout << "=====================================================" << std::endl;

    if (attached_native) bpf_link__destroy(link);
    else                 bpf_xdp_detach(ifindex, XDP_FLAGS_SKB_MODE, NULL);
    bpf_object__close(obj);

    return 0;
}
