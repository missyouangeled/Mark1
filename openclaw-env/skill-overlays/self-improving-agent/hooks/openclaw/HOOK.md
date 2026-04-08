---
name: self-improvement
description: "Keeps the bootstrap self-improvement reminder and proactively auto-routes high-confidence corrections, feature gaps, and failures into .learnings/ while sending low-confidence signals to INBOX."
metadata: {"openclaw":{"emoji":"🧠","events":["agent:bootstrap","message:preprocessed","message:sent"]}}
---

# Self-Improvement Hook

Keep the original bootstrap reminder, then use internal message hooks to capture only low-risk, high-confidence learning signals.

## What It Does

- Fires on `agent:bootstrap` and injects the existing reminder block
- Watches `message:preprocessed` for:
  - explicit user corrections → `.learnings/LEARNINGS.md`
  - explicit missing-capability requests → `.learnings/FEATURE_REQUESTS.md`
  - high-confidence user-reported failures → `.learnings/ERRORS.md`
- Watches `message:sent` for:
  - outbound delivery failures
  - assistant messages that clearly surface technical errors
- Routes weaker or ambiguous signals to `.learnings/INBOX.md` instead of formal logs
- Deduplicates repeated signals with a lightweight local state file: `.learnings/.hook-state.json`

## Risk Posture

- Favor false negatives over false positives
- Never auto-promote low-confidence signals into formal learnings
- Sanitize excerpts before writing them to disk
- Skip sub-agent sessions by default

## Optional Config

Put settings under `hooks.internal.entries.self-improvement`:

```json
{
  "hooks": {
    "internal": {
      "entries": {
        "self-improvement": {
          "enabled": true,
          "skipSubagents": true,
          "formalCooldownMinutes": 720,
          "inboxCooldownMinutes": 180,
          "maxExcerptChars": 280
        }
      }
    }
  }
}
```

## Enable

```bash
openclaw hooks enable self-improvement
```
