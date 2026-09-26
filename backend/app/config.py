"""运行配置：端口、跨域、运行环境，全部支持用环境变量覆盖。

解析遵循“宽容读取、集中校验”：非法的环境变量不在 import 时抛异常，
而是原样保留 + 记录解析错误，由启动管线的环境校验步骤统一汇总并说明原因，
避免进程在配置阶段就报一串难懂的栈。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_origins(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _read_int(name: str, default: int, errors: list[str]) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        errors.append(f"环境变量 {name}={raw!r} 不是合法整数")
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "影视剧组拍摄制作管理平台"
    env: str = "local"
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_origins: list[str] = field(default_factory=list)
    page_size_default: int = 20
    page_size_max: int = 200
    # 环境校验阶段收集到的配置解析问题；为空表示配置可正常使用。
    parse_errors: list[str] = field(default_factory=list)


def _load_settings() -> Settings:
    parse_errors: list[str] = []
    origins_raw = os.getenv("APP_ALLOWED_ORIGINS")
    origins = (
        _split_origins(origins_raw)
        if origins_raw is not None and origins_raw.strip()
        else ["http://127.0.0.1:5173", "http://localhost:5173"]
    )
    settings = Settings(
        env=os.getenv("APP_ENV", "local").strip() or "local",
        host=os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=_read_int("APP_PORT", 8000, parse_errors),
        allowed_origins=origins,
        page_size_default=_read_int("APP_PAGE_SIZE_DEFAULT", 20, parse_errors),
        page_size_max=_read_int("APP_PAGE_SIZE_MAX", 200, parse_errors),
        parse_errors=parse_errors,
    )
    return settings


settings = _load_settings()
