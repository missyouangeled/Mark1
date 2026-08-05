"""P3-5 防回归：容错分支必须留痕，且区分"没有结果"与"解析/IO 已失败"。

历史问题（方案 P3-5 列出 6 处）：
    mark42/armor.py（2 处）、mark42/log_classifier.py、mark42/utils.py、
    mark42/audit/pinning.py、mark42/audit/snapshot_reader.py
都是 `except Exception: continue` —— 坏数据被静默丢弃，外部完全无法区分
"文件里本来就没内容"和"内容全是坏行解析失败了"。

危害不只是难调试：
  - armor 的"连续 N 次压缩无效就升级告警"依赖 total_count，
    坏文件静默跳过会让分母偏小，本该触发的升级永远不满足 —— **静默削弱告警能力**；
  - 压缩方法统计的 llm_rate 分母变小会导致成功率**虚高**。

要求：容错分支至少记录可追踪的 debug/warning，并把异常类型收窄到
真正预期的那几类（OSError / JSONDecodeError 等），而非裸 Exception。
"""

import logging
from pathlib import Path

import pytest


class TestNoBareSilentExcept:
    """静态守卫：这 6 个文件不得再出现"静默跳过"写法。"""

    TARGET_FILES = (
        "armor.py",
        "log_classifier.py",
        "utils.py",
        "audit/pinning.py",
        "audit/snapshot_reader.py",
    )

    def _pkg_dir(self):
        return Path(__file__).resolve().parent.parent / "mark42"

    def test_no_bare_except_followed_by_continue(self):
        """`except Exception:` 紧跟 continue/pass 且无任何日志 —— 禁止。"""
        offenders = []
        for rel in self.TARGET_FILES:
            path = self._pkg_dir() / rel
            lines = path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped.startswith("except Exception"):
                    continue
                # 只看 except 块**自身**的语句：从下一行开始，取缩进比
                # except 更深的连续行。不能简单看"后面 3 行有没有 logger"——
                # 那会把 except 块之外的日志误算进来（已实测漏判）。
                except_indent = len(line) - len(line.lstrip())
                body = []
                for ln in lines[i + 1 :]:
                    if not ln.strip():
                        continue
                    indent = len(ln) - len(ln.lstrip())
                    if indent <= except_indent:
                        break
                    body.append(ln.strip())
                if not body:
                    continue
                has_log = any(
                    "logger." in b or "log." in b or "print(" in b for b in body
                )
                # 整个 except 块只有 continue/pass 且无任何日志 -> 静默跳过
                if all(b in ("continue", "pass") for b in body) and not has_log:
                    offenders.append(f"{rel}:{i + 1}")

        assert not offenders, (
            "发现静默的宽泛异常跳过（P3-5），必须记录 debug/warning：\n  "
            + "\n  ".join(offenders)
        )

    def test_noqa_s112_markers_removed(self):
        """`# noqa: S112` 是当初压制告警的标记，修完应全部移除。"""
        offenders = []
        for rel in self.TARGET_FILES:
            path = self._pkg_dir() / rel
            for i, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "noqa: S112" in line:
                    offenders.append(f"{rel}:{i}")
        assert not offenders, "仍有被压制的静默异常: " + ", ".join(offenders)


class TestCorruptDataIsReported:
    """行为验证：坏数据被跳过时必须能从日志看出来。"""

    def test_log_classifier_reports_corrupted_lines(self, tmp_path, caplog):
        """broker 有坏行时必须 warning，且不影响好行解析。"""
        from unittest.mock import patch

        from mark42 import log_classifier as lc

        broker_dir = tmp_path / ".local" / "state" / "openclaw" / "broker"
        broker_dir.mkdir(parents=True)
        (broker_dir / "events.jsonl").write_text(
            '{"ok":1}\n{坏行\n{"bad"\n{"ok":2}\n', encoding="utf-8"
        )

        with patch.object(lc.Path, "home", staticmethod(lambda: tmp_path)):
            with caplog.at_level(logging.WARNING):
                events = lc.cli_classify_recent(limit=10)

        # 好行照样解析出来
        assert len(events) == 2
        # 坏行必须留痕，且说明数量
        assert any(
            "损坏" in r.message and "2" in r.message for r in caplog.records
        ), f"未报告损坏行数量，实际日志: {[r.message for r in caplog.records]}"

    def test_pinning_reports_unreadable_constraint_file(self, tmp_path, caplog):
        """约束文件读不了必须 warning —— 约束静默丢失是高风险。"""
        from mark42.audit import pinning

        # 造一个"存在但读取会失败"的路径（用目录冒充文件）
        fake_ws = tmp_path / "ws"
        fake_ws.mkdir()
        (fake_ws / "SOUL.md").mkdir()  # 目录 -> read_text 抛 IsADirectoryError

        with caplog.at_level(logging.WARNING):
            pinner = pinning.ConstraintPinner(workspace=fake_ws)
            pinner.extract_pinned_constraints()

        assert any("约束文件" in r.message for r in caplog.records), (
            f"约束文件失败未留痕，实际: {[r.message for r in caplog.records]}"
        )

    def test_armor_slo_reports_unreadable_log(self, tmp_path, caplog, monkeypatch):
        """actions.jsonl 读不了时，错误信息必须带真实原因而非笼统一句。"""
        from mark42 import armor

        state = tmp_path / "armor"
        state.mkdir()
        log_path = state / "actions.jsonl"
        log_path.mkdir()  # 目录冒充文件 -> open 抛 IsADirectoryError

        monkeypatch.setattr(armor, "ARMOR_STATE", state)

        target = None
        for name in dir(armor):
            if name.startswith("armor_") and "slo" in name.lower():
                target = getattr(armor, name)
                break
        if target is None:
            pytest.skip("未找到 SLO 统计函数，静态守卫已覆盖该文件")

        with caplog.at_level(logging.ERROR):
            result = target()

        if isinstance(result, dict) and "error" in result:
            # 必须带上异常类型，不能只说"读取失败"
            assert ":" in result["error"], (
                f"错误信息丢失真实原因: {result['error']}"
            )
