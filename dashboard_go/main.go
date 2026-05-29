package main

import (
	"bufio"
	"database/sql"
	"encoding/json"
	"log"
	"net"
	"os"
	"sync"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/websocket/v2"
	_ "github.com/mattn/go-sqlite3"
)

const (
	SocketPath = "/tmp/spectre.sock"
	DBPath     = "spectre_history_go.db"
)

// Estrutura do payload recebido do C++
type ThreatLog struct {
	FlowID      int     `json:"flow_id"`
	SrcIP       string  `json:"src_ip"`
	DstIP       string  `json:"dst_ip"`
	Port        int     `json:"port"`
	Protocol    string  `json:"protocol"`
	Probability float64 `json:"probability"`
	IsThreat    bool    `json:"is_threat"`
	Bytes       int     `json:"bytes"`
	Packets     int     `json:"packets"`
	Timestamp   string  `json:"timestamp"`
}

// Hub para gerenciar as conexões WebSocket
type WSHub struct {
	clients    map[*websocket.Conn]bool
	broadcast  chan []byte
	register   chan *websocket.Conn
	unregister chan *websocket.Conn
	mu         sync.Mutex
}

var hub = &WSHub{
	clients:    make(map[*websocket.Conn]bool),
	broadcast:  make(chan []byte, 10000), // Buffer generoso
	register:   make(chan *websocket.Conn),
	unregister: make(chan *websocket.Conn),
}

var dbWriteChan = make(chan ThreatLog, 100000)

func main() {
	log.Println("[SPECTRE_GO] Iniciando Ultra-High Performance Backend")

	// 1. Inicializar DB
	db, err := sql.Open("sqlite3", DBPath)
	if err != nil {
		log.Fatalf("Erro ao abrir DB: %v", err)
	}
	defer db.Close()

	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS threat_log (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		timestamp TEXT, src_ip TEXT, dst_ip TEXT, port INTEGER,
		protocol TEXT, probability REAL, is_threat INTEGER, bytes INTEGER, packets INTEGER
	)`)
	if err != nil {
		log.Fatalf("Erro ao criar tabela: %v", err)
	}

	// 2. Iniciar Workers
	go wsHubRun()
	go dbWriterWorker(db)
	go startUnixSocketListener()

	// 3. Setup Fiber (Web Server API)
	app := fiber.New(fiber.Config{
		DisableStartupMessage: true,
	})
	app.Use(cors.New())

	// Middlewares para Upgrade de WebSocket
	app.Use("/ws", func(c *fiber.Ctx) error {
		if websocket.IsWebSocketUpgrade(c) {
			c.Locals("allowed", true)
			return c.Next()
		}
		return fiber.ErrUpgradeRequired
	})

	app.Get("/ws/threats", websocket.New(func(c *websocket.Conn) {
		hub.register <- c
		defer func() {
			hub.unregister <- c
			c.Close()
		}()
		for {
			// Apenas mantém a conexão viva, lendo pings/close
			if _, _, err := c.ReadMessage(); err != nil {
				break
			}
		}
	}))

	// API REST para histórico
	app.Get("/api/history", func(c *fiber.Ctx) error {
		rows, err := db.Query("SELECT timestamp, src_ip, dst_ip, port, protocol, probability, is_threat, bytes, packets FROM threat_log ORDER BY id DESC LIMIT 50")
		if err != nil {
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}
		defer rows.Close()

		var history []ThreatLog
		for rows.Next() {
			var t ThreatLog
			var isThreatInt int
			if err := rows.Scan(&t.Timestamp, &t.SrcIP, &t.DstIP, &t.Port, &t.Protocol, &t.Probability, &isThreatInt, &t.Bytes, &t.Packets); err == nil {
				t.IsThreat = isThreatInt == 1
				history = append(history, t)
			}
		}
		return c.JSON(history)
	})

	log.Println("[SPECTRE_GO] Servidor escutando na porta 8001")
	log.Fatal(app.Listen(":8001"))
}

// =========================================================
// WOKERS ASSÍNCRONOS
// =========================================================

func wsHubRun() {
	for {
		select {
		case client := <-hub.register:
			hub.mu.Lock()
			hub.clients[client] = true
			hub.mu.Unlock()
		case client := <-hub.unregister:
			hub.mu.Lock()
			if _, ok := hub.clients[client]; ok {
				delete(hub.clients, client)
			}
			hub.mu.Unlock()
		case message := <-hub.broadcast:
			hub.mu.Lock()
			for client := range hub.clients {
				err := client.WriteMessage(websocket.TextMessage, message)
				if err != nil {
					client.Close()
					delete(hub.clients, client)
				}
			}
			hub.mu.Unlock()
		}
	}
}

func dbWriterWorker(db *sql.DB) {
	for {
		// Pega o primeiro item bloqueando
		logItem := <-dbWriteChan
		batch := []ThreatLog{logItem}

		// Tenta drenar a fila rapidamente para fazer um Batch Insert (até 500)
		for i := 0; i < 499; i++ {
			select {
			case item := <-dbWriteChan:
				batch = append(batch, item)
			default:
				break
			}
		}

		// Insert transacional otimizado
		tx, _ := db.Begin()
		stmt, _ := tx.Prepare("INSERT INTO threat_log (timestamp, src_ip, dst_ip, port, protocol, probability, is_threat, bytes, packets) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
		for _, b := range batch {
			isThreatInt := 0
			if b.IsThreat {
				isThreatInt = 1
			}
			stmt.Exec(b.Timestamp, b.SrcIP, b.DstIP, b.Port, b.Protocol, b.Probability, isThreatInt, b.Bytes, b.Packets)
		}
		stmt.Close()
		tx.Commit()
	}
}

func startUnixSocketListener() {
	os.Remove(SocketPath)
	listener, err := net.Listen("unix", SocketPath)
	if err != nil {
		log.Fatalf("Erro ao iniciar Socket Unix: %v", err)
	}
	defer listener.Close()
	os.Chmod(SocketPath, 0666)

	log.Println("[SPECTRE_GO] Ouvindo IPC Unix em", SocketPath)

	for {
		conn, err := listener.Accept()
		if err != nil {
			log.Printf("Erro de accept IPC: %v", err)
			continue
		}
		go handleIPCConnection(conn)
	}
}

func handleIPCConnection(conn net.Conn) {
	defer conn.Close()
	scanner := bufio.NewScanner(conn)
	
	// Aumentar buffer para pacotes grandes
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 1024*1024)

	for scanner.Scan() {
		rawLine := scanner.Bytes()
		
		// 1. Enviar direto para os WebSockets (Zero Parse / Fan-Out)
		// Fazemos uma cópia do slice porque scanner.Bytes() reutiliza a memória
		msgCopy := make([]byte, len(rawLine))
		copy(msgCopy, rawLine)
		
		select {
		case hub.broadcast <- msgCopy:
		default:
			// Buffer do hub cheio, ignora para não bloquear
		}

		// 2. Fazer Parse JSON para gravar no Banco
		var payload ThreatLog
		if err := json.Unmarshal(rawLine, &payload); err == nil {
			select {
			case dbWriteChan <- payload:
			default:
				// Fila do banco cheia, backpressure protection
			}
		}
	}
}
