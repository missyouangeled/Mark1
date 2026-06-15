#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）验证）
# 系统 / OS：Linux / macOS / Windows（取决于本机 OpenClaw 安装位置）
# 用途：为本机 OpenClaw Control UI 重复应用品牌补丁，覆盖左上角品牌名、图标、浏览器标题、PWA 清单，以及页面中可见的 OpenClaw 品牌字样。

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = WORKSPACE / "config" / "control-ui-branding.json"
DEFAULT_PACKAGE_ROOT = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw"
INJECT_MARKER_START = "<!-- jarvis-branding:begin -->"
INJECT_MARKER_END = "<!-- jarvis-branding:end -->"
SCRIPT_NAME = "jarvis-branding-override.js"
CHAT_RUNNING_PATCH_PATTERNS = [
    "let t=e.connected,n=e.sending||e.stream!==null,r=!!(e.canAbort&&e.onAbort),i=e.compactionStatus?.phase===`active`||e.compactionStatus?.phase===`retrying`,a=e.sessions?.sessions?.find(t=>t.key===e.sessionKey),",
    "let t=e.connected,n=e.sending||e.stream!==null||!!e.canAbort||(e.queue?.length??0)>0,r=!!(e.canAbort&&e.onAbort),i=e.compactionStatus?.phase===`active`||e.compactionStatus?.phase===`retrying`,a=e.sessions?.sessions?.find(t=>t.key===e.sessionKey),",
    "let t=e.connected,n=e.loading||e.sending||e.stream!==null||!!e.canAbort||(e.queue?.length??0)>0,r=!!(e.canAbort&&e.onAbort),i=e.compactionStatus?.phase===`active`||e.compactionStatus?.phase===`retrying`,a=e.sessions?.sessions?.find(t=>t.key===e.sessionKey),",
]
CHAT_RUNNING_PATCH_NEW = "let t=e.connected,a=e.sessions?.sessions?.find(t=>t.key===e.sessionKey),n=e.loading||e.sending||e.stream!==null||!!e.canAbort||(e.queue?.length??0)>0||a?.hasActiveRun===!0||a?.status===`running`,r=!!(e.canAbort&&e.onAbort),i=e.compactionStatus?.phase===`active`||e.compactionStatus?.phase===`retrying`,"
INVALID_FINAL_RELOAD_PATCH_OLD = "if(d&&(s.pendingSessionMessageReloadSessionKey=null),u&&!o&&!a){Gl(e);return}f&&!o&&Gl(e)"
INVALID_FINAL_RELOAD_PATCH_OLD_V2 = "if(d&&(s.pendingSessionMessageReloadSessionKey=null),u&&!o&&!a){xl(e);return}f&&!o&&xl(e)"
INVALID_FINAL_RELOAD_PATCH_NEW = "if(d&&(s.pendingSessionMessageReloadSessionKey=null),u&&!o&&!a)return;f&&!o&&Gl(e)"
INVALID_FINAL_RELOAD_PATCH_NEW_V2 = "if(d&&(s.pendingSessionMessageReloadSessionKey=null),u&&!o&&!a)return;f&&!o&&xl(e)"
YIELDED_HISTORY_REPLAY_HELPER_OLD = "function Bl(e,t){if(t.length===0)return e;if(e.length===0)return t.filter(e=>Rl(e)&&!Il(e)).length===t.length?t:e;let n=new Map;e.forEach((e,t)=>{let r=zl(e);r&&n.set(r,t)});let r=-1,i=-1;for(let e=t.length-1;e>=0;e--){let a=zl(t[e]),o=a?n.get(a):void 0;if(typeof o==`number`){r=e,i=o;break}}if(r<0||i<e.length-1)return e;let a=[];for(let i of t.slice(r+1)){if(!Rl(i)||Il(i))return e;let t=zl(i);if(!t||n.has(t))return e;a.push(i)}return a.length>0?[...e,...a]:e}"
YIELDED_HISTORY_REPLAY_HELPER_NEW = "function Bl(e,t){if(t.length===0)return e;if(e.length===0)return t.filter(e=>Rl(e)&&!Il(e)).length===t.length?t:e;let n=new Map;e.forEach((e,t)=>{let r=zl(e);r&&n.set(r,t)});let r=-1,i=-1;for(let e=t.length-1;e>=0;e--){let a=zl(t[e]),o=a?n.get(a):void 0;if(typeof o==`number`){r=e,i=o;break}}if(r<0||i<e.length-1)return e;let a=[];for(let i of t.slice(r+1)){if(!Rl(i)||Il(i))return e;let t=zl(i);if(!t||n.has(t))return e;a.push(i)}return a.length>0?[...e,...a]:e}function JarvisReadYieldedToolResultText(e){let t=g(e?.role);if(t!==`toolresult`)return null;let n=typeof e?.content==`string`?e.content:Array.isArray(e?.content)?e.content.map(e=>typeof e?.text==`string`?e.text:``).join(`\n`):typeof e?.text==`string`?e.text:``;if(!n.trim())return null;try{let r=JSON.parse(n),i=typeof r?.message==`string`?r.message.trim():``;return r?.status===`yielded`&&i&&i!==`NO_REPLY`?i:null}catch{return null}}function JarvisProjectYieldedHistoryReply(e){if(!Array.isArray(e)||e.length===0)return[];let t=e.filter(e=>!Il(e)),n=-1;for(let t=e.length-1;t>=0;t--){if(g(e[t]?.role)===`user`){n=t;break}}if(n<0)return t;for(let r=e.length-1;r>n;r--){let i=e[r];if(Rl(i)&&!Il(i)&&g(i?.role)===`assistant`)return t}for(let r=e.length-1;r>n;r--){let i=JarvisReadYieldedToolResultText(e[r]);if(!i)continue;let a={role:`assistant`,content:[{type:`text`,text:i}],timestamp:typeof e[r]?.timestamp==`number`?e[r].timestamp:Date.now()},o=zl(a);return o&&!t.some(e=>zl(e)===o)?[...t,a]:t}return t}"
YIELDED_HISTORY_REPLAY_HELPER_V2 = "function Bl(e,t){if(t.length===0)return e;if(e.length===0)return t.filter(e=>Rl(e)&&!Il(e)).length===t.length?t:e;let n=new Map;e.forEach((e,t)=>{let r=zl(e);r&&n.set(r,t)});let r=-1,i=-1;for(let e=t.length-1;e>=0;e--){let a=zl(t[e]),o=a?n.get(a):void 0;if(typeof o==`number`){r=e,i=o;break}}if(r<0||i<e.length-1)return e;let a=[];for(let i of t.slice(r+1)){if(!Rl(i)||Il(i))return e;let t=zl(i);if(!t||n.has(t))return e;a.push(i)}return a.length>0?[...e,...a]:e}function JarvisReadYieldedToolResultText(e){let t=g(e?.role);if(t!==`toolresult`)return null;let n=typeof e?.content==`string`?e.content:Array.isArray(e?.content)?e.content.map(e=>typeof e?.text==`string`?e.text:``).join(`\n`):typeof e?.text==`string`?e.text:``;if(!n.trim())return null;try{let r=JSON.parse(n),i=typeof r?.message==`string`?r.message.trim():``;return r?.status===`yielded`&&i&&i!==`NO_REPLY`?i:null}catch{return null}}function JarvisProjectYieldedHistoryReply(e){if(!Array.isArray(e)||e.length===0)return[];let t=e.filter(e=>!Il(e)),n=-1;for(let t=e.length-1;t>=0;t--){if(g(e[t]?.role)===`user`){n=t;break}}if(n<0)return t;for(let r=e.length-1;r>n;r--){let i=e[r];if(Rl(i)&&!Il(i)&&g(i?.role)===`assistant`)return t}for(let r=e.length-1;r>n;r--){let i=JarvisReadYieldedToolResultText(e[r]);if(!i)continue;let a={role:`assistant`,content:[{type:`text`,text:i}],timestamp:typeof e[r]?.timestamp==`number`?e[r].timestamp:Date.now()},o=zl(a);return o&&!t.some(e=>zl(e)===o)?[...t,a]:t}return t}function JarvisAssistantHasVisibleContent(e){let t=JT(e),n=LT(t.role).toLowerCase();if(n!==`assistant`)return!1;for(let r of t.content){if(!r||typeof r!=`object`)continue;if(r.type===`text`&&typeof r.text==`string`){let e=r.text.trim();if(e&&e!==`NO_REPLY`)return!0}if(r.type===`attachment`||r.type===`canvas`)return!0}return!1}function JarvisShouldShowPendingReadingIndicator(e){if(!e||typeof e!=`object`)return!1;let t=e.sessionHasActiveRun===!0||e.sessionStatus===`running`,n=typeof e.sessionEndedAt==`number`&&Date.now()-e.sessionEndedAt<=2e4;if(!t&&!n)return!1;let r=Array.isArray(e.messages)?e.messages:[],i=Array.isArray(e.toolMessages)?e.toolMessages:[],a=-1;for(let e=r.length-1;e>=0;e--){if(g(r[e]?.role)===`user`){a=e;break}}if(a<0)return!1;let o=!1,s=!1,c=0;for(let e=a+1;e<r.length;e++){let t=r[e];if(!t||typeof t!=`object`)continue;if(JarvisAssistantHasVisibleContent(t)){o=!0;break}let n=LT(JT(t).role).toLowerCase();(n===`assistant`||n===`toolresult`)&&(s=!0);let i=typeof t.timestamp==`number`?t.timestamp:0;i>c&&(c=i)}if(o)return!1;if(i.length>0)return!0;if(!s)return!1;return t||!c||Date.now()-c<=3e4}"
YIELDED_HISTORY_REPLAY_HELPER_CURRENT = "function JarvisReadYieldedToolResultText(e){let t=typeof e?.role==`string`?e.role.toLowerCase():``;if(t!==`toolresult`&&t!==`tool_result`&&t!==`tool`&&t!==`function`)return null;let n=typeof e?.content==`string`?e.content:Array.isArray(e?.content)?e.content.map(e=>typeof e?.text==`string`?e.text:``).join(`\n`):typeof e?.text==`string`?e.text:``;if(!n.trim())return null;try{let r=JSON.parse(n),i=typeof r?.message==`string`?r.message.trim():``;return r?.status===`yielded`&&i&&!/^\\s*NO_REPLY\\s*$/.test(i)?i:null}catch{return null}}function JarvisProjectYieldedHistoryReply(e){if(!Array.isArray(e)||e.length===0)return[];let t=e.filter(e=>!Uc(e)),n=-1;for(let t=e.length-1;t>=0;t--){let r=typeof e[t]?.role==`string`?e[t].role.toLowerCase():``;if(r===`user`){n=t;break}}if(n<0)return t;for(let r=e.length-1;r>n;r--){let i=MT(e[r]),a=yT(i.role).toLowerCase();if(a===`assistant`&&i.content.length>0)return t}for(let r=e.length-1;r>n;r--){let i=JarvisReadYieldedToolResultText(e[r]);if(!i)continue;let a={role:`assistant`,content:[{type:`text`,text:i}],timestamp:typeof e[r]?.timestamp==`number`?e[r].timestamp:Date.now()};return[...t,a]}return t}function JarvisAssistantHasVisibleContent(e){let t=MT(e),n=yT(t.role).toLowerCase();if(n!==`assistant`)return!1;for(let r of t.content){if(!r||typeof r!=`object`)continue;if(r.type===`text`&&typeof r.text==`string`){let e=r.text.trim();if(e&&!/^\\s*NO_REPLY\\s*$/.test(e))return!0}if(r.type===`attachment`||r.type===`canvas`)return!0}return!1}function JarvisShouldShowPendingReadingIndicator(e){if(!e||typeof e!=`object`)return!1;let t=e.sessionHasActiveRun===!0||e.sessionStatus===`running`,n=typeof e.sessionEndedAt==`number`&&Date.now()-e.sessionEndedAt<=2e4;if(!t&&!n)return!1;let r=Array.isArray(e.messages)?e.messages:[],i=Array.isArray(e.toolMessages)?e.toolMessages:[],a=-1;for(let e=r.length-1;e>=0;e--){let t=typeof r[e]?.role==`string`?r[e].role.toLowerCase():``;if(t===`user`){a=e;break}}if(a<0)return!1;let o=!1,s=!1,c=0;for(let e=a+1;e<r.length;e++){let t=r[e];if(!t||typeof t!=`object`)continue;if(JarvisAssistantHasVisibleContent(t)){o=!0;break}let n=yT(MT(t).role).toLowerCase();(n===`assistant`||n===`tool`)&&(s=!0);let i=typeof t.timestamp==`number`?t.timestamp:0;i>c&&(c=i)}if(o)return!1;if(i.length>0)return!0;if(!s)return!1;return t||!c||Date.now()-c<=3e4}"
YIELDED_HISTORY_REPLAY_APPLY_OLD = "e.chatMessages=Bl((Array.isArray(a.messages)?a.messages:[]).filter(e=>!Il(e)),i),"
YIELDED_HISTORY_REPLAY_APPLY_NEW = "e.chatMessages=Bl(JarvisProjectYieldedHistoryReply(Array.isArray(a.messages)?a.messages:[]),i),"
YIELDED_HISTORY_REPLAY_APPLY_OLD_V2 = "let t=[],n=(Array.isArray(e.messages)?e.messages:[]).filter(e=>!Uc(e)),r=Array.isArray(e.toolMessages)?e.toolMessages:[],"
YIELDED_HISTORY_REPLAY_APPLY_NEW_V2 = "let t=[],n=JarvisProjectYieldedHistoryReply((Array.isArray(e.messages)?e.messages:[]).filter(e=>!Uc(e))),r=Array.isArray(e.toolMessages)?e.toolMessages:[],"
PENDING_READING_INDICATOR_ARGS_OLD = "x=kD({sessionKey:e.sessionKey,messages:e.messages,toolMessages:e.toolMessages,streamSegments:e.streamSegments,stream:e.stream,streamStartedAt:e.streamStartedAt,showToolCalls:e.showToolCalls,searchOpen:Z.searchOpen,searchQuery:Z.searchQuery});"
PENDING_READING_INDICATOR_ARGS_NEW = "x=kD({sessionKey:e.sessionKey,messages:e.messages,toolMessages:e.toolMessages,streamSegments:e.streamSegments,stream:e.stream,streamStartedAt:e.streamStartedAt,sessionHasActiveRun:a?.hasActiveRun===!0,sessionStatus:a?.status??null,sessionEndedAt:a?.endedAt??null,showToolCalls:e.showToolCalls,searchOpen:Z.searchOpen,searchQuery:Z.searchQuery});"
PENDING_READING_INDICATOR_APPLY_OLD = "let o=e.streamSegments??[],s=Math.max(o.length,r.length);for(let i=0;i<s;i++)i<o.length&&o[i].text.trim().length>0&&t.push({kind:`stream`,key:`stream-seg:${e.sessionKey}:${i}`,text:o[i].text,startedAt:o[i].ts}),i<r.length&&e.showToolCalls&&t.push({kind:`message`,key:AD(r[i],i+n.length),message:r[i]});if(e.stream!==null){let n=`stream:${e.sessionKey}:${e.streamStartedAt??`live`}`;e.stream.trim().length>0?t.push({kind:`stream`,key:n,text:e.stream,startedAt:e.streamStartedAt??Date.now()}):t.push({kind:`reading-indicator`,key:n})}return ED(OD(t))}"
PENDING_READING_INDICATOR_APPLY_NEW = "let o=e.streamSegments??[],s=Math.max(o.length,r.length);for(let i=0;i<s;i++)i<o.length&&o[i].text.trim().length>0&&t.push({kind:`stream`,key:`stream-seg:${e.sessionKey}:${i}`,text:o[i].text,startedAt:o[i].ts}),i<r.length&&e.showToolCalls&&t.push({kind:`message`,key:AD(r[i],i+n.length),message:r[i]});let c=JarvisShouldShowPendingReadingIndicator(e);if(e.stream!==null||c){let n=`stream:${e.sessionKey}:${e.streamStartedAt??`live`}`;e.stream!==null&&e.stream.trim().length>0?t.push({kind:`stream`,key:n,text:e.stream,startedAt:e.streamStartedAt??Date.now()}):t.push({kind:`reading-indicator`,key:n})}return ED(OD(t))}"
PENDING_READING_INDICATOR_APPLY_OLD_V2 = "let o=e.streamSegments??[],s=Math.max(o.length,r.length);for(let i=0;i<s;i++){if(i<o.length){let n=OD(o[i].text);n.length>0&&t.push({kind:`stream`,key:`stream-seg:${e.sessionKey}:${i}`,text:n,startedAt:o[i].ts})}i<r.length&&e.showToolCalls&&t.push({kind:`message`,key:AD(r[i],i+n.length),message:r[i]})}if(e.stream!==null){let n=`stream:${e.sessionKey}:${e.streamStartedAt??`live`}`,r=OD(e.stream);r.length>0?Bc(r).shouldSkip||t.push({kind:`stream`,key:n,text:r,startedAt:e.streamStartedAt??Date.now()}):e.stream.trim().length===0&&t.push({kind:`reading-indicator`,key:n})}return wD(ED(t))}"
PENDING_READING_INDICATOR_APPLY_NEW_V2 = "let o=e.streamSegments??[],s=Math.max(o.length,r.length);for(let i=0;i<s;i++){if(i<o.length){let n=OD(o[i].text);n.length>0&&t.push({kind:`stream`,key:`stream-seg:${e.sessionKey}:${i}`,text:n,startedAt:o[i].ts})}i<r.length&&e.showToolCalls&&t.push({kind:`message`,key:AD(r[i],i+n.length),message:r[i]})}let c=JarvisShouldShowPendingReadingIndicator(e);if(e.stream!==null||c){let n=`stream:${e.sessionKey}:${e.streamStartedAt??`live`}`,r=e.stream!==null?OD(e.stream):``;r.length>0?Bc(r).shouldSkip||t.push({kind:`stream`,key:n,text:r,startedAt:e.streamStartedAt??Date.now()}):t.push({kind:`reading-indicator`,key:n})}return wD(ED(t))}"

# ── v2026.6.5 适配 — 函数映射: OD/fj→OA, ek/g→w, ij/MT→uf, bx/Bl→Ag, Il→gh, Uc/gx→Cg, Bc/Wb→nI/ph, Gl/Tx→qg, kD→WA, wD→wA, ED→EA, AD→GA ──
INVALID_FINAL_RELOAD_V2026_6_5_OLD = "if(d&&(s.pendingSessionMessageReloadSessionKey=null),u&&!o&&!a){qg(e);return}f&&!o&&qg(e)}"
INVALID_FINAL_RELOAD_V2026_6_5_NEW = "if(d&&(s.pendingSessionMessageReloadSessionKey=null),u&&!o&&!a)return;f&&!o&&qg(e)}"
HISTORY_MERGE_V2026_6_5_OLD = "e.chatMessages=Ag(f,c)"
HISTORY_MERGE_V2026_6_5_NEW = "e.chatMessages=Ag(JarvisProjectYieldedHistoryReply(f),c)"
STREAM_INDICATOR_V2026_6_5_OLD = "if(e.stream!==null){let n=`stream:${e.sessionKey}:${e.streamStartedAt??`live`}`,r=_h(OA(e.stream),f),i=NA(t,e.streamStartedAt??Date.now());r.length>0?ph(r).shouldSkip||t.push({kind:`stream`,key:n,text:r,startedAt:i,isStreaming:!0}):e.stream.trim().length===0&&t.push({kind:`reading-indicator`,key:n})}"
STREAM_INDICATOR_V2026_6_5_NEW = "let pendingIndicator=JarvisShouldShowPendingReadingIndicator(e);if(e.stream!==null||pendingIndicator){let n=`stream:${e.sessionKey}:${e.streamStartedAt??`live`}`,r=_h(e.stream!==null?OA(e.stream):'',f),i=NA(t,e.streamStartedAt??Date.now());r.length>0?ph(r).shouldSkip||t.push({kind:`stream`,key:n,text:r,startedAt:i,isStreaming:!0}):t.push({kind:`reading-indicator`,key:n})}"
JARVIS_FUNCTIONS_V2026_6_5 = (
    "function JarvisReadYieldedToolResultText(e){"
    + "if(!e||typeof e!='object')return null;"
    + "let t=typeof e?.role=='string'?e.role.toLowerCase():'';"
    + "if(t!=='toolresult'&&t!=='tool_result'&&t!=='tool'&&t!=='function')return null;"
    + "let n=typeof e?.content=='string'?e.content:Array.isArray(e?.content)?e.content.map(e=>typeof e?.text=='string'?e.text:'').join('\\n'):typeof e?.text=='string'?e.text:'';"
    + "if(!n.trim())return null;"
    + "try{let r=JSON.parse(n),i=typeof r?.message=='string'?r.message.trim():'';"
    + "return r?.status==='yielded'&&i&&!/^\\s*NO_REPLY\\s*$/.test(i)?i:null}catch{return null}}"
    + "function JarvisProjectYieldedHistoryReply(e){"
    + "if(!Array.isArray(e)||e.length===0)return[];"
    + "let t=e.filter(e=>!Cg(e)),n=-1;"
    + "for(let t=e.length-1;t>=0;t--){if(!e[t])continue;let r=typeof e[t]?.role=='string'?e[t].role.toLowerCase():'';if(r==='user'){n=t;break}}"
    + "if(n<0)return t;"
    + "for(let r=e.length-1;r>n;r--){if(!e[r])continue;let i=uf(e[r]);if(!i||!i.role)continue;let a=w(i.role).toLowerCase();if(a==='assistant'&&i.content.length>0)return t}"
    + "for(let r=e.length-1;r>n;r--){let i=JarvisReadYieldedToolResultText(e[r]);if(!i)continue;"
    + "let a={role:'assistant',content:[{type:'text',text:i}],timestamp:typeof e[r]?.timestamp=='number'?e[r].timestamp:Date.now()};return[...t,a]}return t}"
    + "function JarvisAssistantHasVisibleContent(e){"
    + "if(!e||typeof e!='object')return!1;"
    + "let t=uf(e);if(!t||!t.role)return!1;let n=w(t.role).toLowerCase();if(n!=='assistant')return!1;"
    + "for(let r of t.content){if(!r||typeof r!='object')continue;"
    + "if(r.type==='text'&&typeof r.text=='string'){let e=r.text.trim();if(e&&!/^\\s*NO_REPLY\\s*$/.test(e))return!0}"
    + "if(r.type==='attachment'||r.type==='canvas')return!0}return!1}"
    + "function JarvisShouldShowPendingReadingIndicator(e){"
    + "if(!e||typeof e!='object')return!1;"
    + "let t=e.sessionHasActiveRun===!0||e.sessionStatus==='running',"
    + "n=typeof e.sessionEndedAt=='number'&&Date.now()-e.sessionEndedAt<=2e4;"
    + "if(!t&&!n)return!1;"
    + "let r=Array.isArray(e.messages)?e.messages:[],i=Array.isArray(e.toolMessages)?e.toolMessages:[],a=-1;"
    + "for(let e=r.length-1;e>=0;e--){let t=typeof r[e]?.role=='string'?r[e].role.toLowerCase():'';if(t==='user'){a=e;break}}"
    + "if(a<0)return!1;"
    + "let o=!1,s=!1,c=0;"
    + "for(let e=a+1;e<r.length;e++){let t=r[e];if(!t||typeof t!='object')continue;"
    + "if(JarvisAssistantHasVisibleContent(t)){o=!0;break}"
    + "let i=uf(t);if(!i||!i.role)continue;let n=w(i.role).toLowerCase();(n==='assistant'||n==='tool')&&(s=!0);"
    + "let ti=typeof t.timestamp=='number'?t.timestamp:0;ti>c&&(c=ti)}"
    + "if(o)return!1;if(i.length>0)return!0;if(!s)return!1;return t||!c||Date.now()-c<=3e4}"
)

# ── v2026.5.22 适配 — 函数映射: fj→OD, ij→MT, ek→yT, bx→Bl, gx→Uc/Il, Wb→Bc, Tx→Gl/xl ──
CHAT_RUNNING_PATCH_V22 = "let t=e.connected,a=e.sessions?.sessions?.find(t=>t.key===e.sessionKey),n=e.loading||e.sending||e.stream!==null||!!e.canAbort||(e.queue?.length??0)>0||a?.hasActiveRun===!0||a?.status===`running`,r=!!(e.canAbort&&e.onAbort),i=e.compactionStatus?.phase===`active`||e.compactionStatus?.phase===`retrying`,"
INVALID_FINAL_RELOAD_V22_OLD = "if(d&&(s.pendingSessionMessageReloadSessionKey=null),u&&!o&&!a){Tx(e);return}f&&!o&&Tx(e)}"
INVALID_FINAL_RELOAD_V22_NEW = "if(d&&(s.pendingSessionMessageReloadSessionKey=null),u&&!o&&!a)return;f&&!o&&Tx(e)}"
READING_INDICATOR_V22_OLD = "if(e.stream!==null){let n=`stream:${e.sessionKey}:${e.streamStartedAt??`live`}`,r=fj(e.stream);r.length>0?Wb(r).shouldSkip||t.push({kind:`stream`,key:n,text:r,startedAt:e.streamStartedAt??Date.now()}):e.stream.trim().length===0&&t.push({kind:`reading-indicator`,key:n})}"
READING_INDICATOR_V22_BAD = "let c=JarvisShouldShowPendingReadingIndicator(e);if(e.stream!==null||c){let n=`stream:${e.sessionKey}:${e.streamStartedAt??`live`}`,r=e.stream!==null?fj(e.stream):'';r.length>0?Wb(r).shouldSkip||t.push({kind:`stream`,key:n,text:r,startedAt:e.streamStartedAt??Date.now()}):t.push({kind:`reading-indicator`,key:n})}"
READING_INDICATOR_V22_NEW = "let pendingIndicator=JarvisShouldShowPendingReadingIndicator(e);if(e.stream!==null||pendingIndicator){let n=`stream:${e.sessionKey}:${e.streamStartedAt??`live`}`,r=e.stream!==null?fj(e.stream):'';r.length>0?Wb(r).shouldSkip||t.push({kind:`stream`,key:n,text:r,startedAt:e.streamStartedAt??Date.now()}):t.push({kind:`reading-indicator`,key:n})}"
HISTORY_MERGE_V22_OLD = "e.chatMessages=bx((Array.isArray(a.messages)?a.messages:[]).filter(e=>!gx(e)),i),"
HISTORY_MERGE_V22_NEW = "e.chatMessages=bx(JarvisProjectYieldedHistoryReply(Array.isArray(a.messages)?a.messages:[]),i),"
JARVIS_FUNCTIONS_V22 = (
    "function JarvisReadYieldedToolResultText(e){"
    + "let t=typeof e?.role=='string'?e.role.toLowerCase():'';"
    + "if(t!=='toolresult'&&t!=='tool_result'&&t!=='tool'&&t!=='function')return null;"
    + "let n=typeof e?.content=='string'?e.content:Array.isArray(e?.content)?e.content.map(e=>typeof e?.text=='string'?e.text:'').join('\\n'):typeof e?.text=='string'?e.text:'';"
    + "if(!n.trim())return null;"
    + "try{let r=JSON.parse(n),i=typeof r?.message=='string'?r.message.trim():'';"
    + "return r?.status==='yielded'&&i&&!/^\\\\s*NO_REPLY\\\\s*$/.test(i)?i:null}catch{return null}}"
    + "function JarvisProjectYieldedHistoryReply(e){"
    + "if(!Array.isArray(e)||e.length===0)return[];"
    + "let t=e.filter(e=>!gx(e)),n=-1;"
    + "for(let t=e.length-1;t>=0;t--){let r=typeof e[t]?.role=='string'?e[t].role.toLowerCase():'';if(r==='user'){n=t;break}}"
    + "if(n<0)return t;"
    + "for(let r=e.length-1;r>n;r--){let i=ij(e[r]),a=ek(i.role).toLowerCase();if(a==='assistant'&&i.content.length>0)return t}"
    + "for(let r=e.length-1;r>n;r--){let i=JarvisReadYieldedToolResultText(e[r]);if(!i)continue;"
    + "let a={role:'assistant',content:[{type:'text',text:i}],timestamp:typeof e[r]?.timestamp=='number'?e[r].timestamp:Date.now()};return[...t,a]}return t}"
    + "function JarvisAssistantHasVisibleContent(e){"
    + "let t=ij(e),n=ek(t.role).toLowerCase();if(n!=='assistant')return!1;"
    + "for(let r of t.content){if(!r||typeof r!='object')continue;"
    + "if(r.type==='text'&&typeof r.text=='string'){let e=r.text.trim();if(e&&!/^\\\\s*NO_REPLY\\\\s*$/.test(e))return!0}"
    + "if(r.type==='attachment'||r.type==='canvas')return!0}return!1}"
    + "function JarvisShouldShowPendingReadingIndicator(e){"
    + "if(!e||typeof e!='object')return!1;"
    + "let t=e.sessionHasActiveRun===!0||e.sessionStatus==='running',"
    + "n=typeof e.sessionEndedAt=='number'&&Date.now()-e.sessionEndedAt<=2e4;"
    + "if(!t&&!n)return!1;"
    + "let r=Array.isArray(e.messages)?e.messages:[],i=Array.isArray(e.toolMessages)?e.toolMessages:[],a=-1;"
    + "for(let e=r.length-1;e>=0;e--){let t=typeof r[e]?.role=='string'?r[e].role.toLowerCase():'';if(t==='user'){a=e;break}}"
    + "if(a<0)return!1;"
    + "let o=!1,s=!1,c=0;"
    + "for(let e=a+1;e<r.length;e++){let t=r[e];if(!t||typeof t!='object')continue;"
    + "if(JarvisAssistantHasVisibleContent(t)){o=!0;break}"
    + "let n=ek(ij(t).role).toLowerCase();(n==='assistant'||n==='tool')&&(s=!0);"
    + "let i=typeof t.timestamp=='number'?t.timestamp:0;i>c&&(c=i)}"
    + "if(o)return!1;if(i.length>0)return!0;if(!s)return!1;return t||!c||Date.now()-c<=3e4}"
)


def die(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)



def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"配置文件不存在：{path}")
    except json.JSONDecodeError as exc:
        die(f"配置文件不是合法 JSON：{path} ({exc})")



def resolve_package_root() -> Path:
    env_override = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    if env_override:
        candidate = Path(env_override).expanduser().resolve()
        if (candidate / "dist" / "control-ui").exists():
            return candidate
        die(f"OPENCLAW_PACKAGE_ROOT 无效：{candidate}")

    if (DEFAULT_PACKAGE_ROOT / "dist" / "control-ui").exists():
        return DEFAULT_PACKAGE_ROOT

    try:
        npm_root = subprocess.run(
            ["npm", "root", "-g"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        candidate = Path(npm_root) / "openclaw"
        if (candidate / "dist" / "control-ui").exists():
            return candidate.resolve()
    except Exception:
        pass

    die("找不到 OpenClaw 包目录；可手动设置 OPENCLAW_PACKAGE_ROOT=/path/to/openclaw")



def resolve_source(workspace_relative: str) -> Path:
    source = (WORKSPACE / workspace_relative).resolve()
    if not source.exists():
        die(f"品牌源图片不存在：{source}")
    if not source.is_file():
        die(f"品牌源图片不是文件：{source}")
    return source



def replace_once(text: str, pattern: str, replacement: str, *, flags: int = 0, description: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        die(f"未能定位需要替换的 {description}")
    return updated



def inject_head_block(html: str, version: str) -> str:
    block = (
        f"{INJECT_MARKER_START}\n"
        f'    <script src="./assets/{SCRIPT_NAME}?v={version}"></script>\n'
        f"    {INJECT_MARKER_END}"
    )
    existing = re.compile(
        rf"\s*{re.escape(INJECT_MARKER_START)}.*?{re.escape(INJECT_MARKER_END)}",
        flags=re.S,
    )
    if existing.search(html):
        html = existing.sub("\n    " + block, html, count=1)
    else:
        html = replace_once(html, r"</head>", "\n    " + block + "\n  </head>", description="index.html </head>")
    return html



def patch_chat_running_indicator_v22(asset_path: Path, content: str) -> tuple[str, bool]:
    """Returns (updated_content, changed)."""
    updated = content
    changed = False

    # 1. Chat running indicator — hasActiveRun is natively present in v22, skip
    # 2. Invalid final reload
    if INVALID_FINAL_RELOAD_V22_OLD in updated and INVALID_FINAL_RELOAD_V22_NEW not in updated:
        updated = updated.replace(INVALID_FINAL_RELOAD_V22_OLD, INVALID_FINAL_RELOAD_V22_NEW, 1)
        changed = True

    # 3. Inject Jarvis helper functions before function fj(
    if 'JarvisProjectYieldedHistoryReply' not in updated:
        fj_idx = updated.find('function fj(')
        if fj_idx >= 0:
            updated = updated[:fj_idx] + JARVIS_FUNCTIONS_V22 + updated[fj_idx:]
            changed = True

    # 4. Patch history merge
    if HISTORY_MERGE_V22_NEW not in updated and HISTORY_MERGE_V22_OLD in updated:
        updated = updated.replace(HISTORY_MERGE_V22_OLD, HISTORY_MERGE_V22_NEW, 1)
        changed = True

    # 5. Patch reading indicator
    if READING_INDICATOR_V22_BAD in updated:
        updated = updated.replace(READING_INDICATOR_V22_BAD, READING_INDICATOR_V22_NEW, 1)
        changed = True
    elif READING_INDICATOR_V22_NEW not in updated and READING_INDICATOR_V22_OLD in updated:
        updated = updated.replace(READING_INDICATOR_V22_OLD, READING_INDICATOR_V22_NEW, 1)
        changed = True

    return updated, changed


def patch_chat_running_indicator(dist_root: Path) -> list[Path]:
    assets_dir = dist_root / "assets"
    if not assets_dir.exists():
        die(f"Control UI assets 目录不存在：{assets_dir}")

    patched_paths: list[Path] = []
    for asset_path in sorted(assets_dir.glob("index-*.js")):
        content = asset_path.read_text(encoding="utf-8")
        updated = content
        changed = False

        # Detect v2026.6.5+ — function OA present, fj and OD absent
        is_v2026_6_5 = "function OA(e){" in content and "function fj(" not in content and "function OD(e){" not in content
        if is_v2026_6_5:
            if INVALID_FINAL_RELOAD_V2026_6_5_OLD in updated:
                updated = updated.replace(INVALID_FINAL_RELOAD_V2026_6_5_OLD, INVALID_FINAL_RELOAD_V2026_6_5_NEW, 1)
                changed = True
            # Inject Jarvis yielded-history helpers (before WA / chat render)
            # Check if injection needed: helpers absent OR old non-guarded version present
            _has_jarvis = "JarvisReadYieldedToolResultText" in updated
            _has_nullguard = "if(!e||typeof e!='object')return null" in updated and "if(!i||!i.role)" in updated
            if not _has_jarvis or not _has_nullguard:
                # Re-inject: strip old helpers between "return a}" and "function WA(e){"
                _pre = "return a}"
                _post = "function WA(e){"
                if _has_jarvis and _pre in updated and _post in updated:
                    # Find "return a}" before the Jarvis functions
                    _jarvis_pos = updated.index("function JarvisReadYieldedToolResultText(")
                    _pre_idx = updated.rfind(_pre, 0, _jarvis_pos)
                    _post_idx = updated.index(_post, _jarvis_pos)
                    if _pre_idx >= 0 and _post_idx >= 0:
                        updated = updated[:_pre_idx + len(_pre)] + updated[_post_idx:]
                        changed = True
                if _pre in updated and _post in updated:
                    _pre_idx = updated.rfind(_pre, 0, updated.index(_post) + len(_post))
                    _post_idx = updated.index(_post, _pre_idx)
                    if _pre_idx >= 0 and _post_idx >= 0:
                        _between = updated[_pre_idx + len(_pre):_post_idx]
                        if "Jarvis" not in _between:
                            updated = updated[:_pre_idx + len(_pre)] + JARVIS_FUNCTIONS_V2026_6_5 + updated[_post_idx:]
                            changed = True
            if HISTORY_MERGE_V2026_6_5_OLD in updated and HISTORY_MERGE_V2026_6_5_NEW not in updated:
                updated = updated.replace(HISTORY_MERGE_V2026_6_5_OLD, HISTORY_MERGE_V2026_6_5_NEW, 1)
                changed = True
            if STREAM_INDICATOR_V2026_6_5_OLD in updated and STREAM_INDICATOR_V2026_6_5_NEW not in updated:
                updated = updated.replace(STREAM_INDICATOR_V2026_6_5_OLD, STREAM_INDICATOR_V2026_6_5_NEW, 1)
                changed = True
            if changed:
                asset_path.write_text(updated, encoding="utf-8")
            patched_paths.append(asset_path)
            continue

        # Detect v2026.5.22+ — function fj(=OD) present, old OD function absent
        is_v22 = "function fj(" in content and "function OD(e){" not in content
        if is_v22:
            updated, changed = patch_chat_running_indicator_v22(asset_path, content)
            if changed:
                asset_path.write_text(updated, encoding="utf-8")
            patched_paths.append(asset_path)
            continue

        # Legacy (<2026.5.22) patching
            for pattern in CHAT_RUNNING_PATCH_PATTERNS:
                if pattern in updated:
                    updated = updated.replace(pattern, CHAT_RUNNING_PATCH_NEW, 1)
                    changed = True
                    break

        if INVALID_FINAL_RELOAD_PATCH_OLD in updated:
            updated = updated.replace(INVALID_FINAL_RELOAD_PATCH_OLD, INVALID_FINAL_RELOAD_PATCH_NEW, 1)
            changed = True
        if INVALID_FINAL_RELOAD_PATCH_OLD_V2 in updated:
            updated = updated.replace(INVALID_FINAL_RELOAD_PATCH_OLD_V2, INVALID_FINAL_RELOAD_PATCH_NEW_V2, 1)
            changed = True

        if YIELDED_HISTORY_REPLAY_HELPER_NEW not in updated and YIELDED_HISTORY_REPLAY_HELPER_OLD in updated:
            updated = updated.replace(YIELDED_HISTORY_REPLAY_HELPER_OLD, YIELDED_HISTORY_REPLAY_HELPER_NEW, 1)
            changed = True

        if YIELDED_HISTORY_REPLAY_HELPER_V2 not in updated and YIELDED_HISTORY_REPLAY_HELPER_NEW in updated:
            updated = updated.replace(YIELDED_HISTORY_REPLAY_HELPER_NEW, YIELDED_HISTORY_REPLAY_HELPER_V2, 1)
            changed = True

        if YIELDED_HISTORY_REPLAY_HELPER_CURRENT not in updated and "function OD(e){let t=kT(e);return t.trim().length>0?t:``}function kD(e){" in updated:
            updated = updated.replace(
                "function OD(e){let t=kT(e);return t.trim().length>0?t:``}function kD(e){",
                "function OD(e){let t=kT(e);return t.trim().length>0?t:``}" + YIELDED_HISTORY_REPLAY_HELPER_CURRENT + "function kD(e){",
                1,
            )
            changed = True

        if YIELDED_HISTORY_REPLAY_APPLY_NEW not in updated and YIELDED_HISTORY_REPLAY_APPLY_OLD in updated:
            updated = updated.replace(YIELDED_HISTORY_REPLAY_APPLY_OLD, YIELDED_HISTORY_REPLAY_APPLY_NEW, 1)
            changed = True
        if YIELDED_HISTORY_REPLAY_APPLY_NEW_V2 not in updated and YIELDED_HISTORY_REPLAY_APPLY_OLD_V2 in updated:
            updated = updated.replace(YIELDED_HISTORY_REPLAY_APPLY_OLD_V2, YIELDED_HISTORY_REPLAY_APPLY_NEW_V2, 1)
            changed = True

        if PENDING_READING_INDICATOR_ARGS_NEW not in updated and PENDING_READING_INDICATOR_ARGS_OLD in updated:
            updated = updated.replace(PENDING_READING_INDICATOR_ARGS_OLD, PENDING_READING_INDICATOR_ARGS_NEW, 1)
            changed = True

        if PENDING_READING_INDICATOR_APPLY_NEW not in updated and PENDING_READING_INDICATOR_APPLY_OLD in updated:
            updated = updated.replace(PENDING_READING_INDICATOR_APPLY_OLD, PENDING_READING_INDICATOR_APPLY_NEW, 1)
            changed = True
        if PENDING_READING_INDICATOR_APPLY_NEW_V2 not in updated and PENDING_READING_INDICATOR_APPLY_OLD_V2 in updated:
            updated = updated.replace(PENDING_READING_INDICATOR_APPLY_OLD_V2, PENDING_READING_INDICATOR_APPLY_NEW_V2, 1)
            changed = True

        if (
            INVALID_FINAL_RELOAD_PATCH_NEW in updated
            or CHAT_RUNNING_PATCH_NEW in updated
            or YIELDED_HISTORY_REPLAY_APPLY_NEW in updated
            or PENDING_READING_INDICATOR_APPLY_NEW in updated
        ):
            if changed:
                asset_path.write_text(updated, encoding="utf-8")
            patched_paths.append(asset_path)

    if not patched_paths:
        die("未能定位聊天页补丁入口；请检查 Control UI 前端结构是否已变化")
    return patched_paths



def file_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type or not mime_type.startswith("image/"):
        die(f"无法识别为图片文件，不能生成 data URL：{path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"



def resolve_runtime_href(base_url: str | None, path_or_url: str | None, fallback: str) -> str:
    value = str(path_or_url or fallback).strip() or fallback
    if re.match(r"^https?://", value):
        return value
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return value
    normalized_value = value if value.startswith("/") else f"/{value}"
    return base + normalized_value



def write_override_script(
    path: Path,
    *,
    brand_title: str,
    brand_eyebrow: str,
    window_title: str,
    logo_file: str,
    favicon_file: str,
    apple_touch_file: str,
    user_avatar_data_url: str | None,
    infos_handle_base_url: str,
    infos_handle_summary_href: str,
    infos_handle_contract_href: str,
    infos_handle_sse_href: str,
    infos_handle_tasks_href: str,
    infos_handle_recovery_href: str,
    version: str,
) -> None:
    payload = {
        "brandTitle": brand_title,
        "brandEyebrow": brand_eyebrow,
        "windowTitle": window_title,
        "logoHref": f"./{logo_file}?v={version}",
        "faviconHref": f"./{favicon_file}?v={version}",
        "appleTouchHref": f"./{apple_touch_file}?v={version}",
        "logoAlt": brand_title,
        "userAvatarDataUrl": user_avatar_data_url or "",
        "healthEntry": {
            "label": "前台状态",
            "title": "前台状态总览",
            "description": "查看 broker / 监工 / 恢复观察 / 本地健康",
            "href": "/__openclaw__/control-ui/assets/jarvis-frontstage-status.html",
            "snapshotJsonHref": "/__openclaw__/control-ui/assets/jarvis-frontstage-snapshot.json",
            "legacyStatusJsonHref": "/__openclaw__/control-ui/assets/jarvis-frontstage-status.json",
            "statusJsonHref": "/__openclaw__/control-ui/assets/jarvis-frontstage-status.json",
            "infosHandleBaseUrl": infos_handle_base_url,
            "infosHandleSummaryHref": infos_handle_summary_href,
            "infosHandleContractHref": infos_handle_contract_href,
            "infosHandleSseHref": infos_handle_sse_href,
            "infosHandleTasksHref": infos_handle_tasks_href,
            "infosHandleRecoveryHref": infos_handle_recovery_href,
            "refreshMs": 60000,
            "openLabel": "打开状态页",
        },
        "visibleTextReplacements": [
            ["OpenClaw Control", window_title],
            ["OpenClaw", brand_title],
        ],
        "attributeNames": ["title", "aria-label", "placeholder", "alt"],
        "targetedTextSelectors": [
            [".dashboard-header__breadcrumb-link", brand_title],
            [".login-gate__title", brand_title],
            [".sidebar-brand__title", brand_title],
            [".sidebar-brand__eyebrow", brand_eyebrow],
        ],
        "skipClosestSelectors": [
            "pre",
            "code",
            "textarea",
            "input",
            ".message",
            ".message-list",
            ".message-bubble",
            ".chat-thread",
            ".tool-output",
            ".tool-call",
            ".tool-result",
            ".cm-editor",
        ],
    }
    script = f"""(() => {{
  const BRAND = {json.dumps(payload, ensure_ascii=False, indent=2)};
  const TOOL_NOISE_STYLE_ID = 'jarvis-tool-noise-filter';
  const HEALTH_DOCK_ID = 'jarvis-health-dock';
  const HEALTH_DOCK_STYLE_ID = 'jarvis-health-dock-style';
  const USER_IDENTITY_STORAGE_KEY = 'openclaw.control.user.v1';
  let healthRefreshTimerId = null;
  let healthEventSource = null;
  let healthEventSourceHref = '';
  let healthDockExpanded = false;

  function setAttr(node, name, value) {{
    if (node && node.getAttribute(name) !== value) node.setAttribute(name, value);
  }}

  function setText(node, value) {{
    if (node && value && node.textContent !== value) node.textContent = value;
  }}

  function escapeHtml(value) {{
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }}

  function replaceLiterals(value) {{
    if (typeof value !== 'string' || !value) return value;
    let next = value;
    for (const [from, to] of BRAND.visibleTextReplacements) {{
      if (from && typeof to === 'string' && next.includes(from)) {{
        next = next.split(from).join(to);
      }}
    }}
    return next;
  }}

  function shouldSkipElement(element) {{
    if (!element || typeof element.closest !== 'function') return false;
    return BRAND.skipClosestSelectors.some((selector) => {{
      try {{
        return Boolean(element.closest(selector));
      }} catch {{
        return false;
      }}
    }});
  }}

  function patchAttribute(element, name) {{
    if (!element || shouldSkipElement(element)) return;
    const current = element.getAttribute(name);
    if (!current) return;
    const next = replaceLiterals(current);
    if (next !== current) setAttr(element, name, next);
  }}

  function patchTextNode(node) {{
    if (!node || typeof node.nodeValue !== 'string') return;
    const parent = node.parentElement;
    if (!parent || shouldSkipElement(parent)) return;
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'INPUT', 'CODE', 'PRE'].includes(parent.tagName)) return;
    const current = node.nodeValue;
    const next = replaceLiterals(current);
    if (next !== current) node.nodeValue = next;
  }}

  function replaceVisibleText(root) {{
    const base = root && root.nodeType ? root : (document.body || document.documentElement);
    if (!base) return;

    if (base.nodeType === Node.ELEMENT_NODE) {{
      BRAND.attributeNames.forEach((attr) => patchAttribute(base, attr));
    }}

    const walker = document.createTreeWalker(base, NodeFilter.SHOW_TEXT);
    let textNode;
    while ((textNode = walker.nextNode())) {{
      patchTextNode(textNode);
    }}

    if (typeof base.querySelectorAll === 'function') {{
      base.querySelectorAll('*').forEach((element) => {{
        BRAND.attributeNames.forEach((attr) => patchAttribute(element, attr));
      }});
    }}
  }}

  function applyTargetedTextOverrides() {{
    for (const [selector, value] of BRAND.targetedTextSelectors) {{
      document.querySelectorAll(selector).forEach((node) => setText(node, value));
    }}
  }}

  function applyUserAvatar() {{
    if (!BRAND.userAvatarDataUrl) return;
    try {{
      const currentRaw = window.localStorage.getItem(USER_IDENTITY_STORAGE_KEY);
      let current = {{}};
      if (currentRaw) {{
        try {{
          const parsed = JSON.parse(currentRaw);
          if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) current = parsed;
        }} catch {{}}
      }}
      if (current.avatar !== BRAND.userAvatarDataUrl) {{
        current.avatar = BRAND.userAvatarDataUrl;
        window.localStorage.setItem(USER_IDENTITY_STORAGE_KEY, JSON.stringify(current));
      }}
    }} catch (err) {{
      console.warn('[jarvis-branding] user avatar storage update failed:', err);
    }}
    try {{
      const app = document.querySelector('openclaw-app');
      if (app && typeof app.applyLocalUserIdentity === 'function') {{
        app.applyLocalUserIdentity({{ avatar: BRAND.userAvatarDataUrl }});
      }}
    }} catch (err) {{
      console.warn('[jarvis-branding] user avatar runtime apply failed:', err);
    }}
  }}

  function ensureToolNoiseStyle() {{
    if (document.getElementById(TOOL_NOISE_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = TOOL_NOISE_STYLE_ID;
    style.textContent = `
      .chat-tools-inline,
      .chat-tool-msg-collapse,
      .chat-bubble--tool-shell,
      .chat-group.tool,
      .chat-group[data-jarvis-hidden-tool-group="true"] {{
        display: none !important;
      }}
    `;
    document.head.appendChild(style);
  }}

  function ensureHealthDockStyle() {{
    if (document.getElementById(HEALTH_DOCK_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = HEALTH_DOCK_STYLE_ID;
    style.textContent = `
      #${{HEALTH_DOCK_ID}} {{
        position: fixed;
        right: 18px;
        top: 148px;
        z-index: 80;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 10px;
        pointer-events: none;
      }}
      #${{HEALTH_DOCK_ID}}[data-expanded="false"] .jarvis-health-dock__panel {{
        display: none;
      }}
      #${{HEALTH_DOCK_ID}}[data-expanded="true"] .jarvis-health-dock__fab {{
        display: none;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__fab {{
        appearance: none;
        border: 1px solid rgba(148, 163, 184, 0.22);
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(2, 6, 23, 0.92));
        box-shadow: 0 18px 48px rgba(2, 6, 23, 0.28);
        backdrop-filter: blur(14px);
        color: #e5eefb;
        min-height: 44px;
        padding: 0 14px;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;
        font-size: 12px;
        font-weight: 700;
        pointer-events: auto;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__fab-label {{
        letter-spacing: 0.02em;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__fab-badge {{
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 11px;
        background: rgba(148, 163, 184, 0.16);
        color: #d9e6f5;
      }}
      #${{HEALTH_DOCK_ID}}[data-severity="ok"] .jarvis-health-dock__fab,
      #${{HEALTH_DOCK_ID}}[data-severity="ok"] .jarvis-health-dock__panel {{
        border-color: rgba(34, 197, 94, 0.30);
      }}
      #${{HEALTH_DOCK_ID}}[data-severity="warn"] .jarvis-health-dock__fab,
      #${{HEALTH_DOCK_ID}}[data-severity="warn"] .jarvis-health-dock__panel {{
        border-color: rgba(245, 158, 11, 0.34);
      }}
      #${{HEALTH_DOCK_ID}}[data-severity="critical"] .jarvis-health-dock__fab,
      #${{HEALTH_DOCK_ID}}[data-severity="critical"] .jarvis-health-dock__panel {{
        border-color: rgba(239, 68, 68, 0.38);
      }}
      #${{HEALTH_DOCK_ID}}[data-severity="ok"] .jarvis-health-dock__fab-badge,
      #${{HEALTH_DOCK_ID}}[data-severity="ok"] .jarvis-health-dock__badge {{
        background: rgba(34, 197, 94, 0.16);
        color: #97f0b3;
      }}
      #${{HEALTH_DOCK_ID}}[data-severity="warn"] .jarvis-health-dock__fab-badge,
      #${{HEALTH_DOCK_ID}}[data-severity="warn"] .jarvis-health-dock__badge {{
        background: rgba(245, 158, 11, 0.18);
        color: #ffd796;
      }}
      #${{HEALTH_DOCK_ID}}[data-severity="critical"] .jarvis-health-dock__fab-badge,
      #${{HEALTH_DOCK_ID}}[data-severity="critical"] .jarvis-health-dock__badge {{
        background: rgba(239, 68, 68, 0.18);
        color: #ffb1b1;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__panel {{
        width: min(288px, calc(100vw - 24px));
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.22);
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(2, 6, 23, 0.92));
        box-shadow: 0 18px 48px rgba(2, 6, 23, 0.36);
        backdrop-filter: blur(14px);
        color: #e5eefb;
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        pointer-events: auto;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__top {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 10px;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__top-right {{
        display: flex;
        align-items: center;
        gap: 8px;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__eyebrow {{
        font-size: 11px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8ea5c0;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__badge {{
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        background: rgba(148, 163, 184, 0.16);
        color: #d9e6f5;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__close {{
        appearance: none;
        border: 0;
        width: 28px;
        height: 28px;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        background: rgba(255,255,255,0.08);
        color: #d6e3f5;
        font-size: 16px;
        line-height: 1;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__title {{
        font-size: 17px;
        font-weight: 800;
        line-height: 1.3;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__desc,
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__meta {{
        font-size: 12px;
        color: #a8bdd5;
        line-height: 1.45;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__tips {{
        margin: 2px 0 0;
        padding-left: 18px;
        color: #d6e2f0;
        font-size: 12px;
        line-height: 1.45;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__tips li + li {{
        margin-top: 6px;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__actions {{
        display: flex;
        gap: 8px;
        margin-top: 4px;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__open {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 36px;
        padding: 0 12px;
        border-radius: 12px;
        text-decoration: none;
        font-size: 12px;
        font-weight: 700;
        color: #eff6ff;
        background: linear-gradient(180deg, rgba(59, 130, 246, 0.95), rgba(37, 99, 235, 0.90));
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__open:hover,
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__fab:hover {{
        filter: brightness(1.05);
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__sub-cards {{
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 2px;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__sub-card {{
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        border-radius: 12px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(148, 163, 184, 0.10);
        font-size: 12px;
        line-height: 1.35;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__sub-card-badge {{
        flex-shrink: 0;
        padding: 3px 8px;
        border-radius: 999px;
        font-size: 10px;
        font-weight: 700;
        background: rgba(148, 163, 184, 0.14);
        color: #d9e6f5;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__sub-card-badge[data-severity="ok"] {{
        background: rgba(34, 197, 94, 0.15);
        color: #97f0b3;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__sub-card-badge[data-severity="warn"] {{
        background: rgba(245, 158, 11, 0.16);
        color: #ffd796;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__sub-card-badge[data-severity="critical"] {{
        background: rgba(239, 68, 68, 0.16);
        color: #ffb1b1;
      }}
      #${{HEALTH_DOCK_ID}} .jarvis-health-dock__sub-card-text {{
        color: #cbdff5;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      @media (max-width: 900px) {{
        #${{HEALTH_DOCK_ID}} {{
          right: 12px;
          top: 140px;
        }}
        #${{HEALTH_DOCK_ID}} .jarvis-health-dock__panel {{
          width: min(320px, calc(100vw - 20px));
        }}
      }}
    `;
    document.head.appendChild(style);
  }}

  function setHealthDockExpanded(nextExpanded) {{
    healthDockExpanded = !!nextExpanded;
    const dock = document.getElementById(HEALTH_DOCK_ID);
    if (dock) dock.dataset.expanded = healthDockExpanded ? 'true' : 'false';
  }}

  function positionHealthDock() {{
    const dock = document.getElementById(HEALTH_DOCK_ID);
    if (!dock) return;

    const margin = 12;
    const fallbackTop = window.innerWidth <= 900 ? 140 : 148;
    let top = fallbackTop;

    const topbar = document.querySelector('.topbar');
    if (topbar) {{
      const rect = topbar.getBoundingClientRect();
      if (Number.isFinite(rect.bottom) && rect.bottom > 0) top = Math.max(top, Math.round(rect.bottom + margin));
    }}

    const actionCandidates = Array.from(document.querySelectorAll('button, a, [role="button"]')).filter((node) => {{
      if (!(node instanceof Element) || node === dock || dock.contains(node)) return false;
      const rect = node.getBoundingClientRect();
      if (!Number.isFinite(rect.bottom) || rect.width <= 0 || rect.height <= 0) return false;
      if (rect.bottom <= 0 || rect.top >= Math.min(window.innerHeight * 0.4, 240)) return false;
      if (rect.right < window.innerWidth * 0.45) return false;
      const style = window.getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') === 0) return false;
      return true;
    }});

    for (const node of actionCandidates) {{
      const rect = node.getBoundingClientRect();
      top = Math.max(top, Math.round(rect.bottom + margin));
    }}

    dock.style.top = `${{top}}px`;
  }}

  function ensureHealthDock() {{
    let dock = document.getElementById(HEALTH_DOCK_ID);
    if (dock) return dock;
    dock = document.createElement('section');
    dock.id = HEALTH_DOCK_ID;
    dock.dataset.severity = 'unknown';
    dock.dataset.expanded = healthDockExpanded ? 'true' : 'false';
    dock.innerHTML = `
      <button class="jarvis-health-dock__fab" type="button" aria-label="展开前台状态详情" title="前台状态">
        <span class="jarvis-health-dock__fab-label">${{BRAND.healthEntry.label}}</span>
        <span class="jarvis-health-dock__fab-badge">读取中</span>
      </button>
      <div class="jarvis-health-dock__panel">
        <div class="jarvis-health-dock__top">
          <div class="jarvis-health-dock__eyebrow">${{BRAND.healthEntry.label}}</div>
          <div class="jarvis-health-dock__top-right">
            <div class="jarvis-health-dock__badge">读取中</div>
            <button class="jarvis-health-dock__close" type="button" aria-label="收起前台状态卡片" title="收起">×</button>
          </div>
        </div>
        <div class="jarvis-health-dock__title">${{BRAND.healthEntry.title}}</div>
        <div class="jarvis-health-dock__desc">${{BRAND.healthEntry.description}}</div>
        <div class="jarvis-health-dock__meta">等待前台状态快照…</div>
        <ul class="jarvis-health-dock__tips"><li>等待前台状态快照…</li></ul>
        <div class="jarvis-health-dock__sub-cards">
          <div class="jarvis-health-dock__sub-card" data-jarvis-dock="task">
            <span class="jarvis-health-dock__sub-card-badge">—</span>
            <span class="jarvis-health-dock__sub-card-text">后台任务：读取中…</span>
          </div>
          <div class="jarvis-health-dock__sub-card" data-jarvis-dock="recovery">
            <span class="jarvis-health-dock__sub-card-badge">—</span>
            <span class="jarvis-health-dock__sub-card-text">恢复观察：读取中…</span>
          </div>
        </div>
        <div class="jarvis-health-dock__actions">
          <a class="jarvis-health-dock__open" href="${{BRAND.healthEntry.href}}" target="_blank" rel="noopener noreferrer">${{BRAND.healthEntry.openLabel || '打开状态页'}}</a>
        </div>
      </div>
    `;
    const fabButton = dock.querySelector('.jarvis-health-dock__fab');
    const closeButton = dock.querySelector('.jarvis-health-dock__close');
    if (fabButton) fabButton.addEventListener('click', () => setHealthDockExpanded(true));
    if (closeButton) closeButton.addEventListener('click', () => setHealthDockExpanded(false));
    (document.body || document.documentElement).appendChild(dock);
    positionHealthDock();
    return dock;
  }}

  function healthBadgeText(severity) {{
    return severity === 'critical' ? '严重异常' : severity === 'warn' ? '告警' : severity === 'ok' ? '正常' : '未知';
  }}

  function formatCheckedAt(raw) {{
    if (!raw) return '更新时间未知';
    const dt = new Date(raw);
    if (Number.isNaN(dt.getTime())) return '更新时间未知';
    const diffMinutes = Math.max(0, Math.floor((Date.now() - dt.getTime()) / 60000));
    if (diffMinutes <= 1) return '刚更新';
    return `${{diffMinutes}} 分钟前更新`;
  }}

  function normalizeFrontstageSnapshot(payload) {{
    const snapshot = payload && typeof payload === 'object' ? payload : {{}};
    const infosHandleResult = snapshot && typeof snapshot.result === 'object' ? snapshot.result : null;
    const infosHandleResponse = snapshot && snapshot.response && typeof snapshot.response === 'object' ? snapshot.response : null;
    const infosHandleNestedResult = infosHandleResponse && typeof infosHandleResponse.result === 'object' ? infosHandleResponse.result : null;
    const summaryPayload = infosHandleResult || infosHandleNestedResult;
    if (summaryPayload) {{
      return {{
        severity: summaryPayload.severity || 'unknown',
        summary: summaryPayload.summary || BRAND.healthEntry.title,
        issueOverview: summaryPayload.issueOverview || summaryPayload.detail || BRAND.healthEntry.description,
        checkedAt: summaryPayload.checkedAt || null,
        host: snapshot.host || '',
        selfHelpActions: Array.isArray(summaryPayload.selfHelpActions) ? summaryPayload.selfHelpActions : [],
      }};
    }}
    const panels = snapshot && typeof snapshot.panels === 'object' ? snapshot.panels : null;
    const healthPanel = panels && panels.health && typeof panels.health === 'object'
      ? panels.health
      : (snapshot.health && typeof snapshot.health === 'object' ? snapshot.health : null);
    return {{
      severity: snapshot && snapshot.severity ? snapshot.severity : (healthPanel && healthPanel.severity ? healthPanel.severity : 'unknown'),
      summary: snapshot && snapshot.summary ? snapshot.summary : (healthPanel && healthPanel.summary ? healthPanel.summary : BRAND.healthEntry.title),
      issueOverview: snapshot && snapshot.issueOverview ? snapshot.issueOverview : (healthPanel && healthPanel.detail ? healthPanel.detail : BRAND.healthEntry.description),
      checkedAt: snapshot && snapshot.checkedAt ? snapshot.checkedAt : (healthPanel && healthPanel.checkedAt ? healthPanel.checkedAt : null),
      host: snapshot && snapshot.host ? snapshot.host : '',
      selfHelpActions: Array.isArray(snapshot && snapshot.selfHelpActions) ? snapshot.selfHelpActions : [],
    }};
  }}

  async function fetchJsonNoStore(href) {{
    const resp = await fetch(href, {{ cache: 'no-store' }});
    if (!resp.ok) throw new Error(`http_${{resp.status}}`);
    return await resp.json();
  }}

  function updateHealthDock(payload) {{
    const dock = ensureHealthDock();
    if (!dock) return;
    const snapshot = normalizeFrontstageSnapshot(payload);
    const severity = snapshot.severity || 'unknown';
    dock.dataset.severity = severity;
    const fabBadge = dock.querySelector('.jarvis-health-dock__fab-badge');
    const badge = dock.querySelector('.jarvis-health-dock__badge');
    const title = dock.querySelector('.jarvis-health-dock__title');
    const desc = dock.querySelector('.jarvis-health-dock__desc');
    const meta = dock.querySelector('.jarvis-health-dock__meta');
    const tips = dock.querySelector('.jarvis-health-dock__tips');
    const badgeText = healthBadgeText(severity);
    if (fabBadge) fabBadge.textContent = badgeText;
    if (badge) badge.textContent = badgeText;
    if (title) title.textContent = snapshot.summary || BRAND.healthEntry.title;
    if (desc) desc.textContent = snapshot.issueOverview || BRAND.healthEntry.description;
    if (meta) meta.textContent = formatCheckedAt(snapshot.checkedAt) + (snapshot.host ? ` · ${{snapshot.host}}` : '');
    if (tips) {{
      const actions = Array.isArray(snapshot.selfHelpActions) ? snapshot.selfHelpActions.slice(0, 3) : [];
      tips.innerHTML = actions.length
        ? actions.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')
        : '<li>如果页面卡住但这里显示正常，优先刷新页面；仍无效再重开浏览器。</li>';
    }}
    positionHealthDock();
  }}

  async function refreshHealthDock() {{
    const dock = ensureHealthDock();
    if (!dock) return;
    const infosHandleSummaryHref = BRAND.healthEntry.infosHandleSummaryHref || '';
    const snapshotJsonHref = BRAND.healthEntry.snapshotJsonHref || BRAND.healthEntry.statusJsonHref;
    try {{
      if (infosHandleSummaryHref) {{
        try {{
          const payload = await fetchJsonNoStore(infosHandleSummaryHref);
          updateHealthDock(payload);
          return;
        }} catch (err) {{
          console.warn('[jarvis-branding] infos-handle summary fetch failed, falling back to snapshot JSON:', err);
        }}
      }}
      const payload = await fetchJsonNoStore(snapshotJsonHref);
      updateHealthDock(payload);
    }} catch (err) {{
      console.warn('[jarvis-branding] health dock fetch failed:', err);
      updateHealthDock({{
        severity: 'warn',
        summary: '前台状态暂时不可读',
        issueOverview: 'infos-handle 直连与静态状态文件都暂时不可读；请刷新页面，必要时再检查本机 gateway / infos-handle sidecar。',
      }});
    }}
  }}

  function connectHealthDockSse() {{
    const href = BRAND.healthEntry.infosHandleSseHref || '';
    if (!href || typeof window.EventSource !== 'function') return;
    if (healthEventSource && healthEventSourceHref === href) return;
    if (healthEventSource) {{
      healthEventSource.close();
      healthEventSource = null;
    }}
    healthEventSourceHref = href;
    try {{
      const source = new EventSource(href);
      source.onmessage = (event) => {{
        try {{
          const payload = JSON.parse(event.data || '{{}}');
          updateHealthDock(payload);
        }} catch (err) {{
          console.warn('[jarvis-branding] infos-handle sse payload parse failed:', err);
        }}
      }};
      source.onerror = () => {{
        if (source.readyState === EventSource.CLOSED) {{
          healthEventSource = null;
        }}
      }};
      healthEventSource = source;
    }} catch (err) {{
      console.warn('[jarvis-branding] infos-handle sse connect failed:', err);
    }}
  }}

  function normalizeTasksSummary(payload) {{
    const result = payload && typeof payload.result === 'object' ? payload.result : null;
    const response = payload && payload.response && typeof payload.response === 'object' ? payload.response : null;
    const nested = response && typeof response.result === 'object' ? response.result : null;
    const data = result || nested;
    if (data) {{
      const sv = data.supervisor && typeof data.supervisor === 'object' ? data.supervisor : null;
      return {{
        severity: sv ? (sv.severity || 'ok') : 'ok',
        summary: sv ? (sv.summary || '无活跃后台任务') : '无活跃后台任务',
        checkedAt: sv ? (sv.checkedAt || null) : null,
      }};
    }}
    const panels = payload && typeof payload.panels === 'object' ? payload.panels : null;
    const taskPanel = panels && panels.supervisor && typeof panels.supervisor === 'object' ? panels.supervisor : null;
    return {{
      severity: taskPanel ? (taskPanel.severity || 'ok') : 'ok',
      summary: taskPanel ? (taskPanel.summary || '无活跃后台任务') : '无活跃后台任务',
      checkedAt: taskPanel ? (taskPanel.checkedAt || null) : null,
    }};
  }}

  function updateTaskCard(data) {{
    const panel = document.getElementById(HEALTH_DOCK_ID);
    if (!panel) return;
    const card = panel.querySelector('[data-jarvis-dock="task"]');
    if (!card) return;
    const badge = card.querySelector('.jarvis-health-dock__sub-card-badge');
    const text = card.querySelector('.jarvis-health-dock__sub-card-text');
    if (badge) {{
      badge.dataset.severity = data.severity || 'ok';
      badge.textContent = healthBadgeText(data.severity);
    }}
    if (text) {{
      text.textContent = '后台任务：' + (data.summary || '无活跃后台任务');
    }}
  }}

  async function refreshTaskCard() {{
    const tasksHref = BRAND.healthEntry.infosHandleTasksHref || (BRAND.healthEntry.infosHandleBaseUrl ? (BRAND.healthEntry.infosHandleBaseUrl + '/v1/query/tasks.summary?format=json') : '');
    const snapshotJsonHref = BRAND.healthEntry.snapshotJsonHref || BRAND.healthEntry.statusJsonHref;
    try {{
      if (tasksHref) {{
        try {{
          const payload = await fetchJsonNoStore(tasksHref);
          updateTaskCard(normalizeTasksSummary(payload));
          return;
        }} catch (err) {{
          console.warn('[jarvis-branding] infos-handle tasks fetch failed, falling back to snapshot:', err);
        }}
      }}
      if (snapshotJsonHref) {{
        const payload = await fetchJsonNoStore(snapshotJsonHref);
        updateTaskCard(normalizeTasksSummary(payload));
      }}
    }} catch (err) {{
      updateTaskCard({{ severity: 'warn', summary: '暂时不可读' }});
    }}
  }}

  function normalizeRecoverySummary(payload) {{
    const result = payload && typeof payload.result === 'object' ? payload.result : null;
    const response = payload && payload.response && typeof payload.response === 'object' ? payload.response : null;
    const nested = response && typeof response.result === 'object' ? response.result : null;
    const data = result || nested;
    if (data) {{
      return {{
        severity: data.severity || 'ok',
        summary: data.summary || '未发现明显异常',
        checkedAt: data.checkedAt || null,
      }};
    }}
    const panels = payload && typeof payload.panels === 'object' ? payload.panels : null;
    const recoveryPanel = panels && panels.recovery && typeof panels.recovery === 'object' ? panels.recovery : null;
    return {{
      severity: recoveryPanel ? (recoveryPanel.severity || 'ok') : 'ok',
      summary: recoveryPanel ? (recoveryPanel.summary || '未发现明显异常') : '未发现明显异常',
      checkedAt: recoveryPanel ? (recoveryPanel.checkedAt || null) : null,
    }};
  }}

  function updateRecoveryCard(data) {{
    const panel = document.getElementById(HEALTH_DOCK_ID);
    if (!panel) return;
    const card = panel.querySelector('[data-jarvis-dock="recovery"]');
    if (!card) return;
    const badge = card.querySelector('.jarvis-health-dock__sub-card-badge');
    const text = card.querySelector('.jarvis-health-dock__sub-card-text');
    if (badge) {{
      badge.dataset.severity = data.severity || 'ok';
      badge.textContent = healthBadgeText(data.severity);
    }}
    if (text) {{
      text.textContent = '恢复观察：' + (data.summary || '未发现明显异常');
    }}
  }}

  async function refreshRecoveryCard() {{
    const recoveryHref = BRAND.healthEntry.infosHandleRecoveryHref || (BRAND.healthEntry.infosHandleBaseUrl ? (BRAND.healthEntry.infosHandleBaseUrl + '/v1/query/recovery.summary?format=json') : '');
    const snapshotJsonHref = BRAND.healthEntry.snapshotJsonHref || BRAND.healthEntry.statusJsonHref;
    try {{
      if (recoveryHref) {{
        try {{
          const payload = await fetchJsonNoStore(recoveryHref);
          updateRecoveryCard(normalizeRecoverySummary(payload));
          return;
        }} catch (err) {{
          console.warn('[jarvis-branding] infos-handle recovery fetch failed, falling back to snapshot:', err);
        }}
      }}
      if (snapshotJsonHref) {{
        const payload = await fetchJsonNoStore(snapshotJsonHref);
        updateRecoveryCard(normalizeRecoverySummary(payload));
      }}
    }} catch (err) {{
      updateRecoveryCard({{ severity: 'warn', summary: '暂时不可读' }});
    }}
  }}

  function isVisible(node) {{
    if (!(node instanceof Element)) return false;
    const style = window.getComputedStyle(node);
    return style.display !== 'none' && style.visibility !== 'hidden';
  }}

  function refreshHiddenToolGroups(root) {{
    const candidateGroups = new Set();
    if (root instanceof Element) {{
      if (root.matches('.chat-group')) candidateGroups.add(root);
      root.querySelectorAll('.chat-group').forEach((group) => candidateGroups.add(group));
    }}
    document.querySelectorAll('.chat-group').forEach((group) => candidateGroups.add(group));

    for (const group of candidateGroups) {{
      const bubbles = Array.from(group.querySelectorAll('.chat-bubble'));
      const visibleNonToolBubble = bubbles.some((bubble) => !bubble.classList.contains('chat-bubble--tool-shell') && isVisible(bubble));
      const visibleMedia = Array.from(group.querySelectorAll('.chat-assistant-attachments, .chat-message-image, .chat-assistant-attachment-card')).some(isVisible);
      if (!visibleNonToolBubble && !visibleMedia) {{
        group.setAttribute('data-jarvis-hidden-tool-group', 'true');
      }} else {{
        group.removeAttribute('data-jarvis-hidden-tool-group');
      }}
    }}
  }}

  function applyBranding(root) {{
    try {{
      if (document.title !== BRAND.windowTitle) document.title = BRAND.windowTitle;

      document.querySelectorAll('link[rel="icon"]').forEach((link) => {{
        const href = BRAND.faviconHref || '';
        setAttr(link, 'href', href);
        if (href && /\\.svg(\\?|$)/.test(href)) {{
          setAttr(link, 'type', 'image/svg+xml');
        }}
      }});

      document.querySelectorAll('link[rel="apple-touch-icon"]').forEach((link) => {{
        setAttr(link, 'href', BRAND.appleTouchHref);
      }});

      const logo = document.querySelector('.sidebar-brand__logo');
      setAttr(logo, 'src', BRAND.logoHref);
      setAttr(logo, 'alt', BRAND.logoAlt);

      applyUserAvatar();
      ensureToolNoiseStyle();
      ensureHealthDockStyle();
      ensureHealthDock();
      applyTargetedTextOverrides();
      replaceVisibleText(root);
      refreshHiddenToolGroups(root instanceof Element ? root : document.body || document.documentElement);
    }} catch (err) {{
      console.warn('[jarvis-branding] apply failed:', err);
    }}
  }}

  let scheduled = false;
  function scheduleApply(root) {{
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {{
      scheduled = false;
      applyBranding(root);
    }});
  }}

  function boot() {{
    applyBranding(document.body || document.documentElement);
    refreshHealthDock();
    refreshTaskCard();
    refreshRecoveryCard();
    connectHealthDockSse();
    if (!healthRefreshTimerId) {{
      healthRefreshTimerId = window.setInterval(() => {{ refreshHealthDock(); refreshTaskCard(); refreshRecoveryCard(); }}, Number(BRAND.healthEntry.refreshMs) || 60000);
    }}
    const observer = new MutationObserver((mutations) => {{
      for (const mutation of mutations) {{
        if (mutation.type === 'childList') {{
          mutation.addedNodes.forEach((node) => scheduleApply(node));
        }} else if (mutation.type === 'characterData') {{
          scheduleApply(mutation.target?.parentElement || document.body || document.documentElement);
        }}
      }}
    }});
    observer.observe(document.documentElement, {{ childList: true, subtree: true, characterData: true }});
    window.addEventListener('pageshow', () => {{ applyBranding(document.body || document.documentElement); refreshHealthDock(); refreshTaskCard(); refreshRecoveryCard(); connectHealthDockSse(); positionHealthDock(); }});
    window.addEventListener('resize', positionHealthDock);
    document.addEventListener('visibilitychange', () => {{
      applyBranding(document.body || document.documentElement);
      positionHealthDock();
      if (document.visibilityState === 'visible') {{
        refreshHealthDock();
        refreshTaskCard();
        refreshRecoveryCard();
        connectHealthDockSse();
      }}
    }});
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', boot, {{ once: true }});
  }} else {{
    boot();
  }}
}})();
"""
    path.write_text(script, encoding="utf-8")



def main() -> int:
    config_path = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else DEFAULT_CONFIG
    cfg = read_json(config_path)

    branding = cfg.get("branding") or {}
    assets = cfg.get("assets") or {}
    control_ui = cfg.get("controlUi") or {}

    brand_title = str(branding.get("brandTitle") or "贾维斯")
    brand_eyebrow = str(branding.get("brandEyebrow") or "CONTROL")
    window_title = str(branding.get("windowTitle") or f"{brand_title} Control")
    manifest_name = str(branding.get("manifestName") or window_title)
    manifest_short_name = str(branding.get("manifestShortName") or brand_title)
    notification_title = str(branding.get("notificationTitle") or brand_title)

    logo_source = resolve_source(str(assets.get("logoSource") or "avatars/jarvis-neon-20260507.png"))
    user_avatar_source_value = assets.get("chatUserAvatarSource")
    user_avatar_source = resolve_source(str(user_avatar_source_value)) if user_avatar_source_value else None
    runtime_logo_file = str(assets.get("runtimeLogoFile") or f"jarvis-brand{logo_source.suffix.lower() or '.png'}")
    favicon_file = str(assets.get("favicon32File") or "favicon-32.png")
    favicon_16_file = str(assets.get("favicon16File") or "favicon-16.png")
    favicon_svg_file = str(assets.get("faviconSvgFile") or "favicon.svg")
    favicon_ico_file = str(assets.get("faviconIcoFile") or "favicon.ico")
    apple_touch_file = str(assets.get("appleTouchIconFile") or "apple-touch-icon.png")

    favicon_32_source_value = assets.get("favicon32Source")
    favicon_16_source_value = assets.get("favicon16Source")
    favicon_svg_source_value = assets.get("faviconSvgSource")
    favicon_ico_source_value = assets.get("faviconIcoSource")
    apple_touch_source_value = assets.get("appleTouchIconSource")
    infos_handle_base_url = str(control_ui.get("infosHandleBaseUrl") or "")
    infos_handle_summary_href = resolve_runtime_href(
        infos_handle_base_url,
        control_ui.get("infosHandleSnapshotSummaryPath"),
        "/v1/query/snapshot.summary?format=json",
    )
    infos_handle_contract_href = resolve_runtime_href(
        infos_handle_base_url,
        control_ui.get("infosHandleContractPath"),
        "/v1/query/contract.catalog?format=json",
    )
    infos_handle_sse_href = resolve_runtime_href(
        infos_handle_base_url,
        control_ui.get("infosHandleSsePath"),
        "/v1/events/stream?kind=snapshot.summary",
    )
    infos_handle_tasks_href = resolve_runtime_href(
        infos_handle_base_url,
        control_ui.get("infosHandleTasksPath"),
        "/v1/query/tasks.summary?format=json",
    )
    infos_handle_recovery_href = resolve_runtime_href(
        infos_handle_base_url,
        control_ui.get("infosHandleRecoveryPath"),
        "/v1/query/recovery.summary?format=json",
    )

    package_root = resolve_package_root()
    dist_root = package_root / "dist" / "control-ui"
    if not dist_root.exists():
        die(f"Control UI 目录不存在：{dist_root}")

    version = str(int(time.time()))

    runtime_logo_path = dist_root / runtime_logo_file
    shutil.copyfile(logo_source, runtime_logo_path)

    if favicon_32_source_value:
        favicon_32_source = resolve_source(favicon_32_source_value)
        shutil.copyfile(favicon_32_source, dist_root / favicon_file)
    else:
        shutil.copyfile(logo_source, dist_root / favicon_file)

    if favicon_16_source_value:
        favicon_16_source = resolve_source(favicon_16_source_value)
        shutil.copyfile(favicon_16_source, dist_root / favicon_16_file)

    if favicon_svg_source_value:
        favicon_svg_source = resolve_source(favicon_svg_source_value)
        shutil.copyfile(favicon_svg_source, dist_root / favicon_svg_file)

    if favicon_ico_source_value:
        favicon_ico_source = resolve_source(favicon_ico_source_value)
        shutil.copyfile(favicon_ico_source, dist_root / favicon_ico_file)

    if apple_touch_source_value:
        apple_touch_source = resolve_source(apple_touch_source_value)
        shutil.copyfile(apple_touch_source, dist_root / apple_touch_file)
    else:
        shutil.copyfile(logo_source, dist_root / apple_touch_file)

    index_html_path = dist_root / "index.html"
    html = index_html_path.read_text(encoding="utf-8")
    html = replace_once(html, r"<title>.*?</title>", f"<title>{window_title}</title>", flags=re.S, description="index.html 标题")
    html = inject_head_block(html, version)
    index_html_path.write_text(html, encoding="utf-8")

    override_script_path = dist_root / "assets" / SCRIPT_NAME
    write_override_script(
        override_script_path,
        brand_title=brand_title,
        brand_eyebrow=brand_eyebrow,
        window_title=window_title,
        logo_file=runtime_logo_file,
        favicon_file=favicon_file,
        apple_touch_file=apple_touch_file,
        user_avatar_data_url=file_to_data_url(user_avatar_source) if user_avatar_source else None,
        infos_handle_base_url=infos_handle_base_url,
        infos_handle_summary_href=infos_handle_summary_href,
        infos_handle_contract_href=infos_handle_contract_href,
        infos_handle_sse_href=infos_handle_sse_href,
        infos_handle_tasks_href=infos_handle_tasks_href,
        infos_handle_recovery_href=infos_handle_recovery_href,
        version=version,
    )
    patched_assets = patch_chat_running_indicator(dist_root)

    manifest_path = dist_root / "manifest.webmanifest"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["name"] = manifest_name
    manifest["short_name"] = manifest_short_name
    manifest["icons"] = [
        {
            "src": f"./{favicon_file}",
            "sizes": "32x32",
            "type": "image/png",
        },
        {
            "src": f"./{apple_touch_file}",
            "sizes": "180x180",
            "type": "image/png",
        },
    ]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sw_path = dist_root / "sw.js"
    sw = sw_path.read_text(encoding="utf-8")
    sw = sw.replace('data = { title: "OpenClaw", body: event.data.text() };', f'data = {{ title: {json.dumps(notification_title, ensure_ascii=False)}, body: event.data.text() }};')
    sw = sw.replace('const title = data.title || "OpenClaw";', f'const title = data.title || {json.dumps(notification_title, ensure_ascii=False)};')
    sw_path.write_text(sw, encoding="utf-8")

    print("Applied Control UI branding patch.")
    print(f"- packageRoot: {package_root}")
    print(f"- logoSource: {logo_source}")
    print(f"- runtimeLogo: {runtime_logo_path}")
    print(f"- windowTitle: {window_title}")
    print(f"- brandTitle: {brand_title}")
    print(f"- infosHandleBaseUrl: {infos_handle_base_url or '[same-origin]'}")
    print(f"- infosHandleSummaryHref: {infos_handle_summary_href}")
    print(f"- infosHandleContractHref: {infos_handle_contract_href}")
    print(f"- infosHandleSseHref: {infos_handle_sse_href}")
    print(f"- infosHandleTasksHref: {infos_handle_tasks_href}")
    print(f"- infosHandleRecoveryHref: {infos_handle_recovery_href}")
    print("- chatRunningPatched:")
    for path in patched_assets:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
