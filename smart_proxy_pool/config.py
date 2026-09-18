"""
Configuration settings for Smart Proxy Pool.
"""

import os
from pydantic import BaseModel

class Config(BaseModel):
    # Proxy Server (Rotating Forward Proxy)
    proxy_host: str = os.getenv("PROXY_HOST", "0.0.0.0")
    proxy_port: int = int(os.getenv("PROXY_PORT", "8080"))

    # REST API & Web Dashboard
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "5010"))

    # Validation parameters
    max_concurrent_checks: int = int(os.getenv("MAX_CONCURRENT_CHECKS", "150"))
    check_timeout: float = float(os.getenv("CHECK_TIMEOUT", "3.5"))
    min_speed_threshold_ms: float = float(os.getenv("MIN_SPEED_THRESHOLD_MS", "4000"))

    # Periodic background intervals (seconds)
    fetch_interval_seconds: int = int(os.getenv("FETCH_INTERVAL_SECONDS", "600"))  # 10 min
    recheck_interval_seconds: int = int(os.getenv("RECHECK_INTERVAL_SECONDS", "300"))  # 5 min

    # Pool limits
    max_pool_size: int = int(os.getenv("MAX_POOL_SIZE", "1500"))
    db_path: str = os.getenv("DB_PATH", "proxies.db")

    # Verification endpoints
    test_urls: list[str] = [
        "http://httpbin.org/ip",
        "https://api.ipify.org?format=json"
    ]

config = Config()
