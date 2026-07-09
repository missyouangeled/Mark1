#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SH = timezone(timedelta(hours=8))
NOW = datetime.now(SH)
HOME = Path.home()
WORKSPACE = HOME / '.openclaw' / 'workspace'
STATE_DIR = HOME / '.local' / 'state' / 'openclaw' / 'incident-recovery'
EVIDENCE_DIR = STATE_DIR / 'evidence'
PLANS_DIR = STATE_DIR / 'plans'
STATUS_JSON = STATE_DIR / 'status.json'
LOG_JSONL = STATE_DIR / 'recovery-log.jsonl'
BACKUP_ROOT = Path('/mnt/data/openclaw/session-backup')
BACKUP_MANIFEST = BACKUP_ROOT / 'backup-manifest.json'
EMERGENCY_STATUS = HOME / '.local' / 'state' / 'openclaw' / 'emergency-aggregator' / 'status.json'
HEALTH_REPORT = HOME / '.local' / 'state' / 'openclaw' / 'health-collector' / 'last-report.json'
FRONTSTAGE_REPORT = HOME / '.local' / 'state' / 'openclaw' / 'frontstage-guardian' / 'last-report.json'
SESSIONS_JSON = HOME / '.openclaw' / 'agents' / 'main' / 'sessions' / 'sessions.json'
RECOVERY_DOC = WORKSPACE / 'docs' / 'runtime' / '事故自救链运行说明-2026-07-06.md'

# 时间窗（分钟）：real_events 距当前时间超过该窗口视为“历史残留”，
# 只入 stale 桶，不计入 severity 触发的 fresh_real_events。
# 选 15 分钟的依据：
# - 一次 gateway restart loop 典型 5-10 分钟（事件间网 30s~1min）；
# - 后检取到 latest fresh event 距 NOW >= 15 分钟 → 该次事件序列已结束
#   → 转 stale，severity 可以从 degrading 收敛回 noise / none。
# - 不选 5-10 分钟是怕 gateway 重启隔几分钟后又来一波，误判为已收敛；
# - 不选 30 分钟是会让系统长期不能退出 degrading。
ACTIVE_EVENT_WINDOW_MINUTES = 15


def ensure_dirs() -> None:
    for path in (STATE_DIR, EVIDENCE_DIR, PLANS_DIR, RECOVERY_DOC.parent):
        path.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str], timeout: int = 60) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(WORKSPACE), check=False)
        return {
            'ok': proc.returncode == 0,
            'exitCode': proc.returncode,
            'stdout': (proc.stdout or '').strip(),
            'stderr': (proc.stderr or '').strip(),
            'cmd': cmd,
        }
    except subprocess.TimeoutExpired:
        return {'ok': False, 'exitCode': -1, 'stdout': '', 'stderr': f'TIMEOUT({timeout}s)', 'cmd': cmd}
    except Exception as exc:
        return {'ok': False, 'exitCode': -2, 'stdout': '', 'stderr': str(exc), 'cmd': cmd}


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def append_log(item: dict[str, Any]) -> None:
    with LOG_JSONL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        return datetime.fromisoformat(text).astimezone(SH)
    except Exception:
        return None


def collect_runtime_evidence(reason: str) -> dict[str, Any]:
    emergency = load_json(EMERGENCY_STATUS) or {}
    health = load_json(HEALTH_REPORT) or {}
    frontstage = load_json(FRONTSTAGE_REPORT) or {}
    sessions = load_json(SESSIONS_JSON) or {}
    status = run(['openclaw', 'status'])
    system_summary = run(['python3', str(WORKSPACE / 'scripts' / 'openclaw-system-summary.py'), '--print-json'])
    backup_last = run(['python3', str(WORKSPACE / 'scripts' / 'openclaw-session-backup.py'), '--restore-last'])
    main = (sessions.get('agent:main:main') or {}) if isinstance(sessions, dict) else {}
    transcript_repair = detect_transcript_repair_signals()
    reply_init = detect_reply_init_conflict_signals()
    severity = classify_overall_severity(transcript_repair, reply_init)
    evidence = {
        'capturedAt': NOW.isoformat(),
        'reason': reason,
        'mainSession': {
            'sessionId': main.get('sessionId'),
            'status': main.get('status'),
            'model': main.get('model'),
            'abortedLastRun': main.get('abortedLastRun'),
            'updatedAt': main.get('updatedAt'),
        },
        'emergencyStatus': emergency,
        'healthReport': health,
        'frontstageReport': frontstage,
        'openclawStatus': status,
        'systemSummary': system_summary,
        'backupLast': backup_last,
        'autoOverrideSessions': detect_auto_override_sessions(),
        'transcriptRepairSignals': transcript_repair,
        'replyInitSignals': reply_init,
        'severity': severity,
    }
    evidence_path = EVIDENCE_DIR / f'incident-{NOW.strftime("%Y-%m-%dT%H%M%S")}.json'
    save_json(evidence_path, evidence)
    return {'path': str(evidence_path), 'data': evidence}


def detect_auto_override_sessions() -> list[dict[str, Any]]:
    sessions = load_json(SESSIONS_JSON) or {}
    rows: list[dict[str, Any]] = []
    if not isinstance(sessions, dict):
        return rows
    for key, value in sessions.items():
        if not isinstance(value, dict):
            continue
        if value.get('modelOverrideSource') != 'auto':
            continue
        rows.append({
            'key': key,
            'status': value.get('status'),
            'model': value.get('model'),
            'provider': value.get('provider'),
            'modelOverride': value.get('modelOverride'),
            'providerOverride': value.get('providerOverride'),
            'updatedAt': value.get('updatedAt'),
        })
    return rows


def _iter_main_session_messages(session_file: Path, max_lines: int = 200) -> list[dict[str, Any]]:
    """按 JSON 解析最近 max_lines 行主 session，保留结构化消息。

    每条返回的结构都来自 json.loads（line 级别）；解析失败的行跳过。
    """
    if not session_file.exists():
        return []
    lines = session_file.read_text(encoding='utf-8', errors='ignore').splitlines()
    tail = lines[-max_lines:]
    msgs: list[dict[str, Any]] = []
    for idx, raw in enumerate(tail, start=max(1, len(lines) - len(tail) + 1)):
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if isinstance(obj, dict) and obj.get('type') == 'message':
            msgs.append({'line': idx, 'raw': obj})
    return msgs


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for item in content:
            if isinstance(item, dict):
                txt = item.get('text')
                if isinstance(txt, str):
                    out.append(txt)
        return '\n'.join(out)
    return ''


def _split_fresh_stale(
    events: list[dict[str, Any]],
    now: datetime,
    window_minutes: int = ACTIVE_EVENT_WINDOW_MINUTES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """按时间窗把 real_events 分成 fresh / stale 两桶。

    - fresh：timestamp 距 now 不超过 window_minutes（计入 severity 触发）
    - stale：timestamp 距 now 超过 window_minutes（仅留痕，不触发降级）

    timestamp 缺失或解析失败的事件默认归入 fresh（保守）：宁可误报一次
    degrading，也不能漏掉一次真正的实时事故。
    """
    fresh: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    cutoff = now - timedelta(minutes=window_minutes)
    for ev in events:
        ts = parse_iso(ev.get('timestamp'))
        if ts is None:
            fresh.append(ev)
            continue
        if ts >= cutoff:
            fresh.append(ev)
        else:
            stale.append(ev)
    return fresh, stale


def detect_transcript_repair_signals() -> dict[str, Any]:
    """结构化识别 transcript repair 事故。

    输出包含 noise / real_events 两个桶：
    - noise：只在 toolResult 的 read 文本里被读出来的字符串（昨天 daily/对话
      里提到这些字面量时也会命中）；不应当作事故证据。
    - real_events：assistant provider=openclaw/model=gateway-injected 的
      Gateway restart 注入消息，或 assistant 错误消息 "missing tool result
      in session history; inserted synthetic error result for transcript repair"。

    `detected=True` 只在 real_events 非空时返回。
    """
    sessions = load_json(SESSIONS_JSON) or {}
    main = (sessions.get('agent:main:main') or {}) if isinstance(sessions, dict) else {}
    session_file = Path(main.get('sessionFile') or '')
    if not session_file.exists():
        return {'detected': False, 'noise': [], 'real_events': [], 'summary': '主 session 文件不存在，无法检查 transcript repair'}

    msgs = _iter_main_session_messages(session_file)
    noise: list[dict[str, Any]] = []
    real_events: list[dict[str, Any]] = []

    # 真实事件严格条件：assistant role + provider=openclaw + model=gateway-injected
    # （以及 assistant role + stopReason=error 且 provider 缺失但错误文本独特）
    def is_gateway_injected_message(m: dict[str, Any]) -> bool:
        return (
            m.get('provider') == 'openclaw'
            and m.get('model') == 'gateway-injected'
        )

    for entry in msgs:
        line = entry['line']
        m = entry['raw'].get('message') or {}
        role = m.get('role')
        text = _extract_text(m.get('content'))

        if role == 'assistant':
            # 1) 真实 Gateway restart 注入事件
            injected_needles = (
                'Gateway is restarting',
                'system is initializing',
                'system boot event',
                '系统启动事件',  # 中文注入
            )
            if is_gateway_injected_message(m):
                if any(needle.lower() in text.lower() for needle in injected_needles):
                    real_events.append({
                        'line': line,
                        'kind': 'gateway_restart_injected',
                        'timestamp': entry['raw'].get('timestamp'),
                        'text': text[:200],
                        'provider': m.get('provider'),
                        'model': m.get('model'),
                        'api': m.get('api'),
                    })
                    continue
                # 即使不含上面那几句，只要是 gateway-injected 且 stopReason=stop 且文本极短，也怀疑事件
                if text and len(text) <= 400 and ('Gateway' in text or 'gateway' in text or 'system' in text.lower() or '注入' in text):
                    real_events.append({
                        'line': line,
                        'kind': 'gateway_restart_injected',
                        'timestamp': entry['raw'].get('timestamp'),
                        'text': text[:200],
                        'provider': m.get('provider'),
                        'model': m.get('model'),
                        'api': m.get('api'),
                    })
                    continue

            # 2) 真实 transcript repair 错误消息：要求 provider=openclaw + model=gateway-injected
            # （普通 taotoken/gpt-5.4 assistant 消息中出现这些字面量不算事件）
            if is_gateway_injected_message(m) and (
                'inserted synthetic error result for transcript repair' in text
                or 'missing tool result in session history' in text
            ):
                real_events.append({
                    'line': line,
                    'kind': 'transcript_repair_error',
                    'timestamp': entry['raw'].get('timestamp'),
                    'text': text[:200],
                    'stopReason': m.get('stopReason'),
                })
                continue

        # 3) toolResult 文本里读到这些字符串 → 仅算 noise（不是真实事故）
        if role == 'toolResult' and text:
            for needle in (
                'Gateway is restarting',
                'inserted synthetic error result for transcript repair',
                'missing tool result in session history',
                '系统启动事件',
            ):
                if needle in text:
                    noise.append({
                        'line': line,
                        'kind': 'echo_in_tool_result',
                        'needle': needle,
                        'text': text[:160],
                    })
                    break

    if not real_events:
        return {
            'detected': False,
            'noise': noise[-8:],
            'real_events': [],
            'fresh_real_events': [],
            'stale_real_events': [],
            'summary': (
                f'未发现真实 gateway_restart_injected / transcript_repair_error 事件；'
                f'仅在 {len(noise)} 条 toolResult 文本里看到相关字符串（视为 noise，非事故）'
                if noise else
                '未发现 transcript repair / gateway restart 真实事件；可视为 transcript repair 噪音，不是持续性 activeWork 卡死'
            ),
        }

    fresh, stale = _split_fresh_stale(real_events, NOW)
    # `detected` 仅看 fresh；stale 事件仅留痕，不触发降级。
    return {
        'detected': bool(fresh),
        'noise': noise[-8:],
        'real_events': real_events[-12:],
        'fresh_real_events': fresh[-12:],
        'stale_real_events': stale[-12:],
        'realEventCount': len(real_events),
        'freshRealEventCount': len(fresh),
        'staleRealEventCount': len(stale),
        'activeWindowMinutes': ACTIVE_EVENT_WINDOW_MINUTES,
        'summary': (
            f'fresh={len(fresh)} stale={len(stale)}（窗口 {ACTIVE_EVENT_WINDOW_MINUTES} 分钟）；'
            f'另有 {len(noise)} 条 noise'
        ),
    }


def detect_reply_init_conflict_signals() -> dict[str, Any]:
    """识别 reply session initialization conflicted 事故。

    与 transcript repair 不同，这条错误通常在 reply session 初始化阶段抛出。
    我们只识别**真实事件**：
    - 普通 assistant 消息里，provider 被注入为 openclaw、且 stopReason=error
      或消息文本以 "reply session initialization conflicted" / 包含
      "activeWork" 字样的 error payload；
    - 错误事件（type=event, kind=error ...）包含相同字面量。

    同时按 severity 估算：
    - 'noise'：仅在 read 文本回声里看到（不应当作事故）；
    - 'degrading'：至少有 1 条真实 reply-init 错误事件但没看到 synthetic toolResult 续上；
    - 'activeWork_deadlock'：在主 session 里最近 N 条真实事件里
      同时出现 reply-init 冲突 + transcript-repair 续上。
    """
    sessions = load_json(SESSIONS_JSON) or {}
    main = (sessions.get('agent:main:main') or {}) if isinstance(sessions, dict) else {}
    session_file = Path(main.get('sessionFile') or '')
    if not session_file.exists():
        return {'detected': False, 'noise': [], 'real_events': [], 'severity': 'none', 'summary': '主 session 文件不存在'}

    msgs = _iter_main_session_messages(session_file)
    noise: list[dict[str, Any]] = []
    real_events: list[dict[str, Any]] = []

    needles = (
        'reply session initialization conflicted',
        'reply session initialization failed',
        'activeWork',
    )

    def is_gateway_injected_message(m: dict[str, Any]) -> bool:
        return (
            m.get('provider') == 'openclaw'
            and m.get('model') == 'gateway-injected'
        )

    for entry in msgs:
        line = entry['line']
        obj = entry['raw']
        m = obj.get('message') or {}
        role = m.get('role')
        text = _extract_text(m.get('content'))

        # 真实 assistant 错误消息：必须是 provider=openclaw (gateway 注入) 或 stopReason=error 的准事件
        if role == 'assistant' and text:
            stop_reason = m.get('stopReason')
            provider = m.get('provider')
            if is_gateway_injected_message(m) or stop_reason == 'error':
                for needle in needles:
                    if needle in text:
                        real_events.append({
                            'line': line,
                            'kind': 'reply_init_conflict',
                            'timestamp': obj.get('timestamp'),
                            'needle': needle,
                            'text': text[:200],
                            'stopReason': stop_reason,
                            'provider': provider,
                            'model': m.get('model'),
                        })
                        break
            continue

        # 错误事件
        if obj.get('kind') == 'error' or obj.get('type') == 'event':
            etext = _extract_text(m.get('content')) or _extract_text(obj.get('error'))
            if etext:
                for needle in needles:
                    if needle in etext:
                        real_events.append({
                            'line': line,
                            'kind': 'reply_init_conflict_event',
                            'timestamp': obj.get('timestamp'),
                            'needle': needle,
                            'text': etext[:200],
                        })
                        break
            continue

        # toolResult 文本里的回声
        if role == 'toolResult' and text:
            for needle in needles:
                if needle in text:
                    noise.append({'line': line, 'kind': 'echo_in_tool_result', 'needle': needle})
                    break

    # severity 估算
    # 只看 fresh（窗口内）事件；stale 仅留痕，不计入 severity。
    fresh, stale = _split_fresh_stale(real_events, NOW)
    severity = 'none'
    if fresh:
        # 简化：如果在最近 3 条 fresh 真实事件里同时见到 reply-init + transcript repair 文本
        recent = fresh[-3:]
        recent_kinds = {e['kind'] for e in recent}
        seen_transcript = any('transcript' in (e.get('needle') or '') or 'synthetic' in (e.get('text','').lower()) for e in recent)
        if recent_kinds and seen_transcript and ('reply_init_conflict' in recent_kinds or 'reply_init_conflict_event' in recent_kinds):
            severity = 'activeWork_deadlock'
        elif len(fresh) >= 1:
            severity = 'degrading'
    if not fresh and noise:
        severity = 'noise'

    if not real_events:
        return {
            'detected': False,
            'noise': noise[-8:],
            'real_events': [],
            'fresh_real_events': [],
            'stale_real_events': [],
            'severity': severity,
            'summary': (
                f'未发现 reply-init 真实事件；noise={len(noise)}（仅回声）'
                if noise else
                '未发现 reply session initialization conflicted 真实事件'
            ),
        }

    summary = (
        f'reply-init fresh={len(fresh)} stale={len(stale)}（窗口 {ACTIVE_EVENT_WINDOW_MINUTES} 分钟）；'
        f'severity={severity}'
    )
    return {
        'detected': bool(fresh),
        'noise': noise[-8:],
        'real_events': real_events[-12:],
        'fresh_real_events': fresh[-12:],
        'stale_real_events': stale[-12:],
        'realEventCount': len(real_events),
        'freshRealEventCount': len(fresh),
        'staleRealEventCount': len(stale),
        'activeWindowMinutes': ACTIVE_EVENT_WINDOW_MINUTES,
        'severity': severity,
        'summary': summary,
    }


def classify_overall_severity(
    repair_signals: dict[str, Any],
    reply_signals: dict[str, Any],
) -> dict[str, Any]:
    """综合 transcript repair 与 reply-init 冲突，给出一个 severity 分级与策略。

    四级：
    - none：两条都是 noise 或无事件。
    - noise：只有 toolResult 文本里的字面量；可继续观察，不进入自救流程。
    - degrading：有真实事件但没形成持续性 deadlock，仍在跑可继续在主会话继续推进
      但要保持“后台执行 + 监工常驻 + 前台轻交互”策略。
    - activeWork_deadlock：真实事件+transcript repair 续上，主会话已不可信，需冻结
      当前主 transcript，立刻切到隔离恢复面，并把后续重任务推到后台 subagent。
    """
    if not repair_signals.get('detected') and not reply_signals.get('detected'):
        return {
            'severity': 'none',
            'strategy': 'observe',
            'note': '两条事故模式都没真实事件命中；继续前台轻交互，不需要切后台/隔离',
        }

    reply_sev = reply_signals.get('severity') or 'none'
    # 只看 fresh（窗口内）；stale 不参与 severity 判定。
    # 保持向后兼容：如果 detector 还没出 fresh 字段（老 evidence），退回 realEventCount。
    repair_real = repair_signals.get('freshRealEventCount')
    if repair_real is None:
        repair_real = repair_signals.get('realEventCount', 0) or 0
    reply_real = reply_signals.get('freshRealEventCount')
    if reply_real is None:
        reply_real = reply_signals.get('realEventCount', 0) or 0

    if reply_sev == 'activeWork_deadlock' or (repair_real >= 1 and reply_real >= 1):
        return {
            'severity': 'activeWork_deadlock',
            'strategy': 'isolate_and_split',
            'note': (
                '主会话已不可信：当前 transcript repair 与 reply-init 冲突同时出现真实事件，'
                '属于持续性 activeWork 卡死。立刻冻结当前主 transcript，停止在主会话继续重任务，'
                '把排障与重写工作放到隔离 subagent；监工继续在后台常驻。'
            ),
        }
    if repair_real >= 1 or reply_real >= 1:
        return {
            'severity': 'degrading',
            'strategy': 'background_supervisor_with_light_foreground',
            'note': (
                '至少有 1 条真实事故事件，但还没形成持续性 deadlock。'
                '运行策略收敛为：后台执行（重任务由 subagent 跑）+ 监工常驻'
                '（incident-recovery / emergency-aggregator 持续采集证据）+ 前台轻交互（主会话只触发/总结/审阅）。'
            ),
        }
    return {
        'severity': 'noise',
        'strategy': 'observe_with_supervisor',
        'note': (
            'toolResult 文本里有相关字符串回声，但没真实事件；当前可继续前台，'
            '但后台监工需保持常驻以捕捉后续真实事件。'
        ),
    }


def choose_backup_candidate() -> dict[str, Any]:
    manifest = load_json(BACKUP_MANIFEST) or {'snapshots': []}
    snapshots = manifest.get('snapshots') or []
    if not snapshots:
        return {'found': False, 'reason': 'no_snapshots'}

    ranked = []
    for item in reversed(snapshots):
        path = Path(item.get('path', ''))
        summary_path = path / 'context-summary.md'
        state_path = path / 'session-state.json'
        if not path.exists() or not summary_path.exists() or not state_path.exists():
            continue
        ts = parse_iso(item.get('timestamp', '').replace('T', 'T'))
        ranked.append({
            'timestamp': item.get('timestamp'),
            'path': str(path),
            'summaryPath': str(summary_path),
            'sessionStatePath': str(state_path),
            'fileCount': item.get('fileCount'),
            'ageMinutes': None if ts is None else (NOW - ts).total_seconds() / 60.0,
        })
    if not ranked:
        return {'found': False, 'reason': 'no_valid_snapshot'}
    return {'found': True, 'candidate': ranked[0], 'alternatives': ranked[1:4]}


def build_recovery_plan(reason: str, evidence: dict[str, Any], backup: dict[str, Any]) -> dict[str, Any]:
    candidate = backup.get('candidate') if backup.get('found') else None
    severity = evidence['data'].get('severity') or {'severity': 'none'}
    strategy = severity.get('strategy') or 'observe'

    base_actions = [
        '冻结当前事故证据，禁止直接在坏状态下继续判断',
        '优先使用最近正常快照的 context-summary / MEMORY / daily 恢复理解上下文',
        '在隔离恢复工作面中执行排障，而不是直接覆盖当前生产态',
        '若发现 modelOverrideSource=auto 的 fallback 钉死，先生成清理方案，只对白名单 auto override 下手',
        '优先读取本地 docs 与历史方案；若不确定则联网搜索 OpenClaw / provider / model 相关问题',
        '仅执行白名单低风险修复；高风险动作保持人工边界',
        '修复后复跑 health / emergency / system-summary 验证',
    ]

    if strategy == 'isolate_and_split':
        base_actions = [
            '【activeWork_deadlock】主会话已不可信：停止在主会话继续重任务，立刻冻结当前主 transcript',
            '重任务一律推到后台 subagent（明确的 prompt / 独立任务名 / 隔离上下文）',
            '监工常驻：incident-recovery 自救链脚本 + emergency-aggregator 持续采集实时证据',
            '前台只做：触发后台任务、读 evidence / plan 文件、做总结与裁决',
        ] + base_actions

    next_actions = base_actions

    plan = {
        'generatedAt': NOW.isoformat(),
        'reason': reason,
        'mode': 'isolated_recovery' if strategy != 'isolate_and_split' else 'isolated_split_recovery',
        'evidencePath': evidence['path'],
        'backupCandidate': candidate,
        'nextActions': next_actions,
        'severity': severity,
        'runtimeStrategy': {
            'name': '后台执行 + 监工常驻 + 前台轻交互',
            'foreground': '主会话只做触发 / 总结 / 审阅，不亲自跑重任务',
            'supervisor': 'incident-recovery / emergency-aggregator / health-collector / session-size-watcher 持续采集',
            'background': '重任务交给 sessions_spawn（独立 model、lightContext=true/false 按任务）',
            'whyThisStrategy': severity.get('note') or '',
        },
        'autoOverrideRecovery': build_auto_override_recovery(evidence['data'].get('autoOverrideSessions') or []),
        'transcriptRepairRecovery': build_transcript_repair_recovery(evidence['data'].get('transcriptRepairSignals') or {}),
        'replyInitRecovery': build_reply_init_recovery(evidence['data'].get('replyInitSignals') or {}),
    }
    plan_path = PLANS_DIR / f'recovery-plan-{NOW.strftime("%Y-%m-%dT%H%M%S")}.json'
    save_json(plan_path, plan)
    return {'path': str(plan_path), 'data': plan}


def build_reply_init_recovery(signal: dict[str, Any]) -> dict[str, Any]:
    if not signal.get('detected'):
        if signal.get('severity') == 'noise':
            return {
                'detected': False,
                'severity': 'noise',
                'summary': '未发现 reply-init 真实事件；toolResult 文本里有相关字符串回声（noise）',
                'safeAction': '不进入自救流程；继续前台轻交互 + 后台监工',
                'noise': signal.get('noise') or [],
            }
        return {
            'detected': False,
            'severity': signal.get('severity') or 'none',
            'summary': '未发现 reply session initialization conflicted 真实事件',
            'safeAction': '无',
        }
    severity = signal.get('severity') or 'degrading'
    if severity == 'activeWork_deadlock':
        return {
            'detected': True,
            'severity': severity,
            'summary': signal.get('summary') or '',
            'safeAction': '立刻冻结主 transcript；把重任务推到后台 subagent；不在主会话继续推进',
            'proposedSteps': [
                '1) 保留当前真实事件证据（不直接修改主 session jsonl）',
                '2) 让孤立 subagent 拉起继续排障与修复；主会话只下结论',
                '3) 监工持续采集 transcript repair / reply-init 真实事件直到清零',
                '4) 清零后再回归“前台可用”状态，按“后台+监工+前台轻交互”策略继续',
            ],
            'realEvents': signal.get('real_events') or [],
        }
    return {
        'detected': True,
        'severity': severity,
        'summary': signal.get('summary') or '',
        'safeAction': '主会话开始降级，但仍可用；按 “后台+监工+前台轻交互” 策略继续',
        'proposedSteps': [
            '1) 继续冻结证据，保留全部真实事件',
            '2) 主会话保持只读 / 触发 / 总结，不做长链 tool 调用',
            '3) 重任务交由 sessions_spawn 后台 subagent',
            '4) incident-recovery / emergency-aggregator 持续监工，留意是否升级为 activeWork_deadlock',
        ],
        'realEvents': signal.get('real_events') or [],
    }


def build_auto_override_recovery(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            'detected': False,
            'summary': '未发现 modelOverrideSource=auto 的会话钉死',
            'safeAction': '无',
        }
    return {
        'detected': True,
        'summary': f'发现 {len(rows)} 个 modelOverrideSource=auto 的会话，需要与 user override 严格区分',
        'safeAction': '仅生成 auto override 清理计划，不直接改现网',
        'candidates': rows,
        'proposedScript': [
            '先备份 sessions.json',
            '只清理 modelOverrideSource == auto 的项',
            '不动 user override，不删 session 文件，不做 gateway restart',
        ],
    }


def build_transcript_repair_recovery(signal: dict[str, Any]) -> dict[str, Any]:
    if not signal.get('detected'):
        return {
            'detected': False,
            'summary': '未发现 gateway restart / transcript repair 事故模式',
            'safeAction': '无',
        }
    return {
        'detected': True,
        'summary': signal.get('summary'),
        'safeAction': '先冻结证据与快照，再在隔离恢复面继续对话，不直接继续复用当前被 repair 的半残 transcript',
        'proposedSteps': [
            '记录 gateway restart 注入消息与 synthetic toolResult 位置',
            '优先使用最近正常快照恢复上下文理解',
            '在隔离恢复分身中继续排障与总结，而不是依赖当前被中断的 toolCall 链',
            '当前仅做 plan-only，不自动重写 transcript，不改主 session 文件',
        ],
        'matches': signal.get('matches') or [],
    }


def build_isolated_prompt(reason: str, evidence: dict[str, Any], backup: dict[str, Any], plan: dict[str, Any]) -> str:
    candidate = backup.get('candidate') or {}
    # plan 是 build_recovery_plan 返回的 {'path': ..., 'data': ...} 包装；剥到内部 data
    inner = plan.get('data') if isinstance(plan, dict) and 'data' in plan else plan
    sev_obj = (inner.get('severity') if isinstance(inner, dict) else None) or {}
    severity = sev_obj.get('severity') or 'none'
    strategy = sev_obj.get('strategy') or 'observe'
    rs = (inner.get('runtimeStrategy') if isinstance(inner, dict) else None) or {}
    tr_signal = (evidence['data'].get('transcriptRepairSignals') or {})
    ri_signal = (evidence['data'].get('replyInitSignals') or {})
    tr_real = tr_signal.get('realEventCount') or 0
    ri_real = ri_signal.get('realEventCount') or 0
    rs_name = rs.get('name') or '后台执行 + 监工常驻 + 前台轻交互'
    rs_foreground = rs.get('foreground') or '主会话只做触发 / 总结 / 审阅'
    rs_background = rs.get('background') or '重任务交给 sessions_spawn 后台 subagent'
    rs_supervisor = rs.get('supervisor') or 'incident-recovery / emergency-aggregator / health-collector 持续采集'
    rs_why = rs.get('whyThisStrategy') or sev_obj.get('note') or ''
    return (
        '你当前处于 OpenClaw 事故自救链的隔离排障阶段。\n\n'
        f'事故原因：{reason}\n'
        f'严重等级：{severity}（策略：{strategy}）\n'
        f'证据文件：{evidence["path"]}\n'
        f'恢复计划：{plan["path"]}\n'
        f'候选快照：{candidate.get("path", "无")}\n'
        f'快照摘要：{candidate.get("summaryPath", "无")}\n'
        f'\n--- 运行期事故信号 ---\n'
        f'transcript repair 真实事件数：{tr_real}\n'
        f'reply-init 冲突真实事件数：{ri_real}\n'
        f'reply-init severity：{ri_signal.get("severity") or "none"}\n'
        f'\n--- 运行策略：{rs_name} ---\n'
        f'前台（本会话）：{rs_foreground}\n'
        f'后台执行：{rs_background}\n'
        f'监工：{rs_supervisor}\n'
        f'why-this-strategy：{rs_why}\n'
        f'\n要求：\n'
        '1. 先读证据文件、快照摘要、本地 docs 和相关脚本，按 noise / degrading / activeWork_deadlock 区分处理。\n'
        '2. 若仍不确定，联网搜索 OpenClaw 文档 / GitHub / provider 已知问题。\n'
        '3. 给出最小低风险修复方案，区分"短期止血"与"根因修复"。\n'
        '4. **绝对边界**：不修改当前主 session 内容，不做 cleanup --enforce，'
        '不做 gateway restart，不改 cron / systemd / gateway 配置，'
        '不动 modelOverrideSource=user 的会话。\n'
        '5. 重任务一律在隔离 subagent 内（你当前这个会话）完成；'
        '返回主会话时只输出"根因 / 修复动作 / 验证步骤 / 需要人工确认的事项"。\n'
        '6. 如遇 activeWork_deadlock：明确告诉主会话"已冻结主 transcript，'
        '请按后台+监工+前台轻交互策略继续"。\n'
    )


def write_doc() -> None:
    RECOVERY_DOC.parent.mkdir(parents=True, exist_ok=True)
    existing = RECOVERY_DOC.read_text(encoding='utf-8') if RECOVERY_DOC.exists() else ''
    if 'replyInitSignals' in existing and 'Severity 分级' in existing and '后台执行 + 监工常驻' in existing:
        return
    RECOVERY_DOC.write_text(
        '# 事故自救链运行说明（2026-07-06，2026-07-07 v2 更新）\n\n'
        '## 一、目标与独立性\n\n'
        '- 独立于现有保命层，专门处理“当前自己已经不可信”的事故场景\n'
        '- 流程：留证 -> 选快照 -> 生成恢复计划 -> 隔离排障 -> 白名单自修 -> 验证\n'
        '- 独立入口：`scripts/openclaw-incident-recovery.py`\n'
        '- 独立状态目录：`~/.local/state/openclaw/incident-recovery/`\n'
        '- 不复用 repair runner 的内部状态；不在坏状态下直接覆盖生产态\n\n'
        '## 二、已纳入的事故模式（v2 / 2026-07-07）\n\n'
        '### 1. `modelOverrideSource=auto` 的 fallback override 钉死\n'
        '- `detect_auto_override_sessions()` 会扫 sessions.json，收集 modelOverrideSource=auto 的会话\n'
        '- 输出：`autoOverrideRecovery`，区分 user override 与 auto override\n'
        '- 现状：只输出安全清理方案，不直接改现网\n\n'
        '### 2. `transcript repair` / `gateway restart` / `synthetic toolResult`\n'
        '- `detect_transcript_repair_signals()` 结构化扫描主 session jsonl\n'
        '- `real_events`（真实事件）与 `noise`（toolResult 文本回声）严格区分\n'
        '- 真实事件识别字段：`assistant` 角色 + `provider=openclaw` + `model=gateway-injected`\n'
        '  或 assistant 错误文本含 `inserted synthetic error result for transcript repair`\n'
        '- 输出：`transcriptRepairRecovery.real_events` / `noise`\n\n'
        '### 3. `reply session initialization conflicted for agent:main:main`\n'
        '- `detect_reply_init_conflict_signals()` 同样结构化扫描\n'
        '- 字段：assistant 文本含 `reply session initialization conflicted/failed`/`activeWork`，'
        '或 `kind=error` 事件含同样字面量\n'
        '- 输出：`replyInitRecovery.severity`，含 `noise / degrading / activeWork_deadlock`\n\n'
        '## 三、Severity 分级与运行策略\n\n'
        '`classify_overall_severity()` 汇总 transcript repair 与 reply-init 冲突，输出四级：\n\n'
        '| severity | 触发条件 | 策略 |\n'
        '|---|---|---|\n'
        '| `none` | 两条事故模式都没真实事件命中 | `observe`：前台轻交互继续 |\n'
        '| `noise` | 只有 toolResult 文本回声，没有真实事件 | `observe_with_supervisor`：后台监工保持常驻，前台继续 |\n'
        '| `degrading` | 真实事件 ≥1 条，但没形成持续性 deadlock | `background_supervisor_with_light_foreground` |\n'
        '| `activeWork_deadlock` | transcript repair 与 reply-init 同时出现真实事件 | `isolate_and_split`：立即冻结主 transcript，重任务切到后台 subagent |\n\n'
        '### 运行策略收敛：“后台执行 + 监工常驻 + 前台轻交互”\n\n'
        '- **前台**：主会话只做触发 / 总结 / 审阅，不亲自跑长链 tool 调用、不读大文件\n'
        '- **后台**：重任务（事故修复 / 重写 / 编译 / 大量 read）一律交给 `sessions_spawn`，'
        '明确 `taskName`、`promptFile`、`model`，独立上下文\n'
        '- **监工**：incident-recovery / emergency-aggregator / health-collector / '
        'session-size-watcher / frontstage-guardian / repair-runner 持续采集证据，'
        '直到 severity 回到 noise / none 才退出\n'
        '- **隔离恢复**：当 severity=activeWork_deadlock 时，主会话不再读故障 transcript，'
        '直接通过 isolated prompt 把任务交给 subagent；监工在后台继续判定是否升级\n\n'
        '## 四、绝对边界（任何 severity 都不破）\n\n'
        '- 不修改当前主 session 内容（jsonl / sessions.json）\n'
        '- 不直接做 `openclaw sessions cleanup --enforce`\n'
        '- 不直接做 `gateway restart`\n'
        '- 不改 cron / systemd / gateway / openclaw 配置\n'
        '- 不动 modelOverrideSource=`user` 的会话；auto override 也只输出清理方案不直接改\n\n'
        '## 五、当前能力（截至 2026-07-07）\n\n'
        '- 抓运行时证据（emergency / health / frontstage / openclaw status / system-summary / backup）\n'
        '- 扫描 auto override / transcript repair（结构化） / reply-init（结构化） 真实事件与 noise\n'
        '- 选择最近可用快照并附属于计划\n'
        '- 汇总 severity 分级，决定是否切到 isolate_and_split\n'
        '- 生成恢复计划（含 `severity` / `runtimeStrategy` / `transcriptRepairRecovery` / `replyInitRecovery`）\n'
        '- 写入 isolation prompt，显式带上 severity 与运行策略\n'
        '- 为后续自动 / 半自动恢复留接口（不直接动 gateway / cron / 配置）\n\n'
        '## 六、回归脚本\n\n'
        '- `scripts/openclaw-incident-recovery-regression.py`\n'
        '- 覆盖：plan/status、auto override / transcript repair / reply-init 三类事故模式段、'
        'severity 分级、no-snapshot fallback、isolation prompt 含策略、不动主 session 的最小边界\n'
        '- 结果写到 `recovery-log.jsonl`，可重放\n',
        encoding='utf-8',
    )


def update_status(reason: str, evidence: dict[str, Any], backup: dict[str, Any], plan: dict[str, Any], prompt_path: str) -> dict[str, Any]:
    # plan 是 build_recovery_plan 返回的 {'path': ..., 'data': ...} 包装
    inner = plan.get('data') if isinstance(plan, dict) and 'data' in plan else plan
    severity = (inner.get('severity') if isinstance(inner, dict) else None) or {'severity': 'none', 'strategy': 'observe'}
    status = {
        'updatedAt': NOW.isoformat(),
        'reason': reason,
        'phase': 'planned',
        'severity': severity.get('severity'),
        'strategy': severity.get('strategy'),
        'runtimeStrategy': inner.get('runtimeStrategy') if isinstance(inner, dict) else None,
        'evidencePath': evidence['path'],
        'backupFound': backup.get('found', False),
        'backupCandidate': backup.get('candidate'),
        'planPath': plan['path'],
        'isolatedPromptPath': prompt_path,
    }
    save_json(STATUS_JSON, status)
    append_log(status)
    return status


def spawn_instruction(status: dict[str, Any]) -> dict[str, Any]:
    prompt_path = status.get('isolatedPromptPath')
    return {
        'recommendedTool': 'sessions_spawn',
        'label': 'incident-recovery-isolated',
        'model': 'minimax/MiniMax-M3',
        'taskName': 'incident_recovery_isolated',
        'promptFile': prompt_path,
        'note': '由主会话按独立事故自救链拉起隔离分身；不要在坏状态主上下文里直接继续判断。',
    }


def cmd_plan(reason: str) -> int:
    ensure_dirs()
    write_doc()
    evidence = collect_runtime_evidence(reason)
    backup = choose_backup_candidate()
    plan = build_recovery_plan(reason, evidence, backup)
    prompt = build_isolated_prompt(reason, evidence, backup, plan)
    prompt_path = PLANS_DIR / f'isolated-recovery-prompt-{NOW.strftime("%Y-%m-%dT%H%M%S")}.txt'
    prompt_path.write_text(prompt, encoding='utf-8')
    status = update_status(reason, evidence, backup, plan, str(prompt_path))
    status['spawnInstruction'] = spawn_instruction(status)
    save_json(STATUS_JSON, status)
    print(json.dumps({'ok': True, 'status': status}, ensure_ascii=False, indent=2))
    return 0


def cmd_status() -> int:
    ensure_dirs()
    data = load_json(STATUS_JSON) or {}
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='OpenClaw 独立事故自救链（第一版）')
    sub = parser.add_subparsers(dest='action', required=True)

    plan = sub.add_parser('plan', help='抓证据、选快照、生成恢复计划')
    plan.add_argument('--reason', default='suspected-model-or-session-incident')

    sub.add_parser('status', help='查看当前事故自救状态')

    args = parser.parse_args()
    if args.action == 'plan':
        return cmd_plan(args.reason)
    if args.action == 'status':
        return cmd_status()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
