/**
 * cloudflare_worker.js
 *
 * This worker acts as a relay between Google Apps Script and a GitHub Runner.
 */

let runnerWs = null;
const pendingRequests = new Map();

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Status check for human users
    if (url.pathname === "/status") {
      return new Response(JSON.stringify({
        connected: !!runnerWs,
        timestamp: new Date().toISOString()
      }), { headers: { "Content-Type": "application/json" } });
    }

    // Endpoint for the GitHub Runner to connect
    if (url.pathname === "/ws") {
      const upgradeHeader = request.headers.get("Upgrade");
      if (!upgradeHeader || upgradeHeader !== "websocket") {
        return new Response("Expected Upgrade: websocket", { status: 426 });
      }

      const [client, server] = new WebSocketPair();
      server.accept();

      runnerWs = server;

      server.addEventListener("message", (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "response" && pendingRequests.has(data.id)) {
            const { resolve } = pendingRequests.get(data.id);
            resolve(new Response(JSON.stringify(data.payload), {
              status: 200,
              headers: { "Content-Type": "application/json" }
            }));
            pendingRequests.delete(data.id);
          }
        } catch (e) {
          console.error("WS error:", e);
        }
      });

      server.addEventListener("close", () => {
        if (runnerWs === server) runnerWs = null;
      });

      return new Response(null, { status: 101, webSocket: client });
    }

    // Endpoint for Google Apps Script
    if (request.method === "POST") {
      if (!runnerWs) {
        return new Response(JSON.stringify({
          e: "Runner not connected to this specific edge instance.",
          note: "Workers are distributed. Re-run your GAS script or refresh."
        }), { status: 503, headers: { "Content-Type": "application/json" } });
      }

      const requestId = crypto.randomUUID();
      const body = await request.json();

      const responsePromise = new Promise((resolve) => {
        pendingRequests.set(requestId, { resolve });
      });

      try {
        runnerWs.send(JSON.stringify({ type: "request", id: requestId, payload: body }));
      } catch (e) {
        return new Response(JSON.stringify({ e: "Failed to send to runner" }), { status: 500 });
      }

      const timeout = setTimeout(() => {
        if (pendingRequests.has(requestId)) {
          pendingRequests.get(requestId).resolve(new Response(JSON.stringify({ e: "Runner timeout" }), { status: 504 }));
          pendingRequests.delete(requestId);
        }
      }, 25000);

      const response = await responsePromise;
      clearTimeout(timeout);
      return response;
    }

    return new Response(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Relay Active</title>
          <meta http-equiv="refresh" content="10">
        </head>
        <body style="font-family:sans-serif;max-width:600px;margin:40px auto;text-align:center">
          <h1>Relay Active</h1>
          <p>Status: <b style="color: ${runnerWs ? "green" : "red"}">${runnerWs ? "Connected" : "Disconnected"}</b></p>
          <p><i>Refreshing every 10 seconds...</i></p>
          <p><small>Note: Status is per-datacenter. If it shows disconnected but your runner is active, it might be connected to a different Cloudflare node.</small></p>
        </body>
      </html>
    `, { headers: { "Content-Type": "text/html" } });
  }
};
