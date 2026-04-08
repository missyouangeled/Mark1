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

## [ERR-20260408-001] tool-explicit-error

**Logged**: 2026-04-08T03:14:39.501Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool process returned an explicit error state.

### Error
```text
[process] process poll faint-crustacean 10000 [redacted] [redacted]|[redacted]+I0xPdDzFuIt+[redacted]/KbnOgc+uFncRf9RRoFz/[redacted]/aLv3+8bM/7oM9ztf1+CgkyTzVk/[redacted]+sYuvDLsaCm5Aq9C1/8s23+rnLA6K7Qb+[redacted]/[redacted]+[redacted]== failed 0 451
```

### Context
- Hook source: plugin:after_tool_call
- Tool: process
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260408-002] tool-timeout

**Logged**: 2026-04-08T03:19:07.741Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool sessions_spawn timed out.

### Error
```text
[sessions_spawn] sessions_spawn 继续处理当前工作区中 QMD 接入 OpenClaw 的卡点，把它尽量推进到真正稳定可用状态。已知现状：1) `@tobilu/qmd` 已全局安装，`qmd --version` 为 2.1.0；2) `~/.openclaw/openclaw.json` 已配置 `memory.backend = "qmd"` 且 gateway 已重启；3) OpenClaw 日志里出现过 `qmd memory startup initialization armed for agent "main"`，说明已接入；4) 但 boot 阶段 `qmd embed` 在 120000ms 超时；5) `qmd status` 显示 node-llama-c…
```

### Context
- Hook source: plugin:after_tool_call
- Tool: sessions_spawn
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260408-003] tool-timeout

**Logged**: 2026-04-08T04:09:45.089Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool memory_search timed out.

### Error
```text
[memory_search] memory_search QMD 接入 OpenClaw 根因 Hugging Face unreachable embed timeout BM25 可用 5 [redacted] [redacted]|m+OTEQgvlOFEb+[redacted]/WUtJlGWk9/omuzL7pO1yucI1v9n0WX/KxsZcfHYPXniFlSPj+MkXJ4o/vqVsXVBthbop0/wsB948zSK5AjRYvsRt9P/[redacted]+DQ/[redacted]/[redacted]+[redacted]/TqMD0xjSJ4GuDWfRpaRCEK+[redacted]== 4067
```

### Context
- Hook source: plugin:after_tool_call
- Tool: memory_search
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260408-004] tool-approval-blocked

**Logged**: 2026-04-08T04:12:53.753Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool write was blocked by an approval gate.

### Error
```text
[write] write # 2026-04-08 - 将当前工作区里的 `self-improving-agent` 从“只在 `agent:bootstrap` 提醒”升级成更主动但保守的版本： - 保留原有 bootstrap reminder。 - 新增 OpenClaw internal hook 自动分流： - 用户明确纠正 → `.learnings/LEARNINGS.md` - 明显缺失能力诉求 → `.learnings/FEATURE_REQUESTS.md` - 高置信失败 / 报错 → `.learnings/ERRORS.md` - 低置信信号 → `.learnings/INBOX.md` - 新增去重状态文件设计：运行时写 `.learnings/.hook-state.js…
```

### Context
- Hook source: plugin:after_tool_call
- Tool: write
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: sometimes
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260408-005] tool-timeout

**Logged**: 2026-04-08T04:32:33.368Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec timed out.

### Error
```text
[exec] exec python3 - <<'PY' import urllib.request for url in [ '[url] '[url] '[url] ]: try: req=urllib.request.Request(url, method='HEAD') with urllib.request.urlopen(req, timeout=20) as r: print(url, r.status, r.getheader('content-length'), r.getheader('content-type')) except Exception as e: print(url, 'ERROR', e) PY /home/missyouangeled/.openclaw/workspa…
```

### Context
- Hook source: plugin:after_tool_call
- Tool: exec
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260408-006] tool-explicit-error

**Logged**: 2026-04-08T04:33:27.561Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec systemctl --user daemon-reload && systemctl --user restart openclaw-gateway.service && systemctl --user cat openclaw-gateway.service | sed -n '1,240p' /home/missyouangeled/.openclaw/workspace 1000 120 [redacted] [redacted]|[redacted]/6UmHuosmycrZ9dQgNvoH/z/bDuLb5kHR2XG+[redacted]+[redacted]+[redacted]/[redacted]+[redacted]+tmyAjhYBP8C18yQdci+[re…
```

### Context
- Hook source: plugin:after_tool_call
- Tool: exec
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260408-006] tool-timeout

**Logged**: 2026-04-08T04:33:27.600Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec timed out.

### Error
```text
[exec] exec HF_ENDPOINT=[url] QMD_LLAMA_GPU=false python3 - <<'PY' import urllib.request urls=[ '[url] '[url] ] for url in urls: try: req=urllib.request.Request(url, method='HEAD') with urllib.request.urlopen(req, timeout=20) as r: print(url, r.status, r.getheader('content-length')) except Exception as e: print(url, 'ERROR', e) PY /home/missyouangeled/.open…
```

### Context
- Hook source: plugin:after_tool_call
- Tool: exec
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260408-007] tool-explicit-error

**Logged**: 2026-04-08T04:34:29.143Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec systemctl --user daemon-reload && systemctl --user restart openclaw-gateway.service && sleep 2 && systemctl --user cat openclaw-gateway.service | sed -n '1,260p' && printf '\n---\n' && systemctl --user status openclaw-gateway.service --no-pager | sed -n '1,80p' /home/missyouangeled/.openclaw/workspace 1000 120 [redacted] [redacted]|DU9fWAm8Y57tk…
```

### Context
- Hook source: plugin:after_tool_call
- Tool: exec
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---
