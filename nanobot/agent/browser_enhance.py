"""
browser_enhance.py — 借鉴 browser-harness 的三个设计理念
1. BrowserFallback: 预定义工具失败时，自动降级到 raw JS
2. DomainSkills: 成功操作后自动沉淀域名技能
3. VerifyLoop: 操作后截图验证，失败换策略重试

~200 行，零外部依赖，纯增强层不改现有工具。
"""

import json
import time
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Dict, Any, List
from datetime import datetime

# ─── Domain Skills 存储路径 ───
DOMAIN_SKILLS_DIR = Path(__file__).parent.parent / "skills" / "browser" / "domain_skills"


# ═══════════════════════════════════════════════════════════
# 1. BrowserFallback — 预定义工具失败时自动生成 JS 降级方案
# ═══════════════════════════════════════════════════════════

class BrowserFallback:
    """
    当 browser_click / browser_extract 等工具失败时，
    自动生成等效的 JS 代码，通过 browser_execute_js 重试。
    
    灵感来源：browser-harness 的 "Agent 自己写工具" 哲学。
    区别：我们不让模型从零写，而是提供预制的 JS 模板。
    """

    # 常见操作的 JS 降级模板
    FALLBACK_TEMPLATES = {
        "click": """
            (function() {
                // 策略1: CSS 选择器
                let el = document.querySelector('{selector}');
                if (el) { el.click(); return 'clicked via selector'; }
                
                // 策略2: 文本匹配
                let all = document.querySelectorAll('a, button, [role="button"], [onclick]');
                for (let e of all) {
                    if (e.textContent.trim().includes('{text}')) {
                        e.click(); return 'clicked via text match: ' + e.tagName;
                    }
                }
                
                // 策略3: 坐标点击 (穿透 iframe/shadow DOM)
                let target = document.elementFromPoint({x}, {y});
                if (target) { target.click(); return 'clicked via coordinates: ' + target.tagName; }
                
                return 'FAILED: no clickable element found';
            })()
        """,
        "extract": """
            (function() {
                let results = [];
                let items = document.querySelectorAll('{list_selector}');
                if (items.length === 0) {
                    // 降级: 尝试常见列表容器
                    let guesses = ['table tbody tr', 'ul li', '.list-item', '[class*="item"]', '[class*="card"]'];
                    for (let g of guesses) {
                        items = document.querySelectorAll(g);
                        if (items.length > 1) break;
                    }
                }
                items.forEach((item, i) => {
                    if (i >= {limit}) return;
                    let row = {};
                    let fields = {fields_json};
                    for (let [key, sel] of Object.entries(fields)) {
                        let el = item.querySelector(sel);
                        row[key] = el ? el.textContent.trim() : '';
                    }
                    results.push(row);
                });
                return JSON.stringify(results);
            })()
        """,
        "fill": """
            (function() {
                let el = document.querySelector('{selector}');
                if (!el) {
                    // 降级: name/id/placeholder 匹配
                    el = document.querySelector('[name*="{hint}"], [id*="{hint}"], [placeholder*="{hint}"]');
                }
                if (el) {
                    el.focus();
                    el.value = '{value}';
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return 'filled: ' + el.tagName + '#' + (el.id || el.name || '');
                }
                return 'FAILED: input not found';
            })()
        """,
        "scroll_to_bottom": """
            (function() {
                window.scrollTo(0, document.body.scrollHeight);
                return 'scrolled to bottom, height=' + document.body.scrollHeight;
            })()
        """,
        "get_all_links": """
            (function() {
                let links = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    links.push({ text: a.textContent.trim().slice(0, 80), href: a.href });
                });
                return JSON.stringify(links.slice(0, {limit}));
            })()
        """
    }

    @classmethod
    def get_fallback_js(cls, action: str, params: Dict[str, Any]) -> Optional[str]:
        """获取降级 JS 代码。返回 None 表示没有对应模板。"""
        template = cls.FALLBACK_TEMPLATES.get(action)
        if not template:
            return None
        try:
            # 安全替换参数
            js = template
            for key, value in params.items():
                placeholder = '{' + key + '}'
                if placeholder in js:
                    # 转义 JS 字符串中的特殊字符
                    safe_val = str(value).replace("'", "\\'").replace("\n", "\\n")
                    js = js.replace(placeholder, safe_val)
            return js.strip()
        except Exception:
            return None

    @classmethod
    def should_fallback(cls, tool_name: str, error_msg: str) -> bool:
        """判断是否应该触发 JS 降级。"""
        fallback_triggers = [
            "element not found",
            "selector",
            "timeout",
            "waiting for",
            "no such element",
            "not visible",
            "intercepted",
            "detached",
        ]
        error_lower = error_msg.lower()
        return any(trigger in error_lower for trigger in fallback_triggers)


# ═══════════════════════════════════════════════════════════
# 2. DomainSkills — 成功操作后自动沉淀域名技能
# ═══════════════════════════════════════════════════════════

class DomainSkills:
    """
    记录每个域名的成功操作模式，下次操作同域名时先查。
    
    灵感来源：browser-harness 的 domain-skills/ 自动生成。
    区别：我们不 PR 回 GitHub，而是本地沉淀到 skills/browser/domain_skills/。
    """

    @staticmethod
    def _domain_key(url: str) -> str:
        """从 URL 提取域名作为 key。"""
        try:
            parsed = urlparse(url)
            # 去掉 www. 前缀
            domain = parsed.netloc.replace("www.", "")
            # 替换特殊字符
            return domain.replace(".", "_").replace(":", "_")
        except Exception:
            return "unknown"

    @staticmethod
    def _skills_file(domain_key: str) -> Path:
        """获取域名技能文件路径。"""
        DOMAIN_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        return DOMAIN_SKILLS_DIR / f"{domain_key}.json"

    @classmethod
    def record(cls, url: str, action: str, selector: str,
               success: bool, tip: str = "") -> None:
        """记录一次操作结果。"""
        domain_key = cls._domain_key(url)
        skills_file = cls._skills_file(domain_key)

        # 读取已有技能
        skills = {}
        if skills_file.exists():
            try:
                skills = json.loads(skills_file.read_text(encoding="utf-8"))
            except Exception:
                skills = {}

        # 更新
        if "operations" not in skills:
            skills["operations"] = []
        
        # 去重：同 action+selector 只保留最新
        skills["operations"] = [
            op for op in skills["operations"]
            if not (op.get("action") == action and op.get("selector") == selector)
        ]

        skills["operations"].append({
            "action": action,
            "selector": selector,
            "success": success,
            "tip": tip,
            "timestamp": datetime.now().isoformat(),
        })

        # 只保留最近 50 条
        skills["operations"] = skills["operations"][-50:]
        skills["domain"] = domain_key
        skills["last_updated"] = datetime.now().isoformat()

        skills_file.write_text(
            json.dumps(skills, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    @classmethod
    def lookup(cls, url: str, action: str = "") -> List[Dict]:
        """查询域名的历史成功操作。"""
        domain_key = cls._domain_key(url)
        skills_file = cls._skills_file(domain_key)

        if not skills_file.exists():
            return []

        try:
            skills = json.loads(skills_file.read_text(encoding="utf-8"))
            ops = skills.get("operations", [])
            # 只返回成功的
            ops = [op for op in ops if op.get("success")]
            if action:
                ops = [op for op in ops if op.get("action") == action]
            return ops
        except Exception:
            return []

    @classmethod
    def get_tips(cls, url: str) -> str:
        """获取域名的操作提示，供 Agent 参考。"""
        ops = cls.lookup(url)
        if not ops:
            return ""
        
        tips = []
        for op in ops[-10:]:  # 最近 10 条
            tip = op.get("tip", "")
            if tip:
                tips.append(f"- {op['action']}: {tip}")
            elif op.get("selector"):
                tips.append(f"- {op['action']}: selector `{op['selector']}` worked")
        
        if tips:
            domain = cls._domain_key(url)
            return f"[Domain Skills for {domain}]\n" + "\n".join(tips)
        return ""


# ═══════════════════════════════════════════════════════════
# 3. VerifyLoop — 操作后截图验证，失败换策略
# ═══════════════════════════════════════════════════════════

class VerifyLoop:
    """
    截图-行动-验证循环。
    
    灵感来源：browser-harness 的 "screenshot → act → screenshot → verify"。
    区别：我们不自己调浏览器，而是生成建议策略供 Agent 使用。
    """

    @staticmethod
    def suggest_verify_plan(action: str, url: str) -> Dict[str, Any]:
        """
        为一次浏览器操作生成验证计划。
        返回 Agent 应该执行的步骤。
        """
        plan = {
            "action": action,
            "steps": [
                {
                    "step": 1,
                    "tool": "browser_screenshot",
                    "params": {"url": url},
                    "purpose": "操作前截图，记录初始状态"
                },
                {
                    "step": 2,
                    "tool": f"browser_{action}",
                    "params": {"url": url},
                    "purpose": f"执行 {action} 操作"
                },
                {
                    "step": 3,
                    "tool": "browser_screenshot",
                    "params": {"url": url},
                    "purpose": "操作后截图，验证结果"
                },
            ],
            "on_failure": [
                "检查截图对比，确认页面是否变化",
                "如果页面无变化，尝试 JS 降级方案",
                "如果元素不存在，尝试先滚动页面",
                "如果被遮挡，尝试关闭弹窗/cookie banner",
            ]
        }
        return plan

    @staticmethod
    def failure_strategies(error_msg: str) -> List[str]:
        """
        根据错误信息推荐恢复策略。
        """
        strategies = []
        error_lower = error_msg.lower()

        if "timeout" in error_lower:
            strategies.append("等待时间不够 → 增加 timeout 或改用 domcontentloaded")
        if "not visible" in error_lower or "hidden" in error_lower:
            strategies.append("元素被隐藏 → 先滚动到元素位置，或用 JS 强制显示")
        if "intercepted" in error_lower:
            strategies.append("点击被拦截 → 可能有弹窗/overlay，先关闭它")
        if "iframe" in error_lower or "frame" in error_lower:
            strategies.append("元素在 iframe 中 → 用坐标点击穿透，或切换到 iframe 上下文")
        if "selector" in error_lower or "not found" in error_lower:
            strategies.append("选择器失效 → 页面可能改版，尝试文本匹配或坐标点击")
        if "navigation" in error_lower:
            strategies.append("页面跳转了 → 可能触发了重定向，检查当前 URL")
        if not strategies:
            strategies.append("通用策略 → 截图查看当前页面状态，用 browser_execute_js 直接操作 DOM")

        return strategies


# ═══════════════════════════════════════════════════════════
# 便捷接口
# ═══════════════════════════════════════════════════════════

def enhance_browser_prompt(url: str, action: str = "") -> str:
    """
    为浏览器操作生成增强提示。
    在 Agent 执行浏览器任务前调用，注入域名技能和验证建议。
    """
    parts = []

    # 1. 查询域名历史技能
    tips = DomainSkills.get_tips(url)
    if tips:
        parts.append(tips)

    # 2. 生成验证建议
    if action:
        plan = VerifyLoop.suggest_verify_plan(action, url)
        parts.append(f"[Verify Plan] 操作后建议截图验证，失败策略：")
        for s in plan["on_failure"]:
            parts.append(f"  {s}")

    return "\n".join(parts) if parts else ""


def handle_browser_error(tool_name: str, error_msg: str,
                         url: str = "", params: Dict = None) -> Dict[str, Any]:
    """
    浏览器工具报错时调用。返回降级方案。
    
    Returns:
        {
            "should_retry": bool,
            "fallback_js": str | None,  # JS 降级代码
            "strategies": list[str],     # 建议策略
        }
    """
    result = {
        "should_retry": False,
        "fallback_js": None,
        "strategies": VerifyLoop.failure_strategies(error_msg),
    }

    # 判断是否可以 JS 降级
    if BrowserFallback.should_fallback(tool_name, error_msg):
        # 从 tool_name 提取 action (browser_click → click)
        action = tool_name.replace("browser_", "")
        fallback_js = BrowserFallback.get_fallback_js(action, params or {})
        if fallback_js:
            result["should_retry"] = True
            result["fallback_js"] = fallback_js

    # 记录失败到域名技能
    if url:
        DomainSkills.record(
            url=url,
            action=tool_name,
            selector=str(params.get("selector", "")) if params else "",
            success=False,
            tip=f"Failed: {error_msg[:100]}"
        )

    return result
