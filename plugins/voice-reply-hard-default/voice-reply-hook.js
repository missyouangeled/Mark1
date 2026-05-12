// voice-reply-hook.js
// OpenClaw plugin prototype: capture the finalized assistant text, then
// optionally replace the outbound final reply with the ChatTTS delivery text.
//
// Important:
// - Not enabled by default. Safe to keep in workspace while iterating.
// - "主会话" ≡ "当前会话". Never inject `agent:main:main` or other session ids.
// - We intentionally do NOT use `before_agent_reply`: that hook receives the
//   cleaned inbound body before the LLM call, not the model's final reply text.
//
// Current prototype architecture:
//   before_agent_finalize(lastAssistantMessage)
//     -> stage final assistant text by runId
//   reply_dispatch(webchat/direct front-session default)
//     -> exec voice-reply-chunked-deliver.sh on the staged text
//     -> dispatcher.sendFinalReply({ text: agentReply })
//     -> fall back to the normal text reply on any failure

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const WORKSPACE_DIR = process.env["OPENCLAW_WORKSPACE_DIR"];
const DELIVER_SH =
  WORKSPACE_DIR
    ? resolve(WORKSPACE_DIR, "tools/voice-reply/voice-reply-chunked-deliver.sh")
    : null;
const STATE_DIR =
  WORKSPACE_DIR
    ? resolve(WORKSPACE_DIR, "tmp/voice-reply-hard-default-state")
    : null;
const DEFAULT_PRESET = process.env["OPENCLAW_VOICE_REPLY_PRESET"] || "default";

function ensureStateDir() {
  if (!STATE_DIR) {
    return false;
  }
  mkdirSync(STATE_DIR, { recursive: true });
  return true;
}

function shouldSkipText(text) {
  if (!text) {
    return true;
  }
  const trimmed = text.trim();
  return (
    trimmed.length < 3 ||
    trimmed === "NO_REPLY" ||
    trimmed.includes("[[audio_as_voice]]") ||
    trimmed.includes("MEDIA:")
  );
}

function statePathForRun(runId) {
  if (!STATE_DIR || !runId) {
    return null;
  }
  return resolve(STATE_DIR, `${runId}.json`);
}

function stageReply(runId, text) {
  if (!runId || !ensureStateDir()) {
    return;
  }
  const target = statePathForRun(runId);
  if (!target) {
    return;
  }
  writeFileSync(
    target,
    JSON.stringify({ text, savedAt: new Date().toISOString() }),
    "utf-8",
  );
}

function takeStagedReply(runId) {
  const target = statePathForRun(runId);
  if (!target || !existsSync(target)) {
    return null;
  }
  try {
    const parsed = JSON.parse(readFileSync(target, "utf-8"));
    return typeof parsed?.text === "string" ? parsed.text : null;
  } finally {
    rmSync(target, { force: true });
  }
}

function synthesizeAgentReply(text) {
  if (!DELIVER_SH) {
    return null;
  }
  const raw = execFileSync("bash", [DELIVER_SH, text, DEFAULT_PRESET], {
    encoding: "utf-8",
    timeout: 60_000,
    maxBuffer: 10 * 1024 * 1024,
    windowsHide: true,
  });
  const result = JSON.parse(raw);
  if (!result?.ok || typeof result?.agentReply !== "string" || !result.agentReply.trim()) {
    return null;
  }
  return result.agentReply;
}

function isWebchatDirectReply(event) {
  const ctx = event?.ctx ?? {};
  const surface = String(ctx.Surface || ctx.Provider || event.originatingChannel || "").trim().toLowerCase();
  const chatType = String(ctx.ChatType || "").trim().toLowerCase();
  return surface === "webchat" && chatType === "direct";
}

export default definePluginEntry({
  id: "voice-reply-hard-default",
  name: "Voice Reply Hard Default",
  description: "Prototype hook plugin for session-level hard-default voice replies",

  register(api) {
    api.on(
      "before_agent_finalize",
      async (event) => {
        const text = event.lastAssistantMessage?.trim();
        if (!event.runId || shouldSkipText(text)) {
          return;
        }
        stageReply(event.runId, text);
        return { action: "continue" };
      },
      {
        priority: 50,
        timeoutMs: 5_000,
      },
    );

    api.on(
      "reply_dispatch",
      async (event, ctx) => {
        if (!isWebchatDirectReply(event)) {
          return;
        }
        if (event.sendPolicy === "deny" || event.suppressUserDelivery) {
          return;
        }
        const text = takeStagedReply(event.runId);
        if (shouldSkipText(text)) {
          return;
        }

        let agentReply;
        try {
          agentReply = synthesizeAgentReply(text);
        } catch (error) {
          api.logger.warn("voice synthesis failed in reply_dispatch", {
            error: String(error),
            runId: event.runId,
          });
          return;
        }

        if (!agentReply) {
          return;
        }

        await ctx.onReplyStart?.();
        const queuedFinal = ctx.dispatcher.sendFinalReply({ text: agentReply });
        const counts = ctx.dispatcher.getQueuedCounts();
        ctx.recordProcessed("completed", { reason: "voice_reply_hard_default" });
        ctx.markIdle("message_completed");
        return {
          handled: true,
          queuedFinal,
          counts,
        };
      },
      {
        priority: 50,
        timeoutMs: 70_000,
      },
    );
  },
});
