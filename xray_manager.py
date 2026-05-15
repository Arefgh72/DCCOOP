import json
import os
import subprocess

def generate_xray_config(proxy_outbound):
    config = {
        "log": {
            "loglevel": "warning"
        },
        "inbounds": [
            {
                "port": 10808,
                "protocol": "socks",
                "settings": {
                    "auth": "noauth",
                    "udp": True
                },
                "tag": "socks-in"
            },
            {
                "port": 10809,
                "protocol": "http",
                "settings": {
                    "auth": "noauth",
                    "udp": True
                },
                "tag": "http-in"
            }
        ],
        "outbounds": [
            proxy_outbound,
            {
                "protocol": "freedom",
                "tag": "direct"
            }
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {
                    "type": "field",
                    "outboundTag": "proxy",
                    "network": "tcp,udp"
                }
            ]
        }
    }
    return config

def start_xray():
    if not os.path.exists("best_proxy.json"):
        print("No best_proxy.json found. Run proxy_tester.py first.")
        return None

    with open("best_proxy.json", "r") as f:
        proxy_outbound = json.load(f)

    config = generate_xray_config(proxy_outbound)
    with open("xray_config.json", "w") as f:
        json.dump(config, f, indent=2)

    print("Starting Xray...")
    # Assume xray is in the path or same directory
    process = subprocess.Popen(["xray", "-c", "xray_config.json"],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             text=True)
    return process

if __name__ == "__main__":
    process = start_xray()
    if process:
        try:
            for line in process.stdout:
                print(f"[Xray] {line.strip()}")
        except KeyboardInterrupt:
            process.terminate()
