"""
In-memory and SQLite-backed Pool Manager with automatic scoring and rotation.
"""

import random
import sqlite3
import asyncio
import logging
from .config import config
from .validator import ProxyItem, ProxyValidator
from .fetcher import ProxyFetcher

logger = logging.getLogger("smart_proxy_pool.pool")


class ProxyPool:
    """
    Manages live pool of verified proxies, background scraping and re-checking.
    """

    def __init__(self):
        self.proxies: dict[str, ProxyItem] = {}
        self.validator = ProxyValidator()
        self.fetcher = ProxyFetcher()
        self.is_running = False
        self._index = 0
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(config.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS proxies (
                        url TEXT PRIMARY KEY,
                        protocol TEXT,
                        ip TEXT,
                        port INTEGER,
                        latency_ms REAL,
                        anonymity TEXT,
                        country TEXT,
                        success_count INTEGER,
                        fail_count INTEGER,
                        last_verified REAL
                    )
                """)
                conn.commit()
                # Load existing proxies into memory
                cursor = conn.cursor()
                cursor.execute("SELECT protocol, ip, port, latency_ms, anonymity, country, success_count, fail_count, last_verified FROM proxies")
                for row in cursor.fetchall():
                    item = ProxyItem(
                        protocol=row[0],
                        ip=row[1],
                        port=row[2],
                        latency_ms=row[3],
                        anonymity=row[4],
                        country=row[5],
                        success_count=row[6],
                        fail_count=row[7],
                        last_verified=row[8]
                    )
                    self.proxies[item.url] = item
            logger.info(f"Loaded {len(self.proxies)} cached proxies from database.")
        except Exception as e:
            logger.warning(f"Could not load database: {e}")

    def _save_db(self):
        try:
            with sqlite3.connect(config.db_path) as conn:
                conn.execute("DELETE FROM proxies")
                for item in self.proxies.values():
                    conn.execute("""
                        INSERT OR REPLACE INTO proxies (url, protocol, ip, port, latency_ms, anonymity, country, success_count, fail_count, last_verified)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item.url, item.protocol, item.ip, item.port,
                        item.latency_ms, item.anonymity, item.country,
                        item.success_count, item.fail_count, item.last_verified
                    ))
                conn.commit()
        except Exception as e:
            logger.warning(f"Error saving to database: {e}")

    async def add_proxies(self, items: list[ProxyItem]):
        async with self._lock:
            for item in items:
                self.proxies[item.url] = item

            # Limit max pool size by pruning slowest
            if len(self.proxies) > config.max_pool_size:
                sorted_items = sorted(self.proxies.values(), key=lambda x: x.latency_ms)
                self.proxies = {x.url: x for x in sorted_items[:config.max_pool_size]}

            self._save_db()

    def get_random(self, protocol: str | None = None) -> ProxyItem | None:
        """
        Get a random healthy proxy (optionally filtered by protocol: http, socks5).
        """
        candidates = list(self.proxies.values())
        if protocol:
            candidates = [p for p in candidates if p.protocol == protocol.lower()]

        if not candidates:
            return None
        return random.choice(candidates)

    def get_round_robin(self) -> ProxyItem | None:
        """
        Get next proxy in round-robin order.
        """
        items = list(self.proxies.values())
        if not items:
            return None
        self._index = (self._index + 1) % len(items)
        return items[self._index]

    def get_all(self, protocol: str | None = None) -> list[ProxyItem]:
        items = list(self.proxies.values())
        if protocol:
            items = [p for p in items if p.protocol == protocol.lower()]
        items.sort(key=lambda x: x.latency_ms)
        return items

    def get_count(self) -> int:
        return len(self.proxies)

    def mark_success(self, proxy_url: str):
        if proxy_url in self.proxies:
            self.proxies[proxy_url].success_count += 1

    def mark_failure(self, proxy_url: str):
        if proxy_url in self.proxies:
            item = self.proxies[proxy_url]
            item.fail_count += 1
            if item.fail_count >= 3:
                del self.proxies[proxy_url]
                logger.debug(f"Removed dead proxy {proxy_url} from pool.")

    async def run_fetch_and_validate(self):
        """
        Fetch fresh proxies and validate them into pool.
        """
        try:
            raw_proxies = await self.fetcher.fetch_all()
            if raw_proxies:
                # Filter out ones we already tested recently
                to_test = [p for p in raw_proxies if f"{p[0]}://{p[1]}:{p[2]}" not in self.proxies]
                logger.info(f"Validating {len(to_test)} new proxy candidates...")
                valid = await self.validator.validate_batch(to_test)
                if valid:
                    await self.add_proxies(valid)
                    logger.info(f"[Pool] Added {len(valid)} fresh proxies. Total pool size: {self.get_count()}")
        except Exception as e:
            logger.error(f"Error during fetch and validate loop: {e}")

    async def run_recheck_existing(self):
        """
        Recheck active proxies to purge dead ones and update latency.
        """
        if not self.proxies:
            return

        logger.info(f"Re-checking {len(self.proxies)} active proxies...")
        raw_list = [(p.protocol, p.ip, p.port) for p in self.proxies.values()]
        valid = await self.validator.validate_batch(raw_list)
        
        async with self._lock:
            new_pool = {p.url: p for p in valid}
            purged = len(self.proxies) - len(new_pool)
            self.proxies = new_pool
            self._save_db()
            logger.info(f"[Pool] Recheck complete. {len(self.proxies)} alive ({purged} purged).")

    async def start_background_tasks(self):
        """
        Starts recurring fetcher and validator loops in background.
        """
        self.is_running = True
        # Run initial fetch immediately
        asyncio.create_task(self.run_fetch_and_validate())

        while self.is_running:
            await asyncio.sleep(config.recheck_interval_seconds)
            await self.run_recheck_existing()
            await self.run_fetch_and_validate()
