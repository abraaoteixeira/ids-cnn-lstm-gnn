// ==========================================================================
// SPECTRE_GRID DIGITAL RADAR CONTROLLER
// ==========================================================================

// Cores para renderização do Canvas GNN (compatível com todos os browsers)
const colors = {
    cyan: '#00b188',   // Safe Teal-Green (Cloudflare style)
    red: '#df3b00',    // Threat Red/Orange (Cloudflare security)
    amber: '#f48120',  // Cloudflare Orange (Warning)
    green: '#00e575',  // Bright Green
    purple: '#0070f3', // Cloud Blue (previously purple)
    textMuted: '#8b9bb4'
};

// Elementos de UI
const totalFlowsEl = document.getElementById('total-flows');
const totalThreatsEl = document.getElementById('total-threats');
const liveRiskPct = document.getElementById('live-risk-pct');
const circularRiskFill = document.getElementById('circular-risk-fill');
const terminalLog = document.getElementById('terminal-log');
const flowInspector = document.getElementById('flow-inspector');
const realTimeClock = document.getElementById('real-time-clock');
const termStatusGlow = document.getElementById('term-status-glow');
const termStatusName = document.getElementById('term-status-name');
const threatStatusPanel = document.querySelector('.threat-status-panel');
const riskBadge = document.getElementById('risk-badge');

// Mini stats adicionais
const gnnAnomalyVal = document.getElementById('gnn-anomaly-val');
const lateralRatioVal = document.getElementById('lateral-ratio-val');
const pingStatus = document.getElementById('ping-status');

// HUD do Nó
const nodeHudPanel = document.getElementById('node-hud-panel');
const hudIpVal = document.getElementById('hud-ip-val');
const hudRole = document.getElementById('hud-role');
const hudRisk = document.getElementById('hud-risk');
const hudDegree = document.getElementById('hud-degree');
const hudVolume = document.getElementById('hud-volume');
const btnCloseHud = document.getElementById('btn-close-hud');

// Configuração do Canvas GNN
const canvas = document.getElementById('gnn-canvas');
const ctx = canvas.getContext('2d');
const btnResetLayout = document.getElementById('btn-reset-layout');
const btnFreezeLayout = document.getElementById('btn-freeze-layout');

// Estado da Aplicação
let flowsCount = 0;
let threatsCount = 0;
let recentThreatsList = [];
let riskTimeline = Array(40).fill(0); // Para o Sparkline
let isFrozen = false;
let selectedNode = null;
let draggedNode = null;

// Tabelas de Grafos
const nodes = new Map(); // IP -> Node Object
const edges = [];       // Array de Arestas
const particles = [];   // Pacotes de rede voadores

// Dimensões do Canvas (Dinâmico)
let width = canvas.offsetWidth;
let height = canvas.offsetHeight;

function resizeCanvas() {
    width = canvas.parentElement.clientWidth;
    height = canvas.parentElement.clientHeight;
    canvas.width = width;
    canvas.height = height;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// ==========================================================================
// 1. ENGINE DE FÍSICA PARA O GRAFO GNN (FORCE-DIRECTED GRAPH LAYOUT)
// ==========================================================================
class GNNNode {
    constructor(ip, isServer = false) {
        this.ip = ip;
        // Posição inicial espalhada aleatoriamente pela tela
        this.x = Math.random() * (width - 160) + 80;
        this.y = Math.random() * (height - 160) + 80;
        this.vx = 0;
        this.vy = 0;
        this.radius = isServer ? 16 : 10;
        this.isServer = isServer;
        this.risk = 0; // Calculado dinamicamente
        this.threatActive = false;
        this.threatTimer = 0;
        this.volume = 0;
        this.connections = 0;
        this.role = isServer ? "Server" : "Client Host";
        this.lastSeen = Date.now();
    }
}

class GNNEdge {
    constructor(source, target, isThreat = false) {
        this.source = source;
        this.target = target;
        this.isThreat = isThreat;
        this.activityLevel = 1.0;
        this.colorTimer = isThreat ? 1.0 : 0.2;
    }

    update() {
        if (this.colorTimer > 0) {
            this.colorTimer -= 0.008;
        }
    }
}

class FlowParticle {
    constructor(source, target, isThreat = false) {
        this.source = source;
        this.target = target;
        this.progress = 0;
        this.speed = isThreat ? 0.05 : 0.035;
        this.isThreat = isThreat;
    }

    update() {
        this.progress += this.speed;
        return this.progress >= 1.0; // Retorna true se chegou ao fim
    }

    draw() {
        const x = this.source.x + (this.target.x - this.source.x) * this.progress;
        const y = this.source.y + (this.target.y - this.source.y) * this.progress;
        
        ctx.beginPath();
        ctx.arc(x, y, this.isThreat ? 5 : 3.5, 0, Math.PI * 2);
        ctx.fillStyle = this.isThreat ? 'var(--neon-red)' : 'var(--neon-cyan)';
        ctx.shadowBlur = this.isThreat ? 12 : 8;
        ctx.shadowColor = this.isThreat ? 'var(--neon-red)' : 'var(--neon-cyan)';
        ctx.fill();
        ctx.shadowBlur = 0; // Reset
    }
}

// Inicializar Servidores de Infraestrutura Estáticos
const servers = ["10.0.0.5 (Active Directory)", "10.0.0.10 (SQL Database)", "10.0.0.1 (Core Gateway)"];
servers.forEach(srv => {
    nodes.set(srv, new GNNNode(srv, true));
});

// Setup da simulação física D3-Force
let d3Nodes = Array.from(nodes.values());
let d3Links = [];

const simulation = d3.forceSimulation(d3Nodes)
    .force("link", d3.forceLink(d3Links).id(d => d.ip).distance(130).strength(0.08))
    .force("charge", d3.forceManyBody().strength(-350).distanceMax(300))
    .force("center", d3.forceCenter(width / 2, height / 2).strength(0.02))
    .force("collision", d3.forceCollide().radius(d => d.radius + 15))
    .on("tick", () => {
        const margin = 40;
        d3Nodes.forEach(node => {
            if (node.x < margin) node.x = margin;
            if (node.x > width - margin) node.x = width - margin;
            if (node.y < margin) node.y = margin;
            if (node.y > height - margin) node.y = height - margin;
        });
    });

function updateD3Simulation() {
    d3Nodes = Array.from(nodes.values());
    d3Links = edges.map(e => ({
        source: e.source.ip,
        target: e.target.ip
    }));
    
    simulation.nodes(d3Nodes);
    simulation.force("link").links(d3Links);
    if (!isFrozen) {
        simulation.alpha(0.3).restart();
    }
}

// Inicializa a simulação D3 com os nós servidores iniciais
updateD3Simulation();

// Atualiza o estado dos temporizadores de ameaças nos nós e cores das arestas
function applyPhysics() {
    nodes.forEach(node => {
        if (node.threatTimer > 0) {
            node.threatTimer -= 0.016;
            if (node.threatTimer <= 0) {
                node.threatActive = false;
            }
        }
    });

    edges.forEach(edge => {
        edge.update();
    });
}

// Loop Principal de Renderização do Canvas GNN
function drawGNNGraph() {
    ctx.clearRect(0, 0, width, height);
    
    // Desenhar Arestas (Linhas de Ligação)
    edges.forEach(edge => {
        ctx.beginPath();
        ctx.moveTo(edge.source.x, edge.source.y);
        ctx.lineTo(edge.target.x, edge.target.y);
        
        if (edge.isThreat) {
            ctx.strokeStyle = `rgba(223, 59, 0, ${0.2 + edge.colorTimer * 0.8})`;
            ctx.lineWidth = 2.5;
        } else {
            ctx.strokeStyle = `rgba(0, 177, 136, ${0.08 + edge.colorTimer * 0.45})`;
            ctx.lineWidth = 1.2;
        }
        ctx.stroke();
    });

    // Atualizar e Desenhar Partículas (Pacotes Voadores)
    for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.draw();
        if (p.update()) {
            particles.splice(i, 1);
        }
    }

    // Desenhar Nós (IPs)
    nodes.forEach(node => {
        // Shockwave se estiver sob ameaça ativa
        if (node.threatActive) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius * (1 + (1 - node.threatTimer) * 1.5), 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(223, 59, 0, ${node.threatTimer})`;
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Desenhar Círculo Central do Nó
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        
        let grad = ctx.createRadialGradient(node.x, node.y, 2, node.x, node.y, node.radius);
        if (node.threatActive) {
            grad.addColorStop(0, '#ff7c5c');
            grad.addColorStop(1, colors.red);
            ctx.fillStyle = grad;
            ctx.shadowBlur = 15;
            ctx.shadowColor = colors.red;
        } else if (node.isServer) {
            grad.addColorStop(0, '#75b3ff');
            grad.addColorStop(1, colors.purple);
            ctx.fillStyle = grad;
            ctx.shadowBlur = 10;
            ctx.shadowColor = colors.purple;
        } else {
            grad.addColorStop(0, '#a2ffd0');
            grad.addColorStop(1, colors.cyan);
            ctx.fillStyle = grad;
            ctx.shadowBlur = selectedNode === node ? 14 : 0;
            ctx.shadowColor = colors.cyan;
        }
        ctx.fill();
        ctx.shadowBlur = 0; // Desativar sombra para o texto

        // Anel exterior para o nó selecionado
        if (selectedNode === node) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius + 5, 0, Math.PI * 2);
            ctx.strokeStyle = colors.cyan;
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        // Texto com o IP do Nó
        ctx.font = '10px "Share Tech Mono"';
        ctx.fillStyle = node.threatActive ? '#ffbca6' : colors.textMuted;
        ctx.textAlign = 'center';
        ctx.fillText(node.ip.split(' ')[0], node.x, node.y - node.radius - 6);
    });

    applyPhysics();
    requestAnimationFrame(drawGNNGraph);
}

// Lógica de Arrasto e Seleção de Nós no Canvas
canvas.addEventListener('mousedown', e => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    let clicked = null;
    nodes.forEach(node => {
        const dist = Math.hypot(node.x - mx, node.y - my);
        if (dist <= node.radius + 10) {
            clicked = node;
        }
    });

    if (clicked) {
        selectedNode = clicked;
        draggedNode = clicked;
        showNodeHUD(clicked);
        
        // Pinar nó para o arrasto no D3
        if (!isFrozen) {
            draggedNode.fx = draggedNode.x;
            draggedNode.fy = draggedNode.y;
        }
    } else {
        selectedNode = null;
        nodeHudPanel.classList.remove('active');
    }
});

canvas.addEventListener('mousemove', e => {
    if (!draggedNode) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    draggedNode.x = x;
    draggedNode.y = y;
    
    if (isFrozen) {
        draggedNode.fx = x;
        draggedNode.fy = y;
    } else {
        draggedNode.fx = x;
        draggedNode.fy = y;
        simulation.alphaTarget(0.3).restart(); // reaquece a simulação durante o arrasto
    }
});

window.addEventListener('mouseup', () => {
    if (draggedNode) {
        if (!isFrozen) {
            draggedNode.fx = null;
            draggedNode.fy = null;
        }
        draggedNode = null;
        simulation.alphaTarget(0);
    }
});

// Controlos de Congelar e Reposicionar Nós
btnResetLayout.addEventListener('click', () => {
    nodes.forEach(node => {
        node.x = width / 2 + (Math.random() - 0.5) * 150;
        node.y = height / 2 + (Math.random() - 0.5) * 150;
        node.vx = 0;
        node.vy = 0;
        if (isFrozen) {
            node.fx = node.x;
            node.fy = node.y;
        } else {
            node.fx = null;
            node.fy = null;
        }
    });
    updateD3Simulation();
});

btnFreezeLayout.addEventListener('click', () => {
    isFrozen = !isFrozen;
    btnFreezeLayout.classList.toggle('active', isFrozen);
    btnFreezeLayout.innerHTML = isFrozen ? `<i class="fa-solid fa-unlock"></i>` : `<i class="fa-solid fa-lock"></i>`;
    if (isFrozen) {
        simulation.stop();
        nodes.forEach(n => {
            n.fx = n.x;
            n.fy = n.y;
        });
    } else {
        nodes.forEach(n => {
            n.fx = null;
            n.fy = null;
        });
        simulation.alpha(0.3).restart();
    }
});

btnCloseHud.addEventListener('click', () => {
    nodeHudPanel.classList.remove('active');
    selectedNode = null;
});

function showNodeHUD(node) {
    nodeHudPanel.classList.add('active');
    hudIpVal.textContent = node.ip;
    hudRole.textContent = node.role;
    hudRisk.textContent = `${(node.risk * 100).toFixed(1)}%`;
    hudRisk.className = node.risk > 0.7 ? 'text-red' : (node.risk > 0.3 ? 'text-amber' : 'text-green');
    hudDegree.textContent = node.connections;
    
    // Formatar volume
    let vol = node.volume;
    if (vol > 1024 * 1024) {
        hudVolume.textContent = `${(vol / (1024 * 1024)).toFixed(1)} MB`;
    } else {
        hudVolume.textContent = `${(vol / 1024).toFixed(1)} KB`;
    }
}

// Iniciar renderização do Grafo
drawGNNGraph();


// ==========================================================================
// 2. CANVAS SPARKLINE (HISTÓRICO DE RISCO)
// ==========================================================================
const sparklineCanvas = document.getElementById('sparkline-canvas');
const sCtx = sparklineCanvas.getContext('2d');

function drawSparkline() {
    const sw = sparklineCanvas.parentElement.clientWidth;
    const sh = sparklineCanvas.parentElement.clientHeight;
    sparklineCanvas.width = sw;
    sparklineCanvas.height = sh;

    sCtx.clearRect(0, 0, sw, sh);
    
    // Desenhar grelha de fundo
    sCtx.strokeStyle = 'rgba(255, 255, 255, 0.02)';
    sCtx.lineWidth = 1;
    for (let i = 0; i < sw; i += 20) {
        sCtx.beginPath();
        sCtx.moveTo(i, 0);
        sCtx.lineTo(i, sh);
        sCtx.stroke();
    }

    if (riskTimeline.length < 2) return;

    // Gradiente da linha
    const grad = sCtx.createLinearGradient(0, 0, 0, sh);
    grad.addColorStop(0, 'rgba(255, 0, 85, 0.25)');
    grad.addColorStop(1, 'rgba(0, 243, 255, 0.0)');

    const step = sw / (riskTimeline.length - 1);
    
    sCtx.beginPath();
    sCtx.moveTo(0, sh - (riskTimeline[0] / 100) * (sh - 10));
    
    for (let i = 1; i < riskTimeline.length; i++) {
        const x = i * step;
        const y = sh - (riskTimeline[i] / 100) * (sh - 10);
        sCtx.lineTo(x, y);
    }
    
    // Desenhar preenchimento de gradiente inferior
    const fillPath = new Path2D(sCtx);
    fillPath.lineTo(sw, sh);
    fillPath.lineTo(0, sh);
    fillPath.closePath();
    sCtx.fillStyle = grad;
    sCtx.fill(fillPath);

    // Contorno da linha principal
    sCtx.lineWidth = 2;
    sCtx.strokeStyle = Math.max(...riskTimeline) > 75 ? colors.red : colors.cyan;
    sCtx.stroke();
}


// ==========================================================================
// 3. WEBSOCKET - INGESTÃO DE FLUXOS E MODELO PYTORCH
// ==========================================================================
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const host = window.location.host || '127.0.0.1:8000';
const wsUrl = `${protocol}//${host}/ws/threats`;
let socket;

function connectWebSocket() {
    console.log("A iniciar ligação ao WebSocket:", wsUrl);
    try {
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log("Conectado ao SPECTRE_GRID NGFW Core.");
            addSystemLog('LIGAÇÃO ESTABELECIDA', 'Motor de inferência GNN ativo e pronto.');
            termStatusGlow.className = 'glow-indicator';
            termStatusName.textContent = 'LISTEN';
            termStatusName.className = 'status-name';
        };
    } catch (e) {
        console.error("Falha ao criar WebSocket:", e);
        addSystemLog('ERRO CRÍTICO', `Não foi possível criar o WebSocket: ${e.message}`, true);
        setTimeout(connectWebSocket, 5000);
        return;
    }

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        let isGraphChanged = false;
        const now = Date.now();
        
        // 1. Processar Nós e Arestas
        let srcNode = nodes.get(data.src_ip);
        if (!srcNode) {
            srcNode = new GNNNode(data.src_ip);
            nodes.set(data.src_ip, srcNode);
            isGraphChanged = true;
        }
        
        let dstNode = nodes.get(data.dst_ip);
        if (!dstNode) {
            dstNode = new GNNNode(data.dst_ip);
            nodes.set(data.dst_ip, dstNode);
            isGraphChanged = true;
        }

        // Atualizar marcação de atividade
        srcNode.lastSeen = now;
        dstNode.lastSeen = now;

        // Atualizar estatísticas dos nós
        srcNode.connections++;
        dstNode.connections++;
        srcNode.volume += data.bytes;
        dstNode.volume += data.bytes;

        const probDec = data.probability / 100;
        srcNode.risk = Math.max(srcNode.risk, probDec);
        dstNode.risk = Math.max(dstNode.risk, probDec * 0.7); // Risco propagado

        if (data.is_threat) {
            srcNode.threatActive = true;
            srcNode.threatTimer = 1.0;
            dstNode.threatActive = true;
            dstNode.threatTimer = 1.0;
        }

        // Adicionar Aresta (Link) se não existir
        let edge = edges.find(e => 
            (e.source === srcNode && e.target === dstNode) || 
            (e.source === dstNode && e.target === srcNode)
        );

        if (!edge) {
            edge = new GNNEdge(srcNode, dstNode, data.is_threat);
            edges.push(edge);
            isGraphChanged = true;
        } else {
            edge.isThreat = edge.isThreat || data.is_threat;
            edge.colorTimer = 1.0;
        }

        // Se houver novos nós ou novas conexões, atualizar simulação física D3
        if (isGraphChanged) {
            updateD3Simulation();
        }

        // Spawn de Partícula
        particles.push(new FlowParticle(srcNode, dstNode, data.is_threat));

        // 2. Incrementar Métricas Gerais
        flowsCount++;
        totalFlowsEl.textContent = flowsCount.toLocaleString();
        
        if (data.is_threat) {
            threatsCount++;
            totalThreatsEl.textContent = threatsCount.toLocaleString();
            recentThreatsList.unshift(data); // Adicionar no início do array
            if (recentThreatsList.length > 10) recentThreatsList.pop();
        }

        // 3. Atualizar Indicador de Risco Circular Geral
        updateRiskMetrics(data.probability, data.is_threat);

        // 4. Empurrar Risco para o Sparkline
        riskTimeline.push(data.probability);
        riskTimeline.shift();
        drawSparkline();

        // 5. Atualizar HUD de nó dinamicamente se estiver aberto
        if (selectedNode) {
            showNodeHUD(selectedNode);
        }

        // 6. Registar Entrada no Log do Terminal
        addLogEntry(data);
    };

    socket.onclose = () => {
        termStatusGlow.className = 'glow-indicator danger';
        termStatusName.textContent = 'DISCONNECTED';
        termStatusName.className = 'status-name danger';
        
        addSystemLog('CONEXÃO PERDIDA', 'A tentar restabelecer ligação em 5 segundos...', true);
        
        // Reset da UI para segurança
        threatStatusPanel.classList.remove('alarm-state');
        riskBadge.textContent = "OFFLINE";
        riskBadge.style.borderColor = "var(--neon-red)";
        riskBadge.style.color = "var(--neon-red)";
        riskBadge.style.background = "rgba(255, 0, 85, 0.15)";
        
        setTimeout(connectWebSocket, 5000);
    };
}

// Atualiza o círculo e a UI de Risco
function updateRiskMetrics(riskVal, isThreat) {
    liveRiskPct.textContent = `${riskVal.toFixed(1)}%`;
    
    // Cálculo do stroke dashoffset para animar o círculo
    // Circunferência total de R=40 é 2 * PI * 40 ≈ 251.2
    const offset = 251.2 - (riskVal / 100) * 251.2;
    circularRiskFill.style.strokeDashoffset = offset;

    // Relação de Risco
    const currentMaxAnomaly = (riskVal / 100 * 0.95).toFixed(3);
    gnnAnomalyVal.textContent = currentMaxAnomaly;
    
    const latPct = ((threatsCount / Math.max(flowsCount, 1)) * 100).toFixed(2);
    lateralRatioVal.textContent = `${latPct}%`;

    // Atualizar Layout e Tema conforme Nível de Perigo
    if (riskVal > 80.0 || isThreat) {
        circularRiskFill.style.stroke = 'var(--neon-red)';
        circularRiskFill.style.filter = 'drop-shadow(0 0 8px var(--neon-red))';
        liveRiskPct.className = 'gauge-value text-red';
        threatStatusPanel.classList.add('alarm-state');
        riskBadge.textContent = "CRÍTICO";
    } else if (riskVal > 35.0) {
        circularRiskFill.style.stroke = 'var(--neon-amber)';
        circularRiskFill.style.filter = 'drop-shadow(0 0 6px var(--neon-amber))';
        liveRiskPct.className = 'gauge-value text-amber';
        threatStatusPanel.classList.remove('alarm-state');
        riskBadge.textContent = "ALERTA";
        riskBadge.style.borderColor = "var(--neon-amber)";
        riskBadge.style.color = "var(--neon-amber)";
        riskBadge.style.background = "rgba(255, 183, 0, 0.15)";
    } else {
        circularRiskFill.style.stroke = 'var(--neon-cyan)';
        circularRiskFill.style.filter = 'drop-shadow(0 0 6px var(--neon-cyan))';
        liveRiskPct.className = 'gauge-value text-cyan';
        threatStatusPanel.classList.remove('alarm-state');
        riskBadge.textContent = "SEGURO";
        riskBadge.style.borderColor = "var(--neon-green)";
        riskBadge.style.color = "var(--neon-green)";
        riskBadge.style.background = "rgba(16, 185, 129, 0.15)";
    }
}

// Ingestão no terminal dinâmico
function addLogEntry(flow) {
    const entry = document.createElement('div');
    entry.className = `log-entry ${flow.is_threat ? 'threat' : ''}`;
    
    // Armazenar os dados na DOM para serem puxados ao clicar
    entry.dataset.flow = JSON.stringify(flow);

    const time = new Date().toLocaleTimeString('pt-PT', { hour12: false });
    
    entry.innerHTML = `
        <div class="left-data">
            <span class="timestamp">[${time}]</span>
            <span class="flow">FLUXO_${String(flow.flow_id).padStart(4, '0')}</span>
            <span class="msg">${flow.is_threat ? 'INTRUSÃO DETETADA // ALERTA' : 'Ligação Normal'}</span>
        </div>
        <span class="prob ${flow.is_threat ? 'text-red' : 'text-cyan'}">${flow.probability}%</span>
    `;

    // Clique no Log para Inspecionar os Detalhes
    entry.addEventListener('click', () => {
        inspectFlow(flow);
    });

    terminalLog.appendChild(entry);
    terminalLog.scrollTop = terminalLog.scrollHeight;

    // Manter tamanho máximo do buffer do console
    if (terminalLog.children.length > 40) {
        terminalLog.removeChild(terminalLog.firstChild);
    }

    // Se for um ataque crítico, inspecionar imediatamente de forma automática
    if (flow.is_threat) {
        inspectFlow(flow);
    }
}

// Inspecionar fluxo de dados de rede
function inspectFlow(flow) {
    const isThreat = flow.is_threat;
    
    // Formatar volume de bytes
    let sizeText = `${(flow.bytes / 1024).toFixed(1)} KB`;
    if (flow.bytes > 1024 * 1024) {
        sizeText = `${(flow.bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    flowInspector.innerHTML = `
        <div class="threat-inspector-card animate-slide-in">
            <div class="inspect-header">
                <span class="flow-badge">ID: FLUXO_${String(flow.flow_id).padStart(4, '0')}</span>
                <span class="${isThreat ? 'danger-tag' : 'normal-tag'}">
                    <i class="fa-solid ${isThreat ? 'fa-circle-radiation' : 'fa-circle-check'}"></i> 
                    ${isThreat ? 'APT ALERT' : 'SECURE'}
                </span>
            </div>
            <div class="inspect-grid">
                <span class="label">Origem (Src):</span>
                <span class="val text-cyan">${flow.src_ip}</span>
                
                <span class="label">Destino (Dst):</span>
                <span class="val text-cyan">${flow.dst_ip}</span>
                
                <span class="label">Porta Alvo:</span>
                <span class="val" style="color: #fff;">${flow.port}</span>
                
                <span class="label">Protocolo:</span>
                <span class="val">${flow.protocol}</span>
                
                <span class="label">Pacotes:</span>
                <span class="val">${flow.packets.toLocaleString()}</span>
                
                <span class="label">Volume:</span>
                <span class="val">${sizeText}</span>
                
                <span class="label">Confiança GAT:</span>
                <span class="val ${isThreat ? 'text-red' : 'text-cyan'}">${flow.probability}%</span>
            </div>
            
            <div class="inspect-footer ${isThreat ? '' : 'safe-footer'}">
                <i class="fa-solid ${isThreat ? 'fa-shield-virus' : 'fa-circle-info'}"></i>
                <span>${isThreat ? 
                    'Ameaça coordenada. Possível movimentação lateral / Portscan agressivo detetado pela GNN.' : 
                    'Tráfego rotineiro verificado através das camadas CNN-LSTM.'}
                </span>
            </div>
        </div>
    `;
}

// Log do Sistema
function addSystemLog(title, msg, isError = false) {
    const entry = document.createElement('div');
    entry.className = 'log-entry system-msg';
    
    const time = new Date().toLocaleTimeString('pt-PT', { hour12: false });
    
    entry.innerHTML = `
        <div class="left-data">
            <span class="timestamp">[${time}]</span>
            <span class="flow" style="color: ${isError ? 'var(--neon-red)' : 'var(--neon-cyan)'}">[${title}]</span>
            <span class="msg" style="color: var(--text-muted)">${msg}</span>
        </div>
    `;
    
    terminalLog.appendChild(entry);
    terminalLog.scrollTop = terminalLog.scrollHeight;
}

// Rotina de Coleta de Lixo para Nós Clientes Inativos (Garbage Collection)
function pruneInactiveNodes() {
    const now = Date.now();
    const maxIdleTime = 30000; // 30 segundos de inatividade
    let changed = false;

    // Rastrear nós clientes inativos
    nodes.forEach((node, ip) => {
        // Ignorar servidores, nós sob ameaça ativa ou IPs do namespace de teste WSL
        if (node.isServer || node.threatActive || ip.startsWith("10.0.0.1") || ip.startsWith("10.0.0.2")) {
            return;
        }

        if (now - node.lastSeen > maxIdleTime) {
            nodes.delete(ip);
            changed = true;
            addSystemLog('GARBAGE COLLECTOR', `Removido nó inativo: ${ip}`);
        }
    });

    if (changed) {
        // Limpar arestas órfãs
        const initialEdges = edges.length;
        for (let i = edges.length - 1; i >= 0; i--) {
            const edge = edges[i];
            if (!nodes.has(edge.source.ip) || !nodes.has(edge.target.ip)) {
                edges.splice(i, 1);
            }
        }
        console.log(`[GC] Liberação de memória completa. Nós atuais: ${nodes.size}, Arestas: ${edges.length}`);
        
        // Atualizar simulação do D3-Force com o novo grafo
        updateD3Simulation();
    }
}

// Iniciar Coleta de Lixo a cada 5 segundos
setInterval(pruneInactiveNodes, 5000);

// ==========================================================================
// 4. INICIALIZAÇÕES E TIMERS DO DASHBOARD
// ==========================================================================

// Elementos das Abas e Histórico SQLite
const tabLive = document.getElementById('tab-live');
const tabHistory = document.getElementById('tab-history');
const liveActions = document.getElementById('live-actions');
const historyActions = document.getElementById('history-actions');
const historyLog = document.getElementById('history-log');
const chkOnlyThreats = document.getElementById('chk-only-threats');
const btnClearHistory = document.getElementById('btn-clear-history');

let activeTab = 'live';

tabLive.addEventListener('click', () => {
    if (activeTab === 'live') return;
    activeTab = 'live';
    
    tabLive.className = 'active-tab';
    tabHistory.className = 'inactive-tab';
    
    liveActions.style.display = 'flex';
    historyActions.style.display = 'none';
    
    terminalLog.style.display = 'flex';
    historyLog.style.display = 'none';
});

tabHistory.addEventListener('click', () => {
    if (activeTab === 'history') return;
    activeTab = 'history';
    
    tabLive.className = 'inactive-tab';
    tabHistory.className = 'active-tab';
    
    liveActions.style.display = 'none';
    historyActions.style.display = 'flex';
    
    terminalLog.style.display = 'none';
    historyLog.style.display = 'flex';
    
    fetchSQLiteHistory();
});

chkOnlyThreats.addEventListener('change', () => {
    if (activeTab === 'history') {
        fetchSQLiteHistory();
    }
});

btnClearHistory.addEventListener('click', async () => {
    if (confirm("Deseja mesmo apagar todo o histórico persistido no SQLite?")) {
        try {
            const response = await fetch('/api/clear_history', { method: 'POST' });
            const res = await response.json();
            if (res.status === 'success') {
                addSystemLog('SQLITE CLEAN', 'Base de dados histórica limpa com sucesso.');
                fetchSQLiteHistory();
            } else {
                console.error("Erro ao limpar histórico:", res.error);
            }
        } catch (err) {
            console.error("Falha na ligação à API:", err);
        }
    }
});

async function fetchSQLiteHistory() {
    historyLog.innerHTML = `
        <div class="log-entry system-msg">
            <span class="timestamp">[SQLITE]</span> 
            <span>Carregando histórico do banco de dados...</span>
        </div>
    `;
    
    const onlyThreats = chkOnlyThreats.checked;
    const url = `/api/history?limit=100&only_threats=${onlyThreats}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.error) {
            historyLog.innerHTML = `
                <div class="log-entry system-msg" style="color: var(--neon-red)">
                    <span class="timestamp">[ERRO]</span> 
                    <span>Falha ao carregar dados: ${data.error}</span>
                </div>
            `;
            return;
        }
        
        if (data.length === 0) {
            historyLog.innerHTML = `
                <div class="log-entry system-msg">
                    <span class="timestamp">[SQLITE]</span> 
                    <span>Nenhum registo encontrado no banco de dados.</span>
                </div>
            `;
            return;
        }
        
        historyLog.innerHTML = '';
        data.forEach(item => {
            const entry = document.createElement('div');
            entry.className = `log-entry ${item.is_threat ? 'anomaly' : ''}`;
            
            // Usar layout premium similar ao console principal
            const sign = item.is_threat ? '<i class="fa-solid fa-shield-virus text-red"></i>' : '<i class="fa-solid fa-circle-check text-green"></i>';
            const riskPct = (item.probability).toFixed(1);
            
            entry.innerHTML = `
                <div class="left-data">
                    <span class="timestamp">[${item.timestamp}]</span>
                    <span class="flow">${item.src_ip} ➔ ${item.dst_ip} (${item.protocol}/${item.port})</span>
                    <span class="meta">${(item.bytes / 1024).toFixed(1)} KB | ${item.packets} pacotes</span>
                </div>
                <div class="right-data">
                    <span class="score" style="color: ${item.is_threat ? 'var(--neon-red)' : 'var(--neon-green)'}">
                        ${sign} GAT: ${riskPct}%
                    </span>
                </div>
            `;
            
            // Adicionar evento para inspecionar fluxo histórico
            entry.addEventListener('click', () => {
                showHistoricalInspection(item);
            });
            
            historyLog.appendChild(entry);
        });
    } catch (err) {
        console.error("Falha ao contactar a API de histórico:", err);
        historyLog.innerHTML = `
            <div class="log-entry system-msg" style="color: var(--neon-red)">
                <span class="timestamp">[ERRO]</span> 
                <span>Erro de comunicação: ${err.message}</span>
            </div>
        `;
    }
}

// Inspecionar fluxo histórico
function showHistoricalInspection(item) {
    const flowInspector = document.getElementById('flow-inspector');
    
    // Formatar volume
    let vol = item.bytes;
    let volStr = vol > 1024 * 1024 ? `${(vol / (1024 * 1024)).toFixed(1)} MB` : `${(vol / 1024).toFixed(1)} KB`;
    
    flowInspector.innerHTML = `
        <div class="threat-inspector-card">
            <div class="inspect-header">
                <span class="flow-badge">REGISTO HISTÓRICO</span>
                <span class="${item.is_threat ? 'danger-tag' : 'normal-tag'}">
                    ${item.is_threat ? 'MITIGADO (XDP_DROP)' : 'SEGURO'}
                </span>
            </div>
            <div class="inspect-grid">
                <span class="label">Origem IP:</span><span class="val">${item.src_ip}</span>
                <span class="label">Destino IP:</span><span class="val">${item.dst_ip}</span>
                <span class="label">Porta Alvo:</span><span class="val">${item.port}</span>
                <span class="label">Protocolo:</span><span class="val">${item.protocol}</span>
                <span class="label">Volume Total:</span><span class="val">${volStr}</span>
                <span class="label">Pacotes:</span><span class="val">${item.packets}</span>
                <span class="label">Risco GNN:</span><span class="val text-cyan">${(item.probability).toFixed(1)}%</span>
            </div>
            <div class="inspect-footer ${item.is_threat ? '' : 'safe-footer'}">
                <i class="fa-solid ${item.is_threat ? 'fa-user-shield' : 'fa-check-double'}"></i>
                <span>${item.is_threat ? 
                    'Ameaça mitigada. Fluxo gravado em base de dados.' : 
                    'Tráfego regular sem anomalias detectadas.'}
                </span>
            </div>
        </div>
    `;
}

// Relógio do Sistema em tempo real
function updateClock() {
    const now = new Date();
    realTimeClock.textContent = now.toLocaleTimeString('pt-PT', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// Simulação realista de latência (ping) flutuante
setInterval(() => {
    const base = 0.40;
    const fluctuation = (Math.random() - 0.5) * 0.08;
    pingStatus.textContent = `${(base + fluctuation).toFixed(2)} ms`;
}, 2000);

// Lançamento Inicial
drawSparkline();
connectWebSocket();
console.log("Interface SPECTRE_GRID inicializada com sucesso!");
