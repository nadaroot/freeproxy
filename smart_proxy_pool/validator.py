"""
Ultra-fast concurrent proxy validator with latency, protocol, and anonymity checks.
"""

import time
import asyncio
import logging
from dataclasses import dataclass, field
import aiohttp
from aiohttp_socks import ProxyConnector

from .config import config

logger = logging.getLogger("smart_proxy_pool.validator")


@dataclass(order=True)
class ProxyItem:
    sort_index: float = field(init=False)
    protocol: str
    ip: str
    port: int
    latency_ms: float = 9999.0
    anonymity: str = "unknown"
    country: str = "XX"
    success_count: int = 1
    fail_count: int = 0
    last_verified: float = field(default_factory=time.time)

    def __post_init__(self):
        self.sort_index = self.latency_ms

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"

    @property
    def host_port(self) -> str:
        return f"{self.ip}:{self.port}"

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "protocol": self.protocol,
            "ip": self.ip,
            "port": self.port,
            "latency_ms": round(self.latency_ms, 1),
            "anonymity": self.anonymity,
            "country": self.country,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "last_verified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_verified))
        }


class ProxyValidator:
    """
    Validates proxies concurrently and measures latency.
    """

    def __init__(self, check_timeout: float = None, max_concurrent: int = None):
        self.check_timeout = check_timeout or config.check_timeout
        self.max_concurrent = max_concurrent or config.max_concurrent_checks
        self.test_url = "http://httpbin.org/ip"
        self.backup_test_url = "https://api.ipify.org?format=json"

    async def check_single(self, protocol: str, ip: str, port: int) -> ProxyItem | None:
        """
        Validate a single proxy and return ProxyItem if valid.
        """
        proxy_url = f"{protocol}://{ip}:{port}"
        start_time = time.time()

        try:
            connector = ProxyConnector.from_url(proxy_url, ssl=False)
            timeout = aiohttp.ClientTimeout(total=self.check_timeout, connect=self.check_timeout)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(self.test_url) as resp:
                    if resp.status == 200:
                        latency = (time.time() - start_time) * 1000
                        if latency > config.min_speed_threshold_ms:
                            return None

                        data = await resp.json()
                        origin = data.get("origin", "")
                        anonymity = "anonymous" if ip in origin else "elite"

                        return ProxyItem(
                            protocol=protocol,
                            ip=ip,
                            port=port,
                            latency_ms=latency,
                            anonymity=anonymity,
                            country="GL",
                            last_verified=time.time()
                        )
        except Exception:
            pass

        return None

    async def validate_batch(self, raw_proxies: list[tuple[str, str, int]]) -> list[ProxyItem]:
        """
        Validate a batch of raw proxies concurrently with a semaphore.
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        valid_items: list[ProxyItem] = []

        async def _worker(proto, ip, port):
            async with semaphore:
                res = await self.check_single(proto, ip, port)
                if res:
                    valid_items.append(res)

        tasks = [_worker(proto, ip, port) for proto, ip, port in raw_proxies]
        await asyncio.gather(*tasks, return_exceptions=True)

        valid_items.sort(key=lambda x: x.latency_ms)
        logger.info(f"Validation finished: {len(valid_items)} / {len(raw_proxies)} proxies passed check.")
        return valid_items
