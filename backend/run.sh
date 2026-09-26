#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

# 启动检查：先跑环境校验 → 数据准备 → 启动检查，任一步失败（退出码非 0）就带原因中止，
# 不启动 uvicorn。该步骤幂等、不覆盖已有道具单据，修复后可直接重跑本脚本。
.venv/bin/python -m app.bootstrap

exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
