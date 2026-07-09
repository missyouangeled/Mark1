#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SH_TZ = timezone(timedelta(hours=8))
NOW = datetime.now(SH_TZ)
HOME = Path.home()
WORKSPACE = HOME / '.openclaw' / 'workspace'
STATE_DIR = HOME / '.local' / 'state' / 'openclaw' / 'emergency-aggregator'
STATUS_JSON = STATE_DIR / 'status.json'
EVENTS_JSONL = STATE_DIR / 'events.jsonl'
SNAPSHOT_MD = WORKSPACE / 'docs' / 'runtime' / '保命状态快照.md'
FAILURES_MD = WORKSPACE / 'docs' / 'runtime' / 'EMERGENCY_FAILURES.md'
SESSIONS_DIR = HOME / '.openclaw' / 'agents' / 'main' / 'sessions'
WATCHER_DIR = HOME / '.local' / 'state' / 'openclaw' / 'session-size-watcher'
BACKUP_DIR = Path('/mnt/data/openclaw/session-backup')
FRONTSTAGE_DIR = HOME / '.local' / 'state' / 'openclaw' / 'frontstage-guardian'
HEALTH_DIR = HOME / '.local' / 'state' / 'openclaw' / 'health-collector'
CONFIG_JSON = WORKSPACE / 'scripts' / 'emergency0-config.json'
CRON_JOB_ID = 'b560cd2c-b4e3-415c-96f7-3074e8f11f62'

OK = 'OK'
WARN = 'WARN'
CRITICAL = 'CRITICAL'
DEADMAN = 'DEADMAN'

DEFAULTS = {
    'trajectoryWarnMb': 5.0,
    'staleWatcherHours': 1.0,
    'backupWarnMinutes': 15,
    'backupDeadmanMinutes': 25,
    'healthStaleMinutes': 10,
    'frontstageStaleMinutes': 10,
    'healthCriticalGraceMinutes': 2,
}
CONFIG = {**DEFAULTS, **(json.loads(CONFIG_JSON.read_text()) if CONFIG_JSON.exists() else {})}
TRAJECTORY_WARN_MB = float(CONFIG['trajectoryWarnMb'])
STALE_WATCHER_HOURS = float(CONFIG['staleWatcherHours'])
BACKUP_WARN_MINUTES = float(CONFIG['backupWarnMinutes'])
BACKUP_DEADMAN_MINUTES = float(CONFIG['backupDeadmanMinutes'])
HEALTH_STALE_MINUTES = float(CONFIG['healthStaleMinutes'])
FRONTSTAGE_STALE_MINUTES = float(CONFIG['frontstageStaleMinutes'])
HEALTH_CRITICAL_GRACE_MINUTES = float(CONFIG['healthCriticalGraceMinutes'])


@dataclass
class Finding:
    level: str
    code: str
    message: str


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_MD.parent.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def load_previous_status() -> dict[str, Any]:
    data = load_json(STATUS_JSON)
    return data if isinstance(data, dict) else {}


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s).astimezone(SH_TZ)
    except Exception:
        return None


def parse_json_text(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def parse_ts_compact(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%dT%H%M%S').replace(tzinfo=SH_TZ)
    except Exception:
        return None


def age_minutes(dt: datetime | None) -> float | None:
    if not dt:
        return None
    return (NOW - dt).total_seconds() / 60.0


def age_hours(dt: datetime | None) -> float | None:
    if not dt:
        return None
    return (NOW - dt).total_seconds() / 3600.0


def is_after(left: datetime | None, right: datetime | None) -> bool:
    return bool(left and right and left > right)


def file_mb(path: Path) -> float:
    try:
        return path.stat().st_size / 1024 / 1024
    except Exception:
        return 0.0


def summarize_watcher_alerts(data: dict[str, Any] | None, main_session: dict[str, Any], watcher_state: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {'unread': False, 'items': [], 'summary': '', 'activeItems': [], 'staleItems': [], 'resolvedItems': []}
    items = data.get('items', []) or []
    levels: dict[str, int] = {}
    active_items: list[dict[str, Any]] = []
    stale_items: list[dict[str, Any]] = []
    resolved_items: list[dict[str, Any]] = []
    current_traj_mb = float(main_session.get('trajectoryMb') or 0)
    watcher_last_success = parse_iso(
        (watcher_state or {}).get('last_successful_run') or (watcher_state or {}).get('last_success_run')
    )
    for it in items:
        lv = str(it.get('level', '?'))
        levels[lv] = levels.get(lv, 0) + 1
        t = parse_iso(it.get('time'))
        ah = age_hours(t)
        detail = it.get('detail') or {}
        traj_mb = float(detail.get('trajectory_mb') or 0)
        enriched = dict(it)
        enriched['ageHours'] = ah
        enriched['trajectoryMb'] = traj_mb
        enriched['resolved'] = False
        # watcher 已在该告警之后再次成功运行，且当前主 trajectory 已回落到阈值下，视为已消化历史尾巴
        if is_after(watcher_last_success, t) and current_traj_mb < TRAJECTORY_WARN_MB:
            enriched['resolved'] = True
            resolved_items.append(enriched)
        elif traj_mb >= TRAJECTORY_WARN_MB and ah is not None and ah <= STALE_WATCHER_HOURS:
            active_items.append(enriched)
        else:
            stale_items.append(enriched)
    summary = ', '.join(f'{k}={v}' for k, v in sorted(levels.items()))
    return {
        'unread': bool(data.get('unread')),
        'items': items,
        'summary': summary,
        'activeItems': active_items,
        'staleItems': stale_items,
        'resolvedItems': resolved_items,
    }


def latest_backup_info() -> dict[str, Any]:
    manifest = load_json(BACKUP_DIR / 'backup-manifest.json') or {}
    snaps = manifest.get('snapshots', []) or []
    latest = snaps[-1] if snaps else None
    latest_dt = parse_ts_compact(latest.get('timestamp')) if latest else None
    return {
        'latest': latest,
        'latestAt': iso(latest_dt),
        'ageMinutes': age_minutes(latest_dt),
        'count': len(snaps),
    }


def get_main_session_info() -> dict[str, Any]:
    sessions = load_json(SESSIONS_DIR / 'sessions.json') or {}
    main = sessions.get('agent:main:main', {}) or {}
    session_file = Path(main.get('sessionFile') or (SESSIONS_DIR / f"{main.get('sessionId','')}.jsonl"))
    lines = 0
    if session_file.exists():
        try:
            with session_file.open('r', encoding='utf-8', errors='ignore') as f:
                for lines, _ in enumerate(f, start=1):
                    pass
        except Exception:
            lines = 0
    traj_file = SESSIONS_DIR / f"{main.get('sessionId','')}.trajectory.jsonl"
    return {
        'sessionId': main.get('sessionId'),
        'sessionFile': str(session_file),
        'updatedAtMs': main.get('updatedAt'),
        'lastInteractionAt': main.get('lastInteractionAt'),
        'status': main.get('status'),
        'lines': lines,
        'jsonlMb': file_mb(session_file),
        'trajectoryMb': file_mb(traj_file),
        'totalTokens': main.get('totalTokens'),
        'contextTokens': main.get('contextTokens'),
        'model': main.get('model'),
    }


def get_cron_info() -> dict[str, Any]:
    rc, out, _ = run(['openclaw', 'cron', 'get', CRON_JOB_ID])
    if rc != 0:
        return {'ok': False}
    data = json.loads(out)
    state = data.get('state', {}) or {}
    last_run = state.get('lastRunAtMs')
    last_dt = datetime.fromtimestamp(last_run / 1000, tz=SH_TZ) if last_run else None
    return {
        'ok': True,
        'name': data.get('name'),
        'enabled': data.get('enabled'),
        'lastRunStatus': state.get('lastRunStatus'),
        'lastDiagnosticSummary': state.get('lastDiagnosticSummary'),
        'lastRunAt': iso(last_dt),
        'lastRunAgeMinutes': age_minutes(last_dt),
        'consecutiveErrors': state.get('consecutiveErrors'),
    }


def get_systemd_units() -> dict[str, Any]:
    rc, out, err = run(['systemctl', '--user', 'list-units', 'openclaw-*', 'mark42-*', '--no-pager', '--plain', '--all'])
    return {'ok': rc == 0, 'raw': out if rc == 0 else err}


def parse_unit_health(raw: str) -> list[dict[str, str]]:
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if (
            not line
            or line.startswith('UNIT ')
            or line.startswith('Legend:')
            or line.startswith('To show')
            or line.endswith('loaded units listed.')
        ):
            continue
        parts = re.split(r'\s+', line, maxsplit=4)
        if len(parts) >= 4:
            rows.append({
                'unit': parts[0],
                'load': parts[1],
                'active': parts[2],
                'sub': parts[3],
                'description': parts[4] if len(parts) >= 5 else '',
            })
    return rows


def get_frontstage_info() -> dict[str, Any]:
    data = load_json(FRONTSTAGE_DIR / 'last-report.json') or {}
    checked = parse_iso(data.get('checkedAt'))
    return {
        'ok': data.get('ok'),
        'overall': data.get('overall'),
        'summary': data.get('summary'),
        'checkedAt': data.get('checkedAt'),
        'ageMinutes': age_minutes(checked),
    }


def get_health_info() -> dict[str, Any]:
    data = load_json(HEALTH_DIR / 'last-report.json') or {}
    checked = parse_iso(data.get('checkedAt'))
    checks = data.get('checks') or []
    degraded = []
    for c in checks:
        embedded = parse_json_text(c.get('stdoutRaw'))
        embedded_ok = embedded.get('ok') if embedded else None
        blocked_main = bool(embedded.get('blockedMain')) if embedded else False
        total_stuck = embedded.get('totalStuck') if embedded else None
        is_bad = c.get('ok') is False or c.get('degraded') is True or embedded_ok is False or blocked_main
        if is_bad:
            summary = c.get('summary')
            if embedded and embedded.get('summary'):
                summary = embedded.get('summary')
            degraded.append({
                'label': c.get('label'),
                'summary': summary,
                'blockedMain': blocked_main,
                'embeddedOk': embedded_ok,
                'totalStuck': total_stuck,
            })
    return {
        'ok': data.get('ok'),
        'overall': data.get('overall'),
        'summary': data.get('summary'),
        'checkedAt': data.get('checkedAt'),
        'ageMinutes': age_minutes(checked),
        'degradedChecks': degraded,
    }


def summarize_repair_state() -> str:
    data = load_json(STATE_DIR / 'repair-state.json') or {}
    actions = data.get('actions') or {}
    if not actions:
        return '无 repair 状态'
    parts = []
    for name in sorted(actions.keys()):
        item = actions.get(name) or {}
        flag = 'ok' if item.get('lastOk') else 'fail'
        parts.append(f'{name}={flag}')
    return ', '.join(parts)


def determine(findings: list[Finding]) -> str:
    if any(f.level == DEADMAN for f in findings):
        return DEADMAN
    if any(f.level == CRITICAL for f in findings):
        return CRITICAL
    if any(f.level == WARN for f in findings):
        return WARN
    return OK


def append_event(event: dict[str, Any]) -> None:
    with EVENTS_JSONL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')


def classify_event(previous: dict[str, Any], current: dict[str, Any]) -> str:
    prev_overall = previous.get('overall')
    prev_codes = previous.get('findings') or []
    prev_codes = [item.get('code') for item in prev_codes if isinstance(item, dict)]
    curr_codes = [item.get('code') for item in current.get('findings') or [] if isinstance(item, dict)]
    if prev_overall != current.get('overall'):
        return 'level_change'
    if prev_codes != curr_codes:
        return 'finding_change'
    return 'heartbeat'


def maybe_record_failure(findings: list[Finding]) -> None:
    failures = [f for f in findings if f.level in (CRITICAL, DEADMAN)]
    if not failures:
        return
    lines = [
        f'## {NOW.isoformat()}',
        '',
    ]
    for f in failures:
        lines.append(f'- [{f.level}] {f.code}: {f.message}')
    lines.append('')
    with FAILURES_MD.open('a', encoding='utf-8') as fp:
        fp.write('\n'.join(lines) + '\n')


def build_snapshot(data: dict[str, Any], findings: list[Finding]) -> str:
    ms = data['mainSession']
    watcher = data['watcher']
    backup = data['backup']
    cron = data['cron']
    front = data['frontstage']
    health = data['health']
    units = data['units']

    lines = [
        '# 保命状态快照',
        '',
        f'- 生成时间：{NOW.isoformat()}',
        f'- 总体状态：**{data["overall"]}**',
        '',
        '## 核心指标',
        '',
        f'- 主 session：`{ms.get("sessionId")}`',
        f'- 主 jsonl 行数：{ms.get("lines")}',
        f'- 主 jsonl 大小：{ms.get("jsonlMb"):.2f} MB',
        f'- trajectory 大小：{ms.get("trajectoryMb"):.2f} MB',
        f'- watcher 未读：{watcher.get("unread")}',
        f'- watcher 活跃告警：{len(watcher.get("activeItems") or [])}',
        f'- watcher 历史未清：{len(watcher.get("staleItems") or [])}',
        f'- watcher 已消化历史告警：{len(watcher.get("resolvedItems") or [])}',
        f'- watcher 摘要：{watcher.get("summary") or "无"}',
        f'- 救命 1 最近运行：{cron.get("lastRunAt") or "未知"} / {cron.get("lastRunStatus") or "未知"}',
        f'- frontstage：{front.get("overall") or "未知"} / {front.get("summary") or "无"}',
        f'- health：{health.get("overall") or "未知"} / {health.get("summary") or "无"}',
        f'- backup 最近快照：{backup.get("latestAt") or "未知"}',
        f'- repair 运行状态：{data.get("repairSummary") or "未知"}',
        '',
        '## 风险判定',
        '',
    ]
    if findings:
        for f in findings:
            lines.append(f'- [{f.level}] {f.code}: {f.message}')
    else:
        lines.append('- 无明显风险点')
    lines.extend([
        '',
        '## systemd 单元摘要',
        '',
    ])
    for row in units[:20]:
        lines.append(f'- `{row["unit"]}`: {row["active"]}/{row["sub"]}')
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    ensure_dirs()
    previous_status = load_previous_status()

    watcher_state = load_json(WATCHER_DIR / 'state.json') or {}
    backup = latest_backup_info()
    main_session = get_main_session_info()
    watcher_raw = load_json(WATCHER_DIR / 'alerts.json') or {}
    watcher = summarize_watcher_alerts(watcher_raw, main_session, watcher_state)
    cron = get_cron_info()
    front = get_frontstage_info()
    health = get_health_info()
    units_raw = get_systemd_units()
    units = parse_unit_health(units_raw.get('raw', '')) if units_raw.get('ok') else []

    findings: list[Finding] = []

    active_alerts = watcher.get('activeItems') or []
    stale_alerts = watcher.get('staleItems') or []
    resolved_alerts = watcher.get('resolvedItems') or []
    if active_alerts:
        findings.append(Finding(WARN, 'WATCHER_ACTIVE_ALERTS', f"session-size-watcher 仍有活跃 trajectory 告警：{len(active_alerts)} 条"))
    elif watcher.get('unread') and stale_alerts:
        findings.append(Finding(WARN, 'WATCHER_STALE_UNREAD', f"session-size-watcher 有 {len(stale_alerts)} 条历史未清告警，当前更像待确认而非现行故障"))

    traj_mb = float(main_session.get('trajectoryMb') or 0)
    if traj_mb >= TRAJECTORY_WARN_MB + 2:
        findings.append(Finding(CRITICAL, 'TRAJECTORY_TOO_LARGE', f'当前主 trajectory {traj_mb:.2f}MB，已明显超过 {TRAJECTORY_WARN_MB:.1f}MB watcher 阈值'))
    elif traj_mb >= TRAJECTORY_WARN_MB:
        findings.append(Finding(WARN, 'TRAJECTORY_OVER_THRESHOLD', f'当前主 trajectory {traj_mb:.2f}MB，超过 {TRAJECTORY_WARN_MB:.1f}MB watcher 阈值'))

    line_count = int(main_session.get('lines') or 0)
    if line_count >= 12000:
        findings.append(Finding(CRITICAL, 'SESSION_LINES_HIGH', f'当前主 session 行数 {line_count} >= 12000'))
    elif line_count >= 8000:
        findings.append(Finding(WARN, 'SESSION_LINES_RISING', f'当前主 session 行数 {line_count}，接近保命阈值 12000'))

    backup_age = backup.get('ageMinutes')
    if backup_age is None or backup_age > BACKUP_DEADMAN_MINUTES:
        findings.append(Finding(DEADMAN, 'BACKUP_STALE', f'backup 最近快照超过 {BACKUP_DEADMAN_MINUTES:.0f} 分钟或无法读取（age={backup_age}）'))
    elif backup_age > BACKUP_WARN_MINUTES:
        findings.append(Finding(WARN, 'BACKUP_SLOW', f'backup 最近快照已 {backup_age:.1f} 分钟未更新'))

    cron_age = cron.get('lastRunAgeMinutes')
    if not cron.get('ok'):
        findings.append(Finding(DEADMAN, 'CRON_UNREADABLE', '无法读取救命 1 cron 状态'))
    elif cron_age is None or cron_age > 15:
        findings.append(Finding(DEADMAN, 'CRON_STALE', f'救命 1 最近成功运行距离现在超过 15 分钟（age={cron_age}）'))
    elif cron.get('lastRunStatus') != 'ok':
        findings.append(Finding(CRITICAL, 'CRON_NOT_OK', f'救命 1 最近状态不是 ok：{cron.get("lastRunStatus")}'))

    if front.get('ok') is False or (front.get('ageMinutes') is not None and front['ageMinutes'] > FRONTSTAGE_STALE_MINUTES):
        findings.append(Finding(WARN, 'FRONTSTAGE_STALE', f'frontstage 状态异常或过旧（age={front.get("ageMinutes")})'))

    health_age = health.get('ageMinutes')
    if health.get('ok') is False or (health_age is not None and health_age > HEALTH_STALE_MINUTES):
        findings.append(Finding(WARN, 'HEALTH_STALE', f'health-collector 状态异常或过旧（age={health_age})'))
    for c in health.get('degradedChecks') or []:
        blocked_main = bool(c.get('blockedMain'))
        level = CRITICAL if blocked_main else WARN
        code = f"HEALTH_{str(c.get('label') or 'CHECK').upper().replace('-', '_')}"
        message = f"health-collector 子检查异常：{c.get('label')} / {c.get('summary')}"
        if blocked_main and health_age is not None and health_age > HEALTH_CRITICAL_GRACE_MINUTES:
            level = WARN
            code = f"{code}_STALE_SNAPSHOT"
            message += f'（已超过 {HEALTH_CRITICAL_GRACE_MINUTES:.0f} 分钟宽限，按旧坏快照降级处理）'
        findings.append(Finding(level, code, message))

    bad_units = [
        u for u in units
        if u['load'] == 'loaded' and (u['active'] == 'failed' or u['sub'] == 'failed')
    ]
    if bad_units:
        findings.append(Finding(CRITICAL, 'SYSTEMD_INACTIVE', '存在 inactive/failed 的 openclaw/mark42 单元：' + ', '.join(u['unit'] for u in bad_units[:5])))

    overall = determine(findings)

    payload = {
        'generatedAt': NOW.isoformat(),
        'overall': overall,
        'findings': [f.__dict__ for f in findings],
        'mainSession': main_session,
        'watcher': watcher,
        'watcherStateLastSuccess': (watcher_state or {}).get('last_successful_run') or (watcher_state or {}).get('last_success_run'),
        'watcherResolvedCount': len(resolved_alerts),
        'backup': backup,
        'cron': cron,
        'frontstage': front,
        'health': health,
        'repairSummary': summarize_repair_state(),
        'units': units,
    }

    STATUS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    SNAPSHOT_MD.write_text(build_snapshot(payload, findings), encoding='utf-8')

    event_kind = classify_event(previous_status, payload)
    append_event({
        'ts': NOW.isoformat(),
        'kind': event_kind,
        'overall': overall,
        'findingCodes': [f.code for f in findings],
    })
    maybe_record_failure(findings)

    print(f'[emergency0] overall={overall} findings={len(findings)} status={STATUS_JSON}')
    if findings:
        for f in findings:
            print(f'[{f.level}] {f.code}: {f.message}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
