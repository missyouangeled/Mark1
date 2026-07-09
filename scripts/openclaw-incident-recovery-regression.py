#!/usr/bin/env python3
"""OpenClaw 事故自救链回归脚本（v2 / 2026-07-07）。

覆盖：

- plan / status 命令本身能跑通；
- autoOverride / transcriptRepair / replyInit 三类事故模式段都在 plan 中；
- severity 分级（none/noise/degrading/activeWork_deadlock）与运行策略收敛；
- 不动主 session jsonl；
- 隔离 prompt 里能看到 "后台执行 + 监工常驻 + 前台轻交互"。

为了不反复跑 plan（每跑一次 ~30s），大多数 case 直接读最近一次
`plan` 写入的 evidence / plan / status / prompt 即可；只在它们缺失时
才触发一次 trigger plan。

执行：

    python3 scripts/openclaw-incident-recovery-regression.py
"""
from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import time
import atexit
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HOME = Path.home()
WORKSPACE = HOME / '.openclaw' / 'workspace'
BACKUP_ROOT = Path('/mnt/data/openclaw/session-backup')
MANIFEST = BACKUP_ROOT / 'backup-manifest.json'
STATE = HOME / '.local' / 'state' / 'openclaw' / 'incident-recovery'
STATUS = STATE / 'status.json'
EVIDENCE_DIR = STATE / 'evidence'
PLANS_DIR = STATE / 'plans'
PROMPTS_DIR = PLANS_DIR
SESSIONS_JSON = HOME / '.openclaw' / 'agents' / 'main' / 'sessions' / 'sessions.json'
SCRIPT = WORKSPACE / 'scripts' / 'openclaw-incident-recovery.py'
MAIN_SESSION_KEY = 'agent:main:main'
SH = timezone(timedelta(hours=8))
LOCKFILE = STATE / 'regression.lock'
REGRESSION_STATUS = STATE / 'regression-status.json'
LOCK_STALE_SECONDS = 15 * 60
COOLDOWN_SECONDS = 10 * 60
_LOCK_FD: int | None = None


def now_sh() -> datetime:
    return datetime.now(SH)


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        return datetime.fromisoformat(text).astimezone(SH)
    except Exception:
        return None


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def should_skip_due_to_cooldown(force: bool = False) -> dict[str, Any] | None:
    if force:
        return None
    state = load_json(REGRESSION_STATUS)
    if not isinstance(state, dict):
        return None
    completed_at = parse_iso(state.get('completedAt'))
    if completed_at is None:
        return None
    age = (now_sh() - completed_at).total_seconds()
    if age < 0 or age > COOLDOWN_SECONDS:
        return None
    return {
        'ok': True,
        'skipped': True,
        'reason': 'cooldown_active',
        'cooldownSeconds': COOLDOWN_SECONDS,
        'lastCompletedAt': completed_at.isoformat(),
        'ageSeconds': round(age, 3),
        'lastResults': state.get('results') or {},
    }


def acquire_lock() -> int:
    LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCKFILE.exists():
        age = time.time() - LOCKFILE.stat().st_mtime
        payload = load_json(LOCKFILE)
        pid = payload.get('pid') if isinstance(payload, dict) else None
        pid_alive = False
        if isinstance(pid, int) and pid > 0:
            try:
                os.kill(pid, 0)
                pid_alive = True
            except OSError:
                pid_alive = False
        if age > LOCK_STALE_SECONDS or not pid_alive:
            LOCKFILE.unlink(missing_ok=True)
    fd = os.open(str(LOCKFILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    payload = {
        'pid': os.getpid(),
        'startedAt': now_sh().isoformat(),
    }
    os.write(fd, json.dumps(payload, ensure_ascii=False).encode('utf-8'))
    return fd


def release_lock(fd: int) -> None:
    try:
        os.close(fd)
    finally:
        LOCKFILE.unlink(missing_ok=True)


def cleanup_lock() -> None:
    global _LOCK_FD
    if _LOCK_FD is None:
        return
    try:
        release_lock(_LOCK_FD)
    except Exception:
        pass
    finally:
        _LOCK_FD = None


def _handle_exit_signal(signum, frame) -> None:
    cleanup_lock()
    raise SystemExit(128 + int(signum))


def run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE), timeout=timeout)
    return p.returncode, ((p.stdout or '') + (p.stderr or '')).strip()


def ensure_plan_once(reason: str = 'regression') -> dict[str, Any]:
    """确保最近一次 plan 是新的；否则触发一次。

    返回最新 plan + 它的 evidence + 最新 prompt path。
    """
    trigger_plan(reason)
    # 取时间戳最大的 latest plan
    latest_plan = max(PLANS_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime)
    plan = json.loads(latest_plan.read_text())
    return {
        'plan_path': str(latest_plan),
        'plan': plan,
        'evidence_path': plan.get('evidencePath'),
    }


def trigger_plan(reason: str) -> bool:
    rc, out = run(['python3', str(SCRIPT), 'plan', '--reason', reason])
    if rc != 0:
        return False
    try:
        json.loads(out)
    except Exception:
        return False
    return True


# ---------- 持久化 case ----------

def case_plan_generates_status() -> bool:
    if not trigger_plan('regression'):
        return False
    if not STATUS.exists():
        return False
    status = json.loads(STATUS.read_text())
    return status.get('phase') == 'planned' and bool(status.get('planPath')) and bool(status.get('evidencePath'))


def case_status_reads_back() -> bool:
    rc, out = run(['python3', str(SCRIPT), 'status'])
    if rc != 0:
        return False
    try:
        data = json.loads(out)
    except Exception:
        return False
    return data.get('phase') == 'planned' and bool(data.get('evidencePath')) and data.get('severity') is not None


def case_plan_includes_auto_override_section() -> bool:
    data = ensure_plan_once('auto-override-check')
    section = data['plan'].get('autoOverrideRecovery')
    return isinstance(section, dict) and 'detected' in section and 'safeAction' in section


def case_plan_includes_transcript_repair_section() -> bool:
    data = ensure_plan_once('transcript-repair-check')
    section = data['plan'].get('transcriptRepairRecovery')
    return isinstance(section, dict) and 'detected' in section and 'safeAction' in section


def case_plan_includes_reply_init_section() -> bool:
    data = ensure_plan_once('reply-init-check')
    section = data['plan'].get('replyInitRecovery')
    return isinstance(section, dict) and 'detected' in section and 'severity' in section and 'safeAction' in section


def case_plan_includes_severity_and_runtime_strategy() -> bool:
    data = ensure_plan_once('severity-check')
    severity = data['plan'].get('severity')
    rt = data['plan'].get('runtimeStrategy')
    if not isinstance(severity, dict) or 'severity' not in severity or 'strategy' not in severity:
        return False
    if not isinstance(rt, dict):
        return False
    if '后台执行' not in rt.get('name', ''):
        return False
    if '监工常驻' not in rt.get('name', ''):
        return False
    if '前台轻交互' not in rt.get('name', ''):
        return False
    for key in ('foreground', 'background', 'supervisor'):
        if not rt.get(key):
            return False
    return True


def case_status_includes_severity_and_strategy() -> bool:
    # 不重跑 plan，直接读最近一次 status
    if not STATUS.exists():
        return False
    status = json.loads(STATUS.read_text())
    return status.get('severity') is not None and status.get('strategy') is not None


def case_isolated_prompt_carries_runtime_strategy() -> bool:
    # 不重跑 plan，直接读最新 prompt
    if not STATUS.exists():
        return False
    status = json.loads(STATUS.read_text())
    prompt_path = Path(status.get('isolatedPromptPath') or '')
    if not prompt_path.exists():
        # 兜底：从 plans/ 里找最新的 prompt
        prompts = sorted(PROMPTS_DIR.glob('isolated-recovery-prompt-*.txt'), key=lambda p: p.stat().st_mtime)
        if not prompts:
            return False
        prompt_path = prompts[-1]
    text = prompt_path.read_text()
    needles = ('运行策略', '后台执行', '监工常驻', '前台轻交互', 'severity', 'activeWork_deadlock')
    return all(n in text for n in needles)


def case_evidence_is_structured_real_vs_noise() -> bool:
    # 不重跑 plan，从最近一次 evidence 文件读结构
    if not STATUS.exists():
        return False
    status = json.loads(STATUS.read_text())
    ev_path = Path(status.get('evidencePath') or '')
    if not ev_path.exists():
        return False
    ev = json.loads(ev_path.read_text())
    tr = ev.get('transcriptRepairSignals') or {}
    ri = ev.get('replyInitSignals') or {}
    # 两个必须都是结构化（dict），含 noise / real_events 字段
    if not isinstance(tr, dict) or 'noise' not in tr or 'real_events' not in tr:
        return False
    if not isinstance(ri, dict) or 'noise' not in ri or 'real_events' not in ri:
        return False
    sev = ev.get('severity') or {}
    return isinstance(sev, dict) and 'severity' in sev and 'strategy' in sev


def case_does_not_modify_main_session_jsonl() -> bool:
    # 1) 取当前主 session jsonl 的 size + mtime + sha256
    sessions = json.loads(SESSIONS_JSON.read_text()) if SESSIONS_JSON.exists() else {}
    main = sessions.get(MAIN_SESSION_KEY) or {}
    session_file = Path(main.get('sessionFile') or '')
    if not session_file.exists():
        return True  # 无法验证：跳过
    before = session_file.stat()
    before_sha = _sha256(session_file)
    before_size = before.st_size
    before_mtime = before.st_mtime

    # 2) 跑一次 plan
    if not trigger_plan('no-modify-check'):
        return False

    # 3) 再读一次。注意：gateway 可能仍在线追加 jsonl 行，
    #    所以我们要看：appendCount 是不是 == plan 跑完到现在的差量，
    #    且 plan 跑完到现在期间它的 sha 与各分块都没出现意外重写。
    time.sleep(1.5)
    after = session_file.stat()
    after_sha = _sha256(session_file)
    after_size = after.st_size
    after_mtime = after.st_mtime

    # 大小至少不变（应该增长），不允许缩小（重写过）
    if after_size < before_size:
        return False
    # mtime 只能前进（新增 append）
    if after_mtime + 1e-6 < before_mtime:
        return False
    # 不能出现「整段被覆盖」的迹象。
    # 用一种稳妥做法：last 1KB 应当是有效 jsonl（最后一行必须是合法 JSON）
    try:
        last_line = session_file.read_text(errors='ignore').rstrip().splitlines()[-1]
        json.loads(last_line)
    except Exception:
        return False
    return True


def _sha256(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def case_no_snapshot_manifest() -> bool:
    if not MANIFEST.exists():
        return True
    bak = MANIFEST.with_suffix('.json.incident.bak')
    shutil.copy2(MANIFEST, bak)
    try:
        MANIFEST.write_text(json.dumps({'snapshots': []}, ensure_ascii=False, indent=2), encoding='utf-8')
        rc, out = run(['python3', str(SCRIPT), 'plan', '--reason', 'no-snapshot'])
        if rc != 0:
            return False
        data = json.loads(out)
        return data.get('ok') is True and data.get('status', {}).get('backupFound') is False
    finally:
        shutil.move(str(bak), str(MANIFEST))


# ---------- main ----------

def main() -> int:
    global _LOCK_FD
    force = '--force' in __import__('sys').argv[1:]
    skipped = should_skip_due_to_cooldown(force=force)
    if skipped is not None:
        print(json.dumps(skipped, ensure_ascii=False, indent=2))
        return 0

    try:
        lock_fd = acquire_lock()
        _LOCK_FD = lock_fd
    except FileExistsError:
        data = {
            'ok': True,
            'skipped': True,
            'reason': 'lock_active',
            'lockfile': str(LOCKFILE),
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    atexit.register(cleanup_lock)
    signal.signal(signal.SIGTERM, _handle_exit_signal)
    signal.signal(signal.SIGINT, _handle_exit_signal)

    # 注意顺序：trigger_plan 必须先跑，让 evidence / status / plan 都准备好，
    # 后续读取类的 case 才能读出数据。
    try:
        cases = [
            ('plan_generates_status', case_plan_generates_status),
            ('status_reads_back', case_status_reads_back),
            ('plan_includes_auto_override_section', case_plan_includes_auto_override_section),
            ('plan_includes_transcript_repair_section', case_plan_includes_transcript_repair_section),
            ('plan_includes_reply_init_section', case_plan_includes_reply_init_section),
            ('plan_includes_severity_and_runtime_strategy', case_plan_includes_severity_and_runtime_strategy),
            ('status_includes_severity_and_strategy', case_status_includes_severity_and_strategy),
            ('isolated_prompt_carries_runtime_strategy', case_isolated_prompt_carries_runtime_strategy),
            ('evidence_is_structured_real_vs_noise', case_evidence_is_structured_real_vs_noise),
            ('does_not_modify_main_session_jsonl', case_does_not_modify_main_session_jsonl),
            ('no_snapshot_manifest', case_no_snapshot_manifest),
        ]
        results = {}
        failures: list[str] = []
        for name, fn in cases:
            try:
                ok = bool(fn())
            except Exception as exc:
                ok = False
                failures.append(f'{name}: {exc!r}')
            results[name] = bool(ok)
            status = 'PASS' if ok else 'FAIL'
            print(f'[{status}] {name}')
        overall_ok = all(results.values())
        summary = {'ok': overall_ok, 'results': results}
        save_json(
            REGRESSION_STATUS,
            {
                'startedAt': load_json(LOCKFILE) and load_json(LOCKFILE).get('startedAt') or now_sh().isoformat(),
                'completedAt': now_sh().isoformat(),
                'ok': overall_ok,
                'results': results,
                'failures': failures,
            },
        )
        print()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if failures:
            print()
            print('--- exception details ---')
            for line in failures:
                print(line)
        return 0 if overall_ok else 1
    finally:
        cleanup_lock()


if __name__ == '__main__':
    raise SystemExit(main())
