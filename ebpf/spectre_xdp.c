#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#include "common.h"

// Map for tracking active flows
struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, MAX_TRACKED_FLOWS);
    __type(key, struct flow_key_t);
    __type(value, struct flow_metrics_t);
} flow_map SEC(".maps");

// Map for blocking malicious IPs (Key: IP source address)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, MAX_BLOCKED_IPS);
    __type(key, __u32);
    __type(value, struct block_info_t);
} block_map SEC(".maps");

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
        key.src_port = tcph->source;
        key.dst_port = tcph->dest;
    } else if (iph->protocol == IPPROTO_UDP) {
        udph = (void *)(iph + 1);
        if ((void *)(udph + 1) > data_end)
            return XDP_PASS;
        key.src_port = udph->source;
        key.dst_port = udph->dest;
    } else {
        return XDP_PASS; // Not tracking other protocols for now
    }

    // Lookup or initialize metrics
    struct flow_metrics_t *metrics = bpf_map_lookup_elem(&flow_map, &key);
    if (metrics) {
        // Update existing flow
        __sync_fetch_and_add(&metrics->bytes, iph->tot_len);
        __sync_fetch_and_add(&metrics->packets, 1);
        metrics->last_time_ns = bpf_ktime_get_ns();
        
        if (tcph) {
            if (tcph->syn) __sync_fetch_and_add(&metrics->syn_count, 1);
            if (tcph->ack) __sync_fetch_and_add(&metrics->ack_count, 1);
            if (tcph->fin) __sync_fetch_and_add(&metrics->fin_count, 1);
            if (tcph->rst) __sync_fetch_and_add(&metrics->rst_count, 1);
        }
    } else {
        // New flow
        struct flow_metrics_t new_metrics = {};
        new_metrics.bytes = iph->tot_len;
        new_metrics.packets = 1;
        new_metrics.start_time_ns = bpf_ktime_get_ns();
        new_metrics.last_time_ns = new_metrics.start_time_ns;
        
        if (tcph) {
            if (tcph->syn) new_metrics.syn_count = 1;
            if (tcph->ack) new_metrics.ack_count = 1;
            if (tcph->fin) new_metrics.fin_count = 1;
            if (tcph->rst) new_metrics.rst_count = 1;
        }

        bpf_map_update_elem(&flow_map, &key, &new_metrics, BPF_ANY);
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
