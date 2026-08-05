"""OpenClaw 配置文件安全写入适配器。

【2026-08-03 新增 — P0-3 C 方案】

## 为什么需要这个模块

`~/.openclaw/openclaw.json` 存着模型路由、Provider、API 密钥、Agent 配置——
它是整个 OpenClaw 的命门。这个文件写坏，Gateway 直接起不来。
历史教训：CASE-20260616-002「Python 脚本直写 openclaw.json 导致 Gateway 启动失败」，评级 High。

改造前，`context_safety.py` 和 `compaction_diag.py` 各自实现了一套写入逻辑，
都是 `open(path, "w")` 截断后再 `json.dump()`。三个具体风险：

1. **写一半崩了**：截断已经发生但新内容只写了一半 → 文件变成半截 JSON → Gateway 读不了。
   虽然两个模块都有 .bak 备份，但那是"出事后补救"，不是"不让出事"。
2. **并发静默覆盖**：模块 A 读了配置正准备写，此时用户在 Control UI 改了模型；
   A 按几秒前的旧快照整份写回 → 用户的修改被悄悄吃掉，**且没有任何报错**。
3. **无 schema 校验**：写出的是合法 JSON 但语义非法（参考 CASE-20260731-010
   「openclaw.json 顶层加未知 key 导致 config validate 失败」），要等下次重启才暴露。

## C 方案做了什么（最小防护，不碰架构）

- **原子写入**：临时文件 → fsync → os.replace()。要么完整旧内容，要么完整新内容。
- **跨进程锁**：fcntl.flock 独占锁。原子替换解决"半截文件"，文件锁解决"更新丢失"。
- **锁内重读**：拿到锁后重新读盘，基于最新内容改，不用几秒前的旧快照。
- **字段级 merge**：只改调用方指定的字段，不整份覆盖。
- **写后校验**：调用 `openclaw config validate`，失败立即回滚。
- **默认 dry-run**：不显式传 apply=True 就只预览。

## 有意不做的事

不引入 OpenClaw 官方配置 API（原方案 A）。那需要先确认当前版本暴露了哪些接口，
属于独立一轮工作。C 方案是纯本地改造，消掉上面三个风险即可，不改变任何现有行为语义。
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def _openclaw_config_path() -> Path:
    """openclaw.json 实际路径。延迟求值，尊重 CLI/环境变量/TOML (P2-16)。

    若调用方（包括测试）**显式**给本模块赋了 ``OPENCLAW_CONFIG``，
    则以该赋值为准（保留原有注入契约）。未赋值时才走统一解析器。
    关键区别：旧实现在 import 时就把默认值写成模块常量，使得环境变量
    永远无法生效；现在默认不预先赋值。
    """
    explicit = globals().get("OPENCLAW_CONFIG")
    if explicit is not None:
        return Path(explicit)

    from .user_config import get_openclaw_config_path

    return get_openclaw_config_path()


def _lock_path() -> Path:
    """锁文件与目标文件同目录，保证在同一文件系统上。"""
    return _openclaw_config_path().with_name(".openclaw.json.mark42.lock")


def __getattr__(name: str) -> Any:
    """向后兼容：旧代码/测试可能仍读模块级 ``OPENCLAW_CONFIG``。

    注意：这里每次访问都重新解析，因此不会像旧常量那样在
    import 时就固化路径。新代码请直接用 ``_openclaw_config_path()``。
    """
    if name == "OPENCLAW_CONFIG":
        return _openclaw_config_path()
    if name == "_LOCK_PATH":
        return _lock_path()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_LOCK_TIMEOUT_S = 30


class ConfigWriteError(RuntimeError):
    """配置写入失败（已回滚或未做任何改动）。"""


@contextmanager
def _exclusive_lock(timeout_s: int = _LOCK_TIMEOUT_S) -> Iterator[None]:
    """跨进程独占锁。

    用独立锁文件而不是锁目标文件本身：避免 os.replace() 把被锁的 inode 换掉，
    导致其他进程锁在了一个已经不是目标文件的 inode 上。
    """
    lock_path = _lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        import time

        deadline = time.monotonic() + timeout_s
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ConfigWriteError(
                        f"获取 openclaw.json 写锁超时（{timeout_s}s），"
                        "可能有其他 Mark42 进程正在修改配置"
                    ) from None
                time.sleep(0.2)
        yield
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError as e:
                logger.debug("释放配置锁失败: %s", e)
        os.close(fd)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """原子写入 JSON（同目录临时文件 + fsync + os.replace）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            try:
                os.chmod(tmp_name, path.stat().st_mode & 0o7777)
            except OSError as e:
                logger.debug("保留配置文件权限失败: %s", e)
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def _load(path: Path) -> dict[str, Any]:
    """读取 openclaw.json。顶层必须是对象，否则拒绝继续。

    【2026-08-05 P3-4】这里读到的内容会被 patch 后原子写回，
    若顶层不是对象（如被写成数组），后续 merge 会静默产出错误结构
    并覆盖真实配置。宁可显式失败也不能带着错误结构往下走。
    """
    if not path.exists():
        raise ConfigWriteError(f"缺少配置文件: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ConfigWriteError(
            f"配置顶层必须是 JSON 对象，实际是 {type(data).__name__}: {path}"
        )
    return data


def _validate() -> tuple[bool, str]:
    """调用 openclaw config validate。找不到可执行文件时视为跳过校验。"""
    from .config import OPENCLAW_BIN

    if not OPENCLAW_BIN or not Path(OPENCLAW_BIN).exists():
        which = shutil.which("openclaw")
        if not which:
            logger.warning("未找到 openclaw 可执行文件，跳过配置校验")
            return True, "skipped: openclaw 不可用"
        binary = which
    else:
        binary = OPENCLAW_BIN
    try:
        proc = subprocess.run(
            [binary, "config", "validate"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        ok = proc.returncode == 0
        return ok, (proc.stdout + proc.stderr).strip()[:2000]
    except subprocess.TimeoutExpired:
        return False, "openclaw config validate 超时"
    except OSError as e:
        logger.warning("执行 openclaw config validate 失败，跳过校验: %s", e)
        return True, f"skipped: {e}"


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> list[str]:
    """把 patch 递归合并进 base（原地修改），返回变更路径列表。

    只动 patch 里出现的字段，其余一律保持不变——这是"不整份覆盖"的关键。
    """
    changes: list[str] = []

    def _merge(dst: dict[str, Any], src: dict[str, Any], prefix: str) -> None:
        for k, v in src.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                _merge(dst[k], v, path)
            else:
                old = dst.get(k, "<缺失>")
                if old != v:
                    dst[k] = v
                    changes.append(f"{path}: {old!r} -> {v!r}")

    _merge(base, patch, "")
    return changes


def patch_openclaw_config(
    patch: dict[str, Any] | None = None,
    *,
    mutate: Callable[[dict[str, Any]], list[str]] | None = None,
    apply: bool = False,
    backup_tag: str = "mark42",
    validate: bool = True,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """安全地对 openclaw.json 做字段级修改。

    Args:
        patch: 要合并的字段（嵌套 dict）。与 mutate 二选一。
        mutate: 自定义修改函数，接收锁内重读的最新配置，原地修改并返回变更描述列表。
                适用于"删除字段"等 merge 表达不了的操作。
        apply: False（默认）只预览不写盘；True 才真正落盘。
        backup_tag: 备份文件名标记。
        validate: 写后是否执行 openclaw config validate。
        config_path: 显式指定目标配置路径。缺省走统一路径解析器。
                调用方（如 context_safety）自己持有路径语义时必须传，
                否则两边各自解析会造成跳模块路径断裂。

    Returns:
        含 status / changes / backupPath 的结果字典。

    Raises:
        ConfigWriteError: 获取锁超时、配置缺失，或校验失败且已回滚。
    """
    if (patch is None) == (mutate is None):
        raise ValueError("patch 与 mutate 必须且只能提供一个")

    with _exclusive_lock():
        # 关键：在锁内重新读盘，避免基于过期快照覆盖别人刚写的内容
        if config_path is None:
            config_path = _openclaw_config_path()
        current = _load(config_path)
        candidate = json.loads(json.dumps(current))  # 深拷贝

        if patch is not None:
            changes = _deep_merge(candidate, patch)
        else:
            assert mutate is not None
            changes = mutate(candidate)

        if not changes:
            return {
                "status": "nothing_to_do",
                "summary": "配置已是目标状态，无需修改",
                "changes": [],
            }

        if not apply:
            return {
                "status": "dry_run",
                "summary": f"预览模式 — 将修改 {len(changes)} 项，未写盘",
                "changes": changes,
            }

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = config_path.with_name(
            f"{config_path.name}.{backup_tag}-{stamp}.bak"
        )
        shutil.copy2(config_path, backup)

        try:
            _atomic_write_json(config_path, candidate)
        except Exception as e:
            # 原子写入失败时原文件本就未被触碰，但仍显式恢复以防万一
            logger.error("写入 openclaw.json 失败: %s", e)
            try:
                shutil.copy2(backup, config_path)
            except OSError:
                pass
            raise ConfigWriteError(f"写入失败，已保持原配置: {e}") from e

        if validate:
            ok, detail = _validate()
            if not ok:
                logger.error("配置校验失败，正在回滚: %s", detail)
                shutil.copy2(backup, config_path)
                raise ConfigWriteError(
                    f"配置校验失败，已回滚到修改前状态: {detail}"
                )

        return {
            "status": "applied",
            "summary": f"已应用 {len(changes)} 项配置修改（备份 {backup.name}）",
            "changes": changes,
            "backupPath": str(backup),
        }
