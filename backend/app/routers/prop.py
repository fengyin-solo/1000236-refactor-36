"""道具管理接口：维护道具，覆盖借出道具、归还道具、登记损毁等动作。

状态与动作常量一律取自 service，路由层不自行维护第二份口径。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.prop import (
    ACTION_RULES,
    STATUS_ORDER,
    PropService,
)

router = APIRouter(prefix="/api/prop", tags=["道具管理"])

service = PropService()

LIST_FIELDS = ["道具编号", "道具名称", "道具类别", "所属场次", "保管人员", "采购单价", "使用状态", "归还日期"]


# ---- 规则元数据与库存统计（静态路径必须声明在 /{entry_id} 之前，否则会被动态路由吞掉）----
@router.get("/meta")
def meta() -> dict[str, Any]:
    """下发统一口径：状态序列、动作清单、每个状态当前可执行的动作。"""
    return {
        "statuses": STATUS_ORDER,
        "actions": list(ACTION_RULES),
        "allowed_actions": {status: service.allowed_actions(status) for status in STATUS_ORDER},
    }


@router.get("/stats")
def stats() -> dict[str, Any]:
    """库存卡片：在库可借 / 已借出待归还 / 已损毁，口径与列表完全一致。"""
    counts = service.stats()
    return {
        "cards": [
            {"label": "在库道具（可借出）", "value": counts["在库"]},
            {"label": "已借出道具（待归还）", "value": counts["已借出"]},
            {"label": "已损毁道具", "value": counts["已损毁"]},
        ],
        **counts,
    }


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出道具管理清单：返回全量数据，口径与列表接口一致。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "prop", "total": total, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按道具编号检索"),
    status: str | None = Query(default=None, description="在库、已借出、已归还、已损毁"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按道具编号与状态过滤道具管理列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if status is not None and status not in STATUS_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"状态「{status}」不合法，可选：{'、'.join(STATUS_ORDER)}",
        )
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条道具，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="道具已登记", entry=entry)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条道具明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"道具 {entry_id} 不存在或已归档")
    return entry


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条道具执行借出道具、归还道具、登记损毁；不允许的流转会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
