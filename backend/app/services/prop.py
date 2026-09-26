"""道具管理业务规则：状态流转、字段校验与筛选口径都收在这里。

借出、归还、损毁的判定统一走 app.rules.PROP_RULES，本文件只负责
读写数据与拼装结果，不再各自维护一份规则。
"""
from __future__ import annotations

from typing import Any

from app.rules import PROP_RULES
from app.store import store

MODULE = PROP_RULES.module
REQUIRED_FIELDS = list(PROP_RULES.required_fields)


class PropService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("道具编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._decorate(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._decorate(row) if row is not None else None

    def stats(self) -> list[dict[str, Any]]:
        """库存统计：口径统一由 PROP_RULES 推导，页面直接展示。"""
        return PROP_RULES.inventory_stats(store.rows(MODULE))

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = PROP_RULES.status_order[0]
        entry["pending"], entry["abnormal"] = PROP_RULES.derive_flags(entry["status"])
        rows.append(entry)
        store.persist()
        return self._decorate(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"道具 {entry_id} 不存在或已归档"
        reason = PROP_RULES.check_action(str(entry.get("status", "")), action)
        if reason:
            return None, f"道具 {entry_id}：{reason}"
        target = PROP_RULES.actions[action].target
        entry["status"] = target
        entry["pending"], entry["abnormal"] = PROP_RULES.derive_flags(target)
        store.persist()
        return self._decorate(entry), f"道具已{action}"

    @staticmethod
    def _decorate(row: dict[str, Any]) -> dict[str, Any]:
        """附上当前状态可执行的动作，页面按它渲染按钮，不再自行判断。"""
        entry = dict(row)
        entry["available_actions"] = PROP_RULES.allowed_actions(str(row.get("status", "")))
        return entry
