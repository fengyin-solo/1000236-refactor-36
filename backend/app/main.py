"""影视剧组拍摄制作管理平台 后端服务入口。

启动：uvicorn app.main:app --host 127.0.0.1 --port 8000
健康检查：GET /api/health

启动前会先跑启动管线（环境校验 → 数据准备 → 启动检查），任一步失败都会带上原因
快速中止，避免“服务起来了但口径不对/数据没就绪”。
"""
from __future__ import annotations

import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap import BootstrapError, run_bootstrap
from app.config import settings
from app.routers import ROUTERS
from app.store import store


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    report = run_bootstrap()
    if not report.ok:
        # 让 uvicorn 带着可读原因退出，而不是继续提供口径不一致的服务。
        failed = next(step for step in report.steps if not step.ok)
        raise BootstrapError(report.failed_step or failed.name, failed.reasons)
    app.state.boot_report = report
    yield


app = FastAPI(title="影视剧组拍摄制作管理平台", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in ROUTERS:
    app.include_router(module.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    """健康检查：确认服务监听、各依赖步骤已通过、示例数据已经就绪。"""
    report = getattr(app.state, "boot_report", None)
    steps = (
        [{"name": step.name, "ok": step.ok, "detail": step.detail} for step in report.steps]
        if report is not None
        else []
    )
    return {
        "ok": True,
        "app": settings.app_name,
        "env": settings.env,
        "modules": len(store.module_names()),
        "steps": steps,
    }


@app.get("/api/overview")
def overview() -> dict[str, object]:
    """运营概览：把各业务模块的待处理量汇总成看板卡片。"""
    return store.overview()
