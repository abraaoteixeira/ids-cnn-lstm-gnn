/**
 * loader_fusion_v2.cpp — SPECTRE-GRID Fusion Engine v2.0 (Multi-Threaded)
 *
 * Motor de fusão: eBPF/XDP (Kernel) + LibTorch (IA)
 * 
 * Arquitetura Side-by-Side:
 *   - Thread 1 (Produtora): eBPF Ring Buffer Polling de altíssima prioridade.
 *   - Thread 2 (Consumidora): Agregação de features e Inferência LibTorch.
 *   - Comunicação via std::queue thread-safe para evitar bloqueios na captura.
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
#include <fstream>
#include <iomanip>
#include <sstream>
#include <ifaddrs.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <netdb.h>
#include <ctime>
#include <thread>
#include <mutex>
#include <queue>
#include <condition_variable>
#include <atomic>

#include "common.h"

// =====================================================================
// CONSTANTES
// =====================================================================
static constexpr int SEQ_LEN        = 10;
static constexpr int NUM_FEATURES   = 20;
static constexpr float DROP_THRESH  = 0.95f;

static std::atomic<bool> exiting(false);
static void sig_handler(int) { exiting = true; }

// =====================================================================
// QUEUE THREAD-SAFE (PRODUTOR-CONSUMIDOR)
// =====================================================================
class EventQueue {
private:
    std::queue<flow_event_t> queue_;
    std::mutex mutex_;
    std::condition_variable cond_;
public:
    void push(const flow_event_t& event) {
        std::lock_guard<std::mutex> lock(mutex_);
        queue_.push(event);
        cond_.notify_one();
    }

    bool pop_all(std::vector<flow_event_t>& out_events) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (queue_.empty()) return false;
        
        while (!queue_.empty()) {
            out_events.push_back(queue_.front());
            queue_.pop();
        }
        return true;
    }
    
    size_t size() {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.size();
    }
};

static EventQueue g_event_queue;

// =====================================================================
// ESTRUTURA DE ALTO DESEMPENHO — ZERO ALOCAÇÃO DINÂMICA (NA THREAD 2)
// =====================================================================
struct FlowContext {
    std::array<std::array<float, NUM_FEATURES>, SEQ_LEN> ring_buffer = {};
    int current_index = 0;
    int packet_count  = 0;

    uint64_t prev_bytes   = 0;
    uint64_t prev_packets = 0;
    uint32_t prev_syn     = 0;
    uint32_t prev_ack     = 0;
    uint32_t prev_fin     = 0;
    uint32_t prev_rst     = 0;
    uint64_t prev_ts_ns   = 0;

    std::array<float, NUM_FEATURES> sum    = {};
    std::array<float, NUM_FEATURES> sq_sum = {};
    int norm_n = 0;

    float peak_pps = 0.0f;

    flow_metrics_t latest_metrics = {};
    flow_key_t latest_key = {};
    bool has_update = false;
};

// ... Funções derive_features, normalize_zscore, build_tensor idênticas ...
static void derive_features(const flow_metrics_t& m, FlowContext& ctx, uint64_t now_ns, std::array<float, NUM_FEATURES>& out) {
    float db  = std::fmax(0.0f, static_cast<float>(m.bytes      - ctx.prev_bytes));
    float dp  = std::fmax(0.0f, static_cast<float>(m.packets    - ctx.prev_packets));
    float ds  = std::fmax(0.0f, static_cast<float>(m.syn_count  - ctx.prev_syn));
    float da  = std::fmax(0.0f, static_cast<float>(m.ack_count  - ctx.prev_ack));
    float df  = std::fmax(0.0f, static_cast<float>(m.fin_count  - ctx.prev_fin));
    float dr  = std::fmax(0.0f, static_cast<float>(m.rst_count  - ctx.prev_rst));

    float dt = (now_ns > ctx.prev_ts_ns) ? static_cast<float>(now_ns - ctx.prev_ts_ns) / 1e9f : 1.0f;
    float tb = static_cast<float>(m.bytes);
    float tp = static_cast<float>(m.packets);
    float ts = static_cast<float>(m.syn_count);
    float ta = static_cast<float>(m.ack_count);
    float tf = static_cast<float>(m.fin_count);
    float tr = static_cast<float>(m.rst_count);
    float safe_pkts = std::fmax(tp, 1.0f);

    out[0] = db; out[1] = dp; out[2] = ds; out[3] = da; out[4] = df; out[5] = dr;
    out[6] = (dp > 0.0f) ? db / dp : 0.0f; out[7] = dp / dt; out[8] = db / dt;
    out[9] = ts / safe_pkts; out[10] = ta / safe_pkts; out[11] = tf / safe_pkts; out[12] = tr / safe_pkts;
    out[13] = ts / std::fmax(ta, 1.0f);
    out[14] = std::fmax(static_cast<float>(m.last_time_ns - m.start_time_ns) / 1e9f, 0.0f);
    out[15] = std::log1p(tb); out[16] = std::log1p(tp);
    
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
    out[18] = (dp > 1.0f) ? (dt * 1000.0f) / dp : dt * 1000.0f;
    float pps = out[7];
    if (pps > ctx.peak_pps) ctx.peak_pps = pps;
    out[19] = (ctx.peak_pps > 0.0f) ? pps / ctx.peak_pps : 0.0f;

    ctx.prev_bytes = m.bytes; ctx.prev_packets = m.packets;
    ctx.prev_syn = m.syn_count; ctx.prev_ack = m.ack_count;
    ctx.prev_fin = m.fin_count; ctx.prev_rst = m.rst_count;
    ctx.prev_ts_ns = now_ns;
}

static void normalize_zscore(FlowContext& ctx, std::array<float, NUM_FEATURES>& feat) {
    ctx.norm_n++;
    float n = static_cast<float>(ctx.norm_n);
    for (int i = 0; i < NUM_FEATURES; ++i) {
        ctx.sum[i] += feat[i]; ctx.sq_sum[i] += feat[i] * feat[i];
        float mean = ctx.sum[i] / n;
        float var = (ctx.sq_sum[i] / n) - (mean * mean);
        float stddev = std::sqrt(std::fmax(var, 1e-8f));
        feat[i] = (feat[i] - mean) / stddev;
    }
}

static torch::Tensor build_tensor(const FlowContext& ctx) {
    float flat[SEQ_LEN * NUM_FEATURES];
    for (int t = 0; t < SEQ_LEN; ++t) {
        int read_idx = (ctx.current_index + t) % SEQ_LEN;
        std::memcpy(&flat[t * NUM_FEATURES], ctx.ring_buffer[read_idx].data(), sizeof(float) * NUM_FEATURES);
    }
    return torch::from_blob(flat, {1, SEQ_LEN, NUM_FEATURES}, torch::kFloat32).clone();
}

static std::string format_ip(__u32 ip) {
    struct in_addr a; a.s_addr = ip;
    return std::string(inet_ntoa(a));
}

static uint64_t clock_ns() {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<uint64_t>(ts.tv_sec) * 1000000000ULL + ts.tv_nsec;
}

static std::string g_local_ip = "127.0.0.1";
static int g_ipc_fd = -1;

static void write_cpp_alert_to_log(uint32_t src_ip, float prob, uint64_t bytes, uint64_t packets) {
    if (g_ipc_fd < 0) {
        g_ipc_fd = socket(AF_UNIX, SOCK_STREAM, 0);
        if (g_ipc_fd >= 0) {
            struct sockaddr_un addr;
            std::memset(&addr, 0, sizeof(addr));
            addr.sun_family = AF_UNIX;
            std::strncpy(addr.sun_path, "/tmp/spectre.sock", sizeof(addr.sun_path) - 1);
            if (connect(g_ipc_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
                close(g_ipc_fd); g_ipc_fd = -1;
            }
        }
    }
    if (g_ipc_fd < 0) return;

    std::time_t t = std::time(nullptr);
    std::tm tm = *std::localtime(&t);
    std::ostringstream ts; ts << std::put_time(&tm, "%H:%M:%S");

    struct in_addr src_addr; src_addr.s_addr = src_ip;
    std::string src_str = inet_ntoa(src_addr);
    bool is_threat = prob > DROP_THRESH;

    std::ostringstream ss;
    ss << "{\"flow_id\": " << (std::rand() % 10000)
       << ", \"src_ip\": \"" << src_str << (is_threat ? " (ALVO SUSPEITO)" : "") << "\""
       << ", \"dst_ip\": \"" << g_local_ip << "\""
       << ", \"port\": 80, \"protocol\": \"TCP\""
       << ", \"probability\": " << std::fixed << std::setprecision(2) << (prob * 100.0f)
       << ", \"is_threat\": " << (is_threat ? "true" : "false")
       << ", \"bytes\": " << bytes << ", \"packets\": " << packets
       << ", \"timestamp\": \"" << ts.str() << "\"}\n";

    std::string payload = ss.str();
    if (send(g_ipc_fd, payload.c_str(), payload.length(), MSG_NOSIGNAL) < 0) {
        close(g_ipc_fd); g_ipc_fd = -1;
    }
}

// Callback do Ring Buffer - Apenas empurra para a Fila (O(1))
static int handle_event(void *ctx, void *data, size_t data_len) {
    if (data_len < sizeof(struct flow_event_t)) return 0;
    auto *event = reinterpret_cast<struct flow_event_t *>(data);
    g_event_queue.push(*event);
    return 0;
}

// =====================================================================
// CONSUMIDOR DE INFERÊNCIA DA IA (Executa na Thread 2)
// =====================================================================
void inference_worker(torch::jit::script::Module module, int block_map_fd) {
    std::unordered_map<uint32_t, FlowContext> flow_tracker;
    torch::Tensor edge_tensor = torch::tensor({{0}, {0}}, torch::kLong);
    uint64_t last_scan_ns = clock_ns();
    
    std::vector<flow_event_t> batch;
    batch.reserve(1000);

    while (!exiting) {
        // Processa eventos da fila e atualiza contextos
        if (g_event_queue.pop_all(batch)) {
            for (const auto& ev : batch) {
                uint32_t src_ip = ev.key.src_ip;
                FlowContext& fctx = flow_tracker[src_ip];
                if (fctx.norm_n == 0 && fctx.packet_count == 0) {
                    fctx.prev_bytes = ev.metrics.bytes; fctx.prev_packets = ev.metrics.packets;
                    fctx.prev_syn = ev.metrics.syn_count; fctx.prev_ack = ev.metrics.ack_count;
                    fctx.prev_fin = ev.metrics.fin_count; fctx.prev_rst = ev.metrics.rst_count;
                    fctx.prev_ts_ns = clock_ns();
                }
                fctx.latest_metrics = ev.metrics;
                fctx.latest_key = ev.key;
                fctx.has_update = true;
            }
            batch.clear();
        }

        uint64_t now = clock_ns();
        // Dispara IA a cada 1 segundo
        if (now - last_scan_ns >= 1000000000ULL) {
            last_scan_ns = now;
            for (auto& pair : flow_tracker) {
                uint32_t src_ip = pair.first;
                FlowContext& ctx = pair.second;
                if (!ctx.has_update) continue;
                ctx.has_update = false;

                std::array<float, NUM_FEATURES> feat = {};
                derive_features(ctx.latest_metrics, ctx, now, feat);

                float raw_pps = feat[7];
                float raw_syn_ratio = feat[9];

                normalize_zscore(ctx, feat);

                const int MODEL_FEATURE_MAPPING[20] = {13, 6, 17, 10, 7, 19, 14, 5, 4, 16, 9, 11, 0, 15, 8, 2, 3, 1, 12, 18};
                std::array<float, NUM_FEATURES> reordered_feat = {};
                for (int i = 0; i < NUM_FEATURES; ++i) {
                    reordered_feat[i] = feat[MODEL_FEATURE_MAPPING[i]];
                }

                ctx.ring_buffer[ctx.current_index] = reordered_feat;
                ctx.current_index = (ctx.current_index + 1) % SEQ_LEN;
                ctx.packet_count++;

                float prob = 0.0f;

                if (ctx.packet_count >= SEQ_LEN) {
                    try {
                        torch::Tensor input = build_tensor(ctx);
                        std::vector<torch::jit::IValue> inputs;
                        inputs.push_back(input); inputs.push_back(edge_tensor);
                        torch::Tensor output = module.forward(inputs).toTensor();
                        prob = torch::sigmoid(output).item<float>();

                        if (raw_pps > 100.0f && raw_syn_ratio > 0.8f) prob = 0.98f;

                        if (prob > DROP_THRESH) {
                            struct block_info_t binfo = {}; binfo.block_time_ns = now; binfo.blocked_packets = 0;
                            bpf_map_update_elem(block_map_fd, &src_ip, &binfo, BPF_ANY);
                        }
                    } catch (const c10::Error& e) {
                        std::cerr << "[ERRO] IA: " << e.what() << std::endl;
                    }
                } else if (raw_pps > 100.0f && raw_syn_ratio > 0.8f) {
                    prob = 0.98f;
                    struct block_info_t binfo = {}; binfo.block_time_ns = now; binfo.blocked_packets = 0;
                    bpf_map_update_elem(block_map_fd, &src_ip, &binfo, BPF_ANY);
                }
                write_cpp_alert_to_log(src_ip, prob, ctx.latest_metrics.bytes, ctx.latest_metrics.packets);
            }
        } else {
            // Dormir um pouco para não fritar a CPU caso a fila esteja vazia
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
    }
}

// =====================================================================
// MAIN
// =====================================================================
int main(int argc, char **argv) {
    if (argc < 2) { std::cerr << "Uso: " << argv[0] << " <interface>\n"; return 1; }
    const char *iface = argv[1];
    int ifindex = if_nametoindex(iface);
    
    std::cout << "[SPECTRE-GRID V2] Carregando motor MT..." << std::endl;

    torch::jit::script::Module module;
    try {
        module = torch::jit::load("spectre_model_scripted.pt");
        module.eval();
    } catch (const c10::Error& e) { std::cerr << "Erro LibTorch: " << e.what() << "\n"; return -1; }

    struct bpf_object *obj = bpf_object__open_file("spectre_xdp.o", NULL);
    if (bpf_object__load(obj)) return 1;

    struct bpf_program *prog = bpf_object__find_program_by_name(obj, "spectre_xdp_prog");
    struct bpf_link *link = bpf_program__attach_xdp(prog, ifindex);
    bool attached_native = !libbpf_get_error(link);

    struct bpf_map *bpf_block_map = bpf_object__find_map_by_name(obj, "block_map");
    int block_map_fd = bpf_map__fd(bpf_block_map);
    struct bpf_map *bpf_ringbuf = bpf_object__find_map_by_name(obj, "ringbuf");
    int ringbuf_map_fd = bpf_map__fd(bpf_ringbuf);

    struct ring_buffer *rb = ring_buffer__new(ringbuf_map_fd, handle_event, NULL, NULL);

    signal(SIGINT, sig_handler); signal(SIGTERM, sig_handler); signal(SIGPIPE, SIG_IGN);

    std::cout << "[SPECTRE-GRID V2] Threads iniciadas: [1] eBPF Poller | [2] GNN Inference Engine" << std::endl;

    // Iniciar Thread de Inferência (Consumidor)
    std::thread inference_th(inference_worker, std::move(module), block_map_fd);

    // Thread Principal (Produtor - Polling eBPF super rápido)
    while (!exiting) {
        ring_buffer__poll(rb, 100);
    }

    inference_th.join();
    
    if (attached_native) bpf_link__destroy(link);
    ring_buffer__free(rb);
    bpf_object__close(obj);
    return 0;
}
