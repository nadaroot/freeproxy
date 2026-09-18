"""
REST API and Minimalist Web Dashboard for Smart Proxy Pool.
"""

import time
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from .pool import ProxyPool
from .config import config

startTime = time.time()


def create_api_app(pool: ProxyPool) -> FastAPI:
    app = FastAPI(title="Smart Proxy Pool API", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        proxies = pool.get_all()
        count = len(proxies)
        http_count = len([p for p in proxies if p.protocol == "http"])
        socks5_count = len([p for p in proxies if p.protocol == "socks5"])
        avg_latency = round(sum(p.latency_ms for p in proxies) / count, 1) if count > 0 else 0
        uptime_min = int((time.time() - startTime) / 60)

        rows_html = ""
        for p in proxies[:40]:
            rows_html += f"""
            <tr>
                <td>{p.protocol.upper()}</td>
                <td class="mono">{p.ip}:{p.port}</td>
                <td>{round(p.latency_ms)} ms</td>
                <td>{p.anonymity}</td>
                <td>{p.success_count}/{p.fail_count}</td>
                <td class="muted">{time.strftime('%H:%M:%S', time.localtime(p.last_verified))}</td>
            </tr>
            """

        if not rows_html:
            rows_html = '<tr><td colspan="6" style="text-align: center; color: #737373; padding: 24px;">Происходит сбор и валидация прокси...</td></tr>'

        html = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Smart Proxy Pool</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: #ffffff;
                    color: #171717;
                    padding: 32px 20px;
                    line-height: 1.4;
                }}
                @media (prefers-color-scheme: dark) {{
                    body {{ background: #0a0a0a; color: #ededed; }}
                    .card, table {{ background: #121212; border-color: #262626 !important; }}
                    th, td {{ border-color: #262626 !important; }}
                    th {{ background: #171717 !important; color: #a3a3a3 !important; }}
                    .code-box {{ background: #171717 !important; border-color: #262626 !important; color: #ededed !important; }}
                    .muted {{ color: #737373 !important; }}
                    tr:hover {{ background: #1a1a1a !important; }}
                    a {{ color: #ededed !important; }}
                }}
                .container {{ max-width: 900px; margin: 0 auto; }}
                header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid #e5e5e5; }}
                h1 {{ font-size: 18px; font-weight: 600; letter-spacing: -0.01em; }}
                .nav-links a {{ color: #171717; text-decoration: none; margin-left: 16px; font-size: 13px; font-family: monospace; }}
                .nav-links a:hover {{ text-decoration: underline; }}
                .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
                .card {{ border: 1px solid #e5e5e5; border-radius: 6px; padding: 12px 14px; background: #fafafa; }}
                .card-label {{ font-size: 12px; color: #737373; margin-bottom: 4px; }}
                .card-val {{ font-size: 20px; font-weight: 600; }}
                .code-box {{ border: 1px solid #e5e5e5; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 12px; background: #fafafa; margin-bottom: 24px; overflow-x: auto; }}
                table {{ width: 100%; border-collapse: collapse; border: 1px solid #e5e5e5; border-radius: 6px; font-size: 13px; }}
                th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e5e5e5; }}
                th {{ background: #f5f5f5; color: #737373; font-weight: 500; font-size: 12px; }}
                tr:hover {{ background: #f9f9f9; }}
                .mono {{ font-family: monospace; }}
                .muted {{ color: #737373; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <header>
                    <div>
                        <h1>Smart Proxy Pool</h1>
                        <span class="muted">Локальный ротатор: 127.0.0.1:{config.proxy_port}</span>
                    </div>
                    <div class="nav-links">
                        <a href="/get">/get</a>
                        <a href="/all">/all</a>
                        <a href="/status">/status</a>
                    </div>
                </header>

                <div class="grid">
                    <div class="card">
                        <div class="card-label">Живых прокси</div>
                        <div class="card-val">{count}</div>
                    </div>
                    <div class="card">
                        <div class="card-label">Средний пинг</div>
                        <div class="card-val">{avg_latency} ms</div>
                    </div>
                    <div class="card">
                        <div class="card-label">HTTP / SOCKS5</div>
                        <div class="card-val">{http_count} / {socks5_count}</div>
                    </div>
                    <div class="card">
                        <div class="card-label">Uptime</div>
                        <div class="card-val">{uptime_min} мин</div>
                    </div>
                </div>

                <div class="code-box">
                    # Использование в Python (авто-смена IP на каждый запрос):<br>
                    import requests<br>
                    requests.get("http://httpbin.org/ip", proxies={{"http": "http://127.0.0.1:{config.proxy_port}", "https": "http://127.0.0.1:{config.proxy_port}"}})
                </div>

                <table>
                    <thead>
                        <tr>
                            <th>Тип</th>
                            <th>Адрес</th>
                            <th>Пинг</th>
                            <th>Анонимность</th>
                            <th>Успех/Сбои</th>
                            <th>Проверка</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        return html

    @app.get("/get")
    async def get_proxy(protocol: str = None, format: str = "text"):
        item = pool.get_random(protocol)
        if not item:
            if format == "json":
                return JSONResponse({"status": "empty", "message": "No proxies available in pool yet"}, status_code=503)
            return PlainTextResponse("No proxies available in pool yet", status_code=503)

        if format == "json":
            return JSONResponse(item.to_dict())
        return PlainTextResponse(item.url)

    @app.get("/all")
    async def get_all_proxies(protocol: str = None, format: str = "json"):
        items = pool.get_all(protocol)
        if format == "text":
            text_lines = "\n".join(p.url for p in items)
            return PlainTextResponse(text_lines)
        return JSONResponse({"count": len(items), "proxies": [p.to_dict() for p in items]})

    @app.get("/count")
    async def get_count():
        return JSONResponse({"count": pool.get_count()})

    @app.get("/status")
    async def get_status():
        return JSONResponse({
            "status": "running",
            "uptime_seconds": int(time.time() - startTime),
            "pool_size": pool.get_count(),
            "proxy_rotator": f"http://{config.proxy_host}:{config.proxy_port}",
            "api_server": f"http://{config.api_host}:{config.api_port}"
        })

    return app
