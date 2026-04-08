import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';
import crypto from 'crypto';

const FORMAL_COOLDOWN_MINUTES = 12 * 60;
const INBOX_COOLDOWN_MINUTES = 3 * 60;
const MAX_EXCERPT_CHARS = 360;
const STATE_RETENTION_DAYS = 30;
const DEFAULT_FILES = {
  errors: '# Errors Log\n\nCommand failures, exceptions, and unexpected behaviors.\n\n---\n',
  inbox: '# Learning Inbox\n\nLow-confidence or ambiguous signals captured automatically for later review.\n\n---\n',
};

function cfgValue(ctx, key, fallback) {
  const config = ctx?.pluginConfig;
  if (!config || typeof config !== 'object') return fallback;
  const value = config[key];
  return value === undefined ? fallback : value;
}

function numberCfg(ctx, key, fallback) {
  const value = cfgValue(ctx, key, fallback);
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : fallback;
}

function booleanCfg(ctx, key, fallback) {
  const value = cfgValue(ctx, key, fallback);
  return typeof value === 'boolean' ? value : fallback;
}

function resolveWorkspaceDir(ctx, event) {
  const candidates = [
    ctx?.workspaceDir,
    ctx?.config?.workspaceDir,
    event?.workspaceDir,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim();
  }
  return path.join(os.homedir(), '.openclaw', 'workspace');
}

function learningsDir(workspaceDir) {
  return path.join(workspaceDir, '.learnings');
}

function normalizeText(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value.replace(/\r/g, '\n').replace(/\u0000/g, '').trim();
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function sanitizeExcerpt(value, maxChars) {
  const collapsed = normalizeText(value)
    .replace(/https?:\/\/\S+/gi, '[url]')
    .replace(/[A-Za-z0-9_\-]{24,}/g, '[redacted]')
    .replace(/\s+/g, ' ')
    .trim();
  if (!collapsed) return '';
  return collapsed.length > maxChars ? `${collapsed.slice(0, maxChars - 1)}…` : collapsed;
}

function flattenSignals(value, out = [], depth = 0) {
  if (depth > 4 || out.length >= 80 || value === null || value === undefined) return out;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    const text = normalizeText(value);
    if (text) out.push(text);
    return out;
  }
  if (Array.isArray(value)) {
    for (const item of value) flattenSignals(item, out, depth + 1);
    return out;
  }
  if (typeof value === 'object') {
    const preferred = ['error', 'message', 'reason', 'status', 'stderr', 'stdout', 'output', 'content', 'summary', 'detail', 'details', 'code', 'exitCode'];
    for (const key of preferred) {
      if (key in value) flattenSignals(value[key], out, depth + 1);
    }
    for (const [key, child] of Object.entries(value)) {
      if (preferred.includes(key)) continue;
      if (['result', 'meta', 'response', 'payload', 'toolResult', 'tool_result'].includes(key) || depth < 2) {
        flattenSignals(child, out, depth + 1);
      }
    }
  }
  return out;
}

function toSignalCorpus(event) {
  return flattenSignals(event).join('\n');
}

function extractExitCode(event) {
  const candidates = [
    event?.result?.exitCode,
    event?.result?.code,
    event?.meta?.exitCode,
    event?.meta?.code,
    event?.exitCode,
    event?.code,
  ];
  for (const value of candidates) {
    const n = typeof value === 'number' ? value : Number(value);
    if (Number.isFinite(n)) return n;
  }
  const corpus = toSignalCorpus(event);
  const match = corpus.match(/(?:exit(?:ed)?(?:\s+with)?\s+code|non[- ]zero exit(?: code)?)[^0-9]{0,8}(\d{1,3})/i);
  return match ? Number(match[1]) : null;
}

function getSessionKey(ctx, event) {
  return ctx?.sessionKey || event?.sessionKey || event?.sessionId || 'unknown';
}

function shouldSkip(ctx, event) {
  const skipSubagents = booleanCfg(ctx, 'skipSubagents', true);
  const sessionKey = getSessionKey(ctx, event);
  return skipSubagents && typeof sessionKey === 'string' && sessionKey.includes(':subagent:');
}

function classifyToolFailure(event, ctx) {
  const toolName = event?.toolName || event?.tool || 'unknown';
  const corpus = toSignalCorpus(event);
  const excerpt = sanitizeExcerpt(`[${toolName}] ${corpus}`, numberCfg(ctx, 'maxExcerptChars', MAX_EXCERPT_CHARS));
  if (!excerpt) return null;

  const exitCode = extractExitCode(event);
  const hasExplicitError = /(?:^|\b)(?:status[^a-z0-9]{0,8}error|error:|exception|traceback|fatal:|failed\b)/i.test(corpus);
  const approvalBlock = /approval(?:\s+was)?\s+(?:denied|rejected|required|blocked)|requireApproval|approval[- ]pending|approval[- ]block/i.test(corpus);
  const policyBlock = /policy(?:\s+block(?:ed)?)?|not allowed|denied by policy|security mode|host not allowed|approval-pending|elevated permissions required/i.test(corpus);
  const timeout = /timeout|timed out|etimedout|deadline exceeded/i.test(corpus);
  const connection = /fetch failed|connection refused|econn|enotfound|network error|socket hang up|bootstrap token invalid|unauthorized|remote url/i.test(corpus);
  const stillRunning = /command still running|process still running|use process \(/i.test(corpus);

  if (toolName === 'exec' && exitCode !== null && exitCode !== 0) {
    return {
      target: 'errors',
      title: 'tool-exec-nonzero-exit',
      summary: `Tool ${toolName} exited with non-zero status ${exitCode}.`,
      excerpt,
      area: 'infra',
      priority: 'high',
      reproducible: 'unknown',
    };
  }

  if (approvalBlock) {
    return {
      target: 'errors',
      title: 'tool-approval-blocked',
      summary: `Tool ${toolName} was blocked by an approval gate.`,
      excerpt,
      area: 'infra',
      priority: 'high',
      reproducible: 'sometimes',
    };
  }

  if (policyBlock) {
    return {
      target: 'errors',
      title: 'tool-policy-blocked',
      summary: `Tool ${toolName} was blocked by policy or runtime restrictions.`,
      excerpt,
      area: 'infra',
      priority: 'high',
      reproducible: 'sometimes',
    };
  }

  if (timeout) {
    return {
      target: 'errors',
      title: 'tool-timeout',
      summary: `Tool ${toolName} timed out.`,
      excerpt,
      area: 'infra',
      priority: 'high',
      reproducible: 'unknown',
    };
  }

  if (connection) {
    return {
      target: 'errors',
      title: 'tool-connection-failure',
      summary: `Tool ${toolName} failed because of a connection or remote access problem.`,
      excerpt,
      area: 'infra',
      priority: 'high',
      reproducible: 'unknown',
    };
  }

  if (hasExplicitError) {
    return {
      target: 'errors',
      title: 'tool-explicit-error',
      summary: `Tool ${toolName} returned an explicit error state.`,
      excerpt,
      area: 'infra',
      priority: 'high',
      reproducible: 'unknown',
    };
  }

  if (stillRunning) {
    return {
      target: 'inbox',
      title: 'tool-long-running-followup-needed',
      summary: `Tool ${toolName} reported a follow-up state rather than a clear failure.`,
      excerpt,
    };
  }

  return null;
}

async function ensureLearningFiles(workspaceDir) {
  const dir = learningsDir(workspaceDir);
  await fs.mkdir(dir, { recursive: true });
  for (const [file, content] of Object.entries({ ERRORS: DEFAULT_FILES.errors, INBOX: DEFAULT_FILES.inbox })) {
    const filePath = path.join(dir, `${file}.md`);
    try {
      await fs.access(filePath);
    } catch {
      await fs.writeFile(filePath, content, 'utf8');
    }
  }
}

async function loadState(workspaceDir) {
  const statePath = path.join(learningsDir(workspaceDir), '.hook-state.json');
  try {
    const parsed = JSON.parse(await fs.readFile(statePath, 'utf8'));
    return {
      statePath,
      state: {
        version: 1,
        records: parsed && typeof parsed.records === 'object' ? parsed.records : {},
      },
    };
  } catch {
    return { statePath, state: { version: 1, records: {} } };
  }
}

async function saveState(statePath, state) {
  await fs.writeFile(statePath, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
}

function pruneState(state, now) {
  const cutoff = now.getTime() - STATE_RETENTION_DAYS * 24 * 60 * 60 * 1000;
  const next = {};
  for (const [key, value] of Object.entries(state.records || {})) {
    const time = Date.parse(value);
    if (Number.isFinite(time) && time >= cutoff) next[key] = value;
  }
  state.records = next;
}

function localStamp(now) {
  return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
}

async function nextSequence(filePath, prefix, stamp) {
  try {
    const raw = await fs.readFile(filePath, 'utf8');
    const regex = new RegExp(`\\[${prefix}-${stamp}-(\\d{3})\\]`, 'g');
    let max = 0;
    for (const match of raw.matchAll(regex)) {
      const value = Number(match[1]);
      if (Number.isFinite(value) && value > max) max = value;
    }
    return String(max + 1).padStart(3, '0');
  } catch {
    return '001';
  }
}

function hashKey(parts) {
  return crypto.createHash('sha1').update(parts.join('||')).digest('hex');
}

async function appendFormalError(workspaceDir, payload, meta, now) {
  const filePath = path.join(learningsDir(workspaceDir), 'ERRORS.md');
  const stamp = localStamp(now);
  const seq = await nextSequence(filePath, 'ERR', stamp);
  const entry = `\n## [ERR-${stamp}-${seq}] ${payload.title}\n\n**Logged**: ${now.toISOString()}\n**Priority**: ${payload.priority || 'high'}\n**Status**: pending\n**Area**: ${payload.area || 'infra'}\n\n### Summary\n${payload.summary}\n\n### Error\n\`\`\`text\n${payload.excerpt}\n\`\`\`\n\n### Context\n- Hook source: plugin:after_tool_call\n- Tool: ${meta.toolName}\n- Session Key: ${meta.sessionKey}\n\n### Suggested Fix\nConfirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.\n\n### Metadata\n- Reproducible: ${payload.reproducible || 'unknown'}\n- Related Files: .learnings/ERRORS.md\n- See Also: openclaw-env/plugins/self-improvement-tool-errors\n\n---\n`;
  await fs.appendFile(filePath, entry, 'utf8');
}

async function appendInbox(workspaceDir, payload, meta, now) {
  const filePath = path.join(learningsDir(workspaceDir), 'INBOX.md');
  const entry = `\n## ${now.toISOString()} · ${payload.title}\n\n- Source: plugin:after_tool_call\n- Tool: ${meta.toolName}\n- Session Key: ${meta.sessionKey}\n- Summary: ${payload.summary}\n- Signal: ${payload.excerpt}\n- Suggested Action: Review manually before promoting to .learnings/ERRORS.md.\n\n---\n`;
  await fs.appendFile(filePath, entry, 'utf8');
}

async function persist(event, ctx) {
  if (shouldSkip(ctx, event)) return;
  const payload = classifyToolFailure(event, ctx);
  if (!payload) return;

  const workspaceDir = resolveWorkspaceDir(ctx, event);
  const now = new Date();
  const formalCooldown = numberCfg(ctx, 'formalCooldownMinutes', FORMAL_COOLDOWN_MINUTES);
  const inboxCooldown = numberCfg(ctx, 'inboxCooldownMinutes', INBOX_COOLDOWN_MINUTES);

  await ensureLearningFiles(workspaceDir);
  const { statePath, state } = await loadState(workspaceDir);
  pruneState(state, now);

  const toolName = event?.toolName || event?.tool || 'unknown';
  const sessionKey = getSessionKey(ctx, event);
  const dedupeKey = hashKey([payload.target, payload.title, toolName, payload.excerpt]);
  const cooldown = payload.target === 'inbox' ? inboxCooldown : formalCooldown;
  const previous = state.records[dedupeKey];
  const lastAt = previous ? Date.parse(previous) : NaN;
  if (Number.isFinite(lastAt) && now.getTime() - lastAt < cooldown * 60 * 1000) return;

  const meta = { toolName, sessionKey };
  if (payload.target === 'errors') await appendFormalError(workspaceDir, payload, meta, now);
  else await appendInbox(workspaceDir, payload, meta, now);

  state.records[dedupeKey] = now.toISOString();
  await saveState(statePath, state);
}

export default {
  id: 'self-improvement-tool-errors',
  name: 'Self-Improvement Tool Errors',
  description: 'Capture high-confidence tool failures into .learnings/ERRORS.md and ambiguous tool failure signals into .learnings/INBOX.md.',
  configSchema: {
    type: 'object',
    additionalProperties: false,
    properties: {
      enabled: { type: 'boolean' },
      skipSubagents: { type: 'boolean' },
      formalCooldownMinutes: { type: 'number', minimum: 1 },
      inboxCooldownMinutes: { type: 'number', minimum: 1 },
      maxExcerptChars: { type: 'number', minimum: 80, maximum: 1200 },
    },
  },
  register(api) {
    api.on('after_tool_call', async (event, ctx) => {
      await persist(event, ctx);
    });
  },
};
