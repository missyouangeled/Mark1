"""内置记忆搜索锁扣实现：包装 QMD 向量引擎。"""

from __future__ import annotations

import os
import shutil
from typing import Any


class BuiltinMemory:
    """将 QMD 向量搜索引擎包装为 MemoryLock 接口。"""

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        try:
            import subprocess
            result = subprocess.run(
                ["qmd", "search", query, "--top-k", str(top_k), "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return []
            import json
            data = json.loads(result.stdout)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def index(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        # QMD 通过文件系统索引，不直接支持程序化写入
        return {"indexed": 0, "status": "not_implemented_for_qmd"}

    def health(self) -> bool:
        qmd_bin = shutil.which("qmd") or os.path.expanduser("~/.npm-global/bin/qmd")
        index_path = os.path.expanduser("~/.cache/qmd/index.sqlite")
        return bool(qmd_bin and os.path.isfile(qmd_bin) and os.path.isfile(index_path))
