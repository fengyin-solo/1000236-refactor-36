"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。

数据准备（seed）由启动管线 ``app/bootstrap.py`` 显式触发，仓库本身启动时保持空表，
这样“数据准备”是一个可单独校验、可安全重跑的步骤：
- 已有 id 的单据直接跳过，绝不覆盖已有道具单据和列表结果；
- 种子里新增的单据会补齐，重跑结果幂等。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def seed_if_missing(self) -> dict[str, dict[str, int]]:
        """幂等灌入示例数据。

        返回每个模块 ``{inserted, skipped, total}``：已存在的 id 跳过，
        只补缺失的种子单据，不修改、不覆盖任何已有行。
        """
        report: dict[str, dict[str, int]] = {}
        for module, seed_rows in SEED_ROWS.items():
            table = self.rows(module)
            existing_ids = {int(row.get("id", 0)) for row in table}
            inserted = 0
            for seed in seed_rows:
                seed_id = int(seed.get("id", 0))
                if seed_id in existing_ids:
                    continue
                table.append(dict(seed))
                existing_ids.add(seed_id)
                inserted += 1
            report[module] = {
                "inserted": inserted,
                "skipped": len(seed_rows) - inserted,
                "total": len(table),
            }
        return report

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


store = Store()
