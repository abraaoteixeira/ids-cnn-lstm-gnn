import React, { useState, useEffect, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Shield, ShieldAlert, Activity, Cpu } from 'lucide-react';
import './index.css';

const WS_URL = "ws://localhost:8001/ws/threats";

function App() {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState({
    totalPackets: 0,
    totalBytes: 0,
    threatsBlocked: 0,
    activeNodes: 0
  });

  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const graphRef = useRef();

  // Gerenciamento de nós e arestas (nodes e links)
  // Utilizamos maps para evitar duplicatas em tempo real
  const nodesMap = useRef(new Map());
  const linksMap = useRef(new Map());

  useEffect(() => {
    // Nós fixos (Core e Internet)
    const coreNode = { id: '127.0.0.1', group: 'core', val: 20, name: 'SPECTRE CORE (XDP)' };
    nodesMap.current.set(coreNode.id, coreNode);
    setGraphData({ nodes: [coreNode], links: [] });

    let ws = new WebSocket(WS_URL);
    
    ws.onopen = () => console.log("WebSocket connected to V2 Backend");
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Atualiza logs (mantem ultimos 50)
        setLogs(prev => [data, ...prev].slice(0, 50));
        
        // Atualiza métricas
        setStats(prev => ({
          ...prev,
          totalPackets: prev.totalPackets + data.packets,
          totalBytes: prev.totalBytes + data.bytes,
          threatsBlocked: data.is_threat ? prev.threatsBlocked + 1 : prev.threatsBlocked
        }));

        // Atualiza Grafo
        const srcIp = data.src_ip.replace(" (ALVO SUSPEITO)", "");
        const dstIp = data.dst_ip;

        // Adiciona Nó Fonte se não existir
        if (!nodesMap.current.has(srcIp)) {
          nodesMap.current.set(srcIp, { 
            id: srcIp, 
            group: data.is_threat ? 'threat' : 'normal',
            val: data.is_threat ? 10 : 5
          });
        } else if (data.is_threat) {
          // Promove nó normal para threat
          const n = nodesMap.current.get(srcIp);
          n.group = 'threat';
          n.val = 10;
        }

        // Adiciona Nó Destino se não existir
        if (!nodesMap.current.has(dstIp)) {
          nodesMap.current.set(dstIp, {
            id: dstIp,
            group: 'normal',
            val: 5
          });
        }

        // Adiciona Link
        const linkId = `${srcIp}-${dstIp}`;
        if (!linksMap.current.has(linkId)) {
          linksMap.current.set(linkId, {
            source: srcIp,
            target: dstIp,
            value: data.is_threat ? 3 : 1,
            isThreat: data.is_threat
          });
        }

        // Atualiza State do Grafo
        setGraphData({
          nodes: Array.from(nodesMap.current.values()),
          links: Array.from(linksMap.current.values())
        });

      } catch (err) {
        console.error("Error parsing WS message:", err);
      }
    };

    return () => ws.close();
  }, []);

  // Efeito Visual: Partículas pulsantes nos links
  const linkParticleColor = (link) => link.isThreat ? 'rgba(223, 59, 0, 0.8)' : 'rgba(0, 177, 136, 0.8)';

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="cyber-header">
        <div className="logo-area">
          <h1>SPECTRE_GRID // V2</h1>
          <div className="status-badge">
            <div className="pulse-ring"></div>
            SYSTEM ONLINE - WEBSOCKET CONNECTED
          </div>
        </div>
      </header>

      {/* Main Layout */}
      <main className="main-layout">
        
        {/* Left Column: Metrics */}
        <aside className="panel left-column">
          <div className="panel-header">
            <Activity size={16} color="var(--neon-cyan)" />
            <h2>REAL-TIME METRICS</h2>
          </div>
          <div className="panel-content metrics-grid">
            <div className="metric-box">
              <div className="metric-title">Traffic Ingested</div>
              <div className="metric-value">{(stats.totalBytes / 1024 / 1024).toFixed(2)} MB</div>
            </div>
            <div className="metric-box">
              <div className="metric-title">Packets Analyzed</div>
              <div className="metric-value">{stats.totalPackets.toLocaleString()}</div>
            </div>
            <div className="metric-box">
              <div className="metric-title">Threats Blocked</div>
              <div className="metric-value danger">{stats.threatsBlocked.toLocaleString()}</div>
            </div>
            <div className="metric-box">
              <div className="metric-title">Active Nodes</div>
              <div className="metric-value">{graphData.nodes.length}</div>
            </div>
          </div>
        </aside>

        {/* Center Column: WebGL Graph */}
        <section className="center-column">
          <div className="graph-overlay">
            <h2>TOPOLOGY VIEW [WebGL]</h2>
          </div>
          <ForceGraph2D
            ref={graphRef}
            width={800} // Será ajustado via ResizeObserver na vida real
            height={600}
            graphData={graphData}
            backgroundColor="transparent"
            nodeRelSize={4}
            nodeColor={node => {
              if (node.group === 'core') return 'var(--neon-cyan)';
              if (node.group === 'threat') return 'var(--neon-red)';
              return 'var(--text-muted)';
            }}
            linkColor={link => link.isThreat ? 'rgba(223, 59, 0, 0.4)' : 'rgba(255, 255, 255, 0.1)'}
            linkWidth={link => link.isThreat ? 2 : 1}
            linkDirectionalParticles={2}
            linkDirectionalParticleSpeed={d => d.isThreat ? 0.01 : 0.005}
            linkDirectionalParticleColor={linkParticleColor}
            onEngineStop={() => graphRef.current.zoomToFit(400, 50)}
          />
        </section>

        {/* Right Column: Log Stream */}
        <aside className="panel right-column">
          <div className="panel-header">
            <Cpu size={16} color="var(--neon-cyan)" />
            <h2>INFERENCE STREAM</h2>
          </div>
          <div className="panel-content">
            <div className="log-container">
              {logs.map((log, i) => (
                <div key={i} className={`log-entry ${log.is_threat ? 'threat' : ''}`}>
                  <div className="log-meta">
                    <span>{log.timestamp}</span>
                    <span>Prob: {log.probability.toFixed(1)}%</span>
                  </div>
                  <div className={`log-msg ${log.is_threat ? 'threat' : ''}`}>
                    {log.is_threat ? 'BLOCK' : 'ALLOW'} {log.src_ip}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

export default App;
