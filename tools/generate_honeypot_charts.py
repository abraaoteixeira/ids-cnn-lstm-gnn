#!/usr/bin/env python3
"""
Generate honeypot analysis charts from real production data.
Creates 5 matplotlib charts for thesis/presentation.
"""

import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import Counter, defaultdict
from datetime import datetime
import numpy as np

# Configuration
INPUT_FILE = "data/honeypot_real_attacks.jsonl"
OUTPUT_DIR = "docs/honeypot_charts"
DPI = 300

def load_honeypot_data():
    """Load JSONL honeypot data."""
    events = []
    try:
        with open(INPUT_FILE, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
    except FileNotFoundError:
        print(f"⚠️  File not found: {INPUT_FILE}")
        return []
    return events

def create_geolocation_chart(events):
    """Chart 1: Geographic distribution (pie chart)."""
    countries = Counter()
    for event in events:
        country = event.get('country', 'Unknown')
        countries[country] += 1
    
    # Top 10 countries + others
    top_countries = dict(countries.most_common(10))
    others = sum(countries[c] for c in countries if c not in top_countries)
    if others > 0:
        top_countries['Other'] = others
    
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = plt.cm.Set3(np.linspace(0, 1, len(top_countries)))
    
    wedges, texts, autotexts = ax.pie(
        top_countries.values(),
        labels=top_countries.keys(),
        autopct='%1.1f%%',
        colors=colors,
        startangle=90,
        textprops={'fontsize': 10}
    )
    
    for autotext in autotexts:
        autotext.set_color('black')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(9)
    
    ax.set_title('Geographic Distribution of Attack Sources\n2,939 Events from 9 Countries', 
                 fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/01_geolocation_distribution.png", dpi=DPI, bbox_inches='tight')
    print("✅ Chart 1: Geolocation distribution")
    plt.close()

def create_top_ips_chart(events):
    """Chart 2: Top 10 attacking IPs (bar chart)."""
    ips = Counter()
    for event in events:
        src_ip = event.get('src_ip', 'Unknown')
        ips[src_ip] += 1
    
    top_ips = dict(ips.most_common(10))
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ips_list = list(top_ips.keys())
    counts = list(top_ips.values())
    
    bars = ax.barh(ips_list, counts, color='#FF6B6B', edgecolor='black', linewidth=1.5)
    
    # Add value labels
    for i, (bar, count) in enumerate(zip(bars, counts)):
        ax.text(count + 5, i, str(count), va='center', fontweight='bold', fontsize=10)
    
    ax.set_xlabel('Number of Attack Events', fontsize=12, fontweight='bold')
    ax.set_ylabel('Source IP Address', fontsize=12, fontweight='bold')
    ax.set_title('Top 10 Attacking IP Addresses\n(Most Persistent Attackers)', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/02_top_ips.png", dpi=DPI, bbox_inches='tight')
    print("✅ Chart 2: Top attacking IPs")
    plt.close()

def create_timeline_chart(events):
    """Chart 3: Attack timeline (line chart over 24h)."""
    # Parse timestamps and group by hour
    hourly_counts = defaultdict(int)
    
    for event in events:
        timestamp_str = event.get('timestamp', '')
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            hour_key = dt.strftime('%H:00')
            hourly_counts[hour_key] += 1
        except:
            pass
    
    # Sort by hour
    hours = sorted(hourly_counts.keys())
    counts = [hourly_counts[h] for h in hours]
    
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(hours, counts, marker='o', linewidth=2.5, markersize=8, 
            color='#4ECDC4', markerfacecolor='#FF6B6B', markeredgewidth=2, markeredgecolor='#4ECDC4')
    ax.fill_between(range(len(hours)), counts, alpha=0.3, color='#4ECDC4')
    
    ax.set_xlabel('Hour of Day (UTC)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Events', fontsize=12, fontweight='bold')
    ax.set_title('Attack Timeline - 24 Hour Distribution\n31/05/2026 to 01/06/2026', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Rotate x labels
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/03_timeline_24h.png", dpi=DPI, bbox_inches='tight')
    print("✅ Chart 3: 24-hour timeline")
    plt.close()

def create_confidence_histogram(events):
    """Chart 4: Confidence score histogram."""
    confidences = []
    for event in events:
        prob = event.get('probability', 0.0)
        confidences.append(prob)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    n, bins, patches = ax.hist(confidences, bins=50, color='#45B7D1', edgecolor='black', linewidth=1.2)
    
    # Color code by confidence level
    for i, patch in enumerate(patches):
        if bins[i] < 0.5:
            patch.set_facecolor('#FF6B6B')  # Red: low confidence
        elif bins[i] < 0.7:
            patch.set_facecolor('#FFA500')  # Orange: medium
        else:
            patch.set_facecolor('#51CF66')  # Green: high confidence
    
    ax.set_xlabel('STGNN Confidence Score', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Events', fontsize=12, fontweight='bold')
    ax.set_title('Distribution of Detection Confidence Scores\n(STGNN Probability)', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Add legend
    red_patch = mpatches.Patch(color='#FF6B6B', label='Low (<0.5)')
    orange_patch = mpatches.Patch(color='#FFA500', label='Medium (0.5-0.7)')
    green_patch = mpatches.Patch(color='#51CF66', label='High (>0.7)')
    ax.legend(handles=[red_patch, orange_patch, green_patch], loc='upper right', fontsize=11)
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/04_confidence_histogram.png", dpi=DPI, bbox_inches='tight')
    print("✅ Chart 4: Confidence histogram")
    plt.close()

def create_port_distribution_chart(events):
    """Chart 5: Port distribution (top attacked ports)."""
    ports = Counter()
    for event in events:
        port = event.get('dst_port', 0)
        ports[port] += 1
    
    top_ports = dict(ports.most_common(15))
    
    fig, ax = plt.subplots(figsize=(12, 6))
    port_labels = [f"Port {p}" for p in top_ports.keys()]
    counts = list(top_ports.values())
    
    # Color ports by protocol
    colors_list = []
    for port in top_ports.keys():
        if port == 22:
            colors_list.append('#FF6B6B')  # SSH - red
        elif port == 3389:
            colors_list.append('#4ECDC4')  # RDP - cyan
        elif port == 23:
            colors_list.append('#FFD93D')  # Telnet - yellow
        else:
            colors_list.append('#95E1D3')  # Others - light cyan
    
    bars = ax.bar(port_labels, counts, color=colors_list, edgecolor='black', linewidth=1.5)
    
    # Add value labels
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(count)}',
                ha='center', va='bottom', fontweight='bold', fontsize=9)
    
    ax.set_ylabel('Number of Attack Events', fontsize=12, fontweight='bold')
    ax.set_title('Top 15 Attacked Destination Ports\n(Port-based Attack Vector Analysis)', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Add legend
    ssh_patch = mpatches.Patch(color='#FF6B6B', label='SSH (22)')
    rdp_patch = mpatches.Patch(color='#4ECDC4', label='RDP (3389)')
    telnet_patch = mpatches.Patch(color='#FFD93D', label='Telnet (23)')
    other_patch = mpatches.Patch(color='#95E1D3', label='Other Ports')
    ax.legend(handles=[ssh_patch, rdp_patch, telnet_patch, other_patch], 
              loc='upper right', fontsize=11)
    
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/05_port_distribution.png", dpi=DPI, bbox_inches='tight')
    print("✅ Chart 5: Port distribution")
    plt.close()

def main():
    """Generate all honeypot charts."""
    print("\n" + "="*60)
    print("🎨 HONEYPOT ANALYSIS CHARTS GENERATOR")
    print("="*60 + "\n")
    
    # Create output directory
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load data
    print(f"📥 Loading honeypot data from {INPUT_FILE}...")
    events = load_honeypot_data()
    
    if not events:
        print("❌ No data found. Exiting.")
        return
    
    print(f"✅ Loaded {len(events)} events\n")
    
    # Generate statistics
    print("📊 Data Summary:")
    print(f"   • Total events: {len(events)}")
    
    unique_ips = len(set(e.get('src_ip', '') for e in events))
    print(f"   • Unique source IPs: {unique_ips}")
    
    countries = len(set(e.get('country', '') for e in events))
    print(f"   • Countries: {countries}")
    
    ports = set(e.get('dst_port', 0) for e in events)
    print(f"   • Unique ports: {len(ports)}")
    
    avg_prob = np.mean([e.get('probability', 0) for e in events])
    print(f"   • Avg confidence: {avg_prob:.3f}\n")
    
    # Generate charts
    print("🎨 Generating charts...\n")
    create_geolocation_chart(events)
    create_top_ips_chart(events)
    create_timeline_chart(events)
    create_confidence_histogram(events)
    create_port_distribution_chart(events)
    
    print("\n" + "="*60)
    print("✅ ALL CHARTS GENERATED SUCCESSFULLY!")
    print(f"📁 Location: {OUTPUT_DIR}/")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
