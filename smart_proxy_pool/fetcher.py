"""
Asynchronous proxy fetcher from 20+ public open-source lists and endpoints.
"""

import re
import asyncio
import logging
import aiohttp

logger = logging.getLogger("smart_proxy_pool.fetcher")

# Regex to match IP:PORT
IP_PORT_REGEX = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})")

# High quality raw text lists
RAW_SOURCES = [
    # TheSpeedX
    {"url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt", "protocol": "http"},
    {"url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt", "protocol": "socks4"},
    {"url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt", "protocol": "socks5"},
    
    # monosans
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", "protocol": "http"},
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt", "protocol": "socks4"},
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt", "protocol": "socks5"},
    
    # clarketm
    {"url": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt", "protocol": "http"},
    
    # hookzof
    {"url": "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt", "protocol": "socks5"},
    
    # proxifly
    {"url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt", "protocol": "http"},
    {"url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt", "protocol": "socks4"},
    {"url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt", "protocol": "socks5"},
    
    # roosterkid
    {"url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt", "protocol": "http"},
    {"url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt", "protocol": "socks4"},
    {"url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt", "protocol": "socks5"},
    
    # sunny9577
    {"url": "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt", "protocol": "http"},
    {"url": "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks4_proxies.txt", "protocol": "socks4"},
    {"url": "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks5_proxies.txt", "protocol": "socks5"},
    
    # ShiftyTR
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt", "protocol": "http"},
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt", "protocol": "http"},
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt", "protocol": "socks5"},

    # ProxyScrape free endpoints
    {"url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all", "protocol": "http"},
    {"url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=5000&country=all", "protocol": "socks4"},
    {"url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=5000&country=all", "protocol": "socks5"}
]


class ProxyFetcher:
    """
    Asynchronously fetches and deduplicates raw proxies from public endpoints.
    """

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def _fetch_source(self, session: aiohttp.ClientSession, source: dict) -> list[tuple[str, str, int]]:
        url = source["url"]
        protocol = source["protocol"]
        results = []

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(url, headers=self.headers, timeout=timeout) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    matches = IP_PORT_REGEX.findall(text)
                    for ip, port in matches:
                        results.append((protocol, ip, int(port)))
        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")

        return results

    async def fetch_all(self) -> set[tuple[str, str, int]]:
        """
        Fetch all sources concurrently and return deduplicated set of (protocol, ip, port).
        """
        logger.info(f"Starting proxy fetch from {len(RAW_SOURCES)} public sources...")
        all_proxies = set()

        connector = aiohttp.TCPConnector(limit=50, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._fetch_source(session, src) for src in RAW_SOURCES]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in batch_results:
                if isinstance(res, list):
                    all_proxies.update(res)

        logger.info(f"Fetched {len(all_proxies)} unique raw proxies from all sources.")
        return all_proxies
