"""业务规则的唯一来源：状态序列、动作流转与库存口径。

道具的借出、归还、损毁规则以前在服务、路由、前端页面里各写一份，
口径漂移后会出现"页面显示可借出、实际无法归还"这类问题。现在统一
收进 PROP_RULES：后端校验、接口元数据、统计口径和页面展示都从这一份
推导，改规则只动这里。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionRule:
    """一个动作：落到哪个状态、允许从哪些状态发起。"""

    target: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class ModuleRules:
    """一个模块的完整流转规则。"""

    module: str
    required_fields: tuple[str, ...]
    status_order: tuple[str, ...]
    actions: dict[str, ActionRule]
    negative_actions: tuple[str, ...]
    pending_statuses: tuple[str, ...]
    status_labels: dict[str, str]

    def allowed_actions(self, status: str) -> list[str]:
        """当前状态下可执行的动作，页面按它渲染按钮，避免全量摆出再被拦。"""
        return [name for name, rule in self.actions.items() if status in rule.sources]

    def derive_flags(self, status: str) -> tuple[bool, bool]:
        """由状态推导 pending / abnormal，保证列表、概览、详情的口径一致。"""
        pending = status in self.pending_statuses
        abnormal = status in {self.actions[name].target for name in self.negative_actions}
        return pending, abnormal

    def check_action(self, status: str, action: str) -> str | None:
        """返回 None 表示可执行；否则返回可读的拦截原因。"""
        rule = self.actions.get(action)
        if rule is None:
            return f"动作「{action}」不在可执行范围（可选：{'、'.join(self.actions)}）"
        if status not in rule.sources:
            return (
                f"当前状态为「{status}」，不能执行「{action}」"
                f"（仅「{'、'.join(rule.sources)}」状态下可执行）"
            )
        return None

    def inventory_stats(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """库存口径：按状态计数，状态未知的数据单列，不与在库混淆。"""
        counts = {status: 0 for status in self.status_order}
        unknown = 0
        for row in rows:
            status = str(row.get("status", ""))
            if status in counts:
                counts[status] += 1
            else:
                unknown += 1
        stats = [
            {"label": self.status_labels.get(status, status), "value": counts[status]}
            for status in self.status_order
        ]
        if unknown:
            stats.append({"label": "状态未知（需检查数据）", "value": unknown})
        return stats


PROP_RULES = ModuleRules(
    module="prop",
    required_fields=("道具编号", "道具名称", "道具类别"),
    status_order=("在库", "已借出", "已归还", "已损毁"),
    actions={
        "借出道具": ActionRule(target="已借出", sources=("在库",)),
        "归还道具": ActionRule(target="已归还", sources=("已借出",)),
        "登记损毁": ActionRule(target="已损毁", sources=("在库", "已借出")),
    },
    negative_actions=("登记损毁",),
    pending_statuses=("在库", "已借出"),
    status_labels={
        "在库": "在库（可借出）",
        "已借出": "已借出（待归还）",
        "已归还": "已归还",
        "已损毁": "已损毁（异常）",
    },
)
