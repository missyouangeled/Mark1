/**
 * Self-Improvement Hook for OpenClaw
 *
 * Keeps the original bootstrap reminder, then proactively captures only
 * high-confidence learnings from internal message hooks:
 * - explicit user corrections -> .learnings/LEARNINGS.md
 * - explicit missing-capability requests -> .learnings/FEATURE_REQUESTS.md
 * - high-confidence failures/errors -> .learnings/ERRORS.md
 *
 * Lower-confidence signals are routed to .learnings/INBOX.md instead of the
 * formal logs to avoid noise.
 */

const fs = require('fs/promises');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

const HOOK_KEY = 'self-improvement';
const FORMAL_COOLDOWN_MINUTES = 12 * 60;
const INBOX_COOLDOWN_MINUTES = 3 * 60;
const MAX_EXCERPT_CHARS = 280;
const STATE_RETENTION_DAYS = 30;

const REMINDER_CONTENT = `
## Self-Improvement Reminder

After completing tasks, evaluate if any learnings should be captured:

**Automatic routing already handles only high-confidence cases:**
- Explicit user correction → \`.learnings/LEARNINGS.md\`
- Clear missing-capability request → \`.learnings/FEATURE_REQUESTS.md\`
- High-confidence failure / error → \`.learnings/ERRORS.md\`
- Lower-confidence signal → \`.learnings/INBOX.md\`

**Still review manually when needed:**
- You discover your knowledge was wrong
- You find a better approach worth keeping
- A pattern should be promoted into \`SOUL.md\`, \`AGENTS.md\`, or \`TOOLS.md\`

Keep entries short, sanitized, and actionable.
`.trim();

const DEFAULT_FILES = {
  learnings: '# Learnings\n\nCorrections, insights, and knowledge gaps captured during development.\n\n---\n',
  errors: '# Errors Log\n\nCommand failures, exceptions, and unexpected behaviors.\n\n---\n',
  features: '# Feature Requests\n\nCapabilities requested by user that do not currently exist.\n\n---\n',
  inbox: '# Learning Inbox\n\nLow-confidence or ambiguous signals captured automatically for later review.\n\n---\n',
};

function getHookConfig(event) {
  const entries = event?.context?.cfg?.hooks?.internal?.entries;
  if (!entries || typeof entries !== 'object') {
    return {};
  }
  const cfg = entries[HOOK_KEY];
  return cfg && typeof cfg === 'object' ? cfg : {};
}

function getNumberConfig(value, fallback) {
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function getBooleanConfig(value, fallback) {
  return typeof value === 'boolean' ? value : fallback;
}

function shouldSkipSession(event) {
  const cfg = getHookConfig(event);
  const skipSubagents = getBooleanConfig(cfg.skipSubagents, true);
  return skipSubagents && typeof event?.sessionKey === 'string' && event.sessionKey.includes(':subagent:');
}

function resolveWorkspaceDir(event) {
  const explicit = event?.context?.workspaceDir;
  if (typeof explicit === 'string' && explicit.trim()) {
    return explicit.trim();
  }

  const cfgWorkspace = event?.context?.cfg?.agents?.defaults?.workspace;
  if (typeof cfgWorkspace === 'string' && cfgWorkspace.trim()) {
    return cfgWorkspace.trim();
  }

  const fallback = path.join(os.homedir(), '.openclaw', 'workspace');
  return fallback;
}

function learningsDir(workspaceDir) {
  return path.join(workspaceDir, '.learnings');
}

function normalizeText(value) {
  if (typeof value !== 'string') {
    return '';
  }
  return value.replace(/\r/g, '\n').replace(/\u0000/g, '').trim();
}

function sanitizeExcerpt(value, maxChars) {
  const collapsed = normalizeText(value)
    .replace(/https?:\/\/\S+/gi, '[url]')
    .replace(/[A-Za-z0-9_\-]{24,}/g, '[redacted]')
    .replace(/\s+/g, ' ')
    .trim();
  if (!collapsed) {
    return '';
  }
  return collapsed.length > maxChars ? `${collapsed.slice(0, maxChars - 1)}…` : collapsed;
}

function strongCorrection(text) {
  return [
    /(?:^|\b)(?:no[, ]+that'?s wrong|you(?:'| a)?re wrong|that'?s outdated|actually[, ]+it should be)\b/i,
    /(?:你错了|这是错的|这个不对|不是这样的|不是这个|应该是|我说的是|你理解错了|你搞错了)/,
    /不是.{0,40}而是/,
  ].some((pattern) => pattern.test(text));
}

function weakCorrection(text) {
  return [
    /(?:好像不对|有点不对|不太对|似乎不对)/,
    /(?:maybe that'?s wrong|not quite right|i think that'?s off)/i,
  ].some((pattern) => pattern.test(text));
}

function strongFeatureRequest(text) {
  return [
    /(?:希望你(?:能|可以)|希望以后可以|能不能(?:支持|加上|增加|提供)|为什么(?:还)?不能|缺少(?:这个)?功能)/,
    /(?:i wish you could|can you add|could you support|why can'?t you|missing feature|feature request)/i,
  ].some((pattern) => pattern.test(text));
}

function weakFeatureRequest(text) {
  return [
    /(?:能不能|可以不可以|要是能.*就好了|希望以后)/,
    /(?:can you also|is there a way to|would be nice if)/i,
  ].some((pattern) => pattern.test(text));
}

function strongError(text) {
  return [
    /(?:报错|出错|失败了|执行失败|运行失败|崩了|异常)/,
    /(?:error:|exception|traceback|permission denied|command not found|module not found|syntaxerror|typeerror|fatal:|non-zero exit code|exit code \d+)/i,
  ].some((pattern) => pattern.test(text));
}

function weakError(text) {
  return [
    /(?:好像挂了|似乎有问题|不工作了|没反应)/,
    /(?:something went wrong|seems broken|looks failed)/i,
  ].some((pattern) => pattern.test(text));
}

function classifyInbound(text) {
  const excerpt = sanitizeExcerpt(text, MAX_EXCERPT_CHARS);
  if (!excerpt) {
    return null;
  }

  if (strongCorrection(text)) {
    return {
      target: 'learnings',
      confidence: 'high',
      title: 'user-explicit-correction',
      summary: 'User explicitly corrected the assistant.',
      detailLabel: 'Correction Signal',
      excerpt,
      category: 'correction',
      area: 'docs',
      priority: 'high',
      source: 'user_feedback',
      tags: ['auto-captured', 'correction'],
    };
  }

  if (strongFeatureRequest(text)) {
    return {
      target: 'features',
      confidence: 'high',
      title: 'missing-capability-request',
      summary: 'User explicitly asked for a capability the assistant does not reliably have.',
      detailLabel: 'Requested Capability',
      excerpt,
      area: 'docs',
      priority: 'medium',
      complexity: 'medium',
      frequency: 'first_time',
    };
  }

  if (strongError(text)) {
    return {
      target: 'errors',
      confidence: 'high',
      title: 'user-reported-error',
      summary: 'User message strongly indicated a real failure or error state.',
      detailLabel: 'Observed Signal',
      excerpt,
      area: 'infra',
      priority: 'high',
      reproducible: 'unknown',
    };
  }

  if (weakCorrection(text) || weakFeatureRequest(text) || weakError(text)) {
    return {
      target: 'inbox',
      confidence: 'low',
      title: 'low-confidence-user-signal',
      summary: 'User message may contain a correction, feature gap, or failure signal but was not strong enough for formal logging.',
      detailLabel: 'Observed Signal',
      excerpt,
      tags: ['auto-captured', 'low-confidence'],
    };
  }

  return null;
}

function classifyOutbound(context) {
  const deliveryError = sanitizeExcerpt(context?.error || '', MAX_EXCERPT_CHARS);
  if (context && context.success === false && deliveryError) {
    return {
      target: 'errors',
      confidence: 'high',
      title: 'outbound-delivery-failure',
      summary: 'OpenClaw reported an outbound delivery failure.',
      detailLabel: 'Delivery Error',
      excerpt: deliveryError,
      area: 'infra',
      priority: 'high',
      reproducible: 'unknown',
    };
  }

  const content = normalizeText(context?.content || '');
  const excerpt = sanitizeExcerpt(content, MAX_EXCERPT_CHARS);
  if (!excerpt) {
    return null;
  }

  if (strongError(content) && /(报错|失败|error|exception|traceback|fatal|denied|not found|exit code)/i.test(content)) {
    return {
      target: 'errors',
      confidence: 'high',
      title: 'assistant-surfaced-error',
      summary: 'Assistant surfaced a high-confidence technical error in an outbound message.',
      detailLabel: 'Assistant Output',
      excerpt,
      area: 'infra',
      priority: 'medium',
      reproducible: 'unknown',
    };
  }

  if (weakError(content)) {
    return {
      target: 'inbox',
      confidence: 'low',
      title: 'low-confidence-outbound-error-signal',
      summary: 'Assistant output looked error-adjacent but was not strong enough for formal logging.',
      detailLabel: 'Assistant Output',
      excerpt,
      tags: ['auto-captured', 'low-confidence'],
    };
  }

  return null;
}

async function ensureLearningFiles(workspaceDir) {
  const dir = learningsDir(workspaceDir);
  await fs.mkdir(dir, { recursive: true });

  const files = [
    [path.join(dir, 'LEARNINGS.md'), DEFAULT_FILES.learnings],
    [path.join(dir, 'ERRORS.md'), DEFAULT_FILES.errors],
    [path.join(dir, 'FEATURE_REQUESTS.md'), DEFAULT_FILES.features],
    [path.join(dir, 'INBOX.md'), DEFAULT_FILES.inbox],
  ];

  for (const [filePath, content] of files) {
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
    const raw = await fs.readFile(statePath, 'utf8');
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') {
      throw new Error('invalid state');
    }
    const records = parsed.records && typeof parsed.records === 'object' ? parsed.records : {};
    return { statePath, state: { version: 1, records } };
  } catch {
    return { statePath, state: { version: 1, records: {} } };
  }
}

async function saveState(statePath, state) {
  await fs.writeFile(statePath, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
}

function hashKey(parts) {
  return crypto.createHash('sha1').update(parts.join('||')).digest('hex');
}

function shouldWriteRecord(state, key, cooldownMinutes, now) {
  const existing = state.records[key];
  if (!existing) {
    return true;
  }
  const last = Date.parse(existing);
  if (!Number.isFinite(last)) {
    return true;
  }
  return now.getTime() - last >= cooldownMinutes * 60 * 1000;
}

function pruneState(state, now) {
  const cutoff = now.getTime() - STATE_RETENTION_DAYS * 24 * 60 * 60 * 1000;
  const next = {};
  for (const [key, value] of Object.entries(state.records || {})) {
    const time = Date.parse(value);
    if (Number.isFinite(time) && time >= cutoff) {
      next[key] = value;
    }
  }
  state.records = next;
}

async function nextSequence(filePath, prefix, stamp) {
  try {
    const raw = await fs.readFile(filePath, 'utf8');
    const regex = new RegExp(`\\[${prefix}-${stamp}-(\\d{3})\\]`, 'g');
    let max = 0;
    for (const match of raw.matchAll(regex)) {
      const value = Number(match[1]);
      if (Number.isFinite(value) && value > max) {
        max = value;
      }
    }
    return String(max + 1).padStart(3, '0');
  } catch {
    return '001';
  }
}

function localStamp(now) {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}${month}${day}`;
}

async function appendFormalEntry(workspaceDir, event, payload, now) {
  const dir = learningsDir(workspaceDir);
  const stamp = localStamp(now);
  const iso = now.toISOString();

  if (payload.target === 'learnings') {
    const filePath = path.join(dir, 'LEARNINGS.md');
    const seq = await nextSequence(filePath, 'LRN', stamp);
    const entry = `\n## [LRN-${stamp}-${seq}] ${payload.category || 'insight'}\n\n**Logged**: ${iso}\n**Priority**: ${payload.priority || 'medium'}\n**Status**: pending\n**Area**: ${payload.area || 'docs'}\n\n### Summary\n${payload.summary}\n\n### Details\n${payload.detailLabel}: ${payload.excerpt}\n\n### Suggested Action\nReview the correction and update the working understanding or prompt guidance if it proves durable.\n\n### Metadata\n- Source: ${payload.source || 'conversation'}\n- Related Files: .learnings/LEARNINGS.md\n- Tags: ${(payload.tags || []).join(', ') || 'auto-captured'}\n- Session Key: ${event.sessionKey || 'unknown'}\n\n---\n`;
    await fs.appendFile(filePath, entry, 'utf8');
    return;
  }

  if (payload.target === 'features') {
    const filePath = path.join(dir, 'FEATURE_REQUESTS.md');
    const seq = await nextSequence(filePath, 'FEAT', stamp);
    const entry = `\n## [FEAT-${stamp}-${seq}] ${payload.title}\n\n**Logged**: ${iso}\n**Priority**: ${payload.priority || 'medium'}\n**Status**: pending\n**Area**: ${payload.area || 'docs'}\n\n### Requested Capability\n${payload.excerpt}\n\n### User Context\n${payload.summary}\n\n### Complexity Estimate\n${payload.complexity || 'medium'}\n\n### Suggested Implementation\nEvaluate whether this capability belongs in agent workflow, hook automation, or a dedicated skill update.\n\n### Metadata\n- Frequency: ${payload.frequency || 'first_time'}\n- Related Features: self-improvement\n- Session Key: ${event.sessionKey || 'unknown'}\n\n---\n`;
    await fs.appendFile(filePath, entry, 'utf8');
    return;
  }

  if (payload.target === 'errors') {
    const filePath = path.join(dir, 'ERRORS.md');
    const seq = await nextSequence(filePath, 'ERR', stamp);
    const entry = `\n## [ERR-${stamp}-${seq}] ${payload.title}\n\n**Logged**: ${iso}\n**Priority**: ${payload.priority || 'high'}\n**Status**: pending\n**Area**: ${payload.area || 'infra'}\n\n### Summary\n${payload.summary}\n\n### Error\n\`\`\`text\n${payload.excerpt}\n\`\`\`\n\n### Context\n- Hook source: ${event.type}:${event.action}\n- Session Key: ${event.sessionKey || 'unknown'}\n- Suggested confidence: ${payload.confidence}\n\n### Suggested Fix\nConfirm the failure is real and recurring, then either resolve it or downgrade it to inbox if it was a one-off false positive.\n\n### Metadata\n- Reproducible: ${payload.reproducible || 'unknown'}\n- Related Files: .learnings/ERRORS.md\n- See Also: none\n\n---\n`;
    await fs.appendFile(filePath, entry, 'utf8');
  }
}

async function appendInboxEntry(workspaceDir, event, payload, now) {
  const filePath = path.join(learningsDir(workspaceDir), 'INBOX.md');
  const iso = now.toISOString();
  const entry = `\n## ${iso} · ${payload.title}\n\n- Source: ${event.type}:${event.action}\n- Session Key: ${event.sessionKey || 'unknown'}\n- Summary: ${payload.summary}\n- Signal: ${payload.excerpt}\n- Suggested Action: Review manually before promoting to a formal learning file.\n\n---\n`;
  await fs.appendFile(filePath, entry, 'utf8');
}

async function persistClassification(event, payload) {
  const workspaceDir = resolveWorkspaceDir(event);
  const now = new Date();
  const cfg = getHookConfig(event);
  const formalCooldown = getNumberConfig(cfg.formalCooldownMinutes, FORMAL_COOLDOWN_MINUTES);
  const inboxCooldown = getNumberConfig(cfg.inboxCooldownMinutes, INBOX_COOLDOWN_MINUTES);
  const excerptChars = getNumberConfig(cfg.maxExcerptChars, MAX_EXCERPT_CHARS);

  payload.excerpt = sanitizeExcerpt(payload.excerpt, excerptChars);
  if (!payload.excerpt) {
    return;
  }

  await ensureLearningFiles(workspaceDir);
  const { statePath, state } = await loadState(workspaceDir);
  pruneState(state, now);

  const dedupeKey = hashKey([
    payload.target,
    payload.title,
    payload.excerpt,
    event.type || 'unknown',
    event.action || 'unknown',
    event.sessionKey || 'unknown',
  ]);
  const cooldown = payload.target === 'inbox' ? inboxCooldown : formalCooldown;
  if (!shouldWriteRecord(state, dedupeKey, cooldown, now)) {
    return;
  }

  if (payload.target === 'inbox') {
    await appendInboxEntry(workspaceDir, event, payload, now);
  } else {
    await appendFormalEntry(workspaceDir, event, payload, now);
  }

  state.records[dedupeKey] = now.toISOString();
  await saveState(statePath, state);
}

async function handleBootstrap(event) {
  if (!event.context || typeof event.context !== 'object') {
    return;
  }
  if (Array.isArray(event.context.bootstrapFiles)) {
    event.context.bootstrapFiles.push({
      path: 'SELF_IMPROVEMENT_REMINDER.md',
      content: REMINDER_CONTENT,
      virtual: true,
    });
  }
}

async function handlePreprocessed(event) {
  const text = normalizeText(
    event?.context?.bodyForAgent || event?.context?.body || event?.context?.content || event?.context?.transcript || ''
  );
  if (!text) {
    return;
  }
  const payload = classifyInbound(text);
  if (payload) {
    await persistClassification(event, payload);
  }
}

async function handleSent(event) {
  const payload = classifyOutbound(event?.context || {});
  if (payload) {
    await persistClassification(event, payload);
  }
}

const handler = async (event) => {
  try {
    if (!event || typeof event !== 'object') {
      return;
    }

    if (shouldSkipSession(event)) {
      return;
    }

    if (event.type === 'agent' && event.action === 'bootstrap') {
      await handleBootstrap(event);
      return;
    }

    if (event.type === 'message' && event.action === 'preprocessed') {
      await handlePreprocessed(event);
      return;
    }

    if (event.type === 'message' && event.action === 'sent') {
      await handleSent(event);
    }
  } catch (error) {
    console.warn('[self-improvement hook] failed:', error instanceof Error ? error.message : String(error));
  }
};

module.exports = handler;
module.exports.default = handler;
