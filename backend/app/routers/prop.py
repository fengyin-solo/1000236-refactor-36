"""道具管理接口：维护道具，覆盖借出道具、归还道具、登记损毁等动作。

状态序列与动作流转规则统一来自 app.rules.PROP_RULES，路由层不做业务判断。
注意：/meta、/stats、/export 必须声明在 /{entry_id} 之前，否则会被详情路由截获。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.rules import PROP_RULES
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.prop import PropService

router = APIRouter(prefix="/api/prop", tags=["道具管理"])

service = PropService()

LIST_FIELDS = ["道具编号", "道具名称", "道具类别", "所属场次", "保管人员", "采购单价", "使用状态", "归还日期"]


@router.get("/meta")
def get_meta() -> dict[str, Any]:
    """规则元数据：状态序列、各动作的来源/目标状态，页面据此渲染，不再硬编码。"""
    return {
        "module": "prop",
        "statuses": list(PROP_RULES.status_order),
        "actions": [
            {"name": name, "target": rule.target, "sources": list(rule.sources)}
            for name, rule in PROP_RULES.actions.items()
        ],
        "status_labels": dict(PROP_RULES.status_labels),
    }


@router.get("/stats")
def get_stats() -> dict[str, Any]:
    """库存统计：在库（可借出）、已借出（待归还）等口径与列表、动作判定一致。"""
    return {"module": "prop", "stats": service.stats()}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出道具管理清单：返回当前过滤条件下的全量数据。"""
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
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条道具明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"道具 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条道具，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="道具已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条道具执行借出道具、归还道具、登记损毁；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
