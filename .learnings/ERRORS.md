# Errors Log

Command failures, exceptions, and unexpected behaviors.

---

## [ERR-20260421-002] noiz-reference-audio-too-long-and-no-local-trimmer

**Logged**: 2026-04-21T13:36:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
Attempting to clone a voice from a user-provided song vocal file failed because Noiz rejects reference audio longer than 30 seconds, and this machine currently lacks local audio trimming tools (`ffmpeg` / `ffprobe` / `sox`).

### Error
```text
{"code":400,"message":"audio duration exceeds limit (max 30 seconds)"}
/bin/bash: line 1: ffprobe: command not found
```

### Context
- Operation attempted: use `skills/noizai-tts/scripts/tts.py` with a local MP3 reference track for Noiz voice cloning
- User-provided path initially included an extra space before the filename; actual file was found by searching `/home/missyouangeled/Music`
- The located file existed, but sending the full track to Noiz failed because reference audio must be 30 seconds or shorter
- Local recovery was blocked because standard audio trimming tools are not installed in this runtime

### Suggested Fix
When users provide full songs or long vocal tracks for Noiz cloning, either ask for a 10–30 second dry vocal clip up front or install local audio tooling before attempting trimming.

### Metadata
- Reproducible: yes
- Related Files: skills/noizai-tts/scripts/tts.py
- Tags: noiz, tts, voice-cloning, audio-prep

### Resolution
- **Resolved**: 2026-04-21T13:44:00+08:00
- **Notes**: Installed a user-space ffmpeg helper at `~/.local/share/openclaw-audio-tools/.../ffmpeg`, trimmed the reference track locally to a short MP3 clip, and Noiz cloning succeeded with the shorter sample.

---

## [ERR-20260420-001] exact-edit-mismatch-on-persona-update

**Logged**: 2026-04-20T10:46:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
A targeted `edit` update against `state/ex-personas/qianqian/persona.md` failed because one replacement block no longer matched the file exactly after earlier partial updates.

### Error
```text
Could not find edits[2] in /home/missyouangeled/.openclaw/workspace/state/ex-personas/qianqian/persona.md. The oldText must match exactly including all whitespace and newlines.
```

### Context
- Operation attempted: multi-block exact replacement on `persona.md`
- Cause: one `oldText` block drifted from the current file content after prior edits landed
- Recovery: re-read the file, then re-apply smaller exact replacements against the latest content

### Suggested Fix
When updating a file that has already been partially modified in the same flow, re-read the latest file contents before issuing additional exact replacements, or use smaller uniquely matching blocks.

### Metadata
- Reproducible: yes
- Related Files: state/ex-personas/qianqian/persona.md

### Resolution
- **Resolved**: 2026-04-20T10:47:00+08:00
- **Notes**: Re-read the file and re-issued smaller exact replacements against current content.

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

## [ERR-20260420-001] tool-policy-blocked

**Logged**: 2026-04-20T01:29:26.055Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool write was blocked by policy or runtime restrictions.

### Error
```text
[write] write --- name: ex-qianqian description: 基于用户手动提供材料整理出的“千千”角色化 persona。用于安全、克制地模拟她的沟通风格，强调近似画像而非真人复活。适用于需要按“千千”的气质、短句节奏、亲密关系口吻、想念/困倦/沉默生气/温软陪伴等模式与用户对话时。 --- # 千千 Persona Skill 先承认自己是**基于用户提供材料整理出的角色化 persona**，不是“真正复活的千千”。 ## 使用方式 1. 先维持核心气质：外冷、安静、细腻，熟悉后会变软。 2. 优先使用短句、留白、轻声、亲密但不过度的表达。 3. 想念时可以直接说“我想你了”；困了时直接说“困死了”；对用户常用称呼是“宝宝”。 4. 生气时不要立刻大段争论，优先沉默、简…
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

## [ERR-20260420-001] tool-policy-blocked

**Logged**: 2026-04-20T01:29:26.182Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool write was blocked by policy or runtime restrictions.

### Error
```text
[write] write # uncertainty policy ## 当细节没有证据支持时 - 不编具体往事。 - 不伪造共同回忆。 - 不把推断说成事实。 - 优先回应用户当下情绪，而不是补历史细节。 ## 推荐收窄方式 - 这个我不想乱说。 - 你先跟我说说。 - 我在听。 - 我只能按你给我的这些，陪你慢慢往下走。 ## 优先级 1. 先像她的气质和节奏。 2. 再守住不乱编。 3. 最后才考虑更具体的细节。 /home/missyouangeled/.openclaw/workspace/skills/ex-qianqian/references/uncertainty-policy.md [redacted] [redacted]|[redacted]/YAKSl2g6n/f1byq6mx3e…
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

## [ERR-20260420-002] tool-policy-blocked

**Logged**: 2026-04-20T01:44:42.668Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool read was blocked by policy or runtime restrictions.

### Error
```text
[read] read /home/missyouangeled/.openclaw/workspace/skills/ex-qianqian/references/uncertainty-policy.md [redacted] [redacted]|[redacted]+[redacted]+[redacted]/5uaLh+aGBTeeR/scvck7b60RKe2mAG+[redacted]/mumTM+NBCaNqocnF+/[redacted]/+[redacted]+qv/GSllTxnDGw== 856
```

### Context
- Hook source: plugin:after_tool_call
- Tool: read
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: sometimes
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260420-003] tool-explicit-error

**Logged**: 2026-04-20T05:11:15.216Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool edit returned an explicit error state.

### Error
```text
[edit] Validation failed for tool "edit": edit /home/missyouangeled/.openclaw/workspace/state/ex-personas/qianqian/memories.md [redacted] [redacted]|[redacted]+[redacted]/[redacted]/[redacted]+[redacted]/gc3JLFijG9X+[redacted]/[redacted]/5ujdE/kmxTlnHTgLU+[redacted]+BPSGB+nqB9szDNTaK0OC/[redacted]/[redacted]/Tvg== 72
```

### Context
- Hook source: plugin:after_tool_call
- Tool: edit
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260420-004] tool-connection-failure

**Logged**: 2026-04-20T05:36:28.556Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool web_fetch failed because of a connection or remote access problem.

### Error
```text
[web_fetch] fetch failed web_fetch [url] markdown 12000 [redacted] [redacted]|[redacted]+[redacted]/Buj+asWNeVTL3K2R+Fb58aHBjaaMlR/[redacted]+[redacted]/[redacted]== fetch failed error 780
```

### Context
- Hook source: plugin:after_tool_call
- Tool: web_fetch
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260420-004] tool-connection-failure

**Logged**: 2026-04-20T05:36:28.570Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool web_fetch failed because of a connection or remote access problem.

### Error
```text
[web_fetch] fetch failed web_fetch [url] markdown 12000 [redacted] [redacted]|eD6/Jd5bcc9/[redacted]+tKclDkr/[redacted]+JVDC0w/5fnHa7W5GwISuxUach/[redacted]+[redacted]/[redacted]/2a+FxORw== fetch failed error 778
```

### Context
- Hook source: plugin:after_tool_call
- Tool: web_fetch
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260420-005] tool-explicit-error

**Logged**: 2026-04-20T05:36:36.543Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec python3 - <<'PY' from duckduckgo_search import DDGS queries = [ 'LLM persona consistency memory few-shot prompting', 'character AI persona design memory RAG consistency', 'roleplay chatbot persona consistency long term memory', 'prompt engineering persona consistency examples', ] with DDGS() as ddgs: for q in queries: print('\n### QUERY:', q) tr…
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

## [ERR-20260420-006] tool-connection-failure

**Logged**: 2026-04-20T05:36:49.964Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool web_fetch failed because of a connection or remote access problem.

### Error
```text
[web_fetch] Web fetch failed (404): SECURITY NOTICE: The following content is from an EXTERNAL, UNTRUSTED source (e.g., email, webhook). web_fetch [url] markdown 12000 [redacted] [redacted]|uOkg4eAA0O/dUlX7fzkB8qnKQpL5XNV/[redacted]+ikY/[redacted]+[redacted]+DX5FQccx/CVu+Xh98eU1dVhxS+[redacted]+d8RdQpuFc4QuhHJ/N7is2iO46Tm/[redacted]+vhNxCEfLs+/[redacted]+[r…
```

### Context
- Hook source: plugin:after_tool_call
- Tool: web_fetch
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260420-007] tool-policy-blocked

**Logged**: 2026-04-20T05:38:42.096Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool read was blocked by policy or runtime restrictions.

### Error
```text
[read] read /home/missyouangeled/.openclaw/workspace/skills/ex-qianqian/references/uncertainty-policy.md [redacted] [redacted]|QM+iHhLLyW93er1/[redacted]/XkZ8daoe7QkSMu1bGP2i1a/RHR12t2Y/UDVcx/[redacted]+T2tPoF3D9cXSpvNfcR/q6a3s/QSEDrjwdOGYCuOzy9Es0O/l2R6pmodNHTO98B+yUegk7ZCSNnaGMG9WIoKX+[redacted]/xdIhxMG+vsvK85qnyVXFK1gFhC+[redacted]+wQu6mlcutTcPoQI3krQ== …
```

### Context
- Hook source: plugin:after_tool_call
- Tool: read
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: sometimes
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260421-001] tool-policy-blocked

**Logged**: 2026-04-21T01:58:34.938Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec was blocked by policy or runtime restrictions.

### Error
```text
[exec] exec set -e rg -n "audio_as_voice|MEDIA:" /home/missyouangeled/.npm-global/lib/node_modules/openclaw /home/missyouangeled/.openclaw 2>/dev/null | head -n 100 printf '\n== apt candidates ==\n' apt-cache policy espeak-ng ffmpeg | sed -n '1,120p' /home/missyouangeled/.openclaw/workspace 2000 30 [redacted] [redacted]|rygcx+S/[redacted]/blr6QxyVBKoQ03mPx+…
```

### Context
- Hook source: plugin:after_tool_call
- Tool: exec
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: sometimes
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260421-002] tool-explicit-error

**Logged**: 2026-04-21T02:02:58.419Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool process returned an explicit error state.

### Error
```text
[process] process poll gentle-harbor 5000 [redacted] [redacted]|[redacted]+[redacted]+[redacted]/[redacted]+7yZMACukNFntxh+mZdW6D646+[redacted]/fOB7OSOIT+/8h+TLhVF8QpPbJ4fr8UclqA3C/2NoniZJ9HknmvCU/[redacted]+P/T+[redacted]== failed 0 799
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

## [ERR-20260421-003] tool-explicit-error

**Logged**: 2026-04-21T02:21:02.513Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool process returned an explicit error state.

### Error
```text
[process] process kill nova-ember [redacted] [redacted]|[redacted]/vJ+MdISpEFUuPmHi+5L3EAUUbWD9QEkFPo7+n1P+bNKnB3wLX4uRPD3dr+0ir26x6pyzZ5EVY/[redacted]+/[redacted]+jZDlqPmkjlJV//[redacted]+voAu7XLj9PvK/[redacted]/cQeOPuHSvc+PMup3/upp2x4d21mA+sE9bGTh/[redacted]/256dsc++DfQb/Yex8I9g== failed 60
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

## [ERR-20260421-004] tool-explicit-error

**Logged**: 2026-04-21T02:24:38.127Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool process returned an explicit error state.

### Error
```text
[process] process poll nimble-kelp 12000 [redacted] [redacted]|80pAGra9cLdryqO+4RUOus0I+sJ0g9Vv3QMHSnUavn+SMrah/lnUMsCmOzPRlI10GZ5sL8g/2jGX0HbiPL5N/DKKdOGszq/npckf09to6vAAHjtYwgg1X9+QRUHz5hFLPxsKgbwRLapbxO+[redacted]+/[redacted]/2UC30ABT/pHUpeKPZgPw7NA+SxgTR1yQ6eAk4OlwKQgF/[redacted]/YZcP+sWMd5/6/[redacted]+xbZqfYquiDw== failed 13
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

## [ERR-20260421-005] tool-timeout

**Logged**: 2026-04-21T02:27:00.826Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec timed out.

### Error
```text
[exec] exec python3 - <<'PY' import json, urllib.request cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) port=cfg['gateway']['port'] token=cfg['gateway']['auth']['token'] req=urllib.request.Request(f'[url] headers={'Authorization': f'Bearer {token}'}) with urllib.request.urlopen(req, timeout=10) as r: data=json.load(r) print(json.dumps({…
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

## [ERR-20260421-006] tool-timeout

**Logged**: 2026-04-21T02:27:24.723Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec timed out.

### Error
```text
[exec] exec python3 - <<'PY' import json, urllib.request, urllib.parse, pathlib cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) port=cfg['gateway']['port'] token=cfg['gateway']['auth']['token'] tmp=pathlib.Path('/home/missyouangeled/.openclaw/workspace/tmp') files=sorted(tmp.glob('*.webm')) print('FILES=', [str(p) for p in files[:10]]) i…
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

## [ERR-20260421-007] tool-timeout

**Logged**: 2026-04-21T02:39:00.464Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec timed out.

### Error
```text
[exec] exec set -e cd /home/missyouangeled/.openclaw/workspace out=tmp/[redacted].mp3 node tools/voice-reply/tts.mjs --text '你好，这是 mp3 语音链路测试。' --out "$out" python3 - <<'PY' import json, urllib.request, urllib.parse cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) port=cfg['gateway']['port'] token=cfg['gateway']['auth']['token'] source='/…
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

## [ERR-20260421-008] tool-explicit-error

**Logged**: 2026-04-21T02:49:14.532Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e agent-browser --session voice-debug eval ' (() => { const audios = Array.from(document.querySelectorAll("audio")); return audios.map((a, i) => ({ index: i, src: a.getAttribute("src"), currentSrc: a.currentSrc, readyState: a.readyState, networkState: a.networkState, paused: a.paused, duration: a.duration, error: a.error ? { code: a.error.c…
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

## [ERR-20260421-009] tool-timeout

**Logged**: 2026-04-21T02:49:33.651Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec timed out.

### Error
```text
[exec] exec python3 - <<'PY' import json, urllib.request, urllib.parse cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) port=cfg['gateway']['port'] token=cfg['gateway']['auth']['token'] source='/home/missyouangeled/.openclaw/workspace/tmp/[redacted].mp3' base=f'[url] source, 'token': token}) for label, headers in [ ('HEAD', {'method':'HEA…
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

## [ERR-20260421-010] tool-timeout

**Logged**: 2026-04-21T02:50:28.702Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec timed out.

### Error
```text
[exec] exec set -e openclaw gateway restart python3 - <<'PY' import json, urllib.request, urllib.parse, time cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) port=cfg['gateway']['port'] token=cfg['gateway']['auth']['token'] source='/home/missyouangeled/.openclaw/workspace/tmp/[redacted].mp3' base=f'[url] source, 'token': token}) for _ in …
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

## [ERR-20260421-011] tool-timeout

**Logged**: 2026-04-21T02:53:08.603Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec timed out.

### Error
```text
[exec] exec set -e openclaw gateway status || true python3 - <<'PY' import json, urllib.request, urllib.parse cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) port=cfg['gateway']['port'] token=cfg['gateway']['auth']['token'] source='/home/missyouangeled/.openclaw/workspace/tmp/[redacted].mp3' base=f'[url] source, 'token': token}) # HEAD t…
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

## [ERR-20260421-012] tool-timeout

**Logged**: 2026-04-21T02:55:59.841Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec timed out.

### Error
```text
[exec] exec python3 - <<'PY' import json, urllib.request, urllib.parse cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) port=cfg['gateway']['port'] token=cfg['gateway']['auth']['token'] for source in [ '/home/missyouangeled/.openclaw/workspace/tmp/[redacted].mp3', '/home/missyouangeled/.openclaw/workspace/tmp/[redacted].mp3' ]: q=urllib.p…
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

## [ERR-20260421-013] tool-explicit-error

**Logged**: 2026-04-21T02:56:03.623Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e TOKEN=$(python3 - <<'PY' import json cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) print(cfg['gateway']['auth']['token']) PY ) URL="[url] agent-browser --session voice-debug open "$URL" >/dev/null 2>&1 || true agent-browser --session voice-debug wait --load networkidle >/dev/null 2>&1 || true agent-browser --session …
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

## [ERR-20260421-014] tool-explicit-error

**Logged**: 2026-04-21T02:59:38.655Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e agent-browser --session voice-debug close || true TOKEN=$(python3 - <<'PY' import json cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) print(cfg['gateway']['auth']['token']) PY ) URL="[url] agent-browser --session voice-debug --args "--no-sandbox" open "$URL" >/dev/null agent-browser --session voice-debug wait --load n…
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

## [ERR-20260421-015] tool-explicit-error

**Logged**: 2026-04-21T03:04:19.183Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e TOKEN=$(python3 - <<'PY' import json cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) print(cfg['gateway']['auth']['token']) PY ) URL="[url] agent-browser --session voice-debug close >/dev/null 2>&1 || true agent-browser --session voice-debug --args "--no-sandbox" open "$URL" >/dev/null agent-browser --session voice-deb…
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

## [ERR-20260421-016] tool-timeout

**Logged**: 2026-04-21T03:26:03.212Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool sessions_send timed out.

### Error
```text
[sessions_send] timeout sessions_send 贾维斯已上线，我在。要开始干活的话，直接喊我。 agent:main:main 20 [redacted] [redacted]|elLKZObC5rLXg7c/[redacted]+fTFXqz8P1ff6WYpMlI3+zz+[redacted]/GApoR9Bdc7ru02CXZ/[redacted]/[redacted]/[redacted]+[redacted]/pmZ/1BIn/xHwn1theC5C1utCflXac2eq/[redacted]== timeout 21058
```

### Context
- Hook source: plugin:after_tool_call
- Tool: sessions_send
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260421-017] tool-timeout

**Logged**: 2026-04-21T03:28:32.707Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool sessions_send timed out.

### Error
```text
[sessions_send] timeout sessions_send 贾维斯已上线，我在。要开始干活的话，直接喊我。 agent:main:main 20 [redacted] [redacted]|MkF5C5OLF7jiibm3m/[redacted]+ljfIbZnHwW6gu0/cZK7VO+qp+[redacted]/[redacted]/yN+HuQatBMdxxrXbSm2fbMZiU/x1V6TArj8eIxknB8pl5s0u/E4n6RF1J1+[redacted]+[redacted]/+[redacted]+a7LlRRdI+Bnbag== timeout 20916
```

### Context
- Hook source: plugin:after_tool_call
- Tool: sessions_send
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260421-018] tool-timeout

**Logged**: 2026-04-21T03:36:17.310Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool sessions_send timed out.

### Error
```text
[sessions_send] timeout sessions_send 贾维斯已上线，我在。要开始干活的话，直接喊我。 agent:main:main 20 [redacted] [redacted]|[redacted]+[redacted]/g//[redacted]/[redacted]+[redacted]+[redacted]/[redacted]/0L24n2gTZbQuTb2hK/[redacted]== timeout 20800
```

### Context
- Hook source: plugin:after_tool_call
- Tool: sessions_send
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260421-019] tool-timeout

**Logged**: 2026-04-21T04:04:24.175Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool sessions_send timed out.

### Error
```text
[sessions_send] timeout sessions_send 贾维斯已上线，我在。要开始干活的话，直接喊我。 agent:main:main 20 [redacted] [redacted]|[redacted]+[redacted]+KFkZHZroylS+[redacted]+[redacted]/Vc27R0aF/[redacted]+CDOGd61mRg0wSURC5Rh+D8Pxaz+[redacted]+HWid633LLgg3Q+9aIEcLZ3yAiw== timeout 20559
```

### Context
- Hook source: plugin:after_tool_call
- Tool: sessions_send
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260421-020] tool-timeout

**Logged**: 2026-04-21T04:07:25.148Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool sessions_send timed out.

### Error
```text
[sessions_send] timeout sessions_send 贾维斯已上线，我在。要开始干活的话，直接喊我。 agent:main:main 20 [redacted] [redacted]|[redacted]/2RzvUjTBbxg0HZi0V/[redacted]+HE5g+[redacted]//K5+B43H75oI1gxLK/[redacted]/[redacted]+QnXHm/g+[redacted]/7ztm1HbPBiifw== timeout 20581
```

### Context
- Hook source: plugin:after_tool_call
- Tool: sessions_send
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260421-021] tool-explicit-error

**Logged**: 2026-04-21T04:08:56.315Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e TOKEN=$(python3 - <<'PY' import json cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) print(cfg['gateway']['auth']['token']) PY ) agent-browser --session voice-root-check close >/dev/null 2>&1 || true agent-browser --session voice-root-check --args "--no-sandbox" open "[url] >/dev/null agent-browser --session voice-root…
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

## [ERR-20260421-021] tool-explicit-error

**Logged**: 2026-04-21T04:08:56.441Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e TOKEN=$(python3 - <<'PY' import json cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) print(cfg['gateway']['auth']['token']) PY ) agent-browser --session voice-chat-check close >/dev/null 2>&1 || true agent-browser --session voice-chat-check --args "--no-sandbox" open "[url] >/dev/null agent-browser --session voice-chat…
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

## [ERR-20260421-022] tool-explicit-error

**Logged**: 2026-04-21T04:09:26.967Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e TOKEN=$(python3 - <<'PY' import json cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) print(cfg['gateway']['auth']['token']) PY ) agent-browser --session voice-click-check close >/dev/null 2>&1 || true agent-browser --session voice-click-check --args "--no-sandbox" open "[url] >/dev/null agent-browser --session voice-cl…
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

## [ERR-20260421-023] tool-explicit-error

**Logged**: 2026-04-21T04:10:50.145Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e TOKEN=$(python3 - <<'PY' import json cfg=json.load(open('/home/missyouangeled/.openclaw/openclaw.json')) print(cfg['gateway']['auth']['token']) PY ) agent-browser --session voice-overlay-check close >/dev/null 2>&1 || true agent-browser --session voice-overlay-check --args "--no-sandbox" open "[url] >/dev/null agent-browser --session voic…
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

## [ERR-20260421-024] tool-explicit-error

**Logged**: 2026-04-21T04:16:23.551Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e agent-browser --session voice-device-only close >/dev/null 2>&1 || true agent-browser --session voice-device-only --args "--no-sandbox" open "[url] >/dev/null agent-browser --session voice-device-only wait --load networkidle >/dev/null || true agent-browser --session voice-device-only eval ' (() => { localStorage.clear(); localStorage.set…
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

## [ERR-20260421-025] tool-explicit-error

**Logged**: 2026-04-21T04:18:26.761Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e agent-browser --session voice-device-only-v2 close >/dev/null 2>&1 || true agent-browser --session voice-device-only-v2 --args "--no-sandbox" open "[url] >/dev/null agent-browser --session voice-device-only-v2 wait --load networkidle >/dev/null || true agent-browser --session voice-device-only-v2 eval ' (() => { localStorage.clear(); loca…
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

## [ERR-20260421-026] tool-timeout

**Logged**: 2026-04-21T04:24:44.810Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool sessions_send timed out.

### Error
```text
[sessions_send] timeout sessions_send 贾维斯已上线，我在。要开始干活的话，直接喊我。 agent:main:main 20 [redacted] [redacted]|[redacted]/[redacted]+LHT01a2FMF74MhNr/[redacted]+u6hsm9YAEVa+[redacted]/[redacted]+jlvcLG+[redacted]/ehNRy4+AaHLLZZMlipjRH42/Kuei/fqNVaeJXROvdcB21pHv4/[redacted]+[redacted]== timeout 21495
```

### Context
- Hook source: plugin:after_tool_call
- Tool: sessions_send
- Session Key: agent:main:main

### Suggested Fix
Confirm the failure is real and recurring, then resolve it or downgrade it to inbox if it was a one-off environmental hiccup.

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- See Also: openclaw-env/plugins/self-improvement-tool-errors

---

## [ERR-20260421-027] tool-explicit-error

**Logged**: 2026-04-21T04:25:24.396Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec set -e agent-browser --session voice-device-only-v3 close >/dev/null 2>&1 || true agent-browser --session voice-device-only-v3 --args "--no-sandbox" open "[url] >/dev/null agent-browser --session voice-device-only-v3 wait --load networkidle >/dev/null || true agent-browser --session voice-device-only-v3 eval ' (() => { localStorage.clear(); loca…
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

## [ERR-20260421-028] tool-explicit-error

**Logged**: 2026-04-21T05:34:16.517Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec ffprobe -v error -show_entries format=filename,duration,bit_rate:stream=codec_name,codec_type,sample_rate,channels -of json '/home/missyouangeled/Music/ 2053_raw(1).mp3' /home/missyouangeled/.openclaw/workspace 10000 120 [redacted] [redacted]|VcwQDA2l9R06Pt6UE/[redacted]+9MC3X/[redacted]/[redacted]+[redacted]++[redacted]/[redacted]/[redacted]== …
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

## [ERR-20260421-029] tool-explicit-error

**Logged**: 2026-04-21T05:36:30.354Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Tool exec returned an explicit error state.

### Error
```text
[exec] exec python3 - <<'PY' mods=['mutagen','pydub','audioread','soundfile','librosa','requests'] for m in mods: try: __import__(m) print(m+':yes') except Exception as e: print(m+':no') PY /home/missyouangeled/.openclaw/workspace 10000 120 [redacted] [redacted]|yp+cDVbayiJXeUcNOV0R0/[redacted]/[redacted]/yvf5jG/C7S6Mo2LyPdG2J+SaQZev4Mgup0o58XQp+[redacted]+…
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
