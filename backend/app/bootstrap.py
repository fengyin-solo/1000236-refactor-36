"""启动管线：把数据准备、环境校验、启动检查串成一条有序、可重跑的链路。

设计目标（对应“任一依赖步骤失败要说明原因、失败可安全重跑、不覆盖已有数据”）：

1. ``validate_environment`` 环境校验：集中检查环境变量与配置，一次列出全部问题；
2. ``prepare_data`` 数据准备：幂等灌入示例数据，只补缺失 id，已有道具单据与列表结果不覆盖；
   灌入前先校验种子本身的库存口径，坏种子直接报错、不写库；
3. ``startup_checks`` 启动检查：路由是否注册、道具规则口径是否一致、库存数据是否自洽。

每一步返回结构化结果；任意一步失败，``run_bootstrap`` 立即停止并汇总原因，
调用方（FastAPI lifespan / ``python -m app.bootstrap`` / run.sh）据此快速失败。
整链路只读 + 幂等补数，因此修复后可以安全重跑。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.config import settings
from app.routers import ROUTERS
from app.seed import SEED_ROWS
from app.services.prop import (
    ACTION_RULES,
    MODULE as PROP_MODULE,
    STATUS_FIELD,
    STATUS_ORDER,
    TERMINAL_STATUSES,
    TRANSITIONS,
    PropService,
)
from app.store import store


class BootstrapError(RuntimeError):
    """启动管线失败：携带是哪一步、因为什么失败。"""

    def __init__(self, step: str, reasons: list[str]) -> None:
        self.step = step
        self.reasons = reasons
        super().__init__(f"[{step}] " + "；".join(reasons))


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    reasons: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


# ---- 步骤一：环境校验 ------------------------------------------------------
def validate_environment() -> StepResult:
    reasons = list(settings.parse_errors)

    if settings.env not in {"local", "dev", "test", "staging", "prod"}:
        reasons.append(
            f"APP_ENV={settings.env!r} 不是支持的运行环境（local/dev/test/staging/prod）"
        )
    if not (1 <= settings.port <= 65535):
        reasons.append(f"APP_PORT={settings.port} 超出合法端口范围 1-65535")
    if settings.page_size_default <= 0:
        reasons.append(f"APP_PAGE_SIZE_DEFAULT={settings.page_size_default} 必须为正整数")
    if settings.page_size_max < settings.page_size_default:
        reasons.append(
            f"APP_PAGE_SIZE_MAX={settings.page_size_max} 不能小于默认分页 "
            f"APP_PAGE_SIZE_DEFAULT={settings.page_size_default}"
        )
    for origin in settings.allowed_origins:
        if not (origin.startswith("http://") or origin.startswith("https://")):
            reasons.append(f"跨域来源 {origin!r} 必须是 http:// 或 https:// 开头的完整地址")

    if reasons:
        return StepResult("environment", False, "环境校验未通过", reasons)
    return StepResult(
        "environment",
        True,
        f"环境校验通过（env={settings.env}, port={settings.port}）",
    )


# ---- 步骤二：数据准备（幂等、不覆盖）--------------------------------------
def _validate_prop_seed() -> list[str]:
    """灌入前先校验道具种子的库存口径，避免把坏数据写进内存库。"""
    problems: list[str] = []
    for seed in SEED_ROWS.get(PROP_MODULE, []):
        sid = seed.get("id")
        status = seed.get(STATUS_FIELD)
        if status not in STATUS_ORDER:
            problems.append(f"道具种子 id={sid} 的 status={status!r} 不在 {'、'.join(STATUS_ORDER)}")
            continue
        if seed.get("使用状态") not in (None, "", status):
            problems.append(
                f"道具种子 id={sid} 的「使用状态」={seed.get('使用状态')!r} 与权威 status={status!r} 不一致"
            )
        expect_pending = status not in TERMINAL_STATUSES
        if bool(seed.get("pending")) != expect_pending:
            problems.append(f"道具种子 id={sid} 的 pending 与状态 {status} 口径不一致")
        expect_abnormal = status == "已损毁"
        if bool(seed.get("abnormal")) != expect_abnormal:
            problems.append(f"道具种子 id={sid} 的 abnormal 与状态 {status} 口径不一致（仅已损毁为异常）")
    return problems


def prepare_data() -> StepResult:
    reasons = _validate_prop_seed()
    if reasons:
        return StepResult("data_preparation", False, "道具示例数据库存口径不通过，已跳过写库", reasons)

    # 只补缺失 id；已有单据保持不动，因此重跑不会覆盖任何道具单据或列表结果。
    report = store.seed_if_missing()
    inserted = sum(item["inserted"] for item in report.values())
    skipped = sum(item["skipped"] for item in report.values())
    return StepResult(
        "data_preparation",
        True,
        f"示例数据就绪（新增 {inserted} 条，保留已有 {skipped} 条）",
        data={"modules": report},
    )


# ---- 步骤三：启动检查 ------------------------------------------------------
def _check_prop_rules() -> list[str]:
    problems: list[str] = []

    # 规则自洽：每个动作都有目标状态，且目标状态在状态序列内；
    # 所有出现过的动作都必须能映射到合法目标状态，防止“按钮可点却流转不到任何状态”。
    referenced = {action for actions in TRANSITIONS.values() for action in actions}
    for action, target in ACTION_RULES.items():
        if target not in STATUS_ORDER:
            problems.append(f"动作「{action}」的目标状态 {target!r} 不在状态序列里")
    for status in STATUS_ORDER:
        for action in TRANSITIONS.get(status, []):
            if action not in ACTION_RULES or ACTION_RULES[action] not in STATUS_ORDER:
                problems.append(
                    f"状态 {status} 允许的动作「{action}」缺少落在状态序列内的目标状态映射"
                )
    for status in TRANSITIONS:
        if status not in STATUS_ORDER:
            problems.append(f"流转表出现未知状态 {status!r}")

    # 端到端口径：在库可借出、已借出可归还，且不能“显示可借却无法归还”的错配。
    cases = [
        ("在库", "借出道具", True),
        ("在库", "归还道具", False),
        ("已借出", "归还道具", True),
        ("已借出", "借出道具", False),
        ("已归还", "归还道具", False),
        ("已损毁", "登记损毁", False),
    ]
    service = PropService()
    for status, action, should_pass in cases:
        allowed = action in service.allowed_actions(status)
        if allowed != should_pass:
            problems.append(
                f"道具流转口径异常：状态「{status}」执行「{action}」"
                f"期望{'放行' if should_pass else '拦截'}，实际{'放行' if allowed else '拦截'}"
            )
    return problems


def _check_prop_data() -> list[str]:
    problems: list[str] = []
    for row in store.rows(PROP_MODULE):
        rid = row.get("id")
        status = row.get(STATUS_FIELD)
        if status not in STATUS_ORDER:
            problems.append(f"道具单据 id={rid} 的 status={status!r} 非法，无法判断库存")
    return problems


def _check_routes() -> list[str]:
    expected = {
        "/api/prop",
        "/api/prop/meta",
        "/api/prop/stats",
        "/api/prop/export",
        "/api/prop/{entry_id}",
        "/api/prop/{entry_id}/actions",
        "/api/health",
        "/api/overview",
    }
    registered = {
        getattr(route, "path", None)
        for module in ROUTERS
        for route in getattr(module.router, "routes", [])
    }
    registered.update({"/api/health", "/api/overview"})
    return [f"关键路由 {path} 未注册" for path in sorted(expected) if path not in registered]


def startup_checks() -> StepResult:
    reasons: list[str] = []
    reasons.extend(_check_routes())
    reasons.extend(_check_prop_rules())
    reasons.extend(_check_prop_data())
    if reasons:
        return StepResult("startup_checks", False, "启动检查未通过", reasons)
    prop_total = len(store.rows(PROP_MODULE))
    return StepResult(
        "startup_checks",
        True,
        f"启动检查通过（路由、道具流转规则与 {prop_total} 条道具单据口径自洽）",
    )


# ---- 编排 -----------------------------------------------------------------
STEPS: list[tuple[str, Callable[[], StepResult]]] = [
    ("environment", validate_environment),
    ("data_preparation", prepare_data),
    ("startup_checks", startup_checks),
]


@dataclass
class BootReport:
    ok: bool
    steps: list[StepResult]
    failed_step: str | None = None

    def describe(self) -> str:
        lines = ["启动管线执行结果："]
        for index, step in enumerate(self.steps, start=1):
            mark = "✓" if step.ok else "✗"
            lines.append(f"  {index}. {mark} {step.name}: {step.detail}")
            for reason in step.reasons:
                lines.append(f"      - {reason}")
        if not self.ok:
            lines.append("")
            lines.append(
                f"启动在「{self.failed_step}」中止：请按上述原因修复后重新启动，"
                "数据准备为幂等补数，重跑不会覆盖已有道具单据。"
            )
        return "\n".join(lines)


def run_bootstrap() -> BootReport:
    """按顺序执行三步；任一步失败立即停止，返回完整报告。"""
    results: list[StepResult] = []
    for name, func in STEPS:
        result = func()
        results.append(result)
        if not result.ok:
            return BootReport(ok=False, steps=results, failed_step=name)
    return BootReport(ok=True, steps=results)


if __name__ == "__main__":
    import sys

    report = run_bootstrap()
    print(report.describe())
    sys.exit(0 if report.ok else 1)
