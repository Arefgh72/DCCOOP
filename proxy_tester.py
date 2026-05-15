import requests
import base64
import json
import time
import concurrent.futures
import re
import socket
import os
import subprocess
from urllib.parse import urlparse, unquote

SUB_URL = "https://github.com/Arefgh72/v2ray-proxy-pars-tester-02/raw/main/output/top_500.txt"
TEST_URL = "https://www.youtube.com"
TIMEOUT = 5

def fetch_proxies():
    try:
        response = requests.get(SUB_URL)
        response.raise_for_status()
        lines = response.text.splitlines()
        proxies = [line.strip() for line in lines if line.strip()]
        return proxies
    except Exception as e:
        print(f"Error fetching proxies: {e}")
        return []

def parse_ss(url):
    try:
        parsed = urlparse(url)
        if '@' in parsed.netloc:
            userinfo, addr = parsed.netloc.split('@')
            host, port = addr.split(':')
            decoded = base64.b64decode(userinfo + '=' * (-len(userinfo) % 4)).decode()
            method, password = decoded.split(':')
        else:
            data = parsed.netloc
            decoded = base64.b64decode(data + '=' * (-len(data) % 4)).decode()
            match = re.match(r'(.+):(.+)@(.+):(\d+)', decoded)
            if match:
                method, password, host, port = match.groups()
            else:
                return None
        return {
            "protocol": "shadowsocks",
            "settings": {
                "servers": [{"address": host, "port": int(port), "method": method, "password": password}]
            },
            "tag": "proxy"
        }
    except:
        return None

def parse_vmess(url):
    try:
        data = url[8:]
        decoded = base64.b64decode(data + '=' * (-len(data) % 4)).decode()
        config = json.loads(decoded)
        return {
            "protocol": "vmess",
            "settings": {
                "vnext": [{
                    "address": config["add"],
                    "port": int(config["port"]),
                    "users": [{"id": config["id"], "alterId": int(config.get("aid", 0)), "security": config.get("scy", "auto")}]
                }]
            },
            "streamSettings": {
                "network": config.get("net", "tcp"),
                "security": config.get("tls", "none"),
                "tlsSettings": {"serverName": config.get("sni", "")} if config.get("tls") == "tls" else {},
                "wsSettings": {"path": config.get("path", "/")} if config.get("net") == "ws" else {}
            },
            "tag": "proxy"
        }
    except:
        return None

def tcp_test(proxy_url):
    config = None
    if proxy_url.startswith("ss://"): config = parse_ss(proxy_url)
    elif proxy_url.startswith("vmess://"): config = parse_vmess(proxy_url)

    if not config: return None, float('inf'), None

    try:
        if config["protocol"] == "shadowsocks":
            addr, port = config["settings"]["servers"][0]["address"], config["settings"]["servers"][0]["port"]
        else:
            addr, port = config["settings"]["vnext"][0]["address"], config["settings"]["vnext"][0]["port"]

        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.connect((addr, port))
        sock.close()
        return proxy_url, (time.time() - start) * 1000, config
    except:
        return None, float('inf'), None

def web_test(proxy_config):
    # Setup a temporary Xray config for this one proxy
    temp_config = {
        "inbounds": [{"port": 20809, "protocol": "http"}],
        "outbounds": [proxy_config]
    }
    with open("temp_xray.json", "w") as f:
        json.dump(temp_config, f)

    # Start Xray
    try:
        proc = subprocess.Popen(["xray", "-c", "temp_xray.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1) # wait for xray to start

        start = time.time()
        res = requests.get(TEST_URL, proxies={"http": "http://127.0.0.1:20809", "https": "http://127.0.0.1:20809"}, timeout=TIMEOUT)
        latency = (time.time() - start) * 1000
        proc.terminate()
        if res.status_code < 400:
            return latency
    except:
        if 'proc' in locals(): proc.terminate()
    return float('inf')

def get_best_proxy():
    proxies = fetch_proxies()
    print(f"Found {len(proxies)} proxies. Phase 1: TCP Ping...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        results = [r for r in executor.map(tcp_test, proxies) if r[0]]

    results.sort(key=lambda x: x[1])
    top_candidates = results[:20] # Take top 20 for web test

    print(f"Phase 2: Web Test (YouTube) for top {len(top_candidates)} candidates...")
    best_config = None
    min_web_latency = float('inf')

    for url, tcp_lat, config in top_candidates:
        web_lat = web_test(config)
        if web_lat < min_web_latency:
            min_web_latency = web_lat
            best_config = config
            print(f"New best: {url} | TCP: {tcp_lat:.0f}ms | Web: {web_lat:.0f}ms")

    if best_config:
        return best_config
    return None

if __name__ == "__main__":
    best = get_best_proxy()
    if best:
        with open("best_proxy.json", "w") as f:
            json.dump(best, f)
        print("Best proxy saved to best_proxy.json")
