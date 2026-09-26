"""数据准备：确保数据文件存在、模块齐全、道具单据状态合法。

幂等约定：
- 数据文件不存在时，以示例数据整体初始化；
- 已存在时只补充缺失的模块，绝不改动或覆盖已有记录；
- 道具单据逐条校验（必填字段、状态必须在规则允许范围内），
  发现问题逐条说明原因并以非零码退出，修复后可直接重跑。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import resolve_data_file  # noqa: E402
from app.rules import PROP_RULES  # noqa: E402
from app.seed import SEED_ROWS  # noqa: E402

PROP_MODULE = PROP_RULES.module
PROP_REQUIRED_FIELDS = PROP_RULES.required_fields


def fail(reasons: list[str]) -> int:
    for reason in reasons:
        print(f"  ✗ {reason}")
    print("数据准备未通过：修复上述问题后可安全重跑（已有记录不会被覆盖）。")
    return 1


def validate_prop_rows(rows: list[Any]) -> list[str]:
    problems: list[str] = []
    allowed = "、".join(PROP_RULES.status_order)
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"道具第 {index + 1} 条不是对象结构，无法识别")
            continue
        label = row.get("道具编号") or row.get("id") or f"第 {index + 1} 条"
        missing = [f for f in PROP_REQUIRED_FIELDS if not str(row.get(f) or "").strip()]
        if missing:
            problems.append(f"道具 {label} 缺少必填字段：{'、'.join(missing)}")
        status = str(row.get("status", ""))
        if status not in PROP_RULES.status_order:
            problems.append(f"道具 {label} 状态「{status}」不在允许范围（{allowed}）")
    return problems


def main() -> int:
    data_file = resolve_data_file()
    if data_file is None:
        print("· 纯内存模式（APP_DATA_FILE 为空），无需准备数据文件")
        return 0

    if not data_file.exists():
        tables = {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}
        created = True
        added_modules: list[str] = []
    else:
        try:
            payload = json.loads(data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return fail([f"数据文件 {data_file} 读取失败：{exc}"])
        if not isinstance(payload, dict) or not all(isinstance(v, list) for v in payload.values()):
            return fail([f"数据文件 {data_file} 结构不正确：应为 {{模块名: [记录...]}}"])
        tables = payload
        created = False
        added_modules = [name for name in SEED_ROWS if name not in tables]
        for name in added_modules:
            tables[name] = [dict(row) for row in SEED_ROWS[name]]

    problems = validate_prop_rows(tables.get(PROP_MODULE, []))
    if problems:
        return fail(problems)

    if created or added_modules:
        data_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = data_file.with_name(data_file.name + ".tmp")
        tmp.write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(data_file)

    total = sum(len(rows) for rows in tables.values())
    if created:
        print(f"  ✓ 数据文件不存在，已按示例数据初始化：{data_file}（{len(tables)} 个模块 / {total} 条）")
    else:
        print(f"  ✓ 已有数据文件：{data_file}（{len(tables)} 个模块 / {total} 条），已有记录未改动")
    for name in added_modules:
        print(f"  ✓ 补充缺失模块 {name}：{len(tables[name])} 条示例数据")
    print(f"  ✓ 道具单据校验通过：{len(tables.get(PROP_MODULE, []))} 条，状态均在允许范围")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
