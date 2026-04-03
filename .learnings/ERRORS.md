# Errors Log

Command failures, exceptions, and unexpected behaviors.

---

## [ERR-20260403-001] ripgrep-not-installed

**Logged**: 2026-04-03T14:00:00+08:00
**Priority**: low
**Status**: pending
**Area**: infra

### Summary
Tried to use `rg` for fast CSS/PHP pattern search in the workspace, but ripgrep is not installed in this runtime.

### Error
```text
/bin/bash: line 1: rg: command not found
```

### Context
- Command attempted: `rg -n "backdrop-filter|filter: blur|background-attachment: fixed|box-shadow|transition: all|will-change|transform: translateZ|animation:|position: sticky|blur\(|drop-shadow|radial-gradient|linear-gradient|mix-blend-mode" pulsenest-php -g '!vendor'`
- Fallback used: `find + grep`
- Impact: low, but slows down targeted perf-audit work in larger CSS/PHP files.

### Suggested Fix
Install ripgrep in the environment or remember to default to `grep`/`find` on this machine.

### Metadata
- Reproducible: yes
- Related Files: pulsenest-php/style.css

---
