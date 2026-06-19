# Changelog

## [0.2.0] - 2026-06-19

### Added
- 完整测试体系（pytest、pytest-asyncio、pytest-cov）
- GitHub Actions CI（lint、test、coverage）
- Alembic 数据库迁移
- Loguru 结构化日志
- API Key 与用户笔记加密存储
- SQLite 安全删除与用户数据清理

### Fixed
- SSE 流式端点兼容性
- Ruff lint 错误（F401、F841、E402、E712）

## [0.1.0] - 2026-06-01

### Added
- 初始版本：文献检索、PDF 阅读、知识图谱、Idea 生成、LaTeX 写作、选刊审稿
- ARS 集成（Socratic Mentor、Sprint Contract、Writing Quality Check 等）
- 设置页与 i18n 中英文切换
- Tauri Sidecar 与 PyInstaller 打包
