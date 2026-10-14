#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#include "common.h"

// Map for tracking active flows (Key: IP source address for host aggregation)
struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, MAX_TRACKED_FLOWS);
    __type(key, __u32);
    __type(value, struct flow_metrics_t);
} flow_map SEC(".maps");

// Map for blocking malicious IPs (Key: IP source address)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, MAX_BLOCKED_IPS);
    __type(key, __u32);
    __type(value, struct block_info_t);
} block_map SEC(".maps");

// Map for ring buffer (push events to user space)
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024); // 256KB
} ringbuf SEC(".maps");

SEC("xdp")
int spectre_xdp_prog(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    // Ethernet parsing
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    // IP parsing
    struct iphdr *iph = (void *)(eth + 1);
    if ((void *)(iph + 1) > data_end)
        return XDP_PASS;

    __u32 src_ip = iph->saddr;

    // Check if IP is in the block list
    struct block_info_t *binfo = bpf_map_lookup_elem(&block_map, &src_ip);
    if (binfo) {
        // Block matched, update metrics and drop
        __sync_fetch_and_add(&binfo->blocked_packets, 1);
        return XDP_DROP;
    }

    // Convert tot_len to Host Byte Order (fixes big-endian calculation on x86)
    __u16 pkt_len = bpf_ntohs(iph->tot_len);

    // Populate flow key
    struct flow_key_t key = {};
    key.src_ip = iph->saddr;
    key.dst_ip = iph->daddr;
    key.protocol = iph->protocol;

    struct tcphdr *tcph = NULL;
    struct udphdr *udph = NULL;

    if (iph->protocol == IPPROTO_TCP) {
        tcph = (void *)(iph + 1);
        if ((void *)(tcph + 1) > data_end)
            return XDP_PASS;
        key.src_port = bpf_ntohs(tcph->source);
        key.dst_port = bpf_ntohs(tcph->dest);
    } else if (iph->protocol == IPPROTO_UDP) {
        udph = (void *)(iph + 1);
        if ((void *)(udph + 1) > data_end)
            return XDP_PASS;
        key.src_port = bpf_ntohs(udph->source);
        key.dst_port = bpf_ntohs(udph->dest);
    } else {
        return XDP_PASS; // Not tracking other protocols for now
    }

    __u64 now_ns = bpf_ktime_get_ns();
    int should_export = 0;
    int is_critical_flag = 0;
    if (tcph && (tcph->syn || tcph->rst || tcph->fin)) {
        is_critical_flag = 1;
    }

    // Lookup or initialize metrics (Using src_ip as the map key)
    struct flow_metrics_t current_metrics = {};
    struct flow_metrics_t *metrics = bpf_map_lookup_elem(&flow_map, &src_ip);
    if (metrics) {
        // Update existing flow
        __sync_fetch_and_add(&metrics->bytes, pkt_len);
        __sync_fetch_and_add(&metrics->packets, 1);
        metrics->last_time_ns = now_ns;
        
        if (tcph) {
            if (tcph->syn) __sync_fetch_and_add(&metrics->syn_count, 1);
            if (tcph->ack) __sync_fetch_and_add(&metrics->ack_count, 1);
            if (tcph->fin) __sync_fetch_and_add(&metrics->fin_count, 1);
            if (tcph->rst) __sync_fetch_and_add(&metrics->rst_count, 1);
        }

        // Sampling / Throttling logic to prevent ring buffer saturation:
        // 1. Critical flags (SYN/RST/FIN) throttled at RINGBUF_CRITICAL_FLAG_THROTTLE_NS (100 us)
        // 2. High-rate packet flows throttled at RINGBUF_THROTTLE_NS (500 us) or 1-in-128 sampling
        __u64 elapsed = now_ns - metrics->last_export_ns;
        if (is_critical_flag && elapsed >= RINGBUF_CRITICAL_FLAG_THROTTLE_NS) {
            should_export = 1;
        } else if (elapsed >= RINGBUF_THROTTLE_NS) {
            should_export = 1;
        } else if ((metrics->packets & RINGBUF_PKT_SAMPLE_MASK) == 0) {
            should_export = 1;
        }

        if (should_export) {
            metrics->last_export_ns = now_ns;
        }
        current_metrics = *metrics;
    } else {
        // New flow: always export the very first packet
        current_metrics.bytes = pkt_len;
        current_metrics.packets = 1;
        current_metrics.start_time_ns = now_ns;
        current_metrics.last_time_ns = now_ns;
        current_metrics.last_export_ns = now_ns;
        
        if (tcph) {
            if (tcph->syn) current_metrics.syn_count = 1;
            if (tcph->ack) current_metrics.ack_count = 1;
            if (tcph->fin) current_metrics.fin_count = 1;
            if (tcph->rst) current_metrics.rst_count = 1;
        }

        bpf_map_update_elem(&flow_map, &src_ip, &current_metrics, BPF_ANY);
        should_export = 1;
    }

    // Submit event to User Space via Ring Buffer (if sampling criteria met)
    if (should_export) {
        struct flow_event_t *event = bpf_ringbuf_reserve(&ringbuf, sizeof(struct flow_event_t), 0);
        if (event) {
            event->key = key;
            event->metrics = current_metrics;
            bpf_ringbuf_submit(event, 0);
        }
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
