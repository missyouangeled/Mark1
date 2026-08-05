# Contributing to Mark42

感谢你对 Mark42 的兴趣！欢迎贡献代码、报告问题或提出建议。

## 开发环境

```bash
git clone https://github.com/missyouangeled/Mark1.git
cd Mark1/mark42-pkg
pip install -e . --break-system-packages
pip install pytest ruff
```

## 开发流程

1. Fork 仓库并创建分支：`git checkout -b feature/your-feature`
2. 编写代码，确保：
   - `ruff check mark42/ tests/` 无新增错误
   - `pytest tests/ -q` 全部通过
   - 新功能有对应测试
3. 提交 PR，描述清楚改动内容和原因

## 代码风格

- Python 3.10+
- 纯标准库，不引入第三方依赖
- 函数必须有类型注解
- 中文注释和文档字符串优先（项目面向中文用户）

## 测试

```bash
# 运行全部测试
pytest tests/ -q

# 带覆盖率
pytest tests/ -q --cov=mark42 --cov-report=term-missing
```

## 报告问题

请在 [GitHub Issues](https://github.com/missyouangeled/Mark1/issues) 提交问题，包含：
- 问题描述
- 复现步骤
- 期望行为
- 实际行为
- 环境信息（OS、Python 版本、Mark42 版本）
