"""
Main entrypoint for Smart Proxy Pool.
Runs the Rotating Proxy Server, REST API Dashboard, and Background Fetcher/Validator.
"""

import sys
import asyncio
import logging
import uvicorn
from colorama import init, Fore, Style

from smart_proxy_pool.config import config
from smart_proxy_pool.pool import ProxyPool
from smart_proxy_pool.proxy_server import RotatingProxyServer
from smart_proxy_pool.api_server import create_api_app

init(autoreset=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s · %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("smart_proxy_pool")


def print_banner():
    banner = f"""
{Fore.CYAN}╔═════════════════════════════════════════════════════════════════╗
║                      SMART PROXY POOL                           ║
║          Авто-сборщик, валидатор и локальный ротатор            ║
╚═════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
• {Fore.GREEN}Rotating Proxy Server:{Style.RESET_ALL}  http://127.0.0.1:{config.proxy_port} (auto IP-rotation)
• {Fore.GREEN}REST API & Web UI:{Style.RESET_ALL}      http://127.0.0.1:{config.api_port}
• {Fore.GREEN}Sources:{Style.RESET_ALL}                20+ public lists (HTTP / SOCKS4 / SOCKS5)
• {Fore.GREEN}Re-check interval:{Style.RESET_ALL}      Every {config.recheck_interval_seconds}s
"""
    print(banner)


async def main():
    print_banner()

    # Initialize pool
    pool = ProxyPool()

    # Start background scraper and validator
    asyncio.create_task(pool.start_background_tasks())

    # Create rotating forward proxy server
    proxy_server = RotatingProxyServer(pool, host=config.proxy_host, port=config.proxy_port)
    asyncio.create_task(proxy_server.start())

    # Create REST API & Web Dashboard app
    app = create_api_app(pool)
    uvicorn_config = uvicorn.Config(
        app=app,
        host=config.api_host,
        port=config.api_port,
        log_level="warning"
    )
    server = uvicorn.Server(uvicorn_config)

    logger.info(f"REST API & Web Dashboard ready on http://127.0.0.1:{config.api_port}")
    logger.info(f"Rotating Proxy ready on http://127.0.0.1:{config.proxy_port}")
    logger.info("Initializing initial proxy scraping and validation...")

    await server.serve()


if __name__ == "__main__":
    try:
        if sys.platform != "win32":
            try:
                import uvloop
                uvloop.install()
            except ImportError:
                pass
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down Smart Proxy Pool...")
