#!/usr/bin/env python3
"""
自主决策器 - 根据输入特征自主决定要不要主动跟点点聊天
输出0: 不主动 | 输出1: 触发对话

用法:
  python3 autonomy.py --check          # 跑一次决策
  python3 autonomy.py --check --verbose # 打印详细信息
  python3 autonomy.py --stats           # 查看统计
  python3 autonomy.py --init            # 从daily数据初始化权重
"""

import json
import math
import os
import sys
import time
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# 路径
# ============================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.json"
STATE_PATH = SCRIPT_DIR / "state.json"
LOG_PATH = SCRIPT_DIR / "decisions.jsonl"
ERROR_LOG_PATH = SCRIPT_DIR / "errors.jsonl"

WORKSPACE = Path(os.environ.get(
    "OPENCLAW_WORKSPACE",
    os.path.expanduser("~/.openclaw/workspace")
))
DAILY_DIR = WORKSPACE / "memory" / "daily"
SESSIONS_DIR = Path(os.path.expanduser("~/.openclaw/agents/main/sessions"))
CHAT_DENSITY_WINDOW_MIN = 4  # 最近N分钟内有聊天则跳过


# ============================================================
# 配置 & 状态
# ============================================================

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


MAX_LOG_ENTRIES = 2000  # 日志最多保留2000条（约5天的每5分钟决策）


def rotate_log():
    """日志轮替：超过MAX_LOG_ENTRIES时只保留最近的一半"""
    if not LOG_PATH.exists():
        return
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) > MAX_LOG_ENTRIES:
        keep = lines[-(MAX_LOG_ENTRIES // 2):]
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.writelines(keep)


def load_state():
    if not STATE_PATH.exists():
        return {
            "last_interaction": None,
            "last_trigger": None,
            "today_triggers": 0,
            "today_date": datetime.now().strftime("%Y-%m-%d"),
            "last_mood": "neutral",
            "pending_topic": False,
            "recent_interactions": []
        }
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def log_decision(features, score, decision, reason=""):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "features": {k: round(v, 3) for k, v in features.items()},
        "score": round(score, 4),
        "decision": decision,
        "reason": reason
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ============================================================
# 聊天密度检测
# ============================================================

def get_last_chat_time():
    """检查最近一次真实对话活动的时间（排除心跳 poll）。
    从 session jsonl 中倒序查找最后一条非心跳的 user 消息。"""
    if not SESSIONS_DIR.exists():
        return None
    candidates = []
    for f in SESSIONS_DIR.glob("*.jsonl"):
        if ".lock" in f.name or ".bak" in f.name or ".trajectory" in f.name:
            continue
        candidates.append(f)
    if not candidates:
        return None
    latest = max(candidates, key=lambda f: f.stat().st_mtime)
    # 读最后 50 行，倒序找最后一条真实 user 消息
    try:
        with open(latest, "r", encoding="utf-8") as f:
            lines = f.readlines()[-50:]
    except Exception:
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            msg = obj.get("message", {})
            role = msg.get("role", "")
            if role != "user":
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                text = " ".join(texts)
            else:
                continue
            # 排除心跳 poll
            if "[OpenClaw heartbeat poll]" in text:
                continue
            # 找到真实 user 消息，取时间戳
            ts = obj.get("timestamp")
            if ts:
                # jsonl 时间戳是 UTC（带 Z），转本地时间
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.astimezone().replace(tzinfo=None)
        except Exception:
            continue
    return None


def check_chat_density():
    """检查最近N分钟内是否有对话活动。
    返回 (is_chatting, minutes_since_last)"""
    last = get_last_chat_time()
    if not last:
        return False, 999
    gap = (datetime.now() - last).total_seconds() / 60.0
    return gap < CHAT_DENSITY_WINDOW_MIN, gap


# ============================================================
# 特征提取
# ============================================================

# 紧急程度关键词：从最近对话内容判断是否需要更快回访
URGENCY_KEYWORDS_HIGH = [
    "试试", "测试", "尝试", "报错", "错误", "失败", "bug", "fix", "修复",
    "超时", "崩溃", "不行", "不对", "怎么办", "为什么", "排查", "根因",
    "deploy", "部署", "上线", "发版", "来不及", "赶紧",
]
URGENCY_KEYWORDS_MED = [
    "方案", "配置", "安装", "更新", "升级", "迁移", "重构",
    "工作", "开会", "文档", "整理", "计划", "调研",
]


def get_urgency_score(context_text):
    """从最近对话内容判断紧急程度 (0.0=普通闲聊, 0.3=一般工作, 0.8=技术尝试/调试)
    只看最后3条消息，避免被较早的话题干扰。"""
    if not context_text:
        return 0.0
    # 只取最后3条消息判断当前话题方向
    lines = context_text.strip().split("\n")
    recent = "\n".join(lines[-3:])
    text = recent.lower()
    for kw in URGENCY_KEYWORDS_HIGH:
        if kw in text:
            return 0.8
    for kw in URGENCY_KEYWORDS_MED:
        if kw in text:
            return 0.3
    return 0.0


def get_time_score(now):
    """一天中的时间映射：8:00-22:00 线性映射到 0.2-1.0，深夜 0-7 点为 0.1"""
    hour = now.hour + now.minute / 60.0
    if hour < 7:
        return 0.1
    elif hour < 8:
        return 0.15
    elif hour <= 22:
        return 0.2 + (hour - 8) / 14.0 * 0.8
    else:
        return 0.1


def get_gap_score(last_interaction):
    """距离上次对话的时长：指数增长，像思念一样随时间累积。
    gap(t) = base × (1 + k)^t，每分钟递增 k。
    不是阶梯跳变，是连续平滑增长。"""
    if not last_interaction:
        return 1.0  # 从没聊过，给最高分
    last = datetime.fromisoformat(last_interaction)
    gap_minutes = (datetime.now() - last).total_seconds() / 60.0
    if gap_minutes < 0:
        return 0.0
    # base=0.25, k=0.045: 每分钟增长 4.5%
    # 25分钟普通触发，15分钟调试触发
    base = 0.25
    k = 0.045
    gap_score = base * ((1 + k) ** gap_minutes)
    return min(1.0, gap_score)


def get_frequency_score(today_count):
    """今日已对话次数：太少分高，太多分低"""
    if today_count == 0:
        return 1.0
    elif today_count == 1:
        return 0.7
    elif today_count <= 3:
        return 0.4
    elif today_count <= 5:
        return 0.2
    else:
        return 0.1


def get_mood_score(last_mood):
    """上次对话情绪：低落时多关心"""
    mood_map = {
        "low": 1.0,
        "sad": 1.0,
        "neutral": 0.5,
        "happy": 0.3,
        "excited": 0.2,
    }
    return mood_map.get(last_mood, 0.5)


def get_weekday_score(now):
    """工作日 vs 周末"""
    if now.weekday() < 5:  # 周一到周五
        return 1.0
    else:
        return 0.6


def get_pending_score(state):
    """有无pending话题"""
    return 1.0 if state.get("pending_topic", False) else 0.0


def get_trend_score(recent_interactions):
    """最近3天平均对话频率：低于均值=1.0，高于=0.2"""
    if not recent_interactions:
        return 0.8  # 没有历史数据，给中高分
    now = datetime.now()
    three_days_ago = now - timedelta(days=3)
    recent = [
        ts for ts in recent_interactions
        if datetime.fromisoformat(ts) > three_days_ago
    ]
    if len(recent) < 5:
        return 1.0  # 最近聊得少，更想找你
    elif len(recent) < 15:
        return 0.5
    else:
        return 0.2


def extract_features(state, now, chat_context=None):
    """提取所有特征"""
    base_gap = get_gap_score(state.get("last_interaction"))
    
    # 紧急程度加分：加法而非乘法，urgency=0 时不影响
    # urgency=0.8 + k=0.4 -> 加 0.32，使调试场景 15 分钟即可触发
    urgency = get_urgency_score(chat_context) if chat_context else 0.0
    effective_gap = min(1.0, base_gap + urgency * 0.4)
    
    return {
        "time_score": get_time_score(now),
        "gap_score": effective_gap,
        "urgency_score": urgency,  # 记录用，weights 里默认 0 不参与加权
        "frequency_score": get_frequency_score(state.get("today_triggers", 0)),
        "mood_score": get_mood_score(state.get("last_mood", "neutral")),
        "weekday_score": get_weekday_score(now),
        "pending_score": get_pending_score(state),
        "trend_score": get_trend_score(state.get("recent_interactions", [])),
    }


# ============================================================
# 决策
# ============================================================

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def decide(features, weights, threshold):
    """加权求和 + sigmoid"""
    # urgency_score 是 gap_score 的调节因子，不参与独立加权
    scored_keys = [k for k in features if k != "urgency_score"]
    raw = sum(features[k] * weights.get(k, 0) for k in scored_keys)
    # 把 raw 从 [0, 1] 区间映射到 sigmoid 的敏感区间
    # raw 大约在 0-1 之间，映射到 -3 到 3
    mapped = (raw - 0.5) * 6
    score = sigmoid(mapped)
    return score, score >= threshold


def check_quiet_hours(now, quiet_hours):
    """检查是否在勿扰时段"""
    start, end = quiet_hours
    hour = now.hour
    if start > end:  # 跨夜，如 22-7
        return hour >= start or hour < end
    else:
        return start <= hour < end


def check_cooldown(state, cooldown_minutes):
    """检查冷却期"""
    last_trigger = state.get("last_trigger")
    if not last_trigger:
        return True
    last = datetime.fromisoformat(last_trigger)
    elapsed = (datetime.now() - last).total_seconds() / 60.0
    return elapsed >= cooldown_minutes


def check_daily_limit(state, daily_max):
    """检查每日上限"""
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("today_date") != today:
        state["today_date"] = today
        state["today_triggers"] = 0
    return state.get("today_triggers", 0) < daily_max


def run_decision(config, state, verbose=False):
    """跑一次完整决策流程。返回 (decision, score, reason, features)"""
    now = datetime.now()

    # 同步 last_interaction 到实际 session 文件修改时间
    # （--record-interaction 没有外部调用方，改为自动同步）
    last_chat = get_last_chat_time()
    if last_chat:
        stored = state.get("last_interaction")
        if not stored or datetime.fromisoformat(stored) < last_chat:
            state["last_interaction"] = last_chat.isoformat()
            # 检测到新的交互，加入 recent_interactions 用于 trend_score
            if "recent_interactions" not in state:
                state["recent_interactions"] = []
            state["recent_interactions"].append(last_chat.isoformat())
            # 只保留最近30天的
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            state["recent_interactions"] = [
                ts for ts in state["recent_interactions"]
                if ts > cutoff
            ]
            save_state(state)
            if verbose:
                print(f"[同步] last_interaction -> {last_chat.isoformat()}")

    # 先检查聊天密度：正在聊就不插嘴
    is_chatting, gap_min = check_chat_density()
    if is_chatting:
        if verbose:
            print(f"[聊天中] 距上次对话 {gap_min:.1f}分钟, 跳过决策")
        return 0, 0.0, "chatting", {}

    features = extract_features(state, now, chat_context=get_recent_chat_context(8))

    # 硬性拦截
    if check_quiet_hours(now, config["quiet_hours"]):
        log_decision(features, 0.0, 0, "quiet_hours")
        if verbose:
            print(f"[勿扰时段] score=0, decision=0")
        return 0, 0.0, "quiet_hours", features

    if not check_cooldown(state, config["cooldown_minutes"]):
        log_decision(features, 0.0, 0, "cooldown")
        if verbose:
            print(f"[冷却中] score=0, decision=0")
        return 0, 0.0, "cooldown", features

    if not check_daily_limit(state, config["daily_max_triggers"]):
        log_decision(features, 0.0, 0, "daily_limit")
        if verbose:
            print(f"[今日上限] score=0, decision=0")
        return 0, 0.0, "daily_limit", features

    # 加权决策
    score, triggered = decide(features, config["weights"], config["threshold"])

    if triggered:
        log_decision(features, score, 1, "triggered")
        state["last_trigger"] = now.isoformat()
        state["today_triggers"] = state.get("today_triggers", 0) + 1
        if verbose:
            print(f"[触发] score={score:.4f}, decision=1")
            for k, v in features.items():
                print(f"  {k}: {v:.3f} (weight={config['weights'].get(k, 0)})")
    else:
        log_decision(features, score, 0, "below_threshold")
        if verbose:
            print(f"[未触发] score={score:.4f}, decision=0")
            for k, v in features.items():
                print(f"  {k}: {v:.3f} (weight={config['weights'].get(k, 0)})")

    return (1 if triggered else 0), score, ("triggered" if triggered else "below_threshold"), features


# ============================================================
# 对话上下文提取
# ============================================================

def get_recent_chat_context(num_messages=8):
    """从最近的 session jsonl 中提取最后 N 条 user/assistant 文本消息"""
    if not SESSIONS_DIR.exists():
        return None
    candidates = []
    for f in SESSIONS_DIR.glob("*.jsonl"):
        if ".lock" in f.name or ".bak" in f.name or ".trajectory" in f.name:
            continue
        candidates.append(f)
    if not candidates:
        return None
    latest = max(candidates, key=lambda f: f.stat().st_mtime)
    # 只读最后 50 行（足够取 num_messages 条有效消息）
    try:
        with open(latest, "r", encoding="utf-8") as f:
            all_lines = f.readlines()[-50:]
    except Exception:
        return None
    messages = []
    for line in all_lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            msg = obj.get("message", {})
            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content", "")
            if isinstance(content, list):
                texts = [c.get("text", "") for c in content if c.get("type") == "text" and c.get("text", "")]
                text = " ".join(texts)
            elif isinstance(content, str):
                text = content
            else:
                continue
            text = text.strip()
            if not text:
                continue
            # 跳过心跳poll和HEARTBEAT_OK
            if text in ("HEARTBEAT_OK", "NO_REPLY"):
                continue
            if "[OpenClaw heartbeat poll]" in text:
                continue
            # 每条消息截取前300字
            if len(text) > 300:
                text = text[:300] + "..."
            messages.append(f"[{role}] {text}")
        except Exception:
            continue
    # 取最后 num_messages 条
    return "\n".join(messages[-num_messages:]) if messages else None


# ============================================================
# openclaw 系统事件注入
# ============================================================

def send_trigger_event(score, features):
    """触发时通过 cron wake 唤醒主会话，触发 agent turn"""
    feature_str = ", ".join(f"{k}={v:.2f}" for k, v in features.items())
    context = get_recent_chat_context(8)
    message = (
        f"[自主决策器触发] score={score:.4f}\n"
        f"特征: {feature_str}\n"
    )
    if context:
        message += (
            f"\n## 最近对话上下文\n{context}\n\n"
        )
    message += (
        "## 你的任务\n"
        "根据上面的对话上下文，判断：\n"
        "1. 上次聊天的话题方向（工作/闲聊/人生感悟/技术探索/情绪低落等）\n"
        "2. 点点的情绪状态\n"
        "3. 结尾状态（是否说要去忙、是否有未完成的话题）\n"
        "4. 是否该主动发消息，以及发什么\n\n"
        "判断原则：\n"
        "- 上次聊情绪话题、心情不好 → 该发，安慰+转移注意力\n"
        "- 上次在尝试新技术/新方案 → 该发，问一句结果如何\n"
        "- 上次聊到一半被打断 → 该发，顺一下之前的话题\n"
        "- 上次是轻松闲聊、间隔较久 → 该发，自然打个招呼\n"
        "- 上次明确说去忙/去开会、没什么需要跟进 → 不该发，静默跳过\n"
        "- 上次是工作对话、已结束、无回访点 → 不该发，静默跳过\n\n"
        "如果该发：用自然语言，像朋友突然想找他说句话。不要提技术词。\n"
        "如果不该发：回 HEARTBEAT_OK 静默跳过。"
    )
    try:
        subprocess.run(
            ["openclaw", "system", "event", "--mode", "now", "--expect-final", "--timeout", "60000", "--text", message],
            capture_output=True, timeout=90
        )
    except Exception as e:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "error": f"event_send_failed: {e}"
            }, ensure_ascii=False) + "\n")


# ============================================================
# 统计
# ============================================================

def print_stats():
    """打印统计信息"""
    if not LOG_PATH.exists():
        print("暂无决策记录")
        return

    decisions = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                decisions.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

    total = len(decisions)
    triggered = sum(1 for d in decisions if d.get("decision") == 1)
    today = datetime.now().strftime("%Y-%m-%d")
    today_decisions = [d for d in decisions if d.get("timestamp", "").startswith(today)]

    print(f"=== 自主决策器统计 ===")
    print(f"总决策次数: {total}")
    print(f"触发次数: {triggered}")
    print(f"触发率: {triggered/total*100:.1f}%" if total else "触发率: N/A")
    print(f"今日决策: {len(today_decisions)}")

    state = load_state()
    print(f"\n=== 当前状态 ===")
    print(f"今日已触发: {state.get('today_triggers', 0)}")
    print(f"上次对话: {state.get('last_interaction', '无')}")
    print(f"上次触发: {state.get('last_trigger', '无')}")
    print(f"上次情绪: {state.get('last_mood', 'neutral')}")
    print(f"pending话题: {state.get('pending_topic', False)}")

    # 最近5条决策
    recent = decisions[-5:]
    if recent:
        print(f"\n=== 最近5条决策 ===")
        for d in recent:
            ts = d.get("timestamp", "?")[:19]
            score = d.get("score", 0)
            decision = "触发" if d.get("decision") == 1 else "未触发"
            reason = d.get("reason", "")
            print(f"  {ts} | score={score:.4f} | {decision} | {reason}")


# ============================================================
# 权重初始化
# ============================================================

def init_weights_from_daily():
    """从daily文件里统计对话时间分布，生成初始权重建议"""
    if not DAILY_DIR.exists():
        print(f"daily目录不存在: {DAILY_DIR}")
        return

    hourly = {h: 0 for h in range(24)}
    weekday = {d: 0 for d in range(7)}
    total_files = 0

    for f in DAILY_DIR.glob("*.md"):
        if "transcript" in f.name:
            continue
        total_files += 1
        with open(f, "r", encoding="utf-8") as fh:
            content = fh.read()
            # 找时间戳模式 HH:MM
            import re
            times = re.findall(r'\b(\d{1,2}):(\d{2})\b', content)
            for h_str, m_str in times:
                h = int(h_str)
                if 0 <= h <= 23:
                    hourly[h] += 1
                    # 从文件名取日期判断星期
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', f.name)
                    if date_match:
                        try:
                            d = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                            weekday[d.weekday()] += 1
                        except ValueError:
                            pass

    print(f"=== 从daily数据统计 ===")
    print(f"扫描文件数: {total_files}")

    print(f"\n按小时分布:")
    for h in range(24):
        bar = "█" * (hourly[h] // 2)
        print(f"  {h:02d}:00  [{hourly[h]:4d}]  {bar}")

    print(f"\n按星期分布:")
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for i, d in enumerate(days):
        bar = "█" * (weekday[i] // 2)
        print(f"  {d}  [{weekday[i]:4d}]  {bar}")

    total_mentions = sum(hourly.values())
    if total_mentions > 0:
        peak_hours = sorted(hourly.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"\n最活跃时段: {', '.join(f'{h:02d}:00({c}次)' for h, c in peak_hours)}")
        print(f"总时间戳提及: {total_mentions}")

        # 根据分布给出权重建议
        workday_count = sum(weekday[i] for i in range(5))
        weekend_count = sum(weekday[i] for i in range(5, 7))
        if workday_count + weekend_count > 0:
            workday_ratio = workday_count / (workday_count + weekend_count)
            print(f"\n工作日占比: {workday_ratio*100:.1f}%")

        print(f"\n=== 权重建议（已写入config.json）===")
        config = load_config()
        # 根据统计微调权重
        # 高峰时段越集中，time_score权重越高
        # 工作日占比越高，weekday_score权重越高
        if total_mentions > 100:
            peak_concentration = peak_hours[0][1] / total_mentions
            if peak_concentration > 0.15:
                config["weights"]["time_score"] = 0.25
            else:
                config["weights"]["time_score"] = 0.15

        if workday_count + weekend_count > 0:
            ratio = workday_count / (workday_count + weekend_count)
            if ratio > 0.8:
                config["weights"]["weekday_score"] = 0.15
            elif ratio < 0.6:
                config["weights"]["weekday_score"] = 0.05

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        for k, v in config["weights"].items():
            print(f"  {k}: {v}")
        print(f"  threshold: {config['threshold']}")


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="自主决策器")
    parser.add_argument("--check", action="store_true", help="跑一次决策")
    parser.add_argument("--verbose", action="store_true", help="打印详细信息")
    parser.add_argument("--stats", action="store_true", help="查看统计")
    parser.add_argument("--init", action="store_true", help="从daily数据初始化权重")
    parser.add_argument("--set-mood", type=str, help="设置上次对话情绪")
    parser.add_argument("--set-pending", type=str, choices=["true", "false"], help="设置pending话题")
    parser.add_argument("--record-interaction", action="store_true", help="记录一次交互（更新last_interaction）")
    args = parser.parse_args()

    config = load_config()
    state = load_state()

    if args.stats:
        print_stats()
        return

    if args.init:
        init_weights_from_daily()
        return

    if args.set_mood:
        state["last_mood"] = args.set_mood
        save_state(state)
        print(f"已设置情绪: {args.set_mood}")
        return

    if args.set_pending:
        state["pending_topic"] = args.set_pending == "true"
        save_state(state)
        print(f"已设置pending: {args.set_pending}")
        return

    if args.record_interaction:
        now = datetime.now().isoformat()
        state["last_interaction"] = now
        if "recent_interactions" not in state:
            state["recent_interactions"] = []
        state["recent_interactions"].append(now)
        # 只保留最近30天的
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        state["recent_interactions"] = [
            ts for ts in state["recent_interactions"]
            if ts > cutoff
        ]
        save_state(state)
        print(f"已记录交互: {now}")
        return

    if args.check:
        rotate_log()
        decision, score, reason, features = run_decision(config, state, verbose=args.verbose)
        if decision == 1:
            send_trigger_event(score, features)
        save_state(state)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
