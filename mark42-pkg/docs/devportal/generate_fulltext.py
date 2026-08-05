#!/usr/bin/env python3
"""重新生成全量内联版（2MB+），把每个文件内容嵌进 HTML。"""
from pathlib import Path
import html as html_mod

DESKTOP = Path("/home/missyouangeled/Desktop/mark42-dev-portal")

# 所有源码/测试/文档路径
SECTIONS = [
    ("🛡️ 核心三模块", "mark42", [
        ("armor.py", "上下文铠甲"),
        ("engine.py", "循环引擎"),
        ("heavy.py", "重型战甲"),
    ]),
    ("🗜️ 压缩子系统", "mark42", [
        ("algo_scheduler.py", "算法调度器"),
        ("code_compressor.py", "代码压缩"),
        ("diff_compressor.py", "Diff压缩"),
        ("llm_text_compressor.py", "LLM语义压缩"),
        ("text_compressor.py", "文本压缩"),
        ("smart_crusher.py", "智能压缩调度"),
        ("compaction_diag.py", "压缩诊断"),
        ("compress_queue.py", "压缩队列"),
        ("pii_redactor.py", "PII脱敏"),
        ("log_deduplicator.py", "日志去重"),
    ]),
    ("🔍 审计子系统", "mark42/audit", [
        ("__init__.py", "审计入口"),
        ("checker.py", "审计检查器"),
        ("pinning.py", "Constraint Pinning"),
        ("snapshot_reader.py", "快照读取"),
        ("summary_extractor.py", "摘要提取"),
        ("report.py", "审计报告"),
    ]),
    ("⚙️ v3 核心 8", "mark42", [
        ("consciousness.py", "自主意识层"),
        ("code_analyzer.py", "代码理解引擎"),
        ("log_classifier.py", "日志分类器"),
        ("anomaly_detector.py", "异常检测器"),
        ("core_registry.py", "核心位注册表"),
        ("module_health.py", "模块健康监控"),
        ("failure_contract.py", "降级响应契约"),
        ("llm_provider.py", "LLM Provider"),
        ("error_archive.py", "错误档案"),
        ("circuit_breaker.py", "熔断器"),
        ("chaos_engine.py", "混沌工程"),
        ("cluster_manager.py", "集群管理器"),
        ("advisor_client.py", "Advisor Client"),
        ("actions_runner.py", "动作执行器"),
    ]),
    ("🔌 插件", "mark42/plugins", [
        ("builtin_memory.py", "内存"),
        ("builtin_health.py", "健康"),
        ("builtin_heavy.py", "重型"),
        ("builtin_compress.py", "压缩"),
        ("builtin_audit.py", "审计"),
        ("builtin_engine.py", "引擎"),
        ("builtin_archive.py", "归档"),
        ("builtin_consciousness.py", "意识"),
        ("builtin_chaos.py", "混沌"),
        ("builtin_breaker.py", "熔断"),
    ]),
    ("🛠️ 支撑/安全", "mark42", [
        ("config.py", "配置"),
        ("utils.py", "工具"),
        ("logs.py", "日志"),
        ("log_setup.py", "日志初始化"),
        ("user_config.py", "用户配置"),
        ("installer.py", "安装器"),
        ("__main__.py", "CLI入口"),
        ("metrics_server.py", "指标服务"),
        ("perf_bench.py", "性能基准"),
        ("context_safety.py", "上下文安全"),
        ("session_fence.py", "会话围栏"),
        ("output_guard.py", "输出防护"),
        ("watchdog.py", "看门狗"),
        ("cost_tracker.py", "成本追踪"),
    ]),
]

# 【2026-08-05 改为自动扫描】原为手工维护的固定清单，只收录了 42/77 个测试文件，
# 新增测试不会自动进门户，清单会持续腐化。现改为扫描 tests/ 目录，
# 保证门户与真实测试集永不脱节。排序保证输出稳定（便于 diff 对比）。
_TESTS_DIR = DESKTOP / "tests"
TESTS = sorted(
    p.relative_to(_TESTS_DIR).as_posix()
    for p in _TESTS_DIR.rglob("test_*.py")
) if _TESTS_DIR.is_dir() else []

DESIGN = [
    "mark42-8core-modules-v2.md",
    "mark42-架构设计.md",
    "mark42-开发手册-压缩子系统.md",
    "mark42-测试手册.md",
    "mark42-工程管理方案.md",
    "mark42-开发经验.md",
    "mark42-更新日志.md",
    "mark42-压缩方案借鉴Headroom-20260624.md",
    "mark42-全量审查报告-20260729.md",
    "mark42-发行审计报告-20260720.md",
    "mark42-性能基准报告-20260720.md",
    "mark42-ArcLock-通用适配层设计方案-20260722.md",
    "mark42-post-compact-audit-设计方案.md",
    "mark42-QuickStart-20260701.md",
    "mark42-UI设计哲学-SpaceX钢铁侠参考-20260714.md",
    "mark42-亮点-召回与综合分离-20260710.md",
    "mark42-修改风险评估报告-20260708.md",
    "mark42-商品介绍文案.md",
    "mark42-商品化路线图.md",
    "mark42-frontstage集成调研-20260720.md",
    "mark42-跨编码器接入方案-20260731.md",  # 🆕 今天的
    "mark42-缺口修复方案-20260731.md",      # 🆕 今天的
]

PLANS = [
    "40-Mark42-OS化深化方案-v3.md",
    "Mark42-v3-evaluation-20260714.md",
    "mark42-context-safety-min-spec-2026-07-09.md",
    "mark42-multi-agent-phase1-min-spec-2026-07-09.md",
    "37-2026-07-09Mark42-多Agent阶段性收口说明.md",
    "38-2026-07-09Mark42-Phase2-确认后执行.md",
    "39-2026-07-09Mark42-OS化深化方案-v2.md",
]

PKG = [
    "README.md", "QUICKSTART.md", "TUTORIAL.md", "ARCHITECTURE.md",
    "INDEX.md", "CHANGELOG.md", "ROADMAP.md", "MIGRATION.md",
    "TROUBLESHOOTING.md", "CONFIG-GUIDE.md", "SECURITY.md", "CONTRIBUTING.md",
]


def embed_file(path, file_type="py"):
    if not path.exists():
        return f'<div class="missing">❌ {path.name}</div>'
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        return f'<div class="missing">❌ {e}</div>'
    escaped = html_mod.escape(content)
    return f'<pre class="code code-{file_type}"><code>{escaped}</code></pre>'


def render_section(title, subdir, files):
    parts = [f'<section class="category">', f'<h2>{title}</h2>']
    for fname, label in files:
        fpath = DESKTOP / subdir / fname
        size = fpath.stat().st_size if fpath.exists() else 0
        parts.append(f'<div class="file-block">')
        parts.append(f'<h3>📄 {label} · {subdir}/{fname} <span class="size">({size} 字节)</span></h3>')
        parts.append(embed_file(fpath, "py"))
        parts.append('</div>')
    parts.append('</section>')
    return "\n".join(parts)


def render_tests():
    parts = ['<section class="category"><h2>🧪 测试文件 ({} 个)</h2>'.format(len(TESTS))]
    for t in TESTS:
        fpath = DESKTOP / "tests" / t
        if fpath.exists():
            parts.append(f'<div class="file-block">')
            parts.append(f'<h3>🧪 tests/{t} <span class="size">({fpath.stat().st_size} 字节)</span></h3>')
            parts.append(embed_file(fpath, "py"))
            parts.append('</div>')
    parts.append('</section>')
    return "\n".join(parts)


def render_design():
    parts = [f'<section class="category"><h2>📚 设计文档 ({len(DESIGN)} 篇)</h2>']
    for d in DESIGN:
        fpath = DESKTOP / "docs/design" / d
        if fpath.exists():
            parts.append(f'<div class="file-block">')
            parts.append(f'<h3>📚 {d} <span class="size">({fpath.stat().st_size} 字节)</span></h3>')
            parts.append(embed_file(fpath, "md"))
            parts.append('</div>')
    parts.append('</section>')
    return "\n".join(parts)


def render_plans():
    parts = [f'<section class="category"><h2>📋 方案/计划 ({len(PLANS)} 篇)</h2>']
    for p in PLANS:
        fpath = DESKTOP / "docs/plans" / p
        if fpath.exists():
            parts.append(f'<div class="file-block">')
            parts.append(f'<h3>📋 {p} <span class="size">({fpath.stat().st_size} 字节)</span></h3>')
            parts.append(embed_file(fpath, "md"))
            parts.append('</div>')
    parts.append('</section>')
    return "\n".join(parts)


def render_pkg():
    parts = [f'<section class="category"><h2>🚀 pkg 入门文档 ({len(PKG)} 篇)</h2>']
    for fname in PKG:
        fpath = DESKTOP / "docs" / fname
        if fpath.exists():
            parts.append(f'<div class="file-block">')
            parts.append(f'<h3>🚀 {fname} <span class="size">({fpath.stat().st_size} 字节)</span></h3>')
            parts.append(embed_file(fpath, "md"))
            parts.append('</div>')
    parts.append('</section>')
    return "\n".join(parts)


# 生成全量版
html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Mark42 全量代码+文档 v2.8.1</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.6; color: #1f2937; background: #f9fafb; }
.header { background: linear-gradient(135deg, #1e40af, #3b82f6); color: white; padding: 25px 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); position: sticky; top: 0; z-index: 100; }
.header h1 { font-size: 24px; }
.header .meta { opacity: 0.9; font-size: 13px; margin-top: 4px; }
.toc { background: white; padding: 15px 25px; border-bottom: 1px solid #e5e7eb; position: sticky; top: 90px; z-index: 99; }
.toc a { display: inline-block; padding: 4px 10px; margin: 2px; background: #eff6ff; color: #1e40af; text-decoration: none; border-radius: 12px; font-size: 12px; }
.toc a:hover { background: #1e40af; color: white; }
.main { max-width: 1200px; margin: 0 auto; padding: 20px 30px; }
.category { background: white; padding: 20px 25px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.category h2 { color: #1e40af; font-size: 18px; margin-bottom: 15px; padding-bottom: 8px; border-bottom: 2px solid #eff6ff; }
.file-block { margin: 15px 0; padding: 12px; background: #fafafa; border-radius: 6px; border: 1px solid #e5e7eb; }
.file-block h3 { font-size: 14px; color: #374151; margin-bottom: 8px; }
.file-block .size { color: #9ca3af; font-size: 11px; font-weight: normal; }
.code { background: #1e293b; color: #e2e8f0; padding: 15px; border-radius: 6px; overflow-x: auto; font-family: "Menlo", "Consolas", monospace; font-size: 12px; line-height: 1.5; max-height: 600px; overflow-y: auto; white-space: pre; }
.code-md { background: #f1f5f9; color: #1e293b; }
.missing { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 4px; }
</style>
</head>
<body>
<div class="header">
  <h1>🛡️ Mark42 全量代码 + 文档</h1>
  <div class="meta">模块化智能铠甲系统 · v2.8.1 · 包含 22 篇设计文档 + 7 个方案 + 1684 测试 · Ctrl+F 全文搜索</div>
</div>
<div class="toc">
  <strong style="color:#1e40af;margin-right:8px;">目录：</strong>
  <a href="#core">核心</a>
  <a href="#compression">压缩</a>
  <a href="#audit">审计</a>
  <a href="#v3core">v3核心</a>
  <a href="#plugins">插件</a>
  <a href="#support">支撑</a>
  <a href="#tests">测试</a>
  <a href="#design">设计</a>
  <a href="#plans">方案</a>
  <a href="#pkg">入门</a>
</div>
<div class="main">
"""

for title, subdir, files in SECTIONS:
    html += render_section(title, subdir, files)
html += render_tests()
html += render_design()
html += render_plans()
html += render_pkg()

html += """
</div>
</body>
</html>"""

out = DESKTOP / "index-fulltext.html"
out.write_text(html, encoding='utf-8')
size_mb = out.stat().st_size / 1024 / 1024
print(f"✅ 已生成: {out}")
print(f"   大小: {size_mb:.2f} MB ({out.stat().st_size} 字节)")
