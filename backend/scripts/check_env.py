"""环境校验：启动前确认运行环境满足依赖，失败逐条说明原因。

只读检查，不改任何文件；全部通过才退出 0，否则非零码退出，
修复后可直接重跑。
"""
from __future__ import annotations

import importlib
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR, resolve_data_file, settings  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 10)

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, reason: str = "") -> None:
    results.append((ok, label if ok else f"{label}：{reason}"))


def main() -> int:
    version = sys.version_info
    check(
        version >= MIN_PYTHON,
        f"Python 版本 {version.major}.{version.minor}.{version.micro}",
        f"需要 Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}，当前 {version.major}.{version.minor}",
    )

    venv = BACKEND_DIR / ".venv"
    check(venv.is_dir(), f"虚拟环境 {venv}", "不存在，请先运行 make install 或 python3 -m venv .venv")

    for package in ("fastapi", "uvicorn", "pydantic"):
        try:
            module = importlib.import_module(package)
            check(True, f"依赖 {package} {getattr(module, '__version__', '')}".rstrip())
        except ImportError as exc:
            check(False, f"依赖 {package}", f"导入失败（{exc}），请运行 .venv/bin/pip install -r requirements.txt")

    data_file = resolve_data_file()
    if data_file is None:
        check(True, "数据文件：纯内存模式（APP_DATA_FILE 为空）")
    else:
        data_dir = data_file.parent
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            probe = data_dir / ".write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            check(True, f"数据目录可写：{data_dir}")
        except OSError as exc:
            check(False, f"数据目录 {data_dir}", f"不可写（{exc}），请检查目录权限")

    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((settings.host, settings.port))
            check(True, f"端口可用：{settings.host}:{settings.port}")
        except OSError as exc:
            check(False, f"端口 {settings.host}:{settings.port}", f"被占用或不可绑定（{exc}），请释放端口或用 APP_PORT 更换")

    frontend_env = BASE_DIR.parent / "frontend" / ".env.development"
    check(frontend_env.is_file(), f"前端环境文件 {frontend_env}", "不存在，前端本地开发可能拿不到接口地址")

    for ok, line in results:
        print(f"  {'✓' if ok else '✗'} {line}")
    failed = sum(1 for ok, _ in results if not ok)
    if failed:
        print(f"环境校验未通过：{failed} 项待处理，修复后可安全重跑。")
        return 1
    print("环境校验通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
