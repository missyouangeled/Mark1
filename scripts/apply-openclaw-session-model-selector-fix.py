#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）验证）
# 系统 / OS：Linux / macOS / Windows（取决于本机 OpenClaw 安装位置）
# 用途：修复 Control UI / sessions.list 模型下拉与当前会话实际模型不一致的问题。
#   1) sessions.list / Control UI 会话列表：运行中会话优先显示真实运行模型，而不是旧 override。
#   2) Control UI 聊天页模型下拉：选择后必须调用 sessions.patch，使用后端 resolved 结果回填 UI，并允许 active run 期间提交 live-switch。

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_ROOT = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw"
CONTROL_UI_ASSETS_RELATIVE = Path("dist") / "control-ui" / "assets"

OLD_BLOCK_SELECTED = """function createSessionRowModelCacheKey(provider, model) {
\treturn `${normalizeLowercaseStringOrEmpty(provider)}\\0${normalizeOptionalString(model) ?? ""}`;
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
\t\toverride.providerOverride ?? "",
\t\toverride.modelOverride
\t].join("\\0");
\tconst cached = params.rowContext.selectedModelByOverrideRef.get(key);
\tif (cached) return cached;
\tconst selected = resolveSessionModelRef(params.cfg, params.entry, params.agentId, { allowPluginNormalization: params.allowPluginNormalization });
\tparams.rowContext.selectedModelByOverrideRef.set(key, selected);
\treturn selected;
}"""

NEW_BLOCK_SELECTED = """function createSessionRowModelCacheKey(provider, model) {
\treturn `${normalizeLowercaseStringOrEmpty(provider)}\\0${normalizeOptionalString(model) ?? ""}`;
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
\tif (params.entry?.status === "running" && resolveSessionPromptReportModelRef(params.entry)) return null;
\tif (!params.rowContext) return resolveSessionModelRef(params.cfg, params.entry, params.agentId, { allowPluginNormalization: params.allowPluginNormalization });
\tconst key = [
\t\tnormalizeAgentId(params.agentId),
\t\toverride.providerOverride ?? "",
\t\toverride.modelOverride
\t].join("\\0");
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
\t\tdefaultProvider: resolved.provider || "openai",
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
\tconst promptReportRef = entry?.status === "running" ? resolveSessionPromptReportModelRef(entry) : null;
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
\t\tdefaultProvider: resolved.provider || "openai",
\t\truntimeProvider,
\t\truntimeModel,
\t\toverrideProvider: normalizedOverride.providerOverride,
\t\toverrideModel: normalizedOverride.modelOverride,
\t\tallowPluginNormalization: options?.allowPluginNormalization
\t});
\tif (persisted) return persisted;
\treturn resolved;
}"""

LEGACY_CHAT_MODEL_SWITCH = "async function CW(e,t){if(!e.client||!e.connected)return!1;if(_U(e)===t)return!0;let n=e.sessionKey,r=e.chatModelOverrides[n];e.lastError=null,e.chatModelOverrides={...e.chatModelOverrides,[n]:yp(t)};let i=e.client,a,o=()=>{if(e.chatModelSwitchPromises?.[n]===a){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}};return a=(async()=>{try{return await i.request(`sessions.patch`,{key:n,model:t||null}),mW(e),await RU(e),!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},e.lastError=`Failed to set model: ${String(t)}`,!1}finally{o()}})(),e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:a},a}"

CURRENT_CHAT_MODEL_SWITCH = "async function CW(e,t){if(!e.client||!e.connected)return!1;let n=e.sessionKey,r=e.chatModelOverrides[n];e.lastError=null,e.chatModelOverrides={...e.chatModelOverrides,[n]:yp(t)};let i=e.client,a,o=()=>{if(e.chatModelSwitchPromises?.[n]===a){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}};return a=(async()=>{try{let s=await i.request(`sessions.patch`,{key:n,model:t||null}),c=typeof s?.resolved?.modelProvider==`string`?s.resolved.modelProvider.trim():``,l=typeof s?.resolved?.model==`string`?s.resolved.model.trim():``,u=t?c&&l?`${c}/${l}`:t:null;e.chatModelOverrides={...e.chatModelOverrides,[n]:u?yp(u):null};let d=e.sessionsResult;if(d&&s?.entry)e.sessionsResult={...d,sessions:d.sessions.map(e=>e.key===n||s.key&&e.key===s.key?{...e,...s.entry,key:e.key}:e)};await e.onSlashAction?.(`refresh-tools-effective`),mW(e),await RU(e);return!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},e.lastError=`Failed to set model: ${String(t)}`,!1}finally{o()}})(),e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:a},a}"

PREVIOUS_TARGET_CHAT_MODEL_SWITCH = "async function CW(e,t){if(!e.client||!e.connected)return!1;let n=e.sessionKey,r=e.chatModelOverrides[n],p=_U(e);e.lastError=null,e.chatModelOverrides={...e.chatModelOverrides,[n]:yp(t)};let i=e.client,a,o=()=>{if(e.chatModelSwitchPromises?.[n]===a){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}};return a=(async()=>{try{let s=await i.request(`sessions.patch`,{key:n,model:t||null}),c=typeof s?.resolved?.modelProvider==`string`?s.resolved.modelProvider.trim():``,l=typeof s?.resolved?.model==`string`?s.resolved.model.trim():``,u=t?c&&l?`${c}/${l}`:t:null;e.chatModelOverrides={...e.chatModelOverrides,[n]:u?yp(u):null};let d=e.sessionsResult;if(d&&s?.entry)e.sessionsResult={...d,sessions:d.sessions.map(e=>e.key===n||s.key&&e.key===s.key?{...e,...s.entry,key:e.key}:e)};if((u??null)!==(p??null)){try{await i.request(`chat.inject`,{sessionKey:n,message:`正在加载系统`,label:`system-loading`})}catch{};try{await i.request(`chat.inject`,{sessionKey:n,message:`OK 已经读取完成。`,label:`system-ready`})}catch{}}await e.onSlashAction?.(`refresh-tools-effective`),mW(e),await RU(e);return!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},e.lastError=`Failed to set model: ${String(t)}`,!1}finally{o()}})(),e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:a},a}"

TARGET_CHAT_MODEL_SWITCH = "async function CW(e,t){if(!e.client||!e.connected)return!1;let n=e.sessionKey,r=e.chatModelOverrides[n],p=_U(e);e.lastError=null,e.chatModelOverrides={...e.chatModelOverrides,[n]:yp(t)};let i=e.client,a,o=()=>{if(e.chatModelSwitchPromises?.[n]===a){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}};return a=(async()=>{try{let s=await i.request(`sessions.patch`,{key:n,model:t||null}),c=typeof s?.resolved?.modelProvider==`string`?s.resolved.modelProvider.trim():``,l=typeof s?.resolved?.model==`string`?s.resolved.model.trim():``,u=t?c&&l?`${c}/${l}`:t:null;e.chatModelOverrides={...e.chatModelOverrides,[n]:u?yp(u):null};let d=e.sessionsResult;if(d&&s?.entry)e.sessionsResult={...d,sessions:d.sessions.map(e=>e.key===n||s.key&&e.key===s.key?{...e,...s.entry,key:e.key}:e)};if((u??null)!==(p??null)){try{await i.request(`chat.inject`,{sessionKey:n,message:`正在加载系统`,label:`system-loading`})}catch{};try{await i.request(`chat.inject`,{sessionKey:n,message:`[系统指令] 你是新接管本会话的 AI 模型。在回复用户之前，必须依次读取以下文件：ACTIVE_RULES.md, BOOT_INDEX.md, SOUL.md, USER.md, MEMORY.md, SKILL_CATALOG.md, WORKSPACE_INDEX.md。读完后以「OK 已经读取完成。」作为第一行回复，然后再回应用户的消息。这是硬约束。`,label:`system-boot`})}catch{};try{await i.request(`chat.inject`,{sessionKey:n,message:`OK 已经读取完成。`,label:`system-ready`})}catch{}}await e.onSlashAction?.(`refresh-tools-effective`),mW(e),await RU(e);return!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},e.lastError=`Failed to set model: ${String(t)}`,!1}finally{o()}})(),e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:a},a}"

CURRENT_BUILTIN_CHAT_MODEL_SWITCH = "async function gz(e,t){if(!e.client||!e.connected)return!1;if(ZL(e)===t)return!0;let n=e.sessionKey,r=e.chatModelOverrides[n];_R(e,null),e.chatModelOverrides={...e.chatModelOverrides,[n]:Da(t)};let i=e.client,a={},o=()=>{if(e.chatModelSwitchPromises?.[n]===a.current){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}},s=(async()=>{try{return await i.request(`sessions.patch`,{key:n,...Nv(e,n),model:t||null}),QR(e),await bR(e),!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},_R(e,`Failed to set model: ${String(t)}`),!1}finally{o()}})();return a.current=s,e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:s},s}"

# v2026.6.8: function renamed gz → Gz
CURRENT_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8 = "async function Gz(e,t){if(!e.client||!e.connected)return!1;if(ER(e)===t)return!0;let n=e.sessionKey,r=e.chatModelOverrides[n];KR(e,null),e.chatModelOverrides={...e.chatModelOverrides,[n]:Oa(t)};let i=e.client,a={},o=()=>{if(e.chatModelSwitchPromises?.[n]===a.current){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}},s=(async()=>{try{return await i.request(`sessions.patch`,{key:n,...Lv(e,n),model:t||null}),Dz(e),await YR(e),!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},KR(e,`Failed to set model: ${String(t)}`),!1}finally{o()}})();return a.current=s,e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:s},s}"

PREVIOUS_TARGET_BUILTIN_CHAT_MODEL_SWITCH = "async function gz(e,t){if(!e.client||!e.connected)return!1;if(ZL(e)===t)return!0;let n=e.sessionKey,r=e.chatModelOverrides[n],i=ZL(e);_R(e,null),e.chatModelOverrides={...e.chatModelOverrides,[n]:Da(t)};let a=e.client,o={},s=()=>{if(e.chatModelSwitchPromises?.[n]===o.current){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}},c=(async()=>{try{let r=await a.request(`sessions.patch`,{key:n,...Nv(e,n),model:t||null}),l=typeof r?.resolved?.modelProvider==`string`?r.resolved.modelProvider.trim():``,u=typeof r?.resolved?.model==`string`?r.resolved.model.trim():``,d=t?l&&u?`${l}/${u}`:t:null;e.chatModelOverrides={...e.chatModelOverrides,[n]:d?Da(d):null};let f=e.sessionsResult;f&&r?.entry&&(e.sessionsResult={...f,sessions:f.sessions.map(e=>e.key===n||r.key&&e.key===r.key?{...e,...r.entry,key:e.key}:e)});if((d??null)!==(i??null)){try{await a.request(`chat.inject`,{sessionKey:n,message:`正在加载系统`,label:`system-loading`})}catch{};try{await a.request(`chat.inject`,{sessionKey:n,message:`[系统指令] 你是新接管本会话的 AI 模型。在回复用户之前，必须依次读取以下文件：BOOT_INDEX.md, SOUL.md, USER.md, MEMORY.md, SKILL_CATALOG.md, WORKSPACE_INDEX.md。读完后以「OK 已经读取完成。」作为第一行回复，然后再回应用户的消息。这是硬约束。`,label:`system-boot`})}catch{};try{await a.request(`chat.inject`,{sessionKey:n,message:`OK 已经读取完成。`,label:`system-ready`})}catch{}}await e.onSlashAction?.(`refresh-tools-effective`),QR(e),await bR(e);return!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},_R(e,`Failed to set model: ${String(t)}`),!1}finally{s()}})();return o.current=c,e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:c},c}"

TARGET_BUILTIN_CHAT_MODEL_SWITCH = "async function gz(e,t){if(!e.client||!e.connected)return!1;if(ZL(e)===t)return!0;let n=e.sessionKey,r=e.chatModelOverrides[n],i=ZL(e);_R(e,null),e.chatModelOverrides={...e.chatModelOverrides,[n]:Da(t)};let a=e.client,o={},s=()=>{if(e.chatModelSwitchPromises?.[n]===o.current){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}},c=(async()=>{try{let r=await a.request(`sessions.patch`,{key:n,...Nv(e,n),model:t||null}),l=typeof r?.resolved?.modelProvider==`string`?r.resolved.modelProvider.trim():``,u=typeof r?.resolved?.model==`string`?r.resolved.model.trim():``,d=t?l&&u?`${l}/${u}`:t:null;e.chatModelOverrides={...e.chatModelOverrides,[n]:d?Da(d):null};let f=e.sessionsResult;f&&r?.entry&&(e.sessionsResult={...f,sessions:f.sessions.map(e=>e.key===n||r.key&&e.key===r.key?{...e,...r.entry,key:e.key}:e)});if((d??null)!==(i??null)){try{await a.request(`chat.inject`,{sessionKey:n,message:`正在加载系统`,label:`system-loading`})}catch{};try{await a.request(`chat.inject`,{sessionKey:n,message:`[系统指令] 你是新接管本会话的 AI 模型。在回复用户之前，必须依次读取以下文件：ACTIVE_RULES.md, BOOT_INDEX.md, SOUL.md, USER.md, MEMORY.md, SKILL_CATALOG.md, WORKSPACE_INDEX.md。读完后以「OK 已经读取完成。」作为第一行回复，然后再回应用户的消息。这是硬约束。`,label:`system-boot`})}catch{};try{await a.request(`chat.inject`,{sessionKey:n,message:`OK 已经读取完成。`,label:`system-ready`})}catch{}}await e.onSlashAction?.(`refresh-tools-effective`),QR(e),await bR(e);return!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},_R(e,`Failed to set model: ${String(t)}`),!1}finally{s()}})();return o.current=c,e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:c},c}"

# v2026.6.8 target: Gz with resolved modelProvider/model backfill + inject boot chain + refresh-tools-effective
TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8 = "async function Gz(e,t){if(!e.client||!e.connected)return!1;if(ER(e)===t)return!0;let n=e.sessionKey,r=e.chatModelOverrides[n],i=ER(e);KR(e,null),e.chatModelOverrides={...e.chatModelOverrides,[n]:Oa(t)};let a=e.client,o={},s=()=>{if(e.chatModelSwitchPromises?.[n]===o.current){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}},c=(async()=>{try{let r=await a.request(`sessions.patch`,{key:n,...Lv(e,n),model:t||null}),l=typeof r?.resolved?.modelProvider==`string`?r.resolved.modelProvider.trim():``,u=typeof r?.resolved?.model==`string`?r.resolved.model.trim():``,d=t?l&&u?`${l}/${u}`:t:null;e.chatModelOverrides={...e.chatModelOverrides,[n]:d?Oa(d):null};let f=e.sessionsResult;f&&r?.entry&&(e.sessionsResult={...f,sessions:f.sessions.map(e=>e.key===n||r.key&&e.key===r.key?{...e,...r.entry,key:e.key}:e)});if((d??null)!==(i??null)){try{await a.request(`chat.inject`,{sessionKey:n,message:`正在加载系统`,label:`system-loading`})}catch{};try{await a.request(`chat.inject`,{sessionKey:n,message:`[系统指令] 你是新接管本会话的 AI 模型。在回复用户之前，必须依次读取以下文件：ACTIVE_RULES.md, BOOT_INDEX.md, SOUL.md, USER.md, MEMORY.md, SKILL_CATALOG.md, WORKSPACE_INDEX.md。读完后以「OK 已经读取完成。」作为第一行回复，然后再回应用户的消息。这是硬约束。`,label:`system-boot`})}catch{};try{await a.request(`chat.inject`,{sessionKey:n,message:`OK 已经读取完成。`,label:`system-ready`})}catch{}}await e.onSlashAction?.(`refresh-tools-effective`),Dz(e),await YR(e);return!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},KR(e,`Failed to set model: ${String(t)}`),!1}finally{s()}})();return o.current=c,e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:c},c}"

# v2026.6.9: function renamed Gz → sH
CURRENT_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_9 = "async function sH(e,t){if(!e.client||!e.connected)return!1;let n=e.sessionKey,r=e.chatModelOverrides[n];cV(e,null),e.chatModelOverrides={...e.chatModelOverrides,[n]:Oa(t)};let i=e.client,a={},o=()=>{if(e.chatModelSwitchPromises?.[n]===a.current){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}},s=(async()=>{try{let s=await i.request(`sessions.patch`,{key:n,...ny(e,n),model:t||null}),c=typeof s?.resolved?.modelProvider==`string`?s.resolved.modelProvider.trim():``,l=typeof s?.resolved?.model==`string`?s.resolved.model.trim():``,u=t?c&&l?`${c}/${l}`:t:null;e.chatModelOverrides={...e.chatModelOverrides,[n]:u?Oa(u):null};let d=e.sessionsResult;if(d&&s?.entry)e.sessionsResult={...d,sessions:d.sessions.map(e=>e.key===n||s.key&&e.key===s.key?{...e,...s.entry,key:e.key}:e)};await e.onSlashAction?.(`refresh-tools-effective`),UV(e),await dV(e);return!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},cV(e,`Failed to set model: ${String(t)}`),!1}finally{o()}})();return a.current=s,e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:s},s}"

TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_9 = "async function sH(e,t){if(!e.client||!e.connected)return!1;let n=e.sessionKey,r=e.chatModelOverrides[n];cV(e,null),e.chatModelOverrides={...e.chatModelOverrides,[n]:Oa(t)};let i=e.client,a={},o=()=>{if(e.chatModelSwitchPromises?.[n]===a.current){let t={...e.chatModelSwitchPromises};delete t[n],e.chatModelSwitchPromises=t}},s=(async()=>{try{let s=await i.request(`sessions.patch`,{key:n,...ny(e,n),model:t||null}),c=typeof s?.resolved?.modelProvider==`string`?s.resolved.modelProvider.trim():``,l=typeof s?.resolved?.model==`string`?s.resolved.model.trim():``,u=t?c&&l?`${c}/${l}`:t:null;e.chatModelOverrides={...e.chatModelOverrides,[n]:u?Oa(u):null};let d=e.sessionsResult;if(d&&s?.entry)e.sessionsResult={...d,sessions:d.sessions.map(e=>e.key===n||s.key&&e.key===s.key?{...e,...s.entry,key:e.key}:e)};try{await i.request(`chat.inject`,{sessionKey:n,message:`🔄 正在加载系统...`,label:`system-loading`})}catch{};try{await i.request(`chat.inject`,{sessionKey:n,message:`[系统指令] 你是新接管本会话的 AI 模型。在回复用户之前，必须依次读取以下文件：ACTIVE_RULES.md, BOOT_INDEX.md, SOUL.md, USER.md, MEMORY.md, SKILL_CATALOG.md, WORKSPACE_INDEX.md。读完后以「OK 已经读取完成。」作为第一行回复，然后再回应用户的消息。这是硬约束。`,label:`system-boot`})}catch{};try{await i.request(`chat.inject`,{sessionKey:n,message:`OK 已经读取完成。`,label:`system-ready`})}catch{};await e.onSlashAction?.(`refresh-tools-effective`),UV(e),await dV(e);return!0}catch(t){return e.chatModelOverrides={...e.chatModelOverrides,[n]:r},cV(e,`Failed to set model: ${String(t)}`),!1}finally{o()}})();return a.current=s,e.chatModelSwitchPromises={...e.chatModelSwitchPromises,[n]:s},s}"

OLD_MODEL_SELECT_BUSY_GUARD = "function hW(e){let{currentOverride:t,defaultLabel:n,options:r}=bU(e),i=e.chatLoading||e.chatSending||!!e.chatRunId||e.chatStream!==null,a=!e.connected||i||!!e.chatModelSwitchPromises?.[e.sessionKey]||e.chatModelsLoading&&r.length===0||!e.client,"
NEW_MODEL_SELECT_BUSY_GUARD = "function hW(e){let{currentOverride:t,defaultLabel:n,options:r}=bU(e),i=e.chatSending,a=!e.connected||i||!!e.chatModelSwitchPromises?.[e.sessionKey]||e.chatModelsLoading&&r.length===0||!e.client,"
CURRENT_BUILTIN_MODEL_SELECT_BUSY_GUARD = "function $R(e){let{currentOverride:t,defaultLabel:n,options:r}=eR(e),i=cz(e),a=nz(e,t),o=e.chatLoading||e.chatSending||!!e.chatRunId||e.chatStream!==null,s=!e.connected||o||!!e.chatModelSwitchPromises?.[e.sessionKey]||e.chatModelsLoading&&r.length===0||!e.client,c=!e.connected||o||!e.client||i.options.length===0&&i.currentOverride===``,"
TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD = "function $R(e){let{currentOverride:t,defaultLabel:n,options:r}=eR(e),i=cz(e),a=nz(e,t),o=e.chatSending,s=!e.connected||o||!!e.chatModelSwitchPromises?.[e.sessionKey]||e.chatModelsLoading&&r.length===0||!e.client,c=!e.connected||o||!e.client||i.options.length===0&&i.currentOverride===``,"

# v2026.6.8: renamed $R → Oz
CURRENT_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_8 = "function Oz(e){let{currentOverride:t,defaultLabel:n,options:r}=kR(e),i=Lz(e),a=jz(e,t),o=e.chatLoading||e.chatSending||!!e.chatRunId||e.chatStream!==null,s=!e.connected||o||!!e.chatModelSwitchPromises?.[e.sessionKey]||e.chatModelsLoading&&r.length===0||!e.client,c=!e.connected||o||!e.client||i.options.length===0&&i.currentOverride===``,"

TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_8 = "function Oz(e){let{currentOverride:t,defaultLabel:n,options:r}=kR(e),i=Lz(e),a=jz(e,t),o=e.chatSending,s=!e.connected||o||!!e.chatModelSwitchPromises?.[e.sessionKey]||e.chatModelsLoading&&r.length===0||!e.client,c=!e.connected||o||!e.client||i.options.length===0&&i.currentOverride===``,"

# v2026.6.9: renamed Oz → WV
CURRENT_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_9 = "function WV(e){let{currentOverride:t,defaultLabel:n,options:r}=GB(e),i=$V(e),a=qV(e,t),o=e.chatLoading||e.chatSending||!!e.chatRunId||e.chatStream!==null,s=!e.connected||o||!!e.chatModelSwitchPromises?.[e.sessionKey]||e.chatModelsLoading&&r.length===0||!e.client,c=!e.connected||o||!e.client||i.options.length===0&&i.currentOverride===``,"

TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_9 = "function WV(e){let{currentOverride:t,defaultLabel:n,options:r}=GB(e),i=$V(e),a=qV(e,t),o=e.chatSending,s=!e.connected||o||!!e.chatModelSwitchPromises?.[e.sessionKey]||e.chatModelsLoading&&r.length===0||!e.client,c=!e.connected||o||!e.client||i.options.length===0&&i.currentOverride===``,"


def die(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def resolve_package_root() -> Path:
    env_override = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    if env_override:
        candidate = Path(env_override).expanduser().resolve()
        if (candidate / "dist").exists():
            return candidate
        die(f"OPENCLAW_PACKAGE_ROOT 无效：{candidate}")

    if (DEFAULT_PACKAGE_ROOT / "dist").exists():
        return DEFAULT_PACKAGE_ROOT

    try:
        npm_root = subprocess.run(["npm", "root", "-g"], check=True, capture_output=True, text=True).stdout.strip()
        candidate = (Path(npm_root) / "openclaw").resolve()
        if (candidate / "dist").exists():
            return candidate
    except Exception:
        pass

    die("找不到 OpenClaw 包目录；可手动设置 OPENCLAW_PACKAGE_ROOT=/path/to/openclaw")


def patch_once(text: str, old: str, new: str, description: str) -> tuple[str, bool]:
    if new in text:
        return text, False
    count = text.count(old)
    if count != 1:
        die(f"未能唯一定位需要替换的 {description}（匹配数：{count}）")
    return text.replace(old, new, 1), True


def patch_any_once(text: str, olds: list[str], new: str, description: str) -> tuple[str, bool]:
    if new in text:
        return text, False
    matches = [(old, text.count(old)) for old in olds]
    present = [old for old, count in matches if count == 1]
    bad = [(old, count) for old, count in matches if count not in (0, 1)]
    if bad:
        die(f"未能唯一定位需要替换的 {description}（存在重复匹配）")
    if len(present) != 1:
        die(f"未能定位需要替换的 {description}（候选命中数：{len(present)}）")
    old = present[0]
    return text.replace(old, new, 1), True


def patch_session_utils(package_root: Path) -> list[Path]:
    dist_dir = package_root / "dist"
    candidates = sorted(dist_dir.glob("session-utils-*.js"))
    if not candidates:
        # 上游大版本可能改了文件名；这部分只影响 sessions.list 显示，不应阻断聊天页模型切换补丁。
        return []
    patched: list[Path] = []
    for target in candidates:
        content = target.read_text(encoding="utf-8")
        if "function resolveSessionSelectedModelRef" not in content or "function resolveSessionModelRef" not in content:
            continue
        changed_any = False
        content, changed = patch_once(content, OLD_BLOCK_SELECTED, NEW_BLOCK_SELECTED, "sessions.list selected model block")
        changed_any = changed_any or changed
        content, changed = patch_once(content, OLD_BLOCK_MODEL_REF, NEW_BLOCK_MODEL_REF, "sessions.list runtime model block")
        changed_any = changed_any or changed
        if changed_any:
            target.write_text(content, encoding="utf-8")
        patched.append(target)
    return patched


def patch_control_ui_model_selector(package_root: Path) -> list[Path]:
    assets_dir = package_root / CONTROL_UI_ASSETS_RELATIVE
    if not assets_dir.exists():
        die(f"Control UI assets 目录不存在：{assets_dir}")
    patched: list[Path] = []
    candidates = sorted(assets_dir.glob("index-*.js"))
    if not candidates:
        die(f"找不到 Control UI index-*.js：{assets_dir}")
    for asset in candidates:
        content = asset.read_text(encoding="utf-8")
        if 'data-chat-model-select="true"' not in content:
            continue
        updated = content
        changed_any = False
        is_v2026_6_8 = CURRENT_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8 in updated or TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8 in updated
        is_v2026_6_9 = CURRENT_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_9 in updated or TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_9 in updated
        already_patched_v2026_6_8 = TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8 in updated
        already_patched_v2026_6_9 = TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_9 in updated
        if is_v2026_6_9:
            if already_patched_v2026_6_9:
                patched.append(asset)
                continue
            # v2026.6.9: sH function
            updated, changed = patch_any_once(
                updated,
                [CURRENT_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_9, TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_9],
                TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_9,
                "chat model dropdown switch handler (v2026.6.9)",
            )
            changed_any = changed_any or changed
            updated, changed = patch_any_once(
                updated,
                [CURRENT_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_9, TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_9],
                TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_9,
                "chat model dropdown active-run disable guard (v2026.6.9)",
            )
        elif is_v2026_6_8:
            if already_patched_v2026_6_8:
                patched.append(asset)
                continue
            # v2026.6.8: Gz function
            updated, changed = patch_any_once(
                updated,
                [CURRENT_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8, TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8],
                TARGET_BUILTIN_CHAT_MODEL_SWITCH_V2026_6_8,
                "chat model dropdown switch handler (v2026.6.8)",
            )
            changed_any = changed_any or changed
            updated, changed = patch_any_once(
                updated,
                [CURRENT_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_8, TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_8],
                TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD_V2026_6_8,
                "chat model dropdown active-run disable guard (v2026.6.8)",
            )
        else:
            updated, changed = patch_any_once(
                updated,
                [LEGACY_CHAT_MODEL_SWITCH, CURRENT_CHAT_MODEL_SWITCH, PREVIOUS_TARGET_CHAT_MODEL_SWITCH, CURRENT_BUILTIN_CHAT_MODEL_SWITCH, PREVIOUS_TARGET_BUILTIN_CHAT_MODEL_SWITCH],
                TARGET_BUILTIN_CHAT_MODEL_SWITCH if (CURRENT_BUILTIN_CHAT_MODEL_SWITCH in updated or PREVIOUS_TARGET_BUILTIN_CHAT_MODEL_SWITCH in updated) else TARGET_CHAT_MODEL_SWITCH,
                "chat model dropdown switch handler",
            )
            changed_any = changed_any or changed
            updated, changed = patch_any_once(
                updated,
                [OLD_MODEL_SELECT_BUSY_GUARD, CURRENT_BUILTIN_MODEL_SELECT_BUSY_GUARD, TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD],
                TARGET_BUILTIN_MODEL_SELECT_BUSY_GUARD if CURRENT_BUILTIN_MODEL_SELECT_BUSY_GUARD in updated else NEW_MODEL_SELECT_BUSY_GUARD,
                "chat model dropdown active-run disable guard",
            )
        changed_any = changed_any or changed
        if changed_any:
            asset.write_text(updated, encoding="utf-8")
        patched.append(asset)
    if not patched:
        die("未能定位 Control UI 聊天页模型下拉补丁入口")
    return patched


def patch_control_ui_cache_bust(package_root: Path, assets: list[Path]) -> list[Path]:
    """Force browsers/service workers to fetch the patched hashed bundle."""
    index_html = package_root / "dist" / "control-ui" / "index.html"
    if not index_html.exists() or not assets:
        return []
    version = str(max(int(asset.stat().st_mtime) for asset in assets))
    html = index_html.read_text(encoding="utf-8")
    updated = html
    for asset in assets:
        name = asset.name
        old_plain = f'src="./assets/{name}"'
        old_with_query_prefix = f'src="./assets/{name}?jarvisModelSelector='
        new_src = f'src="./assets/{name}?jarvisModelSelector={version}"'
        if old_plain in updated:
            updated = updated.replace(old_plain, new_src, 1)
            break
        if old_with_query_prefix in updated:
            start = updated.index(old_with_query_prefix)
            end = updated.index('"', start + len('src="'))
            updated = updated[:start] + new_src + updated[end + 1:]
            break
    if updated != html:
        index_html.write_text(updated, encoding="utf-8")
    return [index_html]


def main() -> int:
    package_root = resolve_package_root()
    patched_paths: list[Path] = []
    patched_paths.extend(patch_session_utils(package_root))
    control_ui_assets = patch_control_ui_model_selector(package_root)
    patched_paths.extend(control_ui_assets)
    patched_paths.extend(patch_control_ui_cache_bust(package_root, control_ui_assets))
    for path in patched_paths:
        print(f"patched-or-current: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
