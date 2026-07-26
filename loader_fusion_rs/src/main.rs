use libbpf_rs::RingBufferBuilder;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tch::{jit, Tensor, Kind};
use tokio::sync::mpsc;
use serde_json::json;
use tokio::net::UnixStream;
use tokio::io::AsyncWriteExt;

// Constantes
const SEQ_LEN: usize = 10;
const NUM_FEATURES: usize = 20;
const DROP_THRESH: f32 = 0.95;
const SOCKET_PATH: &str = "/tmp/spectre.sock";

// Estruturas de dados (simplificadas para o protótipo Rust)
#[repr(C)]
#[derive(Debug, Copy, Clone)]
struct FlowKey {
    src_ip: u32,
    dst_ip: u32,
    src_port: u16,
    dst_port: u16,
    protocol: u8,
}

#[repr(C)]
#[derive(Debug, Copy, Clone)]
struct FlowMetrics {
    packets: u64,
    bytes: u64,
    start_time_ns: u64,
    last_time_ns: u64,
    syn_count: u32,
    ack_count: u32,
    fin_count: u32,
    rst_count: u32,
}

#[repr(C)]
#[derive(Debug, Copy, Clone)]
struct FlowEvent {
    key: FlowKey,
    metrics: FlowMetrics,
}

struct FlowContext {
    ring_buffer: [[f32; NUM_FEATURES]; SEQ_LEN],
    current_index: usize,
    packet_count: usize,
    prev_bytes: u64,
    prev_packets: u64,
    has_update: bool,
    latest_metrics: FlowMetrics,
}

impl FlowContext {
    fn new() -> Self {
        FlowContext {
            ring_buffer: [[0.0; NUM_FEATURES]; SEQ_LEN],
            current_index: 0,
            packet_count: 0,
            prev_bytes: 0,
            prev_packets: 0,
            has_update: false,
            latest_metrics: FlowMetrics { packets: 0, bytes: 0, start_time_ns: 0, last_time_ns: 0, syn_count: 0, ack_count: 0, fin_count: 0, rst_count: 0 },
        }
    }
}

// Thread Produtora de Eventos via eBPF
fn handle_event(data: &[u8], tx: &mpsc::Sender<FlowEvent>) -> i32 {
    if data.len() < std::mem::size_of::<FlowEvent>() {
        return 0;
    }
    
    // Unsafe pointer cast (zero-copy extraction)
    let event = unsafe { std::ptr::read_unaligned(data.as_ptr() as *const FlowEvent) };
    
    // Tenta enviar o evento para a thread de ML sem bloquear
    let _ = tx.try_send(event);
    0
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("[SPECTRE_RUST] Iniciando Fusion Engine Concorrente em Rust");

    // Inicialização LibTorch (IA)
    let mut model = jit::CModule::load("../spectre_model_scripted.pt").expect("Falha ao carregar modelo TorchScript");
    model.set_eval();
    println!("[SPECTRE_RUST] Modelo de IA carregado");

    // Fila MPSC de altíssimo desempenho para comunicação Produtor -> Consumidor
    let (tx, mut rx) = mpsc::channel::<FlowEvent>(10000);

    // =========================================================================
    // Thread Consumidora (Agregação de Estado e Inferência com LibTorch)
    // =========================================================================
    tokio::spawn(async move {
        let mut flow_tracker: HashMap<u32, FlowContext> = HashMap::new();
        
        // Edge index simulado para GATConv
        let edge_index = Tensor::zeros(&[2, 1], (Kind::Int64, tch::Device::Cpu));

        loop {
            // Processa eventos pendentes
            while let Ok(event) = rx.try_recv() {
                let src_ip = event.key.src_ip;
                let ctx = flow_tracker.entry(src_ip).or_insert(FlowContext::new());
                ctx.latest_metrics = event.metrics;
                ctx.has_update = true;
            }

            // Inferência disparada a cada segundo
            for (src_ip, ctx) in flow_tracker.iter_mut() {
                if !ctx.has_update { continue; }
                ctx.has_update = false;

                // Extração (Simplificada)
                let db = (ctx.latest_metrics.bytes.saturating_sub(ctx.prev_bytes)) as f32;
                let dp = (ctx.latest_metrics.packets.saturating_sub(ctx.prev_packets)) as f32;
                ctx.prev_bytes = ctx.latest_metrics.bytes;
                ctx.prev_packets = ctx.latest_metrics.packets;

                let mut features = [0.0; NUM_FEATURES];
                features[0] = db;
                features[1] = dp;
                // Preenchimento de array omitido para brevidade...
                
                ctx.ring_buffer[ctx.current_index] = features;
                ctx.current_index = (ctx.current_index + 1) % SEQ_LEN;
                ctx.packet_count += 1;

                if ctx.packet_count >= SEQ_LEN {
                    // Flatten manual
                    let mut flat = Vec::with_capacity(SEQ_LEN * NUM_FEATURES);
                    for t in 0..SEQ_LEN {
                        let idx = (ctx.current_index + t) % SEQ_LEN;
                        flat.extend_from_slice(&ctx.ring_buffer[idx]);
                    }
                    
                    let input_tensor = Tensor::from_slice(&flat)
                        .view([1, SEQ_LEN as i64, NUM_FEATURES as i64]);

                    // Inferência (LibTorch)
                    let output = model.forward_ts(&[input_tensor, edge_index.copy()]).unwrap();
                    let prob = f32::from(output.sigmoid());

                    if prob > DROP_THRESH {
                        println!("[ALERTA CRÍTICO - RUST] Ameaça detectada no IP: {} (Prob: {:.2}%)", src_ip, prob * 100.0);
                        // TODO: Gravar em block_map via eBPF
                    }

                    // Gravar no socket assincronamente
                    send_to_ipc_socket(*src_ip, prob, ctx.latest_metrics.bytes, ctx.latest_metrics.packets).await;
                }
            }

            tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
        }
    });

    // =========================================================================
    // Thread Produtora (Leitura Nativa eBPF RingBuf Bloqueante)
    // Roda na Main Thread para não perder CPU cycles.
    // =========================================================================
    // Simularemos o polling infinito no mock. Num ambiente real, `ringbuf.poll()` bloqueia
    // mas a callback `handle_event` apenas envia para o TX (100% lock-free no hotpath).
    
    // let mut builder = RingBufferBuilder::new();
    // builder.add(bpf_ringbuf_map_fd, |data| handle_event(data, &tx)).unwrap();
    // let mgr = builder.build().unwrap();
    
    println!("[SPECTRE_RUST] Ouvindo anel eBPF (Produtor)...");
    loop {
        // mgr.poll(std::time::Duration::from_millis(100)).unwrap();
        tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
    }
}

async fn send_to_ipc_socket(src_ip: u32, prob: f32, bytes: u64, packets: u64) {
    let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
    
    let is_threat = prob > DROP_THRESH;
    let payload = json!({
        "flow_id": 1234,
        "src_ip": format!("192.168.1.{}", src_ip % 255), // mock
        "dst_ip": "127.0.0.1",
        "port": 80,
        "protocol": "TCP",
        "probability": prob * 100.0,
        "is_threat": is_threat,
        "bytes": bytes,
        "packets": packets,
        "timestamp": format!("{}", now)
    });

    if let Ok(mut stream) = UnixStream::connect(SOCKET_PATH).await {
        let msg = format!("{}\n", payload.to_string());
        let _ = stream.write_all(msg.as_bytes()).await;
    }
}
