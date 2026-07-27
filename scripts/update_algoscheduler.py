#!/usr/bin/env python3
"""Update algo_scheduler.py with CompressorRegistry integration."""

import sys
sys.path.insert(0, '.')

with open('mark42_modules/algo_scheduler.py', 'r') as f:
    content = f.read()

# Insert CompressorRegistry class after the import section
insert_pos = content.find('\nfrom text_compressor import text_compress\n\n') + len('\nfrom text_compressor import text_compress\n\n')

registry_code = '''
# ============================================================================
# Compressor Registry - 注册表模式 (Day ?)
# ============================================================================


class CompressorRegistry:
    """压缩算法注册表。

    支持按内容类型自动选择最优压缩算法，支持优先级排序。
    """

    def __init__(self):
        self._compressors = []  # List of {name, content_type, priority}

    def register(self, name: str, func, content_type: str, priority: int) -> None:
        """注册一个压缩算法。

        Args:
            name: 算法名称 - 用于在 module globals 中查找函数名
            func: 兼容参数，实际从命名空间动态查找
            content_type: 内容类型: json | code | diff | log | text
            priority: 优先级，数值越大优先级越高
        """
        self._compressors.append({
            "name": name,
            "content_type": content_type,
            "priority": priority,
        })

    def select(self, content: str, content_type: str = "") -> tuple[str, callable]:
        """根据内容选择最优压缩算法。

        从模块级全局命名空间动态查找函数，使 monkeypatch 有效。

        Args:
            content: 待压缩内容
            content_type: 可选的显式内容类型

        Returns:
            (name, compressor_func) 元组
        """
        if not content_type:
            content_type = self._detect_content_type(content)

        matching = [c for c in self._compressors if c["content_type"] == content_type]
        if not matching:
            matching = [c for c in self._compressors if c["content_type"] == "text"]

        if not matching:
            return "identity", lambda x: (x, {"ratio": 0.0})

        matching.sort(key=lambda x: x["priority"], reverse=True)
        name = matching[0]["name"]

        # 从当前模块的全局命名空间动态查找函数（支持 monkeypatch）
        import sys
        module_name = __name__
        mod = sys.modules.get(module_name)
        func = getattr(mod, name, None) if mod is not None else None

        if func is None or not callable(func):
            _module_map = {
                "smartcrush": ("smart_crusher", "smartcrush"),
                "code": ("code_compressor", "codecrush"),
                "diff": ("diff_compressor", "diff_compress"),
                "log": ("log_deduplicator", "logdedup"),
                "text": ("text_compressor", "text_compress"),
            }
            if name in _module_map:
                mod_path, fn_name = _module_map[name]
                try:
                    m = __import__(mod_path, fromlist=[fn_name])
                    func = getattr(m, fn_name, None)
                except Exception:
                    func = None

        if func is None or not callable(func):
            func = lambda x: (x, {"ratio": 0.0})

        return name, func

    def list(self) -> list[dict]:
        """列出所有已注册的压缩算法。

        Returns:
            压缩算法列表，按优先级降序排序
        """
        result = [
            {"name": c["name"], "content_type": c["content_type"], "priority": c["priority"]}
            for c in self._compressors
        ]
        result.sort(key=lambda x: x["priority"], reverse=True)
        return result

    def _detect_content_type(self, content: str) -> str:
        """自动检测内容类型。

        Args:
            content: 待检测内容

        Returns:
            内容类型: json | diff | code | log | text
        """
        if not content or not content.strip():
            return "text"

        stripped = content.strip()

        if stripped.startswith("{") or stripped.startswith("["):
            try:
                import json as _json
                _json.loads(content)
                return "json"
            except (ValueError, _json.JSONDecodeError):
                pass

        import re as _re
        if _re.search(r"^@@\s+-\d+", content, _re.MULTILINE):
            return "diff"

        if any(kw in content for kw in ["def ", "class ", "import ", "function ", "var ", "const ", "return ", "=>", "#!/","</"]):
            return "code"

        if any(log_kw in content for log_kw in ["ERROR", "WARN", "INFO", "DEBUG", "CRITICAL", "[ERROR]", "[WARN]", "[INFO]", "[DEBUG]"]):
            return "log"

        return "text"


# 全局注册表实例，预注册内置压缩算法
_compressor_registry = CompressorRegistry()
_compressor_registry.register("smartcrush", smartcrush, "json", 100)
_compressor_registry.register("code", codecrush, "code", 80)
_compressor_registry.register("diff", diff_compress, "diff", 90)
_compressor_registry.register("log", logdedup, "log", 70)
_compressor_registry.register("text", text_compress, "text", 50)
'''

content = content[:insert_pos] + registry_code + content[insert_pos:]

# Update process() function to use registry
# Find the compression section and replace it
process_pattern = r'(\s*# 2\. 压缩 \(如果需要\) - 按 route_algo 选择算法\n\s*if decision\.should_compress:\s*)if decision\.route_algo == "code":.*?\n        elif decision\.route_algo == "diff":.*?\n        elif decision\.route_algo == "log":.*?\n        elif decision\.route_algo == "text":.*?\n        else:  # smartcrush 默认\s*compressed, compress_stats = smartcrush\(current\)'
replacement = r'\2\n        # 使用 CompressorRegistry 替代硬编码的 if-else\n        explicit_route = decision.route_algo if decision.route_algo != "smartcrush" else None\n        \n        if explicit_route:\n            route_name = explicit_route\n            _, compressor_func = _compressor_registry.select(current, explicit_route)\n        else:\n            route_name, compressor_func = _compressor_registry.select(current)\n        \n        # Phase 2-2: env var 决定是否走 LLM\n        if route_name == "text" and _should_use_llm(current):\n            from llm_text_compressor import llm_text_compress\n            compressed, compress_stats = llm_text_compress(current, mode=_LLM_MODE)\n            result["llm_used"] = True\n        else:\n            compressed, compress_stats = compressor_func(current)\n            result["llm_used"] = False'

import re as regex
content = regex.sub(process_pattern, replacement, content, flags=regex.DOTALL)

# Write back
with open('mark42_modules/algo_scheduler.py', 'w') as f:
    f.write(content)

print("Successfully updated algo_scheduler.py")
