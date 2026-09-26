"""启动检查：服务起来后验证健康、规则元数据与库存口径一致。

全程只读（只发 GET），不改动任何单据，可反复重跑；
任一检查失败都会说明原因并以非零码退出。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.rules import PROP_RULES  # noqa: E402

BASE = f"http://{settings.host}:{settings.port}"
TIMEOUT = 5
WAIT_SECONDS = 30

failures: list[str] = []


def get(path: str) -> tuple[int, Any]:
    request = urllib.request.Request(f"{BASE}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def check(ok: bool, label: str, reason: str = "") -> None:
    print(f"  {'✓' if ok else '✗'} {label if ok else f'{label}：{reason}'}")
    if not ok:
        failures.append(label)


def main() -> int:
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        try:
            status, health = get("/api/health")
            if status == 200 and health.get("ok"):
                print(f"  ✓ 健康检查通过：{BASE}/api/health")
                break
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            pass
        if time.monotonic() >= deadline:
            print(f"  ✗ 健康检查：{WAIT_SECONDS}s 内 {BASE}/api/health 未就绪，请查看服务日志")
            return 1
        time.sleep(0.5)

    try:
        _, meta = get("/api/prop/meta")
        names = {item.get("name") for item in meta.get("actions", [])}
        expected = set(PROP_RULES.actions)
        check(
            names == expected and meta.get("statuses") == list(PROP_RULES.status_order),
            "规则元数据 /api/prop/meta 与统一规则一致",
            f"接口返回动作 {sorted(names)}、状态 {meta.get('statuses')}，"
            f"应为动作 {sorted(expected)}、状态 {list(PROP_RULES.status_order)}",
        )
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        check(False, "规则元数据 /api/prop/meta", f"请求失败：{exc}")

    try:
        _, stats_payload = get("/api/prop/stats")
        _, list_payload = get("/api/prop?page=1&size=1")
        stats_total = sum(int(item.get("value", 0)) for item in stats_payload.get("stats", []))
        list_total = int(list_payload.get("total", -1))
        check(
            stats_total == list_total,
            f"库存口径一致：统计合计 {stats_total} = 列表总数 {list_total}",
            f"统计合计 {stats_total} ≠ 列表总数 {list_total}，存在状态未知或口径漂移的数据",
        )
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        check(False, "库存口径一致性", f"请求失败：{exc}")

    try:
        status, export = get("/api/prop/export")
        check(
            status == 200 and isinstance(export.get("items"), list),
            "导出接口 /api/prop/export 可用",
            f"返回状态 {status}，导出应直接返回清单而不是被详情路由截获",
        )
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        check(False, "导出接口 /api/prop/export", f"请求失败：{exc}")

    if failures:
        print(f"启动检查未通过：{'、'.join(failures)}；修复后可安全重跑。")
        return 1
    print("启动检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
