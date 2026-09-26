"""运行配置：端口、跨域、运行环境与数据文件位置。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_name: str = "影视剧组拍摄制作管理平台"
    env: str = field(default_factory=lambda: os.environ.get("APP_ENV", "local"))
    host: str = field(default_factory=lambda: os.environ.get("APP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("APP_PORT", "8000")))
    # 数据文件：默认 backend/data/store.json；APP_DATA_FILE 置空字符串表示纯内存运行
    data_file: str = field(default_factory=lambda: os.environ.get("APP_DATA_FILE", "data/store.json"))
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )
    page_size_default: int = 20
    page_size_max: int = 200


settings = Settings()


def resolve_data_file() -> Path | None:
    """数据文件的绝对路径；配置为空字符串时返回 None（纯内存模式）。"""
    raw = settings.data_file.strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else BASE_DIR / path
