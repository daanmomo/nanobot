#!/usr/bin/env python3
"""Observation 记录系统 — 学自 OpenClaw claude-mem 的自动观察记录。

核心思路：
- 每次重要操作自动记录为一条 observation
- 存储在 SQLite 数据库中，支持搜索和时间线查询
- 为跨会话的上下文注入提供数据基础

用法：
  # 记录一条 observation
  python3 observation.py add --title "部署了飞书日报" --detail "推送成功，包含3个模块"

  # 搜索 observations
  python3 observation.py search "飞书"

  # 查看最近 N 条
  python3 observation.py recent --limit 10

  # 查看今日摘要
  python3 observation.py today

  # 导出为 markdown（用于注入 system prompt）
  python3 observation.py inject --limit 20

  # 清理旧记录（保留最近 N 天）
  python3 observation.py cleanup --days 30
"""

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("/Users/momo/.nanobot/workspace/memory/observations.db")


def get_db() -> sqlite3.Connection:
    """获取数据库连接，自动建表。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            title TEXT NOT NULL,
            detail TEXT,
            category TEXT DEFAULT 'general',
            tool_name TEXT,
            tags TEXT,
            session_id TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON observations(timestamp DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_obs_category ON observations(category)
    """)
    conn.commit()
    return conn


def add_observation(
    title: str,
    detail: str = None,
    category: str = "general",
    tool_name: str = None,
    tags: str = None,
    session_id: str = None,
) -> int:
    """添加一条 observation。返回 ID。"""
    conn = get_db()
    now = time.time()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor = conn.execute(
        """INSERT INTO observations
           (timestamp, title, detail, category, tool_name, tags, session_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (now, title, detail, category, tool_name, tags, session_id, created_at)
    )
    conn.commit()
    obs_id = cursor.lastrowid
    conn.close()
    print(f"✅ Observation #{obs_id}: {title}")
    return obs_id


def search_observations(query: str, limit: int = 10) -> list:
    """搜索 observations。"""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM observations
           WHERE title LIKE ? OR detail LIKE ? OR tags LIKE ?
           ORDER BY timestamp DESC LIMIT ?""",
        (f"%{query}%", f"%{query}%", f"%{query}%", limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recent_observations(limit: int = 10) -> list:
    """获取最近的 observations。"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM observations ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def today_observations() -> list:
    """获取今日的 observations。"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM observations WHERE timestamp >= ? ORDER BY timestamp ASC",
        (today_start,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def inject_context(limit: int = 20) -> str:
    """生成可注入 system prompt 的上下文摘要。"""
    obs_list = recent_observations(limit)
    if not obs_list:
        return ""

    lines = ["## Recent Observations (auto-generated)", ""]
    for obs in reversed(obs_list):  # 时间正序
        ts = obs["created_at"]
        title = obs["title"]
        cat = obs.get("category", "")
        line = f"- [{ts}] [{cat}] {title}"
        if obs.get("detail"):
            line += f" — {obs['detail'][:100]}"
        lines.append(line)

    return "\n".join(lines)


def cleanup_old(days: int = 30) -> int:
    """清理旧记录。"""
    cutoff = time.time() - (days * 86400)
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM observations WHERE timestamp < ?", (cutoff,)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"🗑️ 清理了 {deleted} 条 {days} 天前的记录")
    return deleted


def stats() -> dict:
    """统计信息。"""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    today_count = len(today_observations())
    categories = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM observations GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "today": today_count,
        "categories": {r["category"]: r["cnt"] for r in categories},
    }


def format_observations(obs_list: list) -> str:
    """格式化输出。"""
    if not obs_list:
        return "📭 无记录"

    lines = []
    for obs in obs_list:
        ts = obs["created_at"]
        title = obs["title"]
        cat = obs.get("category", "general")
        line = f"[{ts}] [{cat}] {title}"
        if obs.get("detail"):
            line += f"\n  → {obs['detail'][:200]}"
        lines.append(line)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Observation 记录系统")
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add", help="添加 observation")
    p_add.add_argument("--title", "-t", required=True)
    p_add.add_argument("--detail", "-d", default=None)
    p_add.add_argument("--category", "-c", default="general")
    p_add.add_argument("--tool", default=None)
    p_add.add_argument("--tags", default=None)

    # search
    p_search = sub.add_parser("search", help="搜索")
    p_search.add_argument("query")
    p_search.add_argument("--limit", "-n", type=int, default=10)

    # recent
    p_recent = sub.add_parser("recent", help="最近记录")
    p_recent.add_argument("--limit", "-n", type=int, default=10)

    # today
    sub.add_parser("today", help="今日记录")

    # inject
    p_inject = sub.add_parser("inject", help="生成注入上下文")
    p_inject.add_argument("--limit", "-n", type=int, default=20)

    # cleanup
    p_cleanup = sub.add_parser("cleanup", help="清理旧记录")
    p_cleanup.add_argument("--days", type=int, default=30)

    # stats
    sub.add_parser("stats", help="统计信息")

    args = parser.parse_args()

    if args.command == "add":
        add_observation(
            title=args.title,
            detail=args.detail,
            category=args.category,
            tool_name=args.tool,
            tags=args.tags,
        )
    elif args.command == "search":
        results = search_observations(args.query, args.limit)
        print(format_observations(results))
    elif args.command == "recent":
        results = recent_observations(args.limit)
        print(format_observations(results))
    elif args.command == "today":
        results = today_observations()
        print(f"📅 今日 observations ({len(results)} 条):")
        print(format_observations(results))
    elif args.command == "inject":
        print(inject_context(args.limit))
    elif args.command == "cleanup":
        cleanup_old(args.days)
    elif args.command == "stats":
        s = stats()
        print(f"📊 Observations 统计:")
        print(f"  总计: {s['total']} 条")
        print(f"  今日: {s['today']} 条")
        print(f"  分类: {json.dumps(s['categories'], ensure_ascii=False)}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
