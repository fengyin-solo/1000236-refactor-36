#!/usr/bin/env bash
# 启动链路：数据准备 → 环境校验 → 启动服务 → 启动检查。
# 任一步骤失败都会打印原因并以非零码退出，修复后可直接重跑。
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

echo "==> [1/3] 数据准备"
"$PY" scripts/prepare_data.py

echo "==> [2/3] 环境校验"
"$PY" scripts/check_env.py

echo "==> [3/3] 启动服务并做启动检查"
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

if ! "$PY" scripts/smoke_check.py; then
  echo "启动检查未通过，服务已停止；修复问题后可安全重跑。" >&2
  exit 1
fi

echo "==> 全部检查通过，服务运行中（pid $SERVER_PID，Ctrl+C 停止）"
wait "$SERVER_PID"
