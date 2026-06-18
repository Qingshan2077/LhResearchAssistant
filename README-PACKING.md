# Research Assistant — 打包指南

将前端 + 后端打包成单个 Windows 安装包，用户安装后双击即可使用。

---

## 架构概览

```
┌──────────────────────────────────────────────┐
│              Tauri 安装包 (.msi)               │
│                                                │
│  ┌────────────────────┐  ┌──────────────────┐ │
│  │  前端 (React)       │  │  后端 (Python)    │ │
│  │  Tauri 桌面窗口     │  │  Sidecar 进程     │ │
│  │  localhost:1420     │  │  localhost:8787   │ │
│  └────────┬───────────┘  └────────┬─────────┘ │
│           └────── HTTP ────────────┘           │
│          (前端自动调后端 API)                   │
└──────────────────────────────────────────────┘
```

**启动流程**：用户双击应用 → Tauri 自动拉起 Python 后端进程 → 后端就绪后前端加载 → 用户正常使用

**关闭时**：用户关窗口 → Tauri 自动杀掉后端进程

---

## 前提条件（Windows 开发机）

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.11 | 运行后端 |
| Node.js | ≥ 20 | 构建前端 |
| Rust | latest stable | 编译 Tauri |
| uv | latest | Python 包管理 |
| PyInstaller | latest | 将 Python 打包为 .exe |
| WiX Toolset | v3 | 生成 .msi 安装包（Tauri 需要） |

安装 WiX Toolset（仅第一次需要）：

```bash
# 下载安装 https://github.com/wixtoolset/wix3/releases
# 或者用 winget:
winget install --id WiXToolset.WiXToolset
```

---

## 打包步骤

### Step 1: 打包 Python 后端为 .exe

**在你的 Windows 开发机上运行：**

```bash
cd backend
```

确保所有依赖已安装：

```bash
# 方式 A: 用 uv
uv sync

# 方式 B: 用 pip
pip install -e .
pip install pyinstaller
```

运行打包：

```bash
# 方式 A: 用 build-backend.bat（推荐）
..\scripts\build-backend.bat

# 方式 B: 手动
pyinstaller pack.spec --clean --noconfirm
```

成功后会生成 `backend/dist/research-backend/` 目录，内含 `research-backend.exe` + 依赖的 .pyd 文件。

### Step 2: 拷贝到 Tauri sidecar 目录

上一步的脚本会自动执行以下操作：

```
backend/dist/research-backend/
  └── research-backend.exe
  └── *.pyd
  └── ...
      ↓ 拷贝到
frontend/src-tauri/binaries/research-backend/
  └── research-backend-x86_64-pc-windows-msvc.exe  ← 改名
  └── *.pyd  ← 同目录
```

如果手动操作，请确保文件名符合 `{name}-{target-triple}.exe` 格式，
Tauri v2 的 sidecar 命名规则为 `research-backend-x86_64-pc-windows-msvc.exe`。

### Step 3: 构建 Tauri 安装包

```bash
cd frontend
cargo tauri build
```

首次运行会下载 Rust 依赖并编译。成功后生成：

```
frontend/src-tauri/target/release/bundle/msi/Research Assistant_0.1.0_x64.msi
frontend/src-tauri/target/release/bundle/nsis/Research Assistant_0.1.0_x64-setup.exe
```

用户拿到 `.msi` 或 `.exe` 安装后，双击桌面图标即可使用。

---

## 快速验证

打包前先在开发机上验证功能正常：

```bash
# 终端 1: 启动后端
cd backend
uv run uvicorn app.main:app --port 8787

# 终端 2: 启动 Tauri（含前端 dev server）
cd frontend
cargo tauri dev
```

如果一切正常，窗口会弹出，搜索功能也能正常工作，再进行正式打包。

---

## 常见问题

### Q: PyInstaller 打包后运行报 Missing module

在 `backend/pack.spec` 的 `hiddenimports` 列表中补充缺失的模块名，然后重新运行 `pyinstaller pack.spec --clean --noconfirm`。

常见缺失模块：
```python
'pydantic._internal',
'pydantic._migration',
'pydantic.v1',
'chromadb.api.fastapi',
'sqlalchemy.ext.asyncio',
```

### Q: 打包出来的 exe 很大（通常 200-400MB）

因为 ChromaDB 和 PyMuPDF 内嵌了 native 扩展和预编译模型。这是正常的。
如果想减小体积，可以在 `excludes` 中排除用不到的包（但不要排除 ChromaDB 的组件）。

### Q: 不能直接在我（Linux）服务器上打包

对，PyInstaller 打包是平台特定的。你需要在 **Windows 开发机** 上跑 `build-backend.bat`。
我在 Linux 上帮你写好所有配置文件和代码，你 pull 到 Windows 上执行。

### Q: cargo tauri build 报 sidecar 找不到

检查：
1. `frontend/src-tauri/binaries/research-backend/research-backend-x86_64-pc-windows-msvc.exe` 是否存在
2. `tauri.conf.json` 中 `bundle.externalBin` 配置是否匹配

### Q: 用户安装后打开报错 "Backend health check timed out"

可能原因：
- 端口 8787 被其他程序占用
- 杀毒软件拦截了后端 exe
- 侧载的 exe 路径包含中文/空格

解决办法：在 `main.rs` 的 `wait_for_backend()` 中增大超时或调整端口。

---

## 文件清单（本次修改）

| 文件 | 说明 |
|------|------|
| `backend/pack.spec` | PyInstaller 打包配置文件 |
| `scripts/build-backend.bat` | Windows 一键打包脚本 |
| `frontend/src/lib/api.ts` | 修改：生产环境用绝对 URL |
| `frontend/src-tauri/tauri.conf.json` | 修改：添加 `externalBin` |
| `frontend/src-tauri/capabilities/default.json` | 新增：sidecar 权限 |
| `frontend/src-tauri/src/main.rs` | 重写：自动启动/停止后端 |
