"""pytest 配置：确保 mark42 包可导入。"""
import sys
from pathlib import Path

# 把包目录的父目录加入 sys.path
pkg_parent = Path(__file__).resolve().parent.parent
if str(pkg_parent) not in sys.path:
    sys.path.insert(0, str(pkg_parent))
