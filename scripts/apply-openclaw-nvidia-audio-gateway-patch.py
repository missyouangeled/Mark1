#!/usr/bin/env python3
# 适用机器：公司（Linux）
# 系统 / OS：Linux
# 用途：给当前机器的 OpenClaw gateway 打上 NVIDIA 音频 HTTP 代理补丁。
from __future__ import annotations

from pathlib import Path
import sys

OPENCLAW_DIST = Path.home() / '.npm-global/lib/node_modules/openclaw/dist'

PROXY_MODULE_NAME = 'openai-audio-http-nvidia-bridge.js'
PROXY_MODULE_CONTENT = r'''import { a as sendMethodNotAllowed, i as sendJson } from "./http-common-uH2cJAb0.js";
import { l as resolveOpenAiCompatibleHttpOperatorScopes, n as authorizeScopedGatewayHttpRequestOrReply } from "./http-auth-utils-Dt0U5Xo7.js";
import { Buffer } from "node:buffer";
const DEFAULT_AUDIO_BRIDGE_BASE_URL = process.env.OPENCLAW_NVIDIA_AUDIO_BRIDGE_URL || "http://127.0.0.1:18890";
const DEFAULT_MAX_BODY_BYTES = 64 * 1024 * 1024;
async function readRawBodyOrError(req, res, maxBodyBytes) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buf.length;
    if (total > maxBodyBytes) {
      sendJson(res, 413, { error: { message: `Request body too large (max ${maxBodyBytes} bytes).`, type: "invalid_request_error" } });
      return null;
    }
    chunks.push(buf);
  }
  return Buffer.concat(chunks);
}
async function proxyOpenAiAudioRequest(req, res, opts) {
  if (new URL(req.url ?? "/", `http://${req.headers.host || "localhost"}`).pathname !== opts.pathname) return false;
  if (req.method !== "POST") {
    sendMethodNotAllowed(res);
    return true;
  }
  const authorized = await authorizeScopedGatewayHttpRequestOrReply({
    req,
    res,
    auth: opts.auth,
    trustedProxies: opts.trustedProxies,
    allowRealIpFallback: opts.allowRealIpFallback,
    rateLimiter: opts.rateLimiter,
    operatorMethod: "chat.send",
    resolveOperatorScopes: resolveOpenAiCompatibleHttpOperatorScopes
  });
  if (!authorized) return true;
  const rawBody = await readRawBodyOrError(req, res, opts.maxBodyBytes ?? DEFAULT_MAX_BODY_BYTES);
  if (rawBody === null) return true;
  const upstreamHeaders = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (key === "host" || key === "authorization" || key === "content-length" || key === "connection") continue;
    if (typeof value === "string") upstreamHeaders.set(key, value);
    else if (Array.isArray(value) && value.length > 0) upstreamHeaders.set(key, value.join(", "));
  }
  upstreamHeaders.set("x-openclaw-audio-bridge", "nvidia");
  let upstream;
  try {
    upstream = await fetch(`${(opts.bridgeBaseUrl || DEFAULT_AUDIO_BRIDGE_BASE_URL).replace(/\/$/, "")}${opts.pathname}`, {
      method: "POST",
      headers: upstreamHeaders,
      body: rawBody
    });
  } catch (error) {
    sendJson(res, 502, { error: { message: `Audio bridge unavailable: ${error instanceof Error ? error.message : String(error)}`, type: "api_error" } });
    return true;
  }
  const payload = Buffer.from(await upstream.arrayBuffer());
  res.statusCode = upstream.status;
  upstream.headers.forEach((value, key) => {
    if (key === "content-length" || key === "transfer-encoding" || key === "connection") return;
    res.setHeader(key, value);
  });
  res.setHeader("Content-Length", String(payload.length));
  res.end(payload);
  return true;
}
async function handleOpenAiSpeechHttpRequest(req, res, opts) {
  return proxyOpenAiAudioRequest(req, res, { ...opts, pathname: "/v1/audio/speech" });
}
async function handleOpenAiTranscriptionsHttpRequest(req, res, opts) {
  return proxyOpenAiAudioRequest(req, res, { ...opts, pathname: "/v1/audio/transcriptions" });
}
export { handleOpenAiSpeechHttpRequest, handleOpenAiTranscriptionsHttpRequest };
'''


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f'Patch anchor not found:\n{old}')
    if text.count(old) != 1:
        raise RuntimeError(f'Patch anchor not unique:\n{old}')
    return text.replace(old, new, 1)


def apply_patch() -> None:
    if not OPENCLAW_DIST.exists():
        raise RuntimeError(f'OpenClaw dist 目录不存在: {OPENCLAW_DIST}')
    server_impl_candidates = sorted(OPENCLAW_DIST.glob('server.impl-*.js'))
    if not server_impl_candidates:
        raise RuntimeError('未找到 server.impl-*.js')
    server_impl = server_impl_candidates[0]
    text = server_impl.read_text(encoding='utf-8')

    if 'let openAiAudioHttpModulePromise;' not in text:
        text = replace_once(
            text,
            'let modelsHttpModulePromise;\nlet openAiHttpModulePromise;',
            'let modelsHttpModulePromise;\nlet openAiAudioHttpModulePromise;\nlet openAiHttpModulePromise;'
        )

    if 'function getOpenAiAudioHttpModule()' not in text:
        text = replace_once(
            text,
            'function getModelsHttpModule() {\n\tmodelsHttpModulePromise ??= import("./models-http-CuMJicbz.js");\n\treturn modelsHttpModulePromise;\n}\nfunction getOpenAiHttpModule() {',
            'function getModelsHttpModule() {\n\tmodelsHttpModulePromise ??= import("./models-http-CuMJicbz.js");\n\treturn modelsHttpModulePromise;\n}\nfunction getOpenAiAudioHttpModule() {\n\topenAiAudioHttpModulePromise ??= import("./openai-audio-http-nvidia-bridge.js");\n\treturn openAiAudioHttpModulePromise;\n}\nfunction getOpenAiHttpModule() {'
        )

    if 'function isOpenAiSpeechPath(pathname)' not in text:
        text = replace_once(
            text,
            'function isEmbeddingsPath(pathname) {\n\treturn pathname === "/v1/embeddings";\n}\nfunction isOpenAiChatCompletionsPath(pathname) {',
            'function isEmbeddingsPath(pathname) {\n\treturn pathname === "/v1/embeddings";\n}\nfunction isOpenAiSpeechPath(pathname) {\n\treturn pathname === "/v1/audio/speech";\n}\nfunction isOpenAiTranscriptionsPath(pathname) {\n\treturn pathname === "/v1/audio/transcriptions";\n}\nfunction isOpenAiChatCompletionsPath(pathname) {'
        )

    if 'name: "openai-audio-speech"' not in text:
        text = replace_once(
            text,
            'if (openAiCompatEnabled && isEmbeddingsPath(scopedRequestPath)) requestStages.push({\n\t\t\t\tname: "embeddings",\n\t\t\t\trun: async () => (await getEmbeddingsHttpModule()).handleOpenAiEmbeddingsHttpRequest(req, res, {\n\t\t\t\t\tauth: resolvedAuth,\n\t\t\t\t\ttrustedProxies,\n\t\t\t\t\tallowRealIpFallback,\n\t\t\t\t\trateLimiter\n\t\t\t\t})\n\t\t\t});',
            'if (openAiCompatEnabled && isEmbeddingsPath(scopedRequestPath)) requestStages.push({\n\t\t\t\tname: "embeddings",\n\t\t\t\trun: async () => (await getEmbeddingsHttpModule()).handleOpenAiEmbeddingsHttpRequest(req, res, {\n\t\t\t\t\tauth: resolvedAuth,\n\t\t\t\t\ttrustedProxies,\n\t\t\t\t\tallowRealIpFallback,\n\t\t\t\t\trateLimiter\n\t\t\t\t})\n\t\t\t});\n\t\t\tif (openAiCompatEnabled && isOpenAiSpeechPath(scopedRequestPath)) requestStages.push({\n\t\t\t\tname: "openai-audio-speech",\n\t\t\t\trun: async () => (await getOpenAiAudioHttpModule()).handleOpenAiSpeechHttpRequest(req, res, {\n\t\t\t\t\tauth: resolvedAuth,\n\t\t\t\t\ttrustedProxies,\n\t\t\t\t\tallowRealIpFallback,\n\t\t\t\t\trateLimiter\n\t\t\t\t})\n\t\t\t});\n\t\t\tif (openAiCompatEnabled && isOpenAiTranscriptionsPath(scopedRequestPath)) requestStages.push({\n\t\t\t\tname: "openai-audio-transcriptions",\n\t\t\t\trun: async () => (await getOpenAiAudioHttpModule()).handleOpenAiTranscriptionsHttpRequest(req, res, {\n\t\t\t\t\tauth: resolvedAuth,\n\t\t\t\t\ttrustedProxies,\n\t\t\t\t\tallowRealIpFallback,\n\t\t\t\t\trateLimiter\n\t\t\t\t})\n\t\t\t});'
        )

    server_impl.write_text(text, encoding='utf-8')
    (OPENCLAW_DIST / PROXY_MODULE_NAME).write_text(PROXY_MODULE_CONTENT, encoding='utf-8')
    print(f'Patched {server_impl.name} and wrote {PROXY_MODULE_NAME}')


if __name__ == '__main__':
    try:
        apply_patch()
    except Exception as exc:  # noqa: BLE001
        print(f'[apply-openclaw-nvidia-audio-gateway-patch] {exc}', file=sys.stderr)
        sys.exit(1)
