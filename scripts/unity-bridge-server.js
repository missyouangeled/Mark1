#!/usr/bin/env node
/**
 * Unity Bridge — Standalone HTTP Server
 * Connects OpenClaw AI to Unity Editor without touching Gateway plugins.
 *
 * Start:  node scripts/unity-bridge-server.js [port] [token]
 * Stop:   kill <pid>  or  curl -X POST http://localhost:27182/bridge/stop
 */

const http = require("http");
const path = require("path");
const fs = require("fs");

// ── Config ──────────────────────────────────────────────
const PORT = parseInt(process.argv[2]) || 27182;
const TOKEN = process.argv[3] || process.env.UNITY_BRIDGE_TOKEN || "unity-bridge-local";

// ── Session Store ───────────────────────────────────────
const sessions = new Map();

function generateId() {
  return `u_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

function cleanupStale() {
  const now = Date.now();
  for (const [id, s] of sessions) {
    if (now - s.lastHeartbeat > 120000) sessions.delete(id);
  }
}
setInterval(cleanupStale, 30000);

// ── Helpers ─────────────────────────────────────────────
function readBody(req, maxBytes = 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let total = 0;
    req.on("data", (chunk) => {
      total += chunk.length;
      if (total > maxBytes) { req.destroy(); return reject(new Error("Payload too large")); }
      chunks.push(chunk);
    });
    req.on("end", () => {
      try {
        const raw = Buffer.concat(chunks).toString("utf8");
        resolve(raw.trim() ? JSON.parse(raw) : {});
      } catch (e) { reject(e); }
    });
    req.on("error", reject);
  });
}

function sendJson(res, status, data) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
  res.end(JSON.stringify(data));
}

function checkAuth(req, res) {
  const auth = req.headers["authorization"] || "";
  if (auth.startsWith("Bearer ") && auth.slice(7).trim() !== TOKEN) {
    sendJson(res, 401, { error: "Unauthorized — check API Token in Unity Plugin settings" });
    return false;
  }
  // If no Authorization header is sent, skip auth
  return true;
}

function log(...args) {
  console.log(`[${new Date().toISOString().slice(11, 19)}]`, ...args);
}

// ── HTTP Server ─────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  const pathname = url.pathname;

  // CORS preflight
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
    res.statusCode = 204;
    return res.end();
  }

  // ── Unity Plugin Endpoints ──────────────────────────
  if (pathname.startsWith("/unity/")) {
    const endpoint = pathname.replace("/unity/", "");

    try {
      switch (endpoint) {
        case "connect": {
          // Test: bridge is alive
          sendJson(res, 200, { bridge: "unity", status: "ok", version: "1.0.0" });
          return;
        }

        case "register": {
          if (!checkAuth(req, res)) return;
          if (req.method !== "POST") return sendJson(res, 405, { error: "POST required" });
          const body = await readBody(req);
          const sid = generateId();
          sessions.set(sid, {
            sessionId: sid,
            registeredAt: Date.now(),
            lastHeartbeat: Date.now(),
            projectName: body.project || "Unknown",
            unityVersion: body.version || "Unknown",
            platform: body.platform || "UnityEditor",
            toolCount: body.tools || 0,
            pendingCommands: [],
            results: new Map(),
          });
          log(`✅ Unity registered: ${body.project || "Unknown"} (v${body.version || "?"})`);
          sendJson(res, 200, { sessionId: sid, status: "connected" });
          return;
        }

        case "heartbeat": {
          if (!checkAuth(req, res)) return;
          if (req.method !== "POST") return sendJson(res, 405, { error: "POST required" });
          const body = await readBody(req);
          const s = sessions.get(body.sessionId);
          if (!s) return sendJson(res, 404, { error: "Session not found" });
          s.lastHeartbeat = Date.now();
          sendJson(res, 200, { ok: true });
          return;
        }

        case "poll": {
          if (!checkAuth(req, res)) return;
          const s = sessions.get(url.searchParams.get("sessionId") || "");
          if (!s) return sendJson(res, 404, { error: "Session not found" });
          s.lastHeartbeat = Date.now();
          if (s.pendingCommands.length > 0) {
            const cmd = s.pendingCommands.shift();
            sendJson(res, 200, cmd);
          } else {
            res.statusCode = 204;
            res.end();
          }
          return;
        }

        case "result": {
          if (!checkAuth(req, res)) return;
          if (req.method !== "POST") return sendJson(res, 405, { error: "POST required" });
          const body = await readBody(req);
          const s = sessions.get(body.sessionId);
          if (!s) return sendJson(res, 404, { error: "Session not found" });
          s.results.set(body.toolCallId, body.result);
          log(`📥 Result received for: ${body.toolCallId}`);
          sendJson(res, 200, { ok: true });
          return;
        }

        case "status": {
          if (!checkAuth(req, res)) return;
          const active = [...sessions.values()].map(s => ({
            sessionId: s.sessionId,
            project: s.projectName,
            version: s.unityVersion,
            platform: s.platform,
            connectedAt: new Date(s.registeredAt).toISOString(),
            lastSeen: new Date(s.lastHeartbeat).toISOString(),
            pendingCommands: s.pendingCommands.length,
          }));
          sendJson(res, 200, { enabled: true, sessions: active, sessionCount: active.length });
          return;
        }

        case "tool":
        case "tool-async": {
          // AI → Bridge: queue a tool command for Unity to poll
          if (!checkAuth(req, res)) return;
          if (req.method !== "POST") return sendJson(res, 405, { error: "POST required" });
          const body = await readBody(req);

          let s;
          if (body.sessionId) {
            s = sessions.get(body.sessionId);
          } else {
            // prefer the most recently registered session
            const entries = [...sessions.values()];
            s = entries.sort((a,b) => b.registeredAt - a.registeredAt)[0];
          }

          if (!s) {
            return sendJson(res, 404, {
              success: false,
              error: "No Unity session connected. Open Unity Editor with OpenClaw Plugin enabled.",
            });
          }

          const requestId = generateId();
          s.pendingCommands.push({
            toolCallId: requestId,
            tool: body.tool,
            arguments: body.arguments || {},
            createdAt: Date.now(),
          });
          log(`📤 Queued: ${body.tool} → ${s.projectName} (${requestId})`);

          // async mode: return immediately, result fetched later via poll
          if (endpoint === "tool-async") {
            return sendJson(res, 200, { success: true, toolCallId: requestId, status: "queued" });
          }

          // sync mode: wait for result (60s timeout)
          const start = Date.now();
          while (Date.now() - start < 60000) {
            if (s.results.has(requestId)) {
              const result = s.results.get(requestId);
              s.results.delete(requestId);
              log(`✅ Result: ${body.tool} (${requestId})`);
              return sendJson(res, 200, { success: true, result });
            }
            await new Promise(r => setTimeout(r, 100));
          }

          return sendJson(res, 408, {
            success: false,
            error: "Timeout — Unity did not respond within 60s. Check Unity Plugin settings.",
          });
        }

        default:
          return sendJson(res, 404, { error: `Unknown endpoint: /unity/${endpoint}` });
      }
    } catch (err) {
      log("❌ Error:", err.message);
      return sendJson(res, 500, { error: err.message });
    }
  }

  // ── Bridge Management Endpoints ─────────────────────
  if (pathname === "/bridge/stop") {
    if (!checkAuth(req, res)) return;
    sendJson(res, 200, { ok: true, message: "Bridge stopping..." });
    log("🛑 Bridge stopped by request");
    server.close(() => process.exit(0));
    return;
  }

  if (pathname === "/bridge/health") {
    return sendJson(res, 200, {
      bridge: "unity",
      status: "running",
      uptime: process.uptime(),
      sessions: sessions.size,
      port: PORT,
    });
  }

  // ── Fallback ──────────────────────────────────────────
  sendJson(res, 404, { error: "Not found", endpoints: ["/unity/*", "/bridge/health", "/bridge/stop"] });
});

// ── Start ───────────────────────────────────────────────
server.listen(PORT, "0.0.0.0", () => {
  log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  log("🎮 Unity Bridge Server");
  log(`   Port:  ${PORT}`);
  log(`   Token: ${TOKEN.slice(0, 8)}...`);
  log("   Unity → http://192.168.79.128:" + PORT + "/unity/connect");
  log("   API   → http://localhost:" + PORT + "/unity/tool");
  log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
});

process.on("SIGTERM", () => { log("🛑 Shutting down..."); server.close(() => process.exit(0)); });
process.on("SIGINT", () => { log("🛑 Shutting down..."); server.close(() => process.exit(0)); });
