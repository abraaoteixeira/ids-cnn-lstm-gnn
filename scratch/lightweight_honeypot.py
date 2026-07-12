import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("SPECTRE_HONEYPOT")

async def handle_telnet(reader, writer):
    try:
        writer.write(b"Ubuntu 22.04 LTS\nlogin: ")
        await writer.drain()
        data = await asyncio.wait_for(reader.read(100), timeout=5)
        writer.write(b"Password: ")
        await writer.drain()
        await asyncio.sleep(2)
        writer.write(b"\nLogin incorrect\n")
        await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def handle_http(reader, writer):
    try:
        data = await asyncio.wait_for(reader.read(1024), timeout=5)
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Server: Apache/2.4.41 (Ubuntu)\r\n"
            "Content-Type: text/html; charset=UTF-8\r\n"
            "Content-Length: 137\r\n"
            "Connection: close\r\n\r\n"
            "<html><head><title>Index of /</title></head><body><h1>Index of /</h1><ul><li><a href='/wp-admin/'>wp-admin/</a></li></ul></body></html>"
        )
        writer.write(response.encode('utf-8'))
        await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def handle_mysql(reader, writer):
    try:
        # Fake MySQL packet header
        handshake = b"\x0a\x35\x2e\x37\x2e\x32\x39\x2d\x30\x75\x62\x75\x6e\x74\x75\x30\x2e\x31\x38\x2e\x30\x34\x2e\x31\x00"
        writer.write(handshake)
        await writer.drain()
        await asyncio.sleep(2)
    except Exception:
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def start_honeypot():
    ports = {
        23: handle_telnet,
        80: handle_http,
        3306: handle_mysql,
    }
    servers = []
    for port, handler in ports.items():
        try:
            server = await asyncio.start_server(handler, '0.0.0.0', port)
            logger.info(f"Honeypot ativo na porta: {port}")
            servers.append(server)
        except Exception as e:
            logger.error(f"Erro ao abrir porta {port}: {e}")
    if servers:
        await asyncio.gather(*[server.serve_forever() for server in servers])

if __name__ == "__main__":
    try:
        asyncio.run(start_honeypot())
    except KeyboardInterrupt:
        logger.info("Honeypot finalizado.")
