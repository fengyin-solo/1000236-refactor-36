"""道具管理业务规则：状态流转、字段校验、筛选与库存口径全部收在这里。

口径约定（借出 / 归还 / 损毁只有这一个出处，路由与页面都不再各自维护）：
- 权威状态存内部字段 ``status``，取值固定为 ``STATUS_ORDER``：在库 → 已借出 → 已归还 → 已损毁；
- 展示字段「使用状态」始终由 ``status`` 镜像得到，读时再投影，不允许两处分别写；
- ``TRANSITIONS`` 规定每种当前状态允许的动作：
    在库   → 借出道具 / 登记损毁
    已借出 → 归还道具 / 登记损毁
    已归还、已损毁为终态，不再允许任何流转；
- 「可借出」口径恒等于 status == 在库；待归还恒等于 status == 已借出。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "prop"
REQUIRED_FIELDS = ["道具编号", "道具名称", "道具类别"]
STATUS_FIELD = "status"
DISPLAY_STATUS_FIELD = "使用状态"

# 状态序列同时也是唯一合法的库存口径。
STATUS_ORDER = ["在库", "已借出", "已归还", "已损毁"]
DEFAULT_STATUS = STATUS_ORDER[0]
TERMINAL_STATUSES = ["已归还", "已损毁"]

# 动作 → 目标状态。是否允许执行由 TRANSITIONS 按“当前状态”判定，不能只看动作名。
ACTION_RULES = {"借出道具": "已借出", "归还道具": "已归还", "登记损毁": "已损毁"}
TRANSITIONS: dict[str, list[str]] = {
    "在库": ["借出道具", "登记损毁"],
    "已借出": ["归还道具", "登记损毁"],
    "已归还": [],
    "已损毁": [],
}
# 损毁属于异常单据；借出/归还是正常流转。
ABNORMAL_ACTION = "登记损毁"


class PropService:
    # ---- 读 ----------------------------------------------------------------
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._present(row) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("道具编号", ""))]
        if status:
            rows = [row for row in rows if row[STATUS_FIELD] == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._present(row) if row is not None else None

    def stats(self) -> dict[str, int]:
        """库存卡片口径：在库可借、已借出待归还、已损毁异常，均直接按 status 统计。"""
        rows = store.rows(MODULE)
        return {
            "在库": sum(1 for row in rows if row.get(STATUS_FIELD) == "在库"),
            "已借出": sum(1 for row in rows if row.get(STATUS_FIELD) == "已借出"),
            "已损毁": sum(1 for row in rows if row.get(STATUS_FIELD) == "已损毁"),
        }

    # ---- 写 ----------------------------------------------------------------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry[STATUS_FIELD] = DEFAULT_STATUS
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"道具 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于道具管理可执行范围"

        current = str(entry.get(STATUS_FIELD) or "")
        if current not in TRANSITIONS:
            return None, f"道具当前状态「{current or '空'}」不在允许的状态序列（{'、'.join(STATUS_ORDER)}）里，请先核对单据"
        if action not in TRANSITIONS[current]:
            return None, self._reject_reason(current, action)

        target = ACTION_RULES[action]
        entry[STATUS_FIELD] = target
        entry["pending"] = target not in TERMINAL_STATUSES
        entry["abnormal"] = action == ABNORMAL_ACTION
        return self._present(entry), f"道具已{action}"

    # ---- 规则辅助（路由/启动检查共用）--------------------------------------
    def allowed_actions(self, status: str | None) -> list[str]:
        """返回某个状态当前可执行的动作；前端按钮与启动校验都以这里为准。"""
        return list(TRANSITIONS.get(str(status or ""), []))

    def _reject_reason(self, current: str, action: str) -> str:
        if action == "借出道具":
            return f"道具当前为「{current}」，只有在库道具可借出，请刷新列表核对库存口径"
        if action == "归还道具":
            if current == "已归还":
                return "道具已归还，无需重复归还"
            if current == "已损毁":
                return "道具已损毁登记，不能再归还"
            return f"道具当前为「{current}」，只有已借出道具可归还，未借出的单据无法归还"
        if action == "登记损毁":
            return f"道具当前为「{current}」（终态），不能再登记损毁"
        return f"当前状态「{current}」不允许执行「{action}」"

    def _present(self, row: dict[str, Any]) -> dict[str, Any]:
        """读时投影：权威状态镜像到展示字段「使用状态」，并下发可执行动作。

        不改底层单据，保证重复读取/重跑结果稳定、不覆盖已有数据。
        """
        view = dict(row)
        status = str(view.get(STATUS_FIELD) or "")
        view[DISPLAY_STATUS_FIELD] = status if status in STATUS_ORDER else ""
        view["actions"] = self.allowed_actions(status)
        return view
