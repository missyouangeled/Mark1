# OpenClaw Integration

Complete setup and usage guide for integrating the self-improvement skill with OpenClaw.

## Overview

OpenClaw uses workspace-based prompt injection combined with event-driven hooks. Context is injected from workspace files at session start, and hooks can trigger on lifecycle events.

## Workspace Structure

```
~/.openclaw/                      
├── workspace/                   # Working directory
│   ├── AGENTS.md               # Multi-agent coordination patterns
│   ├── SOUL.md                 # Behavioral guidelines and personality
│   ├── TOOLS.md                # Tool capabilities and gotchas
│   ├── MEMORY.md               # Long-term memory (main session only)
│   └── memory/                 # Daily memory files
│       └── YYYY-MM-DD.md
├── skills/                      # Installed skills
│   └── <skill-name>/
│       └── SKILL.md
└── hooks/                       # Custom hooks
    └── <hook-name>/
        ├── HOOK.md
        └── handler.ts
```

## Quick Setup

### 1. Install the Skill

```bash
clawdhub install self-improving-agent
```

Or copy manually:

```bash
cp -r self-improving-agent ~/.openclaw/skills/
```

### 2. Install the Hook (Optional)

Copy the hook to OpenClaw's hooks directory:

```bash
cp -r hooks/openclaw ~/.openclaw/hooks/self-improvement
```

Enable the hook:

```bash
openclaw hooks enable self-improvement
```

### 3. Create Learning Files

Create the `.learnings/` directory in your workspace:

```bash
mkdir -p ~/.openclaw/workspace/.learnings
```

Or in the skill directory:

```bash
mkdir -p ~/.openclaw/skills/self-improving-agent/.learnings
```

## Injected Prompt Files

### AGENTS.md

Purpose: Multi-agent workflows and delegation patterns.

```markdown
# Agent Coordination

## Delegation Rules
- Use explore agent for open-ended codebase questions
- Spawn sub-agents for long-running tasks
- Use sessions_send for cross-session communication

## Session Handoff
When delegating to another session:
1. Provide full context in the handoff message
2. Include relevant file paths
3. Specify expected output format
```

### SOUL.md

Purpose: Behavioral guidelines and communication style.

```markdown
# Behavioral Guidelines

## Communication Style
- Be direct and concise
- Avoid unnecessary caveats and disclaimers
- Use technical language appropriate to context

## Error Handling
- Admit mistakes promptly
- Provide corrected information immediately
- Log significant errors to learnings
```

### TOOLS.md

Purpose: Tool capabilities, integration gotchas, local configuration.

```markdown
# Tool Knowledge

## Self-Improvement Skill
Log learnings to `.learnings/` for continuous improvement.

## Local Tools
- Document tool-specific gotchas here
- Note authentication requirements
- Track integration quirks
```

## Learning Workflow

### Capturing Learnings

1. **In-session**: Log to `.learnings/` as usual
2. **Cross-session**: Promote to workspace files

### Promotion Decision Tree

```
Is the learning project-specific?
├── Yes → Keep in .learnings/
└── No → Is it behavioral/style-related?
    ├── Yes → Promote to SOUL.md
    └── No → Is it tool-related?
        ├── Yes → Promote to TOOLS.md
        └── No → Promote to AGENTS.md (workflow)
```

### Promotion Format Examples

**From learning:**
> Git push to GitHub fails without auth configured - triggers desktop prompt

**To TOOLS.md:**
```markdown
## Git
- Don't push without confirming auth is configured
- Use `gh auth status` to check GitHub CLI auth
```

## Inter-Agent Communication

OpenClaw provides tools for cross-session communication:

Use these only when cross-session sharing is explicitly needed and the environment is trusted. Prefer short sanitized summaries over raw transcripts, command output, or secret-bearing content.

### sessions_list

View active and recent sessions:
```
sessions_list(activeMinutes=30, messageLimit=3)
```

### sessions_history

Read transcript from another session:
```
sessions_history(sessionKey="session-id", limit=50)
```

Only read another session's transcript when the user explicitly wants shared context or continuation across sessions.

### sessions_send

Send message to another session:
```
sessions_send(sessionKey="session-id", message="Learning: API requires X-Custom-Header")
```

Prefer sending a concise learning summary plus relevant paths rather than forwarding raw transcript content.

### sessions_spawn

Spawn a background sub-agent:
```
sessions_spawn(task="Research X and report back", label="research")
```

## Available Hook Events

OpenClaw internal hooks expose a documented low-level event model that is enough for conservative self-improvement automation without reaching into tool internals.

| Event | When It Fires | How this skill uses it |
|-------|---------------|------------------------|
| `agent:bootstrap` | Before workspace files inject | Keep the original reminder |
| `message:preprocessed` | After media/link understanding | Detect explicit corrections, missing-capability asks, and strong user-reported errors |
| `message:sent` | After outbound delivery | Detect delivery failures and clearly surfaced technical errors |
| `command:new` | When `/new` command issued | Available if you want review-time extensions later |
| `command:reset` | When `/reset` command issued | Available if you want review-time extensions later |
| `command:stop` | When `/stop` command issued | Available for future workflows |
| `gateway:startup` | When gateway starts | Not required for this skill |

## Detection Triggers

### Standard Triggers
- User corrections ("No, that's wrong...")
- Command failures (non-zero exit codes)
- API errors
- Knowledge gaps

### OpenClaw-Specific Triggers

| Trigger | Action |
|---------|--------|
| Explicit user correction in `message:preprocessed` | Auto-log to `.learnings/LEARNINGS.md` |
| Explicit missing-capability request in `message:preprocessed` | Auto-log to `.learnings/FEATURE_REQUESTS.md` |
| High-confidence failure signal in `message:preprocessed` or `message:sent` | Auto-log to `.learnings/ERRORS.md` |
| Ambiguous / weak signal | Auto-log to `.learnings/INBOX.md` only |
| Tool call error | Prefer plugin hooks or manual logging if you need raw tool-level context |
| Session handoff confusion | Log to AGENTS.md with delegation pattern |
| Model behavior surprise | Log to SOUL.md with expected vs actual |
| Skill issue | Log to .learnings/ or report upstream |

## Verification

Check hook is registered:

```bash
openclaw hooks list
```

Check skill is loaded:

```bash
openclaw status
```

## Troubleshooting

### Hook not firing

1. Ensure hooks enabled in config
2. Restart gateway after config changes
3. Check gateway logs for errors
4. Confirm the event type matches the documented internal hook model (`agent:bootstrap`, `message:preprocessed`, `message:sent`)
5. Remember the current design intentionally skips sub-agent sessions by default

### Learnings not persisting

1. Verify `.learnings/` directory exists
2. Check file permissions
3. Ensure workspace path is configured correctly
4. Check whether the signal was intentionally downgraded into `.learnings/INBOX.md`
5. Check `.learnings/.hook-state.json` in case a recent duplicate was suppressed by cooldown

### Skill not loading

1. Check skill is in skills directory
2. Verify SKILL.md has correct frontmatter
3. Run `openclaw status` to see loaded skills
