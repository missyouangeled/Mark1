#!/usr/bin/env python3
"""生成 Mark42 静态开发门户 HTML（绝对路径，双击直接跳转）"""
import sys
from pathlib import Path

WORKSPACE = Path("/home/missyouangeled/.openclaw/workspace")
PKG = WORKSPACE / "mark42-pkg"
# 【2026-08-05 修正】原指向 workspace/docs/（旧位置，只有 22 份）。
# 40 份文档已于 8-05 纳入 mark42-pkg/docs/ 版本控制，改从项目目录读。
DESIGN_DOCS = PKG / "docs" / "design"
PLAN_DOCS = PKG / "docs" / "plans"
# 版本号从包里读，不再硬编码（原写死 2.8.1，升版后页面不跟进）
def _read_version() -> str:
    try:
        import re as _re
        txt = (PKG / "mark42" / "__init__.py").read_text(encoding="utf-8")
        m = _re.search(r'__version__\s*=\s*["\']([^"\']+)', txt)
        if m:
            return m.group(1)
    except Exception as exc:
        # 【2026-08-06】原为 try/except/pass，静默吞异常（ruff S110）。
        # 读版本失败会让页面显示 "unknown"，属于需要被知道的降级，不能默默咽掉。
        print(f"⚠️  读取版本号失败，页面将显示 unknown: {exc}", file=sys.stderr)
    return "unknown"

VERSION = _read_version()
OUTPUT = Path("/home/missyouangeled/.openclaw/workspace/mark42-pkg/docs/devportal/mark42-developer-portal.html")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# 模块分类（基于实际代码结构）
CATEGORIES = [
    {
        "id": "core",
        "title": "🛡️ 核心三模块",
        "desc": "Mark42 的三大主战甲：上下文铠甲、循环引擎、重型战甲",
        "modules": [
            ("armor.py", "上下文铠甲", "实时检测上下文健康 + LLM驱动记忆索引 + 启发式回退 + 守护模式", ["test_armor.py", "test_armor_check.py", "test_armor_compress.py"]),
            ("engine.py", "循环引擎", "Loop注册/执行/终止 + daemon守护 + 模板路由", ["test_engine.py"]),
            ("heavy.py", "重型战甲", "大工程预检 + 上下文感知自动分批 + 收工验证", ["test_heavy.py", "test_heavy_resume.py"]),
        ]
    },
    {
        "id": "compression",
        "title": "🗜️ 压缩子系统",
        "desc": "Mark42 借鉴 Headroom 的多层压缩算法",
        "modules": [
            ("algo_scheduler.py", "算法调度器", "根据内容特征自动选择最优压缩算法 + PII脱敏调度", ["test_algo_scheduler.py"]),
            ("smart_crusher.py", "智能压缩调度", "智能压缩调度主逻辑", ["test_smart_crusher.py"]),
            ("text_compressor.py", "文本压缩", "文本压缩(同义词+填充词)", ["test_code_compressor.py"]),
            ("code_compressor.py", "代码压缩", "代码去注释+AST压缩", ["test_code_compressor.py"]),
            ("diff_compressor.py", "Diff压缩", "git diff压缩", ["test_diff_compressor.py"]),
            ("llm_text_compressor.py", "LLM语义压缩", "LLM语义压缩(同步+异步),支持模型路由", ["test_llm_text_compressor.py"]),
            ("compress_queue.py", "压缩队列", "压缩线程队列,后台work", ["test_compress_queue.py"]),
            ("compaction_diag.py", "压缩诊断", "检测OpenClaw内置压缩配置,生成优化建议", ["test_compaction_diag.py"]),
            ("pii_redactor.py", "PII脱敏", "压缩前对LLM中间内容脱敏,防止隐私泄露", ["test_pii_redactor.py"]),
            ("log_deduplicator.py", "日志去重", "压缩前的日志去重", ["test_log_deduplicator.py"]),
        ]
    },
    {
        "id": "audit",
        "title": "🔍 审计子系统",
        "desc": "compact后自动审计：6类核对 + Constraint Pinning",
        "modules": [
            ("audit/__init__.py", "审计入口", "6类核对: tokens/sections/names/rules/headroom/artifacts", ["test_audit.py"]),
            ("audit/checker.py", "审计检查器", "LLMChecker/RulerChecker两种模式", ["test_audit.py"]),
            ("audit/pinning.py", "Constraint Pinning", "约束保护,关键约束双通道重注入", ["test_audit.py"]),
            ("audit/snapshot_reader.py", "快照读取", "从数据盘读compact前快照", ["test_audit.py"]),
            ("audit/summary_extractor.py", "摘要提取", "从session读compact后摘要", ["test_audit.py"]),
            ("audit/report.py", "审计报告", "生成审计报告+告警渠道", ["test_audit.py"]),
        ]
    },
    {
        "id": "v3-core",
        "title": "⚙️ v3 核心 8 模块 (R10 多核架构)",
        "desc": "Mark42 v3 的 8 个核心功能模块,按设备能力动态装配",
        "modules": [
            ("consciousness.py", "自主意识层", "v3-3 战甲自主意识(C1自检/C2环境感知/C3内省)", ["test_consciousness.py"]),
            ("code_analyzer.py", "代码理解引擎", "v3 核心5: 代码语义分析/找bug/代码审查", ["test_code_analyzer.py"]),
            ("log_classifier.py", "日志分类器", "v3 核心6: broker事件按类型自动分类", ["test_log_classifier.py"]),
            ("anomaly_detector.py", "异常检测器", "v3 核心8: 非依赖LLM纯算法异常检测", ["test_anomaly_detector.py"]),
            ("core_registry.py", "核心位注册表", "v3 §4.8: 8个核心位状态管理(healthy/degraded/down)", ["test_core_registry.py"]),
            ("module_health.py", "模块健康监控", "v3 §3.7: 三态自检 + 4 Golden Signals", ["test_module_health.py"]),
            ("failure_contract.py", "降级响应契约", "v3 §3.6.2 R13-D: 9字段降级响应契约", ["test_failure_contract.py"]),
            ("llm_provider.py", "可插拔LLM Provider", "v3-1: 三层可插拔 Runtime/Model/API", ["test_llm_provider.py"]),
            ("error_archive.py", "错误档案系统", "v3-2: 错误档案数据结构", ["test_error_archive.py"]),
            ("circuit_breaker.py", "熔断器", "v3 R-CAND-02: 每个核心独立熔断", ["test_circuit_breaker.py"]),
            ("chaos_engine.py", "混沌工程", "v3 R11: 每周至少跑一次混沌测试", ["test_chaos_engine.py"]),
            ("cluster_manager.py", "集群管理器", "v3 §3.6.3 R14: 8核=8个独立小集群", ["test_cluster_manager.py"]),
            ("advisor_client.py", "主动交流协议", "v3-4: Advisor Client 主动交流", ["test_advisor_client.py"]),
            ("actions_runner.py", "动作执行器", "半自动骨架,默认dry-run", ["test_actions_runner.py"]),
        ]
    },
    {
        "id": "plugin",
        "title": "🔌 插件模块 (builtin_*)",
        "desc": "11 个 builtin 插件,系统通过插件机制挂载",
        "modules": [
            ("plugins/builtin_memory.py", "内存插件", "内存管理插件", ["test_builtin_memory.py"]),
            ("plugins/builtin_health.py", "健康监控插件", "健康监控挂载", ["test_builtin_health.py"]),
            ("plugins/builtin_heavy.py", "重型战甲插件", "重型战甲挂载", ["test_heavy.py"]),
            ("plugins/builtin_compress.py", "压缩插件", "压缩功能挂载", ["test_builtin_compress.py"]),
            ("plugins/builtin_audit.py", "审计插件", "审计挂载", ["test_audit.py"]),
            ("plugins/builtin_engine.py", "引擎插件", "循环引擎挂载", ["test_engine.py"]),
            ("plugins/builtin_archive.py", "归档插件", "归档功能挂载", ["test_builtin_archive.py"]),
            ("plugins/builtin_consciousness.py", "自主意识插件", "意识层挂载", ["test_consciousness.py"]),
            ("plugins/builtin_chaos.py", "混沌插件", "混沌测试挂载", ["test_chaos_engine.py"]),
            ("plugins/builtin_breaker.py", "熔断器插件", "熔断器挂载", ["test_circuit_breaker.py"]),
        ]
    },
    {
        "id": "interface",
        "title": "🔗 Interface 层",
        "desc": "12 个抽象接口,定义模块协议",
        "modules": [
            ("interfaces/__init__.py", "接口根", "接口包入口", []),
            ("interfaces/audit.py", "审计接口", "审计模块协议", []),
            ("interfaces/chaos.py", "混沌接口", "混沌测试协议", []),
            ("interfaces/circuit_breaker.py", "熔断器接口", "熔断器协议", []),
            ("interfaces/compress.py", "压缩接口", "压缩协议", []),
            ("interfaces/consciousness.py", "意识接口", "意识层协议", []),
            ("interfaces/engine.py", "引擎接口", "循环引擎协议", []),
            ("interfaces/error_archive.py", "错误档案接口", "错误档案协议", []),
            ("interfaces/health.py", "健康接口", "健康监控协议", []),
            ("interfaces/heavy.py", "重型战甲接口", "重型战甲协议", []),
            ("interfaces/memory.py", "内存接口", "内存管理协议", []),
        ]
    },
    {
        "id": "support",
        "title": "🛠️ 支撑模块",
        "desc": "基础设施、日志、配置等",
        "modules": [
            ("config.py", "配置", "XDG路径 + 配置初始化", ["test_config.py"]),
            ("openclaw_config.py", "OpenClaw 配置解析", "openclaw.json 单一路径入口（CLI > env > TOML > 默认）", []),
            ("telemetry.py", "可观测性", "指标采集与上报", []),
            ("utils.py", "工具函数", "JSON加载、文件锁等", []),
            ("logs.py", "日志管理", "日志轮转", ["test_logs.py"]),
            ("log_setup.py", "日志初始化", "统一日志获取", ["test_log_setup.py"]),
            ("user_config.py", "用户配置", "读取config.toml,回退默认值", []),
            ("installer.py", "安装器", "安装脚本辅助", ["test_installer.py"]),
            ("__main__.py", "CLI主入口", "python3 -m mark42 入口", []),
            ("metrics_server.py", "指标服务", "Prometheus格式 /metrics", ["test_metrics_server.py"]),
            ("perf_bench.py", "性能基准", "5个本地压缩算法基准", ["test_perf_bench.py"]),
        ]
    },
    {
        "id": "safety",
        "title": "🛡️ 安全/会话",
        "desc": "会话保护、上下文安全、输出防护",
        "modules": [
            ("context_safety.py", "上下文安全", "安全基线检查", ["test_context_safety.py"]),
            ("session_fence.py", "会话围栏", "防止误操作错误session", ["test_session_fence.py"]),
            ("output_guard.py", "输出防护", "输出内容防护", ["test_output_guard.py"]),
            ("watchdog.py", "看门狗", "心跳超时检测", []),
            ("cost_tracker.py", "成本追踪", "LLM API token/费用追踪", ["test_cost_tracker.py"]),
        ]
    },
]

# 全局文档导航
# 【2026-08-05 改为自动扫描】原为手工维护的 22 条列表，且路径指向旧位置
# （40 份文档已于 8-05 迁入 mark42-pkg/docs/，旧路径链接全部失效）。
# 现改为扫描项目 docs/ 目录，保证门户与真实文档集永不脱节。
_DOC_LABELS = {
    "QUICKSTART.md": ("入门", "5分钟跑起来"),
    "TUTORIAL.md": ("教程", "从零完整学习"),
    "ARCHITECTURE.md": ("架构", "整体架构"),
    "CONFIG-GUIDE.md": ("配置", "配置详解"),
    "MIGRATION.md": ("迁移", "版本迁移"),
    "TROUBLESHOOTING.md": ("故障", "问题排查"),
    "ROADMAP.md": ("路线", "未来方向"),
    "CHANGELOG.md": ("变更", "更新日志"),
    "SECURITY.md": ("安全", "安全策略"),
    "CONTRIBUTING.md": ("贡献", "贡献指南"),
    "INDEX.md": ("索引", "文档导航"),
    "README.md": ("说明", "项目说明"),
    "SBOM.md": ("依赖", "软件物料清单"),
}

def _build_docs_nav():
    docs_root = PKG / "docs"
    if not docs_root.is_dir():
        return []
    items = []
    # 顶层文档：用友好标签，未登记的按文件名
    for f in sorted(docs_root.glob("*.md")):
        label, desc = _DOC_LABELS.get(f.name, (f.stem, "项目文档"))
        items.append((label, f"docs/{f.stem}.html", desc))
    # design/ 与 plans/：全量收录，标签带前缀便于分组
    for sub, prefix in (("design", "设计"), ("plans", "方案")):
        d = docs_root / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            name = f.stem
            for junk in ("mark42-", "Mark42-"):
                if name.startswith(junk):
                    name = name[len(junk):]
            items.append((f"{prefix}-{name[:24]}", f"docs/{sub}/{f.stem}.html", f.stem))
    return items

DOCS_NAV = _build_docs_nav()

def file_url(rel_path: str) -> str:
    """生成 file:// 绝对路径 URL"""
    abs_path = (WORKSPACE / rel_path).resolve()
    return f"file://{abs_path}"

def render_module_row(src_rel: str, name: str, desc: str, tests: list) -> str:
    # 【2026-08-05 修正】两轮修正：
    # ① 原为 PKG / src_rel，拼出 mark42-pkg/armor.py —— 缺了中间 mark42/ 包层
    #   （源码 7-29 从 scripts/mark42_modules/ 迁入包内），68 个链接全失效。
    # ② 改用相对路径指门户内副本：绝对路径指向 workspace 隐藏目录，
    #   门户整体拷到其他机器/其他位置后全部失效。
    # 存在性校验仍用绝对路径（构建时验证源文件真存在）。
    # 【2026-08-06 补】原先只赋值 src_abs 却从未使用（ruff F841），
    # 上行注释承诺的「存在性校验」实际根本没写。源码若被移走/改名，
    # 会照样生成指向不存在文件的死链且不报错 —— 正是 8-05 那类链接腐化的温床。
    # 现补上校验：缺失时标「缺」并向 stderr 告警，与下方 test 链接的处理对齐。
    src_abs = PKG / "mark42" / src_rel
    src_url = f"mark42/{src_rel}"
    if src_abs.exists():
        src_link = f'<a class="link src" href="{src_url}" target="_blank">📄 打开源码</a>'
    else:
        print(f"⚠️  源码缺失，链接标记为缺: mark42/{src_rel}", file=sys.stderr)
        src_link = f'<span class="link src-missing">📄 {src_rel} (缺)</span>'
    test_links = ""
    if tests:
        test_links = '<div class="tests">'
        for t in tests:
            test_path = PKG / "tests" / t
            if test_path.exists():
                test_links += f'<a class="link test" href="tests/{t}" target="_blank">🧪 {t}</a> '
            else:
                test_links += f'<span class="link test-missing">🧪 {t} (缺)</span> '
        test_links += '</div>'
    return f'''
    <div class="module">
      <div class="module-head">
        <span class="module-name">{name}</span>
        <span class="module-path"><code>{src_rel}</code></span>
      </div>
      <div class="module-desc">{desc}</div>
      <div class="module-links">
        {src_link}
        {test_links}
      </div>
    </div>'''

def render_category(cat: dict) -> str:
    modules_html = "\n".join(render_module_row(m[0], m[1], m[2], m[3]) for m in cat["modules"])
    return f'''
    <section class="category" id="cat-{cat["id"]}">
      <h2>{cat["title"]}</h2>
      <p class="cat-desc">{cat["desc"]}</p>
      <div class="modules">{modules_html}</div>
    </section>'''

# 构建 HTML
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Mark42 开发门户 v{VERSION}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.6; color: #1f2937; background: #f9fafb; }}
.header {{ background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); color: white; padding: 30px 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.header h1 {{ font-size: 28px; margin-bottom: 8px; }}
.header .meta {{ opacity: 0.9; font-size: 14px; }}
.container {{ display: flex; max-width: 1400px; margin: 0 auto; }}
.sidebar {{ width: 240px; background: white; padding: 20px; height: calc(100vh - 100px); position: sticky; top: 0; overflow-y: auto; border-right: 1px solid #e5e7eb; }}
.sidebar h3 {{ font-size: 13px; color: #6b7280; text-transform: uppercase; margin: 15px 0 8px; letter-spacing: 0.5px; }}
.sidebar h3:first-child {{ margin-top: 0; }}
.sidebar a {{ display: block; padding: 6px 10px; color: #1e40af; text-decoration: none; font-size: 13px; border-radius: 4px; }}
.sidebar a:hover {{ background: #eff6ff; }}
.sidebar .cat-link {{ font-weight: 600; color: #1f2937; }}
.main {{ flex: 1; padding: 30px 40px; }}
.cat-nav {{ background: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
.cat-nav a {{ display: inline-block; padding: 6px 12px; margin: 3px; background: #eff6ff; color: #1e40af; text-decoration: none; border-radius: 16px; font-size: 13px; }}
.cat-nav a:hover {{ background: #1e40af; color: white; }}
.category {{ background: white; padding: 25px 30px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
.category h2 {{ color: #1e40af; font-size: 20px; margin-bottom: 6px; padding-bottom: 10px; border-bottom: 2px solid #eff6ff; }}
.cat-desc {{ color: #6b7280; font-size: 14px; margin-bottom: 18px; }}
.module {{ padding: 12px 0; border-bottom: 1px solid #f3f4f6; }}
.module:last-child {{ border-bottom: none; }}
.module-head {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px; }}
.module-name {{ font-weight: 600; color: #1f2937; font-size: 15px; }}
.module-path {{ color: #9ca3af; font-size: 12px; }}
.module-path code {{ background: #f3f4f6; padding: 1px 6px; border-radius: 3px; }}
.module-desc {{ color: #4b5563; font-size: 13px; margin: 4px 0 8px; }}
.module-links {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.tests {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.link {{ display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 12px; text-decoration: none; transition: all 0.2s; }}
.link.src {{ background: #dbeafe; color: #1e40af; }}
.link.src:hover {{ background: #1e40af; color: white; }}
.link.test {{ background: #d1fae5; color: #065f46; }}
.link.test:hover {{ background: #059669; color: white; }}
.test-missing {{ background: #fee2e2; color: #991b1b; font-size: 12px; padding: 4px 10px; border-radius: 4px; }}
.src-missing {{ background: #fee2e2; color: #991b1b; font-size: 12px; padding: 4px 10px; border-radius: 4px; }}
.stat-bar {{ background: white; padding: 15px 25px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); display: flex; gap: 30px; font-size: 13px; color: #6b7280; }}
.stat-bar b {{ color: #1e40af; font-size: 16px; }}
</style>
</head>
<body>
<div class="header">
  <h1>🛡️ Mark42 开发门户</h1>
  <div class="meta">模块化智能铠甲系统 · v{VERSION} · {len(CATEGORIES)} 大类 · 共 {sum(len(c["modules"]) for c in CATEGORIES)} 个模块</div>
</div>
<div class="container">
  <aside class="sidebar">
    <h3>📚 文档导航</h3>
"""

# 侧边栏文档链接
for label, rel, desc in DOCS_NAV:
    # 【2026-08-05 修正】原用 file_url() 拼绝对路径指向 workspace 外部的 .md，
    # 但浏览器不渲染 .md（点了只会下载或空白），且链接跑出门户目录导致
    # 整体拷走后失效。现改为相对路径指门户内的 .html（由 pandoc 预渲染）。
    html += f'    <a href="{rel}" target="_blank" title="{desc}">{label}</a>\n'

# 侧边栏分类锚点
html += '\n    <h3>🗂️ 模块分类</h3>\n'
for cat in CATEGORIES:
    html += f'    <a class="cat-link" href="#cat-{cat["id"]}">{cat["title"]}</a>\n'

html += f'''  </aside>
  <main class="main">
    <div class="stat-bar">
      <div>📦 <b>{sum(len(c["modules"]) for c in CATEGORIES)}</b> 模块</div>
      <div>🧪 <b>{sum(len([m for m in c["modules"] if m[3]]) for c in CATEGORIES)}</b> 有测试覆盖</div>
      <div>📚 <b>{len(DOCS_NAV)}</b> 设计/方案文档</div>
      <div>🟢 系统运行中</div>
    </div>
    <div class="cat-nav">
'''

# 顶部分类快速跳转
for cat in CATEGORIES:
    html += f'      <a href="#cat-{cat["id"]}">{cat["title"]}</a>\n'
html += '    </div>\n'

# 渲染所有分类
for cat in CATEGORIES:
    html += render_category(cat)

html += '''
  </main>
</div>
</body>
</html>
'''

# 写入文件
OUTPUT.write_text(html, encoding='utf-8')
print(f"✅ 已生成: {OUTPUT}")
print(f"   大小: {OUTPUT.stat().st_size} 字节")
print(f"   模块数: {sum(len(c['modules']) for c in CATEGORIES)}")
print(f"   文档数: {len(DOCS_NAV)}")

# 【2026-08-05 新增】自动部署到桌面门户。
# 页内链接已改为相对路径，只有放在带 mark42/ tests/ docs/ 副本的
# 门户目录下才能点开。生成在项目目录而不部署，等于生成了一份
# 链接全坏的页面 —— 这正是之前桌面只剩下载页的原因。
PORTAL = Path("/home/missyouangeled/Desktop/mark42-dev-portal")
if PORTAL.is_dir():
    import shutil
    dest = PORTAL / OUTPUT.name
    shutil.copy2(OUTPUT, dest)
    print(f"📦 已部署到门户: {dest}")
else:
    print(f"⚠️  未找到门户目录 {PORTAL}，跳过部署。"
          f"页内为相对路径，需放在带 mark42//tests//docs/ 副本的目录下才能点开。")
