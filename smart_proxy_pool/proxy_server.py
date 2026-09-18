"""
High-performance AsyncIO Forward Proxy with automatic IP rotation and seamless retries.
"""

import re
import asyncio
import logging
import aiohttp
from aiohttp_socks import ProxyConnector
from .config import config
from .pool import ProxyPool

logger = logging.getLogger("smart_proxy_pool.proxy_server")


class RotatingProxyServer:
    """
    Local forward proxy that rotates outbound IP address for every incoming request.
    """

    def __init__(self, pool: ProxyPool, host: str = None, port: int = None):
        self.pool = pool
        self.host = host or config.proxy_host
        self.port = port or config.proxy_port
        self.server = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Handles incoming HTTP/HTTPS request from client and forwards it through rotated proxy.
        """
        try:
            # Read request line and headers
            header_data = await reader.readuntil(b"\r\n\r\n")
        except Exception:
            writer.close()
            return

        lines = header_data.split(b"\r\n")
        if not lines or not lines[0]:
            writer.close()
            return

        request_line = lines[0].decode("utf-8", errors="ignore")
        parts = request_line.split(" ")
        if len(parts) < 2:
            writer.close()
            return

        method = parts[0].upper()
        target = parts[1]

        # HTTPS Tunneling (CONNECT method)
        if method == "CONNECT":
            await self._handle_https_connect(reader, writer, target)
        else:
            # Standard HTTP GET/POST/etc.
            await self._handle_http_request(reader, writer, method, target, header_data)

    async def _handle_https_connect(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter, target: str):
        """
        Handles HTTPS CONNECT tunnels by connecting to upstream destination and piping data.
        """
        try:
            host, port_str = target.split(":")
            port = int(port_str)
        except Exception:
            client_writer.close()
            return

        max_attempts = 3
        remote_reader = None
        remote_writer = None
        used_proxy = None

        for attempt in range(max_attempts):
            proxy = self.pool.get_random()
            if not proxy:
                # Direct connection fallback if pool is empty
                try:
                    remote_reader, remote_writer = await asyncio.open_connection(host, port)
                    break
                except Exception:
                    continue

            used_proxy = proxy
            try:
                # Direct TCP connection or proxy tunnel
                if proxy.protocol == "http":
                    remote_reader, remote_writer = await asyncio.open_connection(proxy.ip, proxy.port)
                    connect_cmd = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\nProxy-Connection: keep-alive\r\n\r\n".encode()
                    remote_writer.write(connect_cmd)
                    await remote_writer.drain()
                    resp = await remote_reader.readuntil(b"\r\n\r\n")
                    if b"200" in resp:
                        break
                    else:
                        remote_writer.close()
                        self.pool.mark_failure(proxy.url)
                        continue
                else:
                    # SOCKS4/5 proxy
                    remote_reader, remote_writer = await asyncio.open_connection(proxy.ip, proxy.port)
                    break
            except Exception:
                if used_proxy:
                    self.pool.mark_failure(used_proxy.url)
                if remote_writer:
                    remote_writer.close()
                continue

        if not remote_writer:
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await client_writer.drain()
            client_writer.close()
            return

        # Tell client tunnel is established
        client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await client_writer.drain()
        if used_proxy:
            self.pool.mark_success(used_proxy.url)

        # Pipe traffic bi-directionally
        async def _pipe(r, w):
            try:
                while True:
                    data = await r.read(16384)
                    if not data:
                        break
                    w.write(data)
                    await w.drain()
            except Exception:
                pass
            finally:
                try:
                    w.close()
                except Exception:
                    pass

        await asyncio.gather(
            _pipe(client_reader, remote_writer),
            _pipe(remote_reader, client_writer),
            return_exceptions=True
        )

    async def _handle_http_request(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter, method: str, target: str, raw_headers: bytes):
        """
        Forwards plain HTTP requests through rotated upstream proxy.
        """
        max_attempts = 3
        for _ in range(max_attempts):
            proxy = self.pool.get_random()
            proxy_url = proxy.url if proxy else None

            try:
                connector = ProxyConnector.from_url(proxy_url, ssl=False) if proxy_url else None
                timeout = aiohttp.ClientTimeout(total=8)

                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    # Parse URL
                    url = target if target.startswith("http") else f"http://{target}"
                    async with session.request(method, url) as upstream_resp:
                        # Write status
                        status_line = f"HTTP/1.1 {upstream_resp.status} {upstream_resp.reason}\r\n".encode()
                        client_writer.write(status_line)

                        # Write headers
                        for k, v in upstream_resp.headers.items():
                            if k.lower() not in ("transfer-encoding", "connection"):
                                client_writer.write(f"{k}: {v}\r\n".encode())
                        client_writer.write(b"Connection: close\r\n\r\n")

                        # Stream body
                        async for chunk in upstream_resp.content.iter_chunked(8192):
                            client_writer.write(chunk)
                            await client_writer.drain()

                        if proxy:
                            self.pool.mark_success(proxy.url)
                        client_writer.close()
                        return
            except Exception:
                if proxy:
                    self.pool.mark_failure(proxy.url)
                continue

        client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/plain\r\n\r\nAll upstream proxy attempts failed.")
        await client_writer.drain()
        client_writer.close()

    async def start(self):
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logger.info(f"Rotating Proxy Server listening on http://{self.host}:{self.port}")
        async with self.server:
            await self.server.serve_forever()
