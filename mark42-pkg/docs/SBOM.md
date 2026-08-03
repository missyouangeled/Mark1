# SBOM - 软件物料清单

> **SBOM** = Software Bill of Materials（软件物料清单）
> 最后更新：2026-08-03

---

## 什么是 SBOM？

SBOM 就是一份"配料表"。

你买食品会看配料表——里面有什么原料、各占多少、有没有过敏原。SBOM 是软件界的配料表：它记录了一个软件项目用到了哪些第三方库、每个库的版本号、许可证是什么。

举个例子：Mark42 本身零第三方依赖，但开发环境里用了 pytest、ruff 等工具。SBOM 会把这些全部列出来，让你一眼看到"这个项目的供应链里到底有什么"。

## 为什么要有 SBOM？

1. **安全**：某个依赖爆出漏洞（比如 log4j 那种），你能在几分钟内查到"我有没有用到它"，不用翻半天代码。
2. **合规**：有些客户或开源协议要求你公开使用了哪些第三方组件。
3. **透明**：让别人（比如审计人员）知道你的软件是怎么组装的。

## 怎么生成？

### 方式一：手动运行脚本

```bash
cd mark42-pkg
./scripts/generate-sbom.sh
```

生成的文件在 `dist/sbom/mark42-sbom.json`。

### 方式二：在 CI 里自动生成

每次推送到 master 分支时，CI 会自动跑一个 `sbom` job 生成 SBOM 并上传为 artifact。你可以在 GitHub Actions 页面下载。

## 怎么看？

SBOM 是 JSON 格式的文件，可以用任何文本编辑器打开。关键字段：

| 字段 | 含义 |
|------|------|
| `metadata.component` | 主组件信息（就是 Mark42 自己） |
| `components` | 所有依赖组件列表 |
| `dependencies` | 组件之间的依赖关系 |
| `specVersion` | CycloneDX 规范版本 |

也可以用在线工具查看：把 JSON 文件上传到 [CycloneDX Tool Center](https://cyclonedx.org/tool-center/) 就能可视化。

## CI 里在哪？

在 `.github/workflows/mark42-ci.yml` 里，有一个叫 `sbom` 的 job。它的特点是：

- **不阻塞开发**：用了 `continue-on-error: true`，SBOM 生成失败不会让整个 CI 挂掉。
- **保留 30 天**：生成的 artifact 在 GitHub 上保留 30 天后自动删除。
- **在 test/lint/build/security 之后运行**：不影响核心流程。

## 用到的工具

- **cyclonedx-bom** (7.3.1)：Python 生态的 CycloneDX SBOM 生成工具
- **CycloneDX**：一个开源的 SBOM 标准格式，被广泛支持
- 文档：https://cyclonedx.org/

---

*如有疑问，请查看脚本源码 `scripts/generate-sbom.sh` 或 CI 配置 `.github/workflows/mark42-ci.yml`。*
