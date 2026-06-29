# Mark42 测试手册

> 实战手册。读这个能上手写测试，不用先读完 14.7KB 的设计方案。
> 
> 背景：2026-06-29 Phase 1 完成，111/111 测试通过，覆盖 37.8%。
> 详细设计：`docs/design/mark42-测试体系设计方案-20260629.md`
> 决策记录：`.learnings/ERRORS.md`（ERR-001 ~ ERR-004）

## 速查

| 我想... | 看哪 |
|---|---|
| 跑测试 | `pytest scripts/tests/` |
| 跑某个文件 | `pytest scripts/tests/unit/test_engine.py` |
| 看覆盖率 | `pytest scripts/tests/ --cov=mark42_modules --cov-report=html` 然后看 htmlcov/index.html |
| 并行加速 | `pytest scripts/tests/ -n auto` |
| 跑烟测（需真守护） | `pytest scripts/tests/smoke/ --runslow`（默认跳过） |
| 写新测试 | 往下读 ↓ |

## 测试目录结构

```
scripts/tests/
├── conftest.py                 # 🔑 共享 fixture + 环境隔离
├── unit/
│   ├── test_<module>.py        # 按源码模块命名
│   └── ...
├── integration/
│   └── (待 Phase 3 填充)
└── smoke/
    └── (默认跳过，需 --runslow)
```

## conftest 设计原则（必读）

### 1. autouse 环境隔离

每个测试自动：
- 准备 `tmp_path/state/`, `tmp_path/data/`, `tmp_path/scratch/`
- 设 `XDG_STATE_HOME`, `HOME` 环境变量
- reload `mark42_modules.config` 让它重新计算路径
- monkeypatch `DATA_ROOT`, `LOG_DIR`, `SCRATCH`, `BROKER_DIR`
- 强制 reload mark42_modules 所有模块（按依赖图顺序）

**结果**：测试永不污染真生产 `~/.local/state/openclaw/mark42/`。

### 2. 共享 fixture

```python
@pytest.fixture
def state_dir(_isolate_mark42_state):        # → mark42 状态目录根
@pytest.fixture
def armor_state(state_dir):                  # → armor 子目录
@pytest.fixture
def engine_state(state_dir):                 # → engine 子目录
@pytest.fixture
def heavy_state(state_dir):                  # → heavy 子目录（自动 mkdir）
@pytest.fixture
def broker_dir(state_dir):                   # → broker 事件目录
@pytest.fixture
def log_dir(_isolate_mark42_state):         # → 数据盘 logs 目录
@pytest.fixture
def scratch_dir(_isolate_mark42_state):     # → SCRATCH 临时目录
@pytest.fixture
def cli_runner():                            # → mark42.py CLI 包装
@pytest.fixture
def sample_messages():                       # → 标准 10 条 session 消息
@pytest.fixture
def fake_session_file(tmp_path):             # → 模拟 session jsonl
```

### 3. reload 顺序（关键！）

```python
reload_order = [
    "mark42_modules.utils",
    "mark42_modules.session_fence_safe",
    "mark42_modules.smart_crusher",
    # ... 压缩子模块
    "mark42_modules.armor",     # ← 先于 engine/heavy
    "mark42_modules.engine",    # ← 后于 armor（依赖）
    "mark42_modules.heavy",
    "mark42_modules.logs",
    "mark42_modules.cli",
]
```

**为什么**：Python `from .armor import X` 不会自动修复引用。
reload `armor` 后，`engine.X` 还是旧引用。所以**先重底层，再重上层**。

### 4. hard-code 路径陷阱 ⚠️

`config.py` 第 32 行 `SCRATCH = Path("/mnt/data/openclaw/scratch")` 是 hard-code，
**不会被 XDG_STATE 派生**。`heavy.SCRATCH` 在 reload 后还是旧值。

**修复**：reload 之后**额外** monkeypatch 依赖模块：

```python
modules_with_hard_paths = [
    ("mark42_modules.heavy", "SCRATCH"),
    ("mark42_modules.cli", "SCRATCH"),
]
for mod_name, attr in modules_with_hard_paths:
    monkeypatch.setattr(sys.modules[mod_name], attr, fake_scratch)
```

⚠️ **测试代码不要直接 `from mark42_modules.config import SCRATCH`**，
用 `scratch_dir` fixture 拿。

## 写新测试的样板

### Unit 测试模板

```python
"""<module>.py 测试群。

覆盖范围:
  - <function_1>  <description>
  - <function_2>  <description>

设计要点:
  - mock armor_check / armor_compress 避免真依赖
  - 用 tmp_path 验证写文件
"""

from unittest.mock import MagicMock, patch

import pytest

from mark42_modules import <module>


class TestFunction1:
    """<function_1>() 测试群。"""

    def test_normal_path(self, mocker):
        """正常路径返回期望结果。"""
        # 1. mock 依赖
        mocker.patch.object(<module>, "<dep>", return_value=...)
        # 2. 调被测函数
        result = <module>.<function_1>(...)
        # 3. 断言
        assert result["..."] == "..."

    def test_edge_case(self, mocker):
        """边界条件。"""
        mocker.patch.object(<module>, "<dep>", return_value=...)
        result = <module>.<function_1>(...)
        assert "..." in result["..."]
```

### Mock 助手 helper

```python
def _patch_du(mocker, size_kb: int):
    """mock 掉 armor 函数内 import 的 subprocess.run (du 调用)。

    armor.py 第 65 行用 `import subprocess as _sp` 然后 `_sp.run(...)`。
    这等价于 subprocess.run 全局对象, 所以 patch 全局一样生效。
    """
    fake_du = MagicMock()
    fake_du.stdout = f"{size_kb}\t/sessions"
    return mocker.patch("subprocess.run", return_value=fake_du)


def _dual_subprocess_mock(du_size_kb: int, cli_result: MagicMock = None):
    """mock 同时 du 和 openclaw agent 两种调用, 按 args 区分。"""
    def side_effect(args, **kwargs):
        if isinstance(args, (list, tuple)) and args:
            if args[0] == "du":
                fake = MagicMock()
                fake.stdout = f"{du_size_kb}\t/sessions"
                return fake
            elif args[0] == "openclaw":
                return cli_result if cli_result else MagicMock(returncode=0)
        return MagicMock()
    return side_effect


def _high_usage_session(target_pct: float):
    """构造一个会产生高使用率的 session mock。"""
    bytes_needed = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = bytes_needed
    return fake_session
```

## 常见陷阱（写测试前先看）

### 1. 函数体内 import

```python
# ❌ 错的（patch 不到）
mocker.patch.object(cli, "armor_check")

# ✅ 对的（patch 完整路径）
mocker.patch("mark42_modules.armor.armor_check")
```

### 2. `_sp = subprocess` 函数内 import

```python
# armor.py:
import subprocess as _sp
result = _sp.run(...)

# 测试要 patch 全局 subprocess.run:
mocker.patch("subprocess.run", return_value=fake)
```

### 3. fcntl.flock 文件锁

```python
# engine._save_loops 用 fcntl:
with open(lock_path, "a") as lf:
    fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
    _save_json(...)

# Mock 的 file handle 不能 fileno(), 所以测试必须 mock 整个 _save_loops:
mocker.patch.object(engine, "_save_loops")
```

### 4. hard-code 路径

```python
# config.py:
SCRATCH = Path("/mnt/data/openclaw/scratch")  # ← 不被 XDG_STATE 派生

# ❌ 错的
from mark42_modules.config import SCRATCH

# ✅ 对的（用 fixture）
def test_xxx(scratch_dir):
    task_dir = scratch_dir / "my-task"
```

### 5. conftest autouse 与 monkeypatch 的嵌套

```python
# autouse fixture 用 monkeypatch.setattr(...) 设临时值
# 测试体里再 monkeypatch.setenv(...) 会覆盖
# 测试结束时 pytest 自动 undo（按 LIFO 顺序）

# 验证示例:
def test_real_xdg_state_unchanged(monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", "/tmp/fake")
    assert os.environ["XDG_STATE_HOME"] == "/tmp/fake"
    monkeypatch.undo()  # ← 撤销后, 回到 autouse 设的值
    assert os.environ.get("XDG_STATE_HOME") == <conftest 设的临时值>
```

### 6. Daemon thread 测试

```python
def test_daemon_writes_heartbeat(engine_state):
    import threading
    t = threading.Thread(
        target=engine.engine_daemon,
        kwargs={"interval_s": 1},
        daemon=True,   # ← 关键：daemon=True, 主进程退出时强杀
    )
    t.start()
    time.sleep(2.5)  # 让 daemon 跑 2 个 tick
    
    heartbeat = engine_state / "daemon-heartbeat.json"
    assert heartbeat.exists()
    # 不调 t.join() — daemon=True 自动清理
```

### 7. `os.popen` vs `subprocess.run`

```python
# heavy_preflight 用 os.popen:
mem = os.popen("free -h | ...").read()

# mock 时不能用 mocker.patch("subprocess.run"):
# ✅ 正确
mocker.patch("os.popen", return_value=MagicMock(read=lambda: "16G"))
```

### 8. MagicMock 路径对象

MagicMock 不像 Path 对象，没有 .name, .suffix 等真实属性。
用 `_mock_kind` 自定义属性标识：

```python
fake_path = MagicMock()
fake_path._mock_kind = "config"  # ← 让 side_effect 区分
mocker.patch("mark42_modules.config.CONFIG_PATH", fake_path)
```

## 跑覆盖率

```bash
# 单文件
pytest scripts/tests/unit/test_armor_check.py \
    --cov=mark42_modules.armor --cov-report=term-missing

# 全部
pytest scripts/tests/ --cov=mark42_modules --cov-report=term-missing

# HTML 报告（打开 htmlcov/index.html）
pytest scripts/tests/ --cov=mark42_modules --cov-report=html
```

**覆盖率门禁**（pyproject.toml）：
- 当前：自动跑覆盖率，但不强制 fail
- 目标：Phase 2 末 `--cov-fail-under=60%`，Phase 3 末 `--cov-fail-under=70%`

## 测试原则（写作守则）

1. **测契约，不测实现**：断言返回字段，不断言函数怎么写
2. **每个测试一件事**：一个 test function 验一个 case，不堆叠
3. **边界优先**：正常 → 边界 → 异常 → 错误路径
4. **真环境零依赖**：mock 所有外部 IO（网络/磁盘/子进程）
5. **bug 优先暴露**：发现 bug 时写**红测试**标记，等代码修复后自动转绿

## 当前覆盖

| 模块 | 覆盖 | 备注 |
|---|---|---|
| armor.py | 50%+ | armor_check 100% / armor_compress 主路径 |
| engine.py | 56.7% | 5 个模板 + daemon 已测 |
| heavy.py | **85.9%** | detect + start/finish 全测 |
| cli.py | 39.7% | status_dashboard + main 分发 |
| utils.py | 51.2% | JSON helper |
| 整体 | **37.8%** | 目标 ≥ 70%（Phase 3 末） |

## 测试进度

- ✅ Phase 0：基础设施（conftest + pyproject）
- ✅ Phase 1：核心模块单测（armor/engine/heavy/cli）111 测试
- 🔲 Phase 2：压缩子模块 + logs 单测（~25 测试）
- 🔲 Phase 3：集成测试（armor → engine → broker 端到端）
- 🔲 Phase 4：CI 接入 + 覆盖率门禁

## 下次写测试前先看

1. `.learnings/ERRORS.md` — 历史 bug + 修复方案
2. `docs/design/mark42-测试体系设计方案-20260629.md` — 详细设计
3. 本文件第 4 节"常见陷阱"

---

_本手册随实战经验持续更新。新发现陷阱请追加到第 4 节并提交。_
EOF
echo "✅ mark42-测试手册.md 写完"
wc -l docs/design/mark42-测试手册.md