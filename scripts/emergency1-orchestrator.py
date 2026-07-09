#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOME = Path.home()
WORKSPACE = HOME / '.openclaw' / 'workspace'
SESSIONS_DIR = HOME / '.openclaw' / 'agents' / 'main' / 'sessions'
WATCHER_ALERTS = HOME / '.local' / 'state' / 'openclaw' / 'session-size-watcher' / 'alerts.json'
ALERT_FLAG = Path('/tmp/emergency1-alert.flag')
FORWARD_FLAG = Path('/tmp/emergency1-watcher-alert.flag')
LINE_THRESHOLD = 12000
COOLDOWN_MINUTES = 30


@dataclass
class StepResult:
    ok: bool
    output: str


def run(cmd: list[str]) -> StepResult:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = ((proc.stdout or '') + (proc.stderr or '')).strip()
    return StepResult(proc.returncode == 0, output)


def cooldown_hit(path: Path) -> bool:
    if not path.exists():
        return False
    age_seconds = max(0.0, __import__('time').time() - path.stat().st_mtime)
    return age_seconds < COOLDOWN_MINUTES * 60


def touch(path: Path) -> None:
    path.touch()


def load_main_session_meta() -> dict[str, Any]:
    p = SESSIONS_DIR / 'sessions.json'
    if not p.exists():
        return {'main_sid': '', 'main_file': ''}
    try:
        data = json.loads(p.read_text())
    except Exception:
        return {'main_sid': '', 'main_file': ''}
    main = (data.get('agent:main:main') or {}) if isinstance(data, dict) else {}
    sid = main.get('sessionId', '')
    session_file = main.get('sessionFile', '') or str(SESSIONS_DIR / f'{sid}.jsonl')
    return {'main_sid': sid, 'main_file': session_file}


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        return sum(1 for _ in f)


def run_core_pipeline(outputs: list[str]) -> bool:
    for name in ('emergency0-aggregator.py', 'emergency0-notify.py', 'emergency0-repair-runner.py'):
        result = run(['python3', str(WORKSPACE / 'scripts' / name)])
        if not result.ok:
            outputs.append(f'[救命 1 错误] {name} 执行失败')
            if result.output:
                outputs.append(result.output)
            return False
    return True


def maybe_alert_main(outputs: list[str]) -> bool:
    meta = load_main_session_meta()
    sid = meta.get('main_sid') or ''
    session_file = Path(meta.get('main_file') or '')
    if not sid or not session_file.exists():
        outputs.append(f'[救命 1 错误] 主 session 文件不存在或无法解析: sid={sid} file={session_file}')
        return False

    lines = count_lines(session_file)
    if lines > LINE_THRESHOLD:
        if cooldown_hit(ALERT_FLAG):
            outputs.append(f'[救命 1 静默（cooldown）] sid={sid} LINES={lines}')
            return True
        message = (
            f'[救命 1 告警] 当前逻辑 main session 行数 {lines} > {LINE_THRESHOLD}。'
            f'sessionId: {sid}。按 CASE-20260706-005 不动 session，建议人工处理。'
        )
        result = run([
            'python3',
            str(WORKSPACE / 'scripts' / 'openclaw-proactive-inject.py'),
            '--source',
            'emergency-1-alert',
            message,
        ])
        if result.ok:
            touch(ALERT_FLAG)
            outputs.append(f'[救命 1 告警已发] sid={sid} LINES={lines}')
            return True
        outputs.append(f'[救命 1 注入失败] sid={sid} LINES={lines}')
        if result.output:
            outputs.append(result.output)
        return False

    if ALERT_FLAG.exists():
        ALERT_FLAG.unlink()
    outputs.append(f'[救命 1 静默] session={sid} LINES={lines}')
    return True


def maybe_forward_watcher(outputs: list[str]) -> bool:
    if not WATCHER_ALERTS.exists():
        return True
    read = run([
        'python3',
        str(WORKSPACE / 'scripts' / 'emergency1-watcher-read.py'),
        str(WATCHER_ALERTS),
    ])
    if not read.ok:
        if read.output:
            outputs.append(read.output)
        return False
    if 'UNREAD_SUMMARY=' not in read.output:
        return True

    if cooldown_hit(FORWARD_FLAG):
        outputs.append('[救命 1 watcher 告警 cooldown]')
        return True

    summary = ''
    details: list[str] = []
    for line in read.output.splitlines():
        if line.startswith('UNREAD_SUMMARY='):
            summary = line[len('UNREAD_SUMMARY='):]
        elif line.startswith('WARN:'):
            details.append(line)
    message = (
        f'[救命 1 watcher 转发] session-size-watcher 未读告警: {summary}\n'
        + '\n'.join(details[:3])
        + '\n（按 docs/系统自动行为盘点.md 第 7 节 P0 修复：观察并自动转发 alerts）'
    )
    inject = run([
        'python3',
        str(WORKSPACE / 'scripts' / 'openclaw-proactive-inject.py'),
        '--source',
        'emergency-1-watcher-forward',
        message,
    ])
    if not inject.ok:
        outputs.append(f'[救命 1 watcher 注入失败] {summary}')
        if inject.output:
            outputs.append(inject.output)
        return False

    mark = run([
        'python3',
        str(WORKSPACE / 'scripts' / 'emergency1-watcher-read.py'),
        str(WATCHER_ALERTS),
        '--mark',
    ])
    if not mark.ok:
        outputs.append(f'[救命 1 watcher mark 失败] {summary}')
        if mark.output:
            outputs.append(mark.output)
        return False
    touch(FORWARD_FLAG)
    outputs.append(f'[救命 1 watcher 告警已转] {summary}')
    return True


def main() -> int:
    outputs: list[str] = []
    if not run_core_pipeline(outputs):
        print('\n'.join(outputs))
        return 1
    if not maybe_alert_main(outputs):
        print('\n'.join(outputs))
        return 1
    if not maybe_forward_watcher(outputs):
        print('\n'.join(outputs))
        return 1
    print('\n'.join(outputs))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
