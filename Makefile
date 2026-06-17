.PHONY: install dev test lint clean

# ── 后端 ─────────────────────────────────────────

install:  ## 安装后端依赖（uv）
	cd backend && uv sync

install-all:  ## 安装全部依赖（含 marker-pdf + semantic-scholar）
	cd backend && uv sync --all-extras

dev:  ## 启动后端开发服务器（热重载）
	cd backend && uv run uvicorn app.main:app --port 8787 --reload

test:  ## 运行测试
	cd backend && uv run pytest

lint:  ## 代码检查
	cd backend && uv run ruff check app/

fmt:  ## 自动格式化
	cd backend && uv run ruff format app/

# ── 前端 ─────────────────────────────────────────

frontend-install:  ## 安装前端依赖
	cd frontend && npm install

frontend-dev:  ## 启动前端开发服务器
	cd frontend && npm run dev

tauri-dev:  ## 启动 Tauri 桌面开发模式
	cd frontend && cargo tauri dev

tauri-build:  ## 构建桌面安装包
	cd frontend && cargo tauri build

# ── 工具 ─────────────────────────────────────────

clean:  ## 清理缓存
	rm -rf backend/data/
	rm -rf backend/.venv/
	rm -rf frontend/node_modules/
	rm -rf frontend/src-tauri/target/

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
