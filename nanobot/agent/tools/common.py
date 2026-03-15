"""
公共工具函数模块

提供各数据 API 模块共用的工具函数：
- 错误处理装饰器
- 类型安全转换
- 时间格式化
"""

import logging
from datetime import datetime
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def api_error_handler(error_prefix: str):
    """
    装饰器：统一处理 API 调用异常。

    参数：
        error_prefix: 错误消息前缀

    用法：
        @api_error_handler("获取数据失败")
        def get_data():
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ImportError as e:
                return {"error": str(e)}
            except Exception as e:
                logger.warning("%s: %s", error_prefix, e)
                return {"error": f"{error_prefix}: {e}"}

        return wrapper

    return decorator


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    安全转换为 float，失败返回默认值。

    参数：
        value: 要转换的值
        default: 默认值

    返回：
        转换后的 float 或默认值
    """
    if value is None or value == "":
        return default
    try:
        # 处理 pandas NaN
        import math
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_float_pandas(value: Any, default: float = 0.0) -> float:
    """
    安全转换为 float（支持 pandas 类型），失败返回默认值。

    参数：
        value: 要转换的值
        default: 默认值

    返回：
        转换后的 float 或默认值
    """
    if value is None or value == "":
        return default
    try:
        import pandas as pd
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_optional_float(value: Any) -> float | None:
    """
    安全转换为 float，空值/失败返回 None。

    参数：
        value: 要转换的值

    返回：
        转换后的 float 或 None
    """
    if value is None or value == "":
        return None
    try:
        import pandas as pd
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def safe_str(value: Any, default: str = "") -> str:
    """
    安全转换为字符串。

    参数：
        value: 要转换的值
        default: 默认值

    返回：
        转换后的字符串或默认值
    """
    if value is None:
        return default
    try:
        import pandas as pd
        if isinstance(value, float) and pd.isna(value):
            return default
    except ImportError:
        pass
    except Exception:
        pass
    return str(value)


def format_datetime(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化当前时间。

    参数：
        fmt: 时间格式字符串

    返回：
        格式化后的时间字符串
    """
    return datetime.now().strftime(fmt)


def format_date(fmt: str = "%Y%m%d") -> str:
    """
    格式化当前日期。

    参数：
        fmt: 日期格式字符串

    返回：
        格式化后的日期字符串
    """
    return datetime.now().strftime(fmt)


def format_large_number(value: float | None) -> str:
    """
    格式化大数字为可读形式。

    参数：
        value: 数字值

    返回：
        格式化后的字符串（如 1.5T, 2.3B, 4.5M）
    """
    if value is None or value == 0:
        return "N/A"
    if abs(value) >= 1e12:
        return f"{value / 1e12:.2f}T"
    if abs(value) >= 1e9:
        return f"{value / 1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:.2f}M"
    return f"{value:,.0f}"


__all__ = [
    "api_error_handler",
    "safe_float",
    "safe_float_pandas",
    "safe_optional_float",
    "safe_str",
    "format_datetime",
    "format_date",
    "format_large_number",
]
