"""数据仓库：JSON 文件持久化 + 内存读写。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
数据文件存在时原样加载（已有单据不被覆盖），不存在时以示例数据初始化；
每次变更通过 persist() 落盘，重启后单据仍在。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import resolve_data_file
from app.seed import SEED_ROWS


class Store:
    def __init__(self, data_file: Path | None = None) -> None:
        self._data_file = data_file
        if data_file is not None and data_file.exists():
            self._tables = self._load(data_file)
        else:
            self._tables = {
                name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
            }

    @staticmethod
    def _load(data_file: Path) -> dict[str, list[dict[str, Any]]]:
        try:
            payload = json.loads(data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"数据文件 {data_file} 读取失败：{exc}；"
                "可修复后重跑，或删除该文件由数据准备步骤重新初始化"
            ) from exc
        if not isinstance(payload, dict) or not all(isinstance(v, list) for v in payload.values()):
            raise RuntimeError(
                f"数据文件 {data_file} 结构不正确：应为 {{模块名: [记录...]}}，"
                "可修复后重跑，或删除该文件由数据准备步骤重新初始化"
            )
        return payload

    @property
    def data_file(self) -> Path | None:
        return self._data_file

    def persist(self) -> None:
        """把当前数据落盘；纯内存模式（无数据文件）下直接跳过。"""
        if self._data_file is None:
            return
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._data_file.with_name(self._data_file.name + ".tmp")
        tmp.write_text(
            json.dumps(self._tables, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._data_file)

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store(resolve_data_file())
