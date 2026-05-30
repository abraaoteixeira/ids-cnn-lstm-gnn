import React, { useEffect, useState, useRef, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import ForceGraph2D from 'react-force-graph-2d';
import { Activity, Shield, AlertTriangle, Network, Server, Lock, Search, Trash2, Download, X, HelpCircle } from 'lucide-react';

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

  // === NOVOS ESTADOS DA POC ===
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterMode, setFilterMode] = useState('all'); // 'all', 'threats', 'allowed'
  const [toasts, setToasts] = useState([]);
  const [networkSpeed, setNetworkSpeed] = useState('0 KB/s');
  
  const totalBytesRef = useRef(0);

  // Sincroniza bytes para cálculo de velocidade
  useEffect(() => {
    totalBytesRef.current = stats.totalBytes;
  }, [stats.totalBytes]);

  // Efeito para cálculo periódico da taxa de transferência por segundo
  useEffect(() => {
    let lastBytes = 0;
    const timer = setInterval(() => {
      const currentBytes = totalBytesRef.current;
      const diff = currentBytes - lastBytes;
      lastBytes = currentBytes;
      
      if (diff > 1024 * 1024) {
        setNetworkSpeed(`${(diff / 1024 / 1024).toFixed(2)} MB/s`);
      } else if (diff > 1024) {
        setNetworkSpeed(`${(diff / 1024).toFixed(1)} KB/s`);
      } else {
        setNetworkSpeed(`${diff} B/s`);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Auxiliar para disparar Toasts dinâmicos
  const addToast = (message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4500);
  };

  useEffect(() => {
    // Carregar histórico inicial do Banco de Dados
    fetch('http://localhost:8001/api/history?limit=100')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          const formatted = data.map(item => {
            const timestamp = item.timestamp || new Date().toLocaleTimeString('en-US', { hour12: false });
            
            // Popula os mapas temporários de grafos com o histórico
            const srcIp = item.src_ip || 'Unknown';
            const dstIp = item.dst_ip || 'Unknown';
            const isThreat = !!item.is_threat;
            
            if (!nodesMap.current.has(srcIp)) nodesMap.current.set(srcIp, { id: srcIp, isThreat });
            if (!nodesMap.current.has(dstIp)) nodesMap.current.set(dstIp, { id: dstIp, isThreat });
            
            const linkId = `${srcIp}-${dstIp}`;
            if (!linksMap.current.has(linkId)) {
              linksMap.current.set(linkId, {
                source: srcIp,
                target: dstIp,
                value: isThreat ? 3 : 1,
                isThreat: isThreat
              });
            }

            return { ...item, timestamp };
          });

          setLogs(formatted);
          setGraphData({
            nodes: Array.from(nodesMap.current.values()),
            links: Array.from(linksMap.current.values())
          });

          // Computar stats iniciais baseados no histórico
          const totalBytes = data.reduce((acc, item) => acc + (item.bytes || 0), 0);
          const threatsBlocked = data.filter(item => item.is_threat).length;
          setStats(prev => ({
            ...prev,
            totalBytes,
            packetsAnalyzed: data.length,
            threatsBlocked,
            activeConnections: nodesMap.current.size
          }));
        }
      })
      .catch(err => console.error("Erro ao carregar histórico inicial:", err));

    // Conectar WebSocket
    const ws = new WebSocket('ws://localhost:8001/ws/threats');
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
        
        // Adiciona aos Logs
        setLogs(prev => {
          const newLogs = [{ ...data, timestamp }, ...prev];
          if (newLogs.length > 100) newLogs.pop();
          return newLogs;
        });

        // Atualiza Stats em tempo real
        setStats(prev => ({
          totalBytes: prev.totalBytes + (data.bytes || 0),
          packetsAnalyzed: prev.packetsAnalyzed + 1,
          threatsBlocked: prev.threatsBlocked + (data.is_threat ? 1 : 0),
          activeConnections: nodesMap.current.size
        }));

        // Atualiza Gráfico de Linha/Área
        setTrafficData(prev => {
          const newData = [...prev];
          const attention = data.attention_weight ? data.attention_weight * 100 : (data.probability ? data.probability * 100 : 0);
          
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
        
        // Atualiza o Grafo
        const srcIp = data.src_ip || 'Unknown';
        const dstIp = data.dst_ip || 'Unknown';
        const isThreat = !!data.is_threat;

        // Limita tamanho do grafo para evitar memory leak
        if (nodesMap.current.size > 80) {
          const firstNodeKey = nodesMap.current.keys().next().value;
          nodesMap.current.delete(firstNodeKey);
        }
        if (linksMap.current.size > 150) {
          const firstLinkKey = linksMap.current.keys().next().value;
          linksMap.current.delete(firstLinkKey);
        }

        // Se o IP for ameaça, sobrescreve o status
        if (!nodesMap.current.has(srcIp) || isThreat) {
          nodesMap.current.set(srcIp, { id: srcIp, isThreat: isThreat || (nodesMap.current.get(srcIp)?.isThreat || false) });
        }
        if (!nodesMap.current.has(dstIp) || isThreat) {
          nodesMap.current.set(dstIp, { id: dstIp, isThreat: isThreat || (nodesMap.current.get(dstIp)?.isThreat || false) });
        }
        
        const linkId = `${srcIp}-${dstIp}`;
        if (!linksMap.current.has(linkId)) {
          linksMap.current.set(linkId, {
            source: srcIp,
            target: dstIp,
            value: isThreat ? 3 : 1,
            isThreat: isThreat
          });
        }

        setGraphData({
          nodes: Array.from(nodesMap.current.values()),
          links: Array.from(linksMap.current.values())
        });

        // Dispara Toast de Alerta caso seja Ameaça detectada pela IA
        if (isThreat) {
          addToast(`Ameaça Mitigada: Fluxo suspeito detectado de ${srcIp} para ${dstIp}`, 'danger');
        }

      } catch (err) {
        console.error("Error parsing WS message:", err);
      }
    };

    return () => ws.close();
  }, []);

  useEffect(() => {
    // Redimensionar grafo se alternar de visualização
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
    setTimeout(updateDimensions, 150);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [viewMode]);

  // === METODOS E LOGICAS DA POC ===

  // Filtragem de Logs
  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      const searchLower = searchQuery.toLowerCase();
      const matchesSearch = (log.src_ip || '').toLowerCase().includes(searchLower) ||
                            (log.dst_ip || '').toLowerCase().includes(searchLower) ||
                            (log.protocol || '').toLowerCase().includes(searchLower);
      const matchesFilter = filterMode === 'all' ||
                            (filterMode === 'threats' && log.is_threat) ||
                            (filterMode === 'allowed' && !log.is_threat);
      return matchesSearch && matchesFilter;
    });
  }, [logs, searchQuery, filterMode]);

  // Estatísticas do IP selecionado
  const selectedNodeStats = useMemo(() => {
    if (!selectedNode) return null;
    const ip = selectedNode.id;
    const related = logs.filter(l => l.src_ip === ip || l.dst_ip === ip);
    const sentBytes = related.reduce((acc, l) => l.src_ip === ip ? acc + (l.bytes || 0) : acc, 0);
    const recvBytes = related.reduce((acc, l) => l.dst_ip === ip ? acc + (l.bytes || 0) : acc, 0);
    const threatCount = related.filter(l => l.is_threat).length;
    return {
      ip,
      status: selectedNode.isThreat ? 'BLOQUEADO' : 'ATIVO / SEGURO',
      isThreat: selectedNode.isThreat,
      totalFlows: related.length,
      sentBytes,
      recvBytes,
      threatCount
    };
  }, [selectedNode, logs]);

  // Limpar Banco de Dados
  const handleClearHistory = async () => {
    if (window.confirm("Deseja realmente limpar todo o histórico de ameaças e logs do banco de dados?")) {
      try {
        const response = await fetch('http://localhost:8001/api/clear_history', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'success') {
          setLogs([]);
          nodesMap.current.clear();
          linksMap.current.clear();
          setGraphData({ nodes: [], links: [] });
          setStats({
            totalBytes: 0,
            packetsAnalyzed: 0,
            threatsBlocked: 0,
            activeConnections: 0
          });
          setSelectedNode(null);
          addToast("Banco de dados limpo com sucesso!", "success");
        } else {
          addToast("Falha ao limpar banco de dados", "warning");
        }
      } catch (err) {
        console.error(err);
        addToast("Erro na comunicação com a API", "danger");
      }
    }
  };

  // Exportar Logs como CSV
  const handleExportCSV = () => {
    if (logs.length === 0) {
      addToast("Nenhum log disponível para exportação", "warning");
      return;
    }
    const headers = ["Horario", "IP Origem", "IP Destino", "Protocolo", "Bytes", "Atenção GNN", "Ação"];
    const csvRows = [
      headers.join(','),
      ...logs.map(l => [
        l.timestamp,
        l.src_ip,
        l.dst_ip,
        l.protocol || 'TCP',
        l.bytes || 0,
        l.attention_weight ? (l.attention_weight * 100).toFixed(1) + '%' : 'N/A',
        l.is_threat ? 'BLOQUEADO' : 'PERMITIDO'
      ].join(','))
    ];
    
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `spectre_grid_logs_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    addToast("Relatório de logs exportado com sucesso!", "success");
  };

  return (
    <div className="dashboard-container">
      {/* Container Flutuante de Toasts */}
      <div className="toast-container">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            <AlertTriangle size={18} />
            <div className="toast-message">{toast.message}</div>
          </div>
        ))}
      </div>

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
            <div className="kpi-subtext" style={{ fontSize: '0.8rem', color: 'var(--accent-green)', fontWeight: 500, marginTop: '4px' }}>
              Taxa: {networkSpeed}
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-title"><Network size={16} /> Pacotes Analisados</div>
            <div className="kpi-value">{stats.packetsAnalyzed.toLocaleString()}</div>
            <div className="kpi-subtext" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Inferências GNN Ativas
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-title"><AlertTriangle size={16} /> Ameaças Bloqueadas</div>
            <div className="kpi-value danger">{stats.threatsBlocked.toLocaleString()}</div>
            <div className="kpi-subtext" style={{ fontSize: '0.8rem', color: 'var(--accent-red)', fontWeight: 500, marginTop: '4px' }}>
              Mitigação eBPF XDP_DROP
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-title"><Server size={16} /> Nós Ativos</div>
            <div className="kpi-value">{stats.activeConnections}</div>
            <div className="kpi-subtext" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Topologia de Conexões
            </div>
          </div>
        </div>

        {/* Panels Grid */}
        <div className="panels-grid">
          
          {/* Traffic Timeseries / Graph Panel */}
          <div className="panel">
            <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={18} color="var(--accent-blue)" />
                Tráfego de Rede & Detecção de Anomalias
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button 
                  onClick={() => setViewMode('chart')}
                  className={`btn-toggle ${viewMode === 'chart' ? 'active' : ''}`}>
                  Nível de Ameaça (GNN)
                </button>
                <button 
                  onClick={() => setViewMode('graph')}
                  className={`btn-toggle ${viewMode === 'graph' ? 'active' : ''}`}>
                  Grafo de Nós
                </button>
              </div>
            </div>
            <div className="panel-content" style={{ position: 'relative', overflow: 'hidden' }}>
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
                <div ref={graphContainerRef} style={{ width: '100%', height: '100%', background: 'var(--bg-main)', borderRadius: '6px', overflow: 'hidden', position: 'relative' }}>
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
                      onNodeClick={node => setSelectedNode(node)}
                      nodeCanvasObject={(node, ctx, globalScale) => {
                        const label = node.id;
                        const fontSize = 12 / globalScale;
                        ctx.font = `${fontSize}px var(--font-mono, monospace)`;
                        const textWidth = ctx.measureText(label).width;
                        const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);

                        ctx.fillStyle = selectedNode?.id === node.id ? 'rgba(37, 99, 235, 0.4)' : 'rgba(14, 16, 21, 0.8)';
                        ctx.strokeStyle = selectedNode?.id === node.id ? '#2563EB' : 'transparent';
                        ctx.lineWidth = 2 / globalScale;
                        
                        ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
                        if (selectedNode?.id === node.id) {
                          ctx.strokeRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
                        }

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

                  {/* Informações detalhadas do nó selecionado (Sidebar flutuante interna) */}
                  {selectedNodeStats && (
                    <div className="node-detail-panel">
                      <div className="node-detail-header">
                        <h4>Detalhes do IP</h4>
                        <button onClick={() => setSelectedNode(null)} className="btn-close-detail"><X size={16} /></button>
                      </div>
                      <div className="node-detail-body">
                        <div className="detail-row">
                          <span className="detail-label">Endereço IP</span>
                          <span className="detail-value mono">{selectedNodeStats.ip}</span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Status</span>
                          <span className={`detail-value badge ${selectedNodeStats.isThreat ? 'block' : 'allow'}`}>
                            {selectedNodeStats.status}
                          </span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Fluxos Relacionados</span>
                          <span className="detail-value">{selectedNodeStats.totalFlows}</span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Bytes Enviados</span>
                          <span className="detail-value">{(selectedNodeStats.sentBytes / 1024).toFixed(1)} KB</span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Bytes Recebidos</span>
                          <span className="detail-value">{(selectedNodeStats.recvBytes / 1024).toFixed(1)} KB</span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Ameaças Associadas</span>
                          <span className={`detail-value ${selectedNodeStats.threatCount > 0 ? 'text-danger' : 'text-success'}`}>
                            {selectedNodeStats.threatCount}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Dica do Grafo */}
                  <div style={{ position: 'absolute', bottom: '10px', left: '10px', fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px', background: 'rgba(0,0,0,0.5)', padding: '4px 8px', borderRadius: '4px' }}>
                    <HelpCircle size={12} /> Clique em um nó IP para inspecionar estatísticas.
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Real-time Threat Logs Panel with Search and Actions */}
          <div className="panel">
            <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={18} color="var(--accent-red)" />
                Logs de Eventos de Segurança
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={handleExportCSV} className="btn-action" title="Exportar para CSV">
                  <Download size={14} /> Exportar
                </button>
                <button onClick={handleClearHistory} className="btn-action danger" title="Limpar Banco de Dados">
                  <Trash2 size={14} /> Limpar BD
                </button>
              </div>
            </div>
            
            {/* Barra de Filtros e Busca */}
            <div className="log-filter-bar">
              <div className="search-box">
                <Search size={14} className="search-icon" />
                <input 
                  type="text" 
                  placeholder="Buscar IP ou Protocolo..." 
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)} 
                />
              </div>
              <div className="filter-buttons">
                <button 
                  onClick={() => setFilterMode('all')} 
                  className={`filter-btn ${filterMode === 'all' ? 'active' : ''}`}>
                  Todos
                </button>
                <button 
                  onClick={() => setFilterMode('threats')} 
                  className={`filter-btn ${filterMode === 'threats' ? 'active' : ''}`}>
                  Ameaças
                </button>
                <button 
                  onClick={() => setFilterMode('allowed')} 
                  className={`filter-btn ${filterMode === 'allowed' ? 'active' : ''}`}>
                  Seguros
                </button>
              </div>
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
                    {filteredLogs.map((log, idx) => (
                      <tr key={idx} style={{ background: log.is_threat ? 'rgba(239, 68, 68, 0.03)' : 'transparent' }}>
                        <td style={{ color: 'var(--text-secondary)' }}>{log.timestamp}</td>
                        <td className="mono">{log.src_ip}</td>
                        <td className="mono">{log.dst_ip}</td>
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
                    {filteredLogs.length === 0 && (
                      <tr>
                        <td colSpan="5" style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                          Nenhum evento corresponde aos filtros.
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
