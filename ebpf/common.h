#ifndef SPECTRE_EBPF_COMMON_H
#define SPECTRE_EBPF_COMMON_H

#include <linux/types.h>

#define MAX_TRACKED_FLOWS 100000
#define MAX_BLOCKED_IPS 10000

// Flow key for tracking (5-tuple)
struct flow_key_t {
    __u32 src_ip;
    __u32 dst_ip;
    __u16 src_port;
    __u16 dst_port;
    __u8 protocol;
};

// Flow metrics to pass to User Space
struct flow_metrics_t {
    __u64 bytes;
    __u64 packets;
    __u64 start_time_ns;
    __u64 last_time_ns;
    __u32 syn_count;
    __u32 ack_count;
    __u32 fin_count;
    __u32 rst_count;
};

// Values for the block map
struct block_info_t {
    __u64 block_time_ns;
    __u64 blocked_packets;
};

#endif /* SPECTRE_EBPF_COMMON_H */
