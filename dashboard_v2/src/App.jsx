import React, { useEffect, useState, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import ForceGraph2D from 'react-force-graph-2d';
import { Activity, Shield, AlertTriangle, Network, Server, Lock } from 'lucide-react';

function App() {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState({
    totalBytes: 0,
    packetsAnalyzed: 0,
    threatsBlocked: 0,
    activeConnections: 0
  });
  
  // Dados para o Gráfico de Tráfego
  const [trafficData, setTrafficData] = useState([]);
  
  // View mode para alternar entre AreaChart e Graph
  const [viewMode, setViewMode] = useState('chart'); // 'chart' ou 'graph'
  
  // Dados do Force Graph
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const nodesMap = useRef(new Map());
  const linksMap = useRef(new Map());
  
  const wsRef = useRef(null);
  
  // Referência para o container do Graph para ser responsivo
  const graphContainerRef = useRef(null);
  const [graphDimensions, setGraphDimensions] = useState({ width: 600, height: 400 });

  useEffect(() => {
    // Atualiza dimensões do grafo dinamicamente
    const updateDimensions = () => {
      if (graphContainerRef.current) {
        setGraphDimensions({
          width: graphContainerRef.current.offsetWidth,
          height: graphContainerRef.current.offsetHeight
        });
      }
    };
    window.addEventListener('resize', updateDimensions);
    updateDimensions();
    // Um timeoutzinho para garantir que a div já renderizou no tamanho certo
    setTimeout(updateDimensions, 100);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [viewMode]); // Atualiza sempre que o viewMode muda para o Graph

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8001/ws/threats');
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
        
        // Atualiza Logs (Mantém os últimos 100)
        setLogs(prev => {
          const newLogs = [{ ...data, timestamp }, ...prev];
          if (newLogs.length > 100) newLogs.pop();
          return newLogs;
        });

        // Atualiza Stats
        setStats(prev => ({
          totalBytes: prev.totalBytes + (data.bytes || 0),
          packetsAnalyzed: prev.packetsAnalyzed + 1,
          threatsBlocked: prev.threatsBlocked + (data.is_threat ? 1 : 0),
          activeConnections: Math.floor(Math.random() * 50) + 10 // Simulado
        }));

        // Atualiza Gráfico de Timeseries (Mantém últimos 30 ticks)
        setTrafficData(prev => {
          const newData = [...prev];
          const attention = data.attention_weight ? data.attention_weight * 100 : (data.probability ? data.probability * 100 : 0);
          
          // Agrupa por segundo
          const lastPoint = newData[newData.length - 1];
          if (lastPoint && lastPoint.time === timestamp) {
            newData[newData.length - 1] = {
              ...lastPoint,
              maxAttention: Math.max(lastPoint.maxAttention, attention),
              threats: lastPoint.threats + (data.is_threat ? 1 : 0)
            };
          } else {
            newData.push({
              time: timestamp,
              maxAttention: attention,
              threats: data.is_threat ? 1 : 0
            });
          }
          if (newData.length > 30) newData.shift();
          return newData;
        });
        
        // Atualiza Force Graph Data (com limite de tamanho para performance)
        const srcIp = data.src_ip || 'Unknown';
        const dstIp = data.dst_ip || 'Unknown';

        if (nodesMap.current.size > 80) {
          const firstNodeKey = nodesMap.current.keys().next().value;
          nodesMap.current.delete(firstNodeKey);
        }
        if (linksMap.current.size > 150) {
          const firstLinkKey = linksMap.current.keys().next().value;
          linksMap.current.delete(firstLinkKey);
        }

        if (!nodesMap.current.has(srcIp)) nodesMap.current.set(srcIp, { id: srcIp, isThreat: data.is_threat });
        if (!nodesMap.current.has(dstIp)) nodesMap.current.set(dstIp, { id: dstIp, isThreat: data.is_threat });
        
        const linkId = `${srcIp}-${dstIp}`;
        if (!linksMap.current.has(linkId)) {
          linksMap.current.set(linkId, {
            source: srcIp,
            target: dstIp,
            value: data.is_threat ? 3 : 1,
            isThreat: data.is_threat
          });
        }

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

  return (
    <div className="dashboard-container">
      {/* Top Header */}
      <header className="top-header">
        <div className="logo-section">
          <img src="/static/logo-ifc.png" alt="IFC Logo" style={{ height: '36px', marginRight: '10px' }} />
          <Shield color="var(--accent-blue)" size={24} />
          <h1>SPECTRE GRID // INTRUSION DETECTION SYSTEM</h1>
        </div>
        <div className="status-badge">
          <div className="status-dot"></div>
          CONEXÃO SEGURA ATIVA
        </div>
      </header>

      {/* Main Content Area */}
      <main className="main-content">
        
        {/* KPI Grid */}
        <div className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-title"><Activity size={16} /> Tráfego Ingerido</div>
            <div className="kpi-value">{(stats.totalBytes / 1024 / 1024).toFixed(2)} MB</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-title"><Network size={16} /> Pacotes Analisados</div>
            <div className="kpi-value">{stats.packetsAnalyzed.toLocaleString()}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-title"><AlertTriangle size={16} /> Ameaças Bloqueadas</div>
            <div className="kpi-value danger">{stats.threatsBlocked.toLocaleString()}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-title"><Server size={16} /> Nós Ativos</div>
            <div className="kpi-value">{stats.activeConnections}</div>
          </div>
        </div>

        {/* Panels Grid */}
        <div className="panels-grid">
          
          {/* Traffic Timeseries Panel */}
          <div className="panel">
            <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={18} color="var(--accent-blue)" />
                Tráfego de Rede & Detecção de Anomalias
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button 
                  onClick={() => setViewMode('chart')}
                  style={{ background: viewMode === 'chart' ? 'var(--accent-blue)' : 'transparent', border: '1px solid var(--border-color)', color: '#fff', padding: '4px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
                  Nível de Ameaça (GNN)
                </button>
                <button 
                  onClick={() => setViewMode('graph')}
                  style={{ background: viewMode === 'graph' ? 'var(--accent-blue)' : 'transparent', border: '1px solid var(--border-color)', color: '#fff', padding: '4px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
                  Grafo de Nós
                </button>
              </div>
            </div>
            <div className="panel-content" style={{ position: 'relative' }}>
              {viewMode === 'chart' ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trafficData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorTraffic" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="colorThreats" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--accent-red)" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="var(--accent-red)" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
                    <XAxis dataKey="time" stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: 'var(--bg-panel)', borderColor: 'var(--border-highlight)', borderRadius: '8px' }}
                      itemStyle={{ color: '#fff' }}
                      formatter={(value, name) => [name === 'maxAttention' ? `${value.toFixed(1)}%` : value, name === 'maxAttention' ? 'Anomalia GNN' : 'Ameaças']}
                    />
                    <Area type="monotone" dataKey="maxAttention" stroke="var(--accent-blue)" fillOpacity={1} fill="url(#colorTraffic)" />
                    <Area type="monotone" dataKey="threats" stroke="var(--accent-red)" fillOpacity={1} fill="url(#colorThreats)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div ref={graphContainerRef} style={{ width: '100%', height: '100%', background: 'var(--bg-main)', borderRadius: '6px', overflow: 'hidden' }}>
                  {graphDimensions.width > 0 && (
                    <ForceGraph2D
                      graphData={graphData}
                      width={graphDimensions.width}
                      height={graphDimensions.height}
                      nodeLabel="id"
                      nodeColor={node => node.isThreat ? '#EF4444' : '#10B981'}
                      linkColor={link => link.isThreat ? '#EF4444' : '#2563EB'}
                      linkWidth={link => link.value}
                      enableNodeDrag={true}
                      enableZoomInteraction={true}
                      nodeCanvasObject={(node, ctx, globalScale) => {
                        const label = node.id;
                        const fontSize = 12 / globalScale;
                        ctx.font = `${fontSize}px var(--font-mono, monospace)`;
                        const textWidth = ctx.measureText(label).width;
                        const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);

                        ctx.fillStyle = 'rgba(14, 16, 21, 0.8)';
                        ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);

                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.fillStyle = node.isThreat ? '#EF4444' : '#10B981';
                        ctx.fillText(label, node.x, node.y);

                        node.__bckgDimensions = bckgDimensions;
                      }}
                      nodePointerAreaPaint={(node, color, ctx) => {
                        ctx.fillStyle = color;
                        const bckgDimensions = node.__bckgDimensions;
                        bckgDimensions && ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
                      }}
                    />
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Real-time Threat Logs Panel */}
          <div className="panel">
            <div className="panel-header">
              <Lock size={18} color="var(--accent-red)" />
              Logs de Eventos de Segurança
            </div>
            <div className="panel-content" style={{ padding: 0 }}>
              <div className="log-table-wrapper">
                <table className="log-table">
                  <thead>
                    <tr>
                      <th>Horário</th>
                      <th>IP de Origem</th>
                      <th>IP de Destino</th>
                      <th>Atenção GNN</th>
                      <th>Ação</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log, idx) => (
                      <tr key={idx}>
                        <td style={{ color: 'var(--text-secondary)' }}>{log.timestamp}</td>
                        <td>{log.src_ip}</td>
                        <td>{log.dst_ip}</td>
                        <td>
                          {log.attention_weight ? (log.attention_weight * 100).toFixed(1) + '%' : 'N/A'}
                        </td>
                        <td>
                          {log.is_threat ? (
                            <span className="badge block">BLOQUEADO</span>
                          ) : (
                            <span className="badge allow">PERMITIDO</span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {logs.length === 0 && (
                      <tr>
                        <td colSpan="5" style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                          Aguardando tráfego...
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}

export default App;
