# Errors Log

Command failures, exceptions, and unexpected behaviors.

---

## [ERR-20260403-001] ripgrep-not-installed

**Logged**: 2026-04-03T14:00:00+08:00
**Priority**: low
**Status**: resolved
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
- See Also: ERR-20260407-001

### Resolution
- **Resolved**: 2026-04-07T16:18:00+08:00
- **Notes**: Environment remains without `rg`, but the working default on this machine is now to use `grep -RIn` / `find` instead of treating `rg` as available.

---
## [ERR-20260407-001] grep-search-tooling

**Logged**: 2026-04-07T10:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: docs

### Summary
Attempted to use `rg` for workspace-wide text search, but the environment did not have ripgrep installed.

### Error
```
/bin/bash: line 1: rg: command not found
```

### Context
- Command/operation attempted: search for leftover English UI labels in `pulsenest-php`
- Environment details: OpenClaw workspace shell on Linux
- Follow-up: switched to system `grep` instead of assuming `rg` exists

### Suggested Fix
Default to `grep -RIn` unless ripgrep availability has been confirmed first.

### Metadata
- Reproducible: yes
- Related Files: pulsenest-php/
- See Also: ERR-20260403-001, ERR-20260407-002

### Resolution
- **Resolved**: 2026-04-07T16:18:00+08:00
- **Notes**: Closed as a working-practice fix rather than an environment change. Future searches on this machine should assume `grep` first, not `rg`.

---

## [ERR-20260407-002] grep-quoting

**Logged**: 2026-04-07T10:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: docs

### Summary
A complex `grep -RInE` command failed because shell quoting became unbalanced.

### Error
```
/bin/bash: -c: line 1: unexpected EOF while looking for matching `"'
```

### Context
- Command/operation attempted: one-shot regex sweep for leftover English labels
- Cause: mixed shell quoting in a long inline pattern
- Follow-up: simplify search commands or break them into smaller checks

### Suggested Fix
For long search patterns, avoid one giant inline regex; split checks or store the pattern in a safer quoted form.

### Metadata
- Reproducible: yes
- Related Files: pulsenest-php/
- See Also: ERR-20260407-001

### Resolution
- **Resolved**: 2026-04-07T16:18:00+08:00
- **Notes**: Subsequent searches were split into smaller `grep` checks and no longer relied on one giant quoted regex blob.

---
## [ERR-20260407-003] git-push-origin-master

**Logged**: 2026-04-07T10:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
Tried to push the latest `master` backup commit to GitHub, but SSH authentication for `origin` failed.

### Error
```
git@github.com: Permission denied (publickey).
fatal: Could not read from remote repository.

Please make sure you have the correct access rights
and the repository exists.
```

### Context
- Command/operation attempted: `git push origin master`
- Remote: `git@github.com:missyouangeled/test-git.git`
- Local commit was created successfully before push: `2c7face` (`backup(xingyun03): tighten final review surfaces`)
- Working tree for project files is committed; push is blocked only by SSH auth

### Suggested Fix
Check whether the current machine has the right GitHub SSH key loaded and authorized for `missyouangeled/test-git.git`, or switch `origin` to an HTTPS remote with available credentials.

### Metadata
- Reproducible: yes
- Related Files: .git/config
- See Also: ERR-20260407-001

### Resolution
- **Resolved**: 2026-04-07T16:18:00+08:00
- **Notes**: Fixed by routing GitHub traffic through `~/.ssh/id_ed25519_github_openclaw`, then making that the default `github.com` identity in `~/.ssh/config`. Subsequent pushes succeeded.

---
## [ERR-20260407-004] openclaw-2026-4-5-missing-carbon

**Logged**: 2026-04-07T16:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
OpenClaw upgraded from 2026.4.2 to 2026.4.5, but post-upgrade CLI commands failed because module `@buape/carbon` could not be resolved.

### Error
```
[openclaw] Failed to start CLI: Error: Cannot find module '@buape/carbon'
Require stack:
- /home/missyouangeled/.npm-global/lib/node_modules/openclaw/dist/ui-7MjYF8PY.js
```

### Context
- Upgrade path used: `openclaw update --yes --json`
- New package version on disk: `2026.4.5`
- Failure surfaced immediately when running `openclaw doctor --fix --non-interactive`
- Gateway service was still the pre-upgrade running instance at the time of failure

### Suggested Fix
Repair the package-manager install so bundled runtime dependencies are fully present again; if needed, rerun the package-manager install for the global `openclaw` package or reinstall the affected version cleanly.

### Metadata
- Reproducible: yes
- Related Files: ~/.npm-global/lib/node_modules/openclaw/
- See Also: ERR-20260407-003

### Resolution
- **Resolved**: 2026-04-07T16:18:00+08:00
- **Notes**: This was a transient mid-upgrade state while npm was still materializing the new dependency tree. After installation finished, OpenClaw 2026.4.5, doctor/fix, gateway restart, and post-restore checks all passed.

---
