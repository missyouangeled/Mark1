"""
Mark42 v3 全量验收单测 (v3-1 + v3-2 + v3-3 合并)
可独立运行：python3 scripts/tests/test_v3_modules.py

每个 case 用独立 XDG_STATE_HOME 隔离（不污染真实档案）。
"""

import os
import sys
import tempfile
import shutil
import threading
from pathlib import Path

# 让脚本可以 import mark42_modules
SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))


def _fresh_env():
    """返回 (tmp_dir, reload_callback) — 调用方负责清理 tmp_dir。"""
    tmp = Path(tempfile.mkdtemp(prefix="m42-v3-test-"))
    os.environ["XDG_STATE_HOME"] = str(tmp)

    import importlib
    import mark42_modules.config as _cfg; importlib.reload(_cfg)
    import mark42_modules.llm_provider as _lp; importlib.reload(_lp)
    import mark42_modules.error_archive as _ea; importlib.reload(_ea)
    import mark42_modules.consciousness as _co; importlib.reload(_co)

    from mark42_modules.llm_provider import (
        StubRuntime, OllamaRuntime, APIRuntime, LLMProviderError,
        load_config, build_provider, build_consciousness, build_advisor,
        chat_with_fallback, ChatMessage,
    )
    from mark42_modules.error_archive import (
        ErrorArchive, STATUS_RESOLVED, STATUS_AUTO_APPROVED, STATUS_REJECTED,
    )
    from mark42_modules.consciousness import Consciousness, DETERMINISTIC_RULES, CertaintyAssessment

    return {
        "tmp": tmp,
        "StubRuntime": StubRuntime,
        "OllamaRuntime": OllamaRuntime,
        "APIRuntime": APIRuntime,
        "LLMProviderError": LLMProviderError,
        "load_config": load_config,
        "build_provider": build_provider,
        "build_consciousness": build_consciousness,
        "build_advisor": build_advisor,
        "chat_with_fallback": chat_with_fallback,
        "ChatMessage": ChatMessage,
        "ErrorArchive": ErrorArchive,
        "STATUS_RESOLVED": STATUS_RESOLVED,
        "STATUS_AUTO_APPROVED": STATUS_AUTO_APPROVED,
        "STATUS_REJECTED": STATUS_REJECTED,
        "Consciousness": Consciousness,
        "DETERMINISTIC_RULES": DETERMINISTIC_RULES,
        "CertaintyAssessment": CertaintyAssessment,
    }


passed_total = 0
failed_total = 0
issues_total = []


def check(name, cond, detail=""):
    global passed_total, failed_total
    if cond:
        print(f"  ✅ {name}")
        passed_total += 1
    else:
        print(f"  ❌ {name}  {detail}")
        issues_total.append(name)
        failed_total += 1


# ════════════════════════════════════════════════════════
# v3-1: llm_provider
# ════════════════════════════════════════════════════════

def test_v3_1_llm_provider():
    print("\n═══ v3-1: llm_provider ═══")
    e = _fresh_env()
    StubRuntime = e["StubRuntime"]
    OllamaRuntime = e["OllamaRuntime"]
    APIRuntime = e["APIRuntime"]
    LLMProviderError = e["LLMProviderError"]
    load_config = e["load_config"]
    build_provider = e["build_provider"]
    build_consciousness = e["build_consciousness"]
    build_advisor = e["build_advisor"]
    chat_with_fallback = e["chat_with_fallback"]
    ChatMessage = e["ChatMessage"]

    # 1. StubRuntime 基础
    s = StubRuntime()
    r = s.chat([ChatMessage("user", "hello")])
    check("StubRuntime 基础", r.ok and "hello" in r.content)

    # 2. StubRuntime 空 messages
    r2 = s.chat([])
    check("StubRuntime 空 messages 不崩", r2.ok and len(r2.content) > 0)

    # 3. StubRuntime None content
    r3 = s.chat([ChatMessage("user", None)])
    check("StubRuntime None content 不崩", r3.ok and len(r3.content) > 0)

    # 4. OllamaRuntime 构造
    o = OllamaRuntime(model="qwen:4b")
    check("OllamaRuntime 默认 base_url", "11434" in o.base_url)

    # 5. OllamaRuntime 不通抛错
    o2 = OllamaRuntime(model="x", base_url="http://127.0.0.1:1", timeout_seconds=2, max_retries=0)
    try:
        o2.chat([ChatMessage("user", "hi")])
        check("OllamaRuntime 不通抛错", False)
    except LLMProviderError:
        check("OllamaRuntime 不通抛错", True)

    # 6. APIRuntime 缺 base_url
    try:
        APIRuntime(model="x", base_url="", api_key="***")
        check("APIRuntime 缺 base_url", False)
    except LLMProviderError:
        check("APIRuntime 缺 base_url", True)

    # 7. APIRuntime 缺 api_key
    try:
        APIRuntime(model="x", base_url="http://x", api_key="")
        check("APIRuntime 缺 api_key", False)
    except LLMProviderError:
        check("APIRuntime 缺 api_key", True)

    # 8. APIRuntime 不通
    a = APIRuntime(model="x", base_url="http://127.0.0.1:1", api_key="***",
                   timeout_seconds=2, max_retries=0)
    try:
        a.chat([ChatMessage("user", "hi")])
        check("APIRuntime 不通抛错", False)
    except LLMProviderError:
        check("APIRuntime 不通抛错", True)

    # 9. load_config 不存在
    cfg = load_config(Path("/nonexistent/yaml"))
    check("load_config 不存在 → 默认", cfg is not None)

    # 10. load_config 空 path
    cfg2 = load_config(Path(""))
    check("load_config 空 path → 默认", cfg2 is not None)

    # 11. load_config 坏 yaml
    bad = e["tmp"] / "bad.yaml"
    bad.write_text("[unclosed: oops", encoding="utf-8")
    cfg3 = load_config(bad)
    check("load_config 坏 yaml → 默认", cfg3 is not None)

    # 12. 未知 runtime 降 stub
    p = build_provider({"runtime": "未知", "model": "x"})
    check("未知 runtime 降 stub", isinstance(p, StubRuntime))

    # 13. API 缺配置降 stub
    p2 = build_provider({"runtime": "api", "model": "x"})
    check("API 缺配置降 stub", isinstance(p2, StubRuntime))

    # 14. 默认配置 = stub
    cs = build_consciousness(load_config())
    check("默认配置 stub", isinstance(cs, StubRuntime))

    # 15. advisor 默认 None
    adv = build_advisor(load_config())
    check("advisor 默认 None", adv is None)

    # 16. advisor 启用+缺配置 → stub
    tmp_cfg = e["tmp"] / "adv.yaml"
    tmp_cfg.write_text("mark42:\n  advisor:\n    enabled: true\n    runtime: api\n    model: gpt-4\n    base_url: ''\n    api_key: ''\n",
                       encoding="utf-8")
    adv2 = build_advisor(load_config(tmp_cfg))
    check("advisor 启用+缺配置 → stub", isinstance(adv2, StubRuntime))

    # 17. fallback chain 工作
    cfg_fail = {"mark42": {"consciousness": {"runtime": "api", "model": "x",
                                             "base_url": "http://127.0.0.1:1",
                                             "api_key": "***", "timeout_seconds": 2,
                                             "max_retries": 0},
                            "fallback_chain": ["stub"]}}
    r_fb = chat_with_fallback([ChatMessage("user", "x")], cfg_fail)
    check("主失败 → fallback stub", r_fb.ok)

    # 18. 空 fallback chain
    cfg_empty = {"mark42": {"consciousness": {"runtime": "stub", "model": "x"},
                            "fallback_chain": []}}
    r_e = chat_with_fallback([ChatMessage("user", "x")], cfg_empty)
    check("空 chain 不崩", r_e.ok)

    shutil.rmtree(e["tmp"], ignore_errors=True)


# ════════════════════════════════════════════════════════
# v3-2: error_archive
# ════════════════════════════════════════════════════════

def test_v3_2_error_archive():
    print("\n═══ v3-2: error_archive ═══")
    e = _fresh_env()
    ErrorArchive = e["ErrorArchive"]
    STATUS_RESOLVED = e["STATUS_RESOLVED"]
    STATUS_AUTO_APPROVED = e["STATUS_AUTO_APPROVED"]
    STATUS_REJECTED = e["STATUS_REJECTED"]

    arc = ErrorArchive()

    # 1. 数据结构
    en = arc.record(category="t", signature="t:1", diagnosis="x")
    check("record 返回 entry", en.id.startswith("ERR-"))
    check("新条目 count=1", en.occurrence_count == 1)
    check("新条目 status=NEW", en.resolution_status == "NEW")

    # 2. 重复事件累加
    en2 = arc.record(category="t", signature="t:1", diagnosis="x")
    check("重复 count=2", en2.occurrence_count == 2)
    check("重复 id 不变", en2.id == en.id)

    # 3. 跨 category 不撞车
    ea = arc.record(category="cat_a", signature="ns:sig_a", diagnosis="x")
    eb = arc.record(category="cat_b", signature="ns:sig_b", diagnosis="x")
    check("跨 cat 不撞车", ea.id != eb.id)

    # 4. lookup 精确匹配 + category 不撞车
    eb_hit = arc.lookup("ns:sig_b", category="cat_b")
    check("lookup cat_b+sig_b 命中 cat_b",
          eb_hit is not None and eb_hit.category == "cat_b")
    eb_wrong = arc.lookup("ns:sig_b", category="cat_a")
    # 精确不命中 cat_b，相似匹配找 cat_a + ns → 命中 cat_a 的 sig_a
    check("lookup cat_a+sig_b 不返回 cat_b",
          eb_wrong is None or eb_wrong.category != "cat_b")

    # 5. lookup 找不到
    check("lookup 不存在 → None", arc.lookup("nope:nope", "nope") is None)

    # 6. 黑名单 4 类
    for cat in ["user_data_modification", "business_logic_modification",
                "systemd_service_modification", "directory_deletion"]:
        e_bl = arc.record(category=cat, signature=f"bl:{cat}", diagnosis="x")
        r = arc.approve_for_auto(e_bl.id, scope="exact_match")
        check(f"黑名单 {cat[:20]}...拒绝", r["ok"] is False)
        check(f"黑名单 {cat[:20]}...状态不变",
              arc.get(e_bl.id).resolution_status != STATUS_AUTO_APPROVED)

    # 7. 正常授权
    e_ok = arc.record(category="normal", signature="normal:1", diagnosis="x")
    r_ok = arc.approve_for_auto(e_ok.id, scope="exact_match")
    check("正常条目可授权", r_ok["ok"] is True)
    check("auto_approved=True 落盘", arc.get(e_ok.id).auto_approved is True)

    # 8. REJECTED
    e_r = arc.record(category="rej", signature="rej:1", diagnosis="x")
    arc.reject(e_r.id)
    check("REJECTED 状态", arc.get(e_r.id).resolution_status == STATUS_REJECTED)
    check("REJECTED 不参与 lookup", arc.lookup("rej:1", "rej") is None)

    # 9. Cooldown: 用户授权 count=1；4 次 increment → 2,3,4,5；第 5 次 warning；第 6 次拦截
    seq = []
    for i in range(6):
        rr = arc.increment_auto_count(e_ok.id)
        seq.append((rr["count"], rr["allowed"], len(rr.get("warnings", []))))
    expected = [(2, True, 0), (3, True, 0), (4, True, 0),
                (5, True, 1), (5, False, 0), (5, False, 0)]
    check("Cooldown 序列符合 §4.3", seq == expected, f"actual={seq}")

    # 10. 并发安全
    e_c = arc.record(category="c", signature="c:1", diagnosis="x")
    errors = []
    def w():
        try:
            for _ in range(3): arc.increment_auto_count(e_c.id)
        except Exception as ex:
            errors.append(str(ex))
    ts = [threading.Thread(target=w) for _ in range(5)]
    for t in ts: t.start()
    for t in ts: t.join()
    check("并发 5 线程不崩", len(errors) == 0)
    check("并发后 count ≤ 6", arc.get(e_c.id).auto_approval_count <= 6)

    # 11. 持久化
    arc2 = ErrorArchive()
    check("新实例读到原数据", arc2.stats()["total"] > 0)

    # 12. 审计日志
    from mark42_modules.error_archive import APPROVAL_LOG_FILE
    if APPROVAL_LOG_FILE.exists():
        text = APPROVAL_LOG_FILE.read_text()
        check("审计含 blacklist_blocked", "blacklist_blocked" in text)
        check("审计含 cooldown_blocked", "cooldown_blocked" in text)
        check("审计含 auto_apply", "auto_apply" in text)

    # 13. 边界
    check("奇怪 category 不崩",
          arc.record(category="weird/cat with spaces", signature="w:1", diagnosis="x") is not None)
    check("空 signature 不崩",
          arc.record(category="x", signature="", diagnosis="x") is not None)
    check("极长 signature 不崩",
          arc.record(category="x", signature="x:" + "a" * 1000, diagnosis="x") is not None)

    shutil.rmtree(e["tmp"], ignore_errors=True)


# ════════════════════════════════════════════════════════
# v3-3: consciousness
# ════════════════════════════════════════════════════════

def test_v3_3_consciousness():
    print("\n═══ v3-3: consciousness ═══")
    e = _fresh_env()
    Consciousness = e["Consciousness"]
    DETERMINISTIC_RULES = e["DETERMINISTIC_RULES"]
    ErrorArchive = e["ErrorArchive"]
    CertaintyAssessment = e["CertaintyAssessment"]

    arc = ErrorArchive()
    cs = Consciousness(llm=None, archive=arc, rules=DETERMINISTIC_RULES)

    # 1. C1 自检不崩
    r1 = cs.self_check()
    check("C1 返回 SelfCheckResult", r1 is not None)
    check("C1 healthy is bool", isinstance(r1.healthy, bool))
    check("C1 issues 是 list", isinstance(r1.issues, list))

    # 2. C2 6 条规则
    rules_check = [
        (("scratch", "unknown_file"), "low", "ask_user"),
        (("sidecar", "embed_index_missing"), "100%", "auto_remediate"),
        (("sidecar", "process_down"), "100%", "auto_remediate"),
        (("armor", "context_alert"), "100%", "auto_remediate"),
        (("engine", "loop_not_registered"), "100%", "auto_remediate"),
        (("systemd", "service_modified"), "unknown", "ask_user"),
    ]
    for (src, cat), cert, act in rules_check:
        a = cs.assess_certainty({"source": src, "category": cat, "msg": "x", "severity": "critical"})
        check(f"C2 {src}/{cat} → {cert}/{act}",
              a.certainty == cert and a.action == act)

    # 3. C2 不存在 → unknown
    a0 = cs.assess_certainty({"source": "xxx", "category": "yyy", "msg": "z", "severity": "warning"})
    check("C2 不存在 → unknown", a0.certainty == "unknown")

    # 4. C3 黑名单 4 类
    for cat in ["user_data_modification", "business_logic_modification",
                "systemd_service_modification", "directory_deletion"]:
        iss = {"source": "x", "category": cat, "msg": "x", "severity": "critical"}
        a_fake = CertaintyAssessment(certainty="100%", matched_rule="fake",
                                     archive_entry_id=None, archive_auto_approved=False,
                                     action="auto_remediate", reason="x", next_step="x")
        rem = cs.auto_remediate(iss, a_fake, dry_run=False)
        check(f"C3 黑名单 {cat[:20]}...拦截", rem["ok"] is False)

    # 5. C3 dry-run 默认
    a100 = cs.assess_certainty({"source": "armor", "category": "context_alert", "msg": "x", "severity": "critical"})
    rem = cs.auto_remediate({"source": "armor", "category": "context_alert", "msg": "x", "severity": "critical"},
                            a100, dry_run=True)
    check("C3 dry-run 默认", rem.get("dry_run") is True)

    # 6. C4 dialog
    req1 = cs.dialog({"source": "armor", "category": "context_alert", "msg": "x", "severity": "critical"}, a100)
    check("C4 100% severity=critical", req1.severity == "critical")
    check("C4 100% options 非空", len(req1.options) > 0)
    check("C4 100% question 非空", bool(req1.question))

    req2 = cs.dialog({"source": "x2", "category": "y2", "msg": "z", "severity": "warning"},
                     cs.assess_certainty({"source": "x2", "category": "y2", "msg": "z", "severity": "warning"}))
    check("C4 unknown 写档案", req2.context.get("archive_id") is not None)
    check("C4 unknown question 含'新类型'", "新类型" in req2.question)

    # 7. C5
    check("C5 无档案 None",
          cs.check_archive({"source": "armor", "category": "context_alert", "msg": "x", "severity": "critical"}) is None)

    e5 = arc.record(category="context_alert", signature="armor:context_alert",
                    decided_by="user", method="user_approved_auto",
                    resolution_status="AUTO_APPROVED")
    arc.approve_for_auto(e5.id, scope="exact_match")
    r5 = cs.check_archive({"source": "armor", "category": "context_alert", "msg": "x", "severity": "critical"})
    check("C5 命中 auto_approved", r5 and r5.get("auto_approved") is True)

    # 8. §4.5 流程
    result_unknown = cs.handle_issue({"source": "xyz", "category": "xyz", "msg": "x", "severity": "warning"}, dry_run=True)
    check("handle unknown → C4", result_unknown["path"] == "C4_dialog")

    # 9. 边界
    check("空 issue 不崩", cs.assess_certainty({}) is not None)
    check("全 None issue 不崩", cs.assess_certainty({"source": None, "category": None, "msg": None, "severity": None}) is not None)
    a_empty = cs.assess_certainty({})
    check("dialog 空 issue 不崩", cs.dialog({}, a_empty) is not None)
    for iss in [{}, {"source": "x"}, {"category": "x"}, {"source": "x", "category": "y"}]:
        check(f"handle {iss} 不崩", cs.handle_issue(iss, dry_run=True) is not None)

    # 10. 黑名单集成
    iss_bl = {"source": "x", "category": "directory_deletion", "msg": "rm", "severity": "critical"}
    result_bl = cs.handle_issue(iss_bl, dry_run=True)
    check("handle 黑名单 → C4 (不绕过)", result_bl["path"] == "C4_dialog")

    shutil.rmtree(e["tmp"], ignore_errors=True)


# ════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 70)
    print("Mark42 v3 全量验收单测 (v3-1 + v3-2 + v3-3)")
    print("═" * 70)

    test_v3_1_llm_provider()
    test_v3_2_error_archive()
    test_v3_3_consciousness()

    print("\n" + "═" * 70)
    print(f"总计: 通过 {passed_total} / 共 {passed_total + failed_total}")
    if issues_total:
        print(f"❌ 未通过: {issues_total}")
    else:
        print("🎉 全部通过")
    print("═" * 70)

    sys.exit(0 if failed_total == 0 else 1)