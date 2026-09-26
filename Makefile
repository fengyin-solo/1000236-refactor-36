.PHONY: install backend frontend check

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

# 启动前依赖检查：环境校验 → 数据准备（幂等补数，不覆盖已有单据）→ 启动检查。
# 任一步失败会打印原因并以非 0 退出；修复后可安全重跑。
check:
	cd backend && .venv/bin/python -m app.bootstrap

backend:
	cd backend && ./run.sh

frontend:
	cd frontend && npm run dev
