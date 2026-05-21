#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）验证）
# 系统 / OS：Linux / macOS / Windows（取决于本机 OpenClaw 安装位置）
# 用途：修复 sessions.list / Control UI 模型下拉在运行中会话里优先显示旧 override、而不是当前实际运行模型的问题。

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_ROOT = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw"
TARGET_RELATIVE = Path("dist") / "session-utils-BcTdpiLf.js"

OLD_BLOCK_SELECTED = """function createSessionRowModelCacheKey(provider, model) {
\treturn `${normalizeLowercaseStringOrEmpty(provider)}\\0${normalizeOptionalString(model) ?? \"\"}`;
}
function resolveSessionSelectedModelRef(params) {
\tconst override = normalizeStoredOverrideModel({
\t\tproviderOverride: params.entry?.providerOverride,
\t\tmodelOverride: params.entry?.modelOverride
\t});
\tif (!override.modelOverride) return null;
\tif (!params.rowContext) return resolveSessionModelRef(params.cfg, params.entry, params.agentId, { allowPluginNormalization: params.allowPluginNormalization });
\tconst key = [
\t\tnormalizeAgentId(params.agentId),
\t\toverride.providerOverride ?? \"\",
\t\toverride.modelOverride
\t].join(\"\\0\");
\tconst cached = params.rowContext.selectedModelByOverrideRef.get(key);
\tif (cached) return cached;
\tconst selected = resolveSessionModelRef(params.cfg, params.entry, params.agentId, { allowPluginNormalization: params.allowPluginNormalization });
\tparams.rowContext.selectedModelByOverrideRef.set(key, selected);
\treturn selected;
}"""

NEW_BLOCK_SELECTED = """function createSessionRowModelCacheKey(provider, model) {
\treturn `${normalizeLowercaseStringOrEmpty(provider)}\\0${normalizeOptionalString(model) ?? \"\"}`;
}
function resolveSessionPromptReportModelRef(entry) {
\tconst reportProvider = normalizeOptionalString(entry?.systemPromptReport?.provider);
\tconst reportModel = normalizeOptionalString(entry?.systemPromptReport?.model);
\tif (!reportProvider || !reportModel) return null;
\tconst reportSessionId = normalizeOptionalString(entry?.systemPromptReport?.sessionId);
\tconst entrySessionId = normalizeOptionalString(entry?.sessionId);
\tif (reportSessionId && entrySessionId && reportSessionId !== entrySessionId) return null;
\treturn {
\t\tprovider: reportProvider,
\t\tmodel: reportModel
\t};
}
function resolveSessionSelectedModelRef(params) {
\tconst override = normalizeStoredOverrideModel({
\t\tproviderOverride: params.entry?.providerOverride,
\t\tmodelOverride: params.entry?.modelOverride
\t});
\tif (!override.modelOverride) return null;
\tif (params.entry?.status === \"running\" && resolveSessionPromptReportModelRef(params.entry)) return null;
\tif (!params.rowContext) return resolveSessionModelRef(params.cfg, params.entry, params.agentId, { allowPluginNormalization: params.allowPluginNormalization });
\tconst key = [
\t\tnormalizeAgentId(params.agentId),
\t\toverride.providerOverride ?? \"\",
\t\toverride.modelOverride
\t].join(\"\\0\");
\tconst cached = params.rowContext.selectedModelByOverrideRef.get(key);
\tif (cached) return cached;
\tconst selected = resolveSessionModelRef(params.cfg, params.entry, params.agentId, { allowPluginNormalization: params.allowPluginNormalization });
\tparams.rowContext.selectedModelByOverrideRef.set(key, selected);
\treturn selected;
}"""

OLD_BLOCK_MODEL_REF = """function resolveSessionModelRef(cfg, entry, agentId, options) {
\tconst normalizedOverride = normalizeStoredOverrideModel({
\t\tproviderOverride: entry?.providerOverride,
\t\tmodelOverride: entry?.modelOverride
\t});
\tif (normalizedOverride.providerOverride && normalizedOverride.modelOverride) return resolvePersistedSelectedModelRef({
\t\tdefaultProvider: normalizedOverride.providerOverride,
\t\toverrideProvider: normalizedOverride.providerOverride,
\t\toverrideModel: normalizedOverride.modelOverride,
\t\tallowPluginNormalization: options?.allowPluginNormalization
\t});
\tconst runtimeProvider = normalizeOptionalString(entry?.modelProvider);
\tconst runtimeModel = normalizeOptionalString(entry?.model);
\tif (runtimeProvider && runtimeModel) return {
\t\tprovider: runtimeProvider,
\t\tmodel: runtimeModel
\t};
\tconst resolved = agentId ? resolveDefaultModelForAgent({
\t\tcfg,
\t\tagentId,
\t\tallowPluginNormalization: options?.allowPluginNormalization
\t}) : resolveConfiguredModelRef({
\t\tcfg,
\t\tdefaultProvider: DEFAULT_PROVIDER,
\t\tdefaultModel: DEFAULT_MODEL,
\t\tallowPluginNormalization: options?.allowPluginNormalization
\t});
\tconst persisted = resolvePersistedSelectedModelRef({
\t\tdefaultProvider: resolved.provider || \"openai\",
\t\truntimeProvider,
\t\truntimeModel,
\t\toverrideProvider: normalizedOverride.providerOverride,
\t\toverrideModel: normalizedOverride.modelOverride,
\t\tallowPluginNormalization: options?.allowPluginNormalization
\t});
\tif (persisted) return persisted;
\treturn resolved;
}"""

NEW_BLOCK_MODEL_REF = """function resolveSessionModelRef(cfg, entry, agentId, options) {
\tconst normalizedOverride = normalizeStoredOverrideModel({
\t\tproviderOverride: entry?.providerOverride,
\t\tmodelOverride: entry?.modelOverride
\t});
\tconst runtimeProvider = normalizeOptionalString(entry?.modelProvider);
\tconst runtimeModel = normalizeOptionalString(entry?.model);
\tif (runtimeProvider && runtimeModel) return {
\t\tprovider: runtimeProvider,
\t\tmodel: runtimeModel
\t};
\tconst promptReportRef = entry?.status === \"running\" ? resolveSessionPromptReportModelRef(entry) : null;
\tif (promptReportRef) return promptReportRef;
\tif (normalizedOverride.providerOverride && normalizedOverride.modelOverride) return resolvePersistedSelectedModelRef({
\t\tdefaultProvider: normalizedOverride.providerOverride,
\t\toverrideProvider: normalizedOverride.providerOverride,
\t\toverrideModel: normalizedOverride.modelOverride,
\t\tallowPluginNormalization: options?.allowPluginNormalization
\t});
\tconst resolved = agentId ? resolveDefaultModelForAgent({
\t\tcfg,
\t\tagentId,
\t\tallowPluginNormalization: options?.allowPluginNormalization
\t}) : resolveConfiguredModelRef({
\t\tcfg,
\t\tdefaultProvider: DEFAULT_PROVIDER,
\t\tdefaultModel: DEFAULT_MODEL,
\t\tallowPluginNormalization: options?.allowPluginNormalization
\t});
\tconst persisted = resolvePersistedSelectedModelRef({
\t\tdefaultProvider: resolved.provider || \"openai\",
\t\truntimeProvider,
\t\truntimeModel,
\t\toverrideProvider: normalizedOverride.providerOverride,
\t\toverrideModel: normalizedOverride.modelOverride,
\t\tallowPluginNormalization: options?.allowPluginNormalization
\t});
\tif (persisted) return persisted;
\treturn resolved;
}"""


def die(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def resolve_package_root() -> Path:
    env_override = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    if env_override:
        candidate = Path(env_override).expanduser().resolve()
        if (candidate / TARGET_RELATIVE).exists():
            return candidate
        die(f"OPENCLAW_PACKAGE_ROOT 无效：{candidate}")

    if (DEFAULT_PACKAGE_ROOT / TARGET_RELATIVE).exists():
        return DEFAULT_PACKAGE_ROOT

    try:
        npm_root = subprocess.run(["npm", "root", "-g"], check=True, capture_output=True, text=True).stdout.strip()
        candidate = (Path(npm_root) / "openclaw").resolve()
        if (candidate / TARGET_RELATIVE).exists():
            return candidate
    except Exception:
        pass

    die("找不到 OpenClaw 包目录；可手动设置 OPENCLAW_PACKAGE_ROOT=/path/to/openclaw")


def patch_once(text: str, old: str, new: str, description: str) -> tuple[str, bool]:
    if new in text:
        return text, False
    if old not in text:
        die(f"未能定位需要替换的 {description}")
    return text.replace(old, new, 1), True


def main() -> int:
    package_root = resolve_package_root()
    target = package_root / TARGET_RELATIVE
    content = target.read_text(encoding="utf-8")

    changed_any = False
    content, changed = patch_once(content, OLD_BLOCK_SELECTED, NEW_BLOCK_SELECTED, "selected model patch block")
    changed_any = changed_any or changed
    content, changed = patch_once(content, OLD_BLOCK_MODEL_REF, NEW_BLOCK_MODEL_REF, "runtime model patch block")
    changed_any = changed_any or changed

    if changed_any:
        target.write_text(content, encoding="utf-8")
        print(f"patched: {target}")
    else:
        print(f"already-patched: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
