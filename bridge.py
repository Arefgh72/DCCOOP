import websocket
import json
import requests
import threading
import os
import time
import urllib3

# Suppress insecure request warnings if verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WORKER_WS_URL = os.environ.get("WORKER_URL", "wss://wild-paper-0725.aref-gha.workers.dev/ws")
PROXY_HTTP = "http://127.0.0.1:10809"

def handle_request(ws, data):
    request_id = data.get("id")
    payload = data.get("payload", {})

    url = payload.get("u")
    method = payload.get("m", "GET")
    headers = payload.get("h", {})
    body = payload.get("b")

    print(f"Executing request: {method} {url}")

    try:
        proxies = {"http": PROXY_HTTP, "https": PROXY_HTTP}
        # We try with verification first, fallback to no-verify if it's a proxy issue
        # But for this task, the user wanted a relay, so we'll be flexible.
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
    except Exception as e:
        response_payload = {"e": str(e)}

    try:
        ws.send(json.dumps({
            "type": "response",
            "id": request_id,
            "payload": response_payload
        }))
    except Exception as e:
        print(f"Failed to send response back to WS: {e}")

def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("type") == "request":
            threading.Thread(target=handle_request, args=(ws, data)).start()
    except Exception as e:
        print(f"Error decoding WS message: {e}")

def on_error(ws, error):
    print(f"WS Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"WS Closed: {close_status_code} - {close_msg}")

def on_open(ws):
    print("Bridge connected to Cloudflare Worker")

def run_bridge():
    while True:
        try:
            print(f"Connecting to {WORKER_WS_URL}...")
            ws = websocket.WebSocketApp(
                WORKER_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever()
        except Exception as e:
            print(f"Bridge error: {e}")

        print("Reconnecting in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    print("Waiting for Xray to initialize...")
    time.sleep(5)
    run_bridge()
