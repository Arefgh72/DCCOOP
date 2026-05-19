import websocket
import json
import requests
import threading
import os
import time
import urllib3
import socket

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WORKER_WS_URL = os.environ.get("WORKER_URL", "wss://wild-paper-0725.aref-gha.workers.dev/ws")
PROXY_HTTP = "http://127.0.0.1:10809"
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 10809

def is_proxy_ready():
    try:
        with socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=2):
            return True
    except:
        return False

def handle_request(ws, data):
    request_id = data.get("id")
    payload = data.get("payload", {})

    url = payload.get("u")
    method = payload.get("m", "GET")
    headers = payload.get("h", {})
    body = payload.get("b")

    print(f"[{time.strftime('%H:%M:%S')}] Executing: {method} {url}")

    try:
        proxies = {"http": PROXY_HTTP, "https": PROXY_HTTP}
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=body,
            proxies=proxies,
            timeout=20,
            verify=False
        )
        response_payload = {
            "s": resp.status_code,
            "h": dict(resp.headers),
            "b": resp.text
        }
        print(f"[{time.strftime('%H:%M:%S')}] Success: {method} {url} -> {resp.status_code}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error: {method} {url} -> {str(e)}")
        response_payload = {"e": str(e)}

    try:
        ws.send(json.dumps({
            "type": "response",
            "id": request_id,
            "payload": response_payload
        }))
    except Exception as e:
        print(f"Failed to send response: {e}")

def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("type") == "request":
            threading.Thread(target=handle_request, args=(ws, data)).start()
    except Exception as e:
        print(f"Error handling WS message: {e}")

def on_error(ws, error):
    print(f"WS Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"WS Connection closed: {close_status_code} {close_msg}")

def on_open(ws):
    print(f"[{time.strftime('%H:%M:%S')}] Tunnel connected to {WORKER_WS_URL}")
    print("Waiting for requests from Google Apps Script...")

def run_bridge():
    while True:
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Attempting to connect to worker...")
            ws = websocket.WebSocketApp(
                WORKER_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever()
        except Exception as e:
            print(f"Bridge connection error: {e}")

        print("Reconnecting in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    print("Bridge started. Checking Xray readiness...")
    # Wait for Xray to be ready (port open)
    retry_count = 0
    while not is_proxy_ready() and retry_count < 30:
        print(f"Waiting for Xray proxy on {PROXY_HOST}:{PROXY_PORT}... ({retry_count}/30)")
        time.sleep(2)
        retry_count += 1

    if is_proxy_ready():
        print("Xray proxy is ready.")
        run_bridge()
    else:
        print("Xray failed to start or proxy port is not open. Exiting.")
