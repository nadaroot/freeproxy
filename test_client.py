"""
Example client showing automatic IP rotation with Smart Proxy Pool.
"""

import time
import requests

PROXY_URL = "http://127.0.0.1:8080"
proxies = {
    "http": PROXY_URL,
    "https": PROXY_URL
}

def main():
    print("==========================================")
    print("ТЕСТИРОВАНИЕ РОТАЦИИ IP (SMART PROXY POOL)")
    print("==========================================\n")

    for i in range(1, 6):
        try:
            start = time.time()
            resp = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=10)
            latency = int((time.time() - start) * 1000)
            ip_info = resp.json()
            print(f"[Запрос #{i}] IP: {ip_info.get('origin')} (Пинг: {latency}ms)")
        except Exception as e:
            print(f"[Запрос #{i}] Ошибка: {e}")
        time.sleep(1)

    print("\n[OK] Тестирование завершено.")

if __name__ == "__main__":
    main()
