@echo off
REM ============================================================================
REM  Research Assistant — 后端打包脚本 (Windows)
REM  在 Windows 开发机上运行，打包 Python 后端为 standalone EXE
REM  然后拷贝到 Tauri sidecar 目录，供 cargo tauri build 使用
REM ============================================================================
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
set BACKEND_DIR=%PROJECT_DIR%\backend
set TAURI_BIN_DIR=%PROJECT_DIR%\frontend\src-tauri\binaries

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║   Research Assistant — 后端打包                          ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

REM ---- Step 1: 检查环境 ---------------------------------------------------
where pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [FAIL] pyinstaller 未安装。正在安装...
    pip install pyinstaller
    if !ERRORLEVEL! neq 0 (
        echo [FAIL] 安装 pyinstaller 失败，请手动运行: pip install pyinstaller
        pause
        exit /b 1
    )
)

echo [OK] pyinstaller 已就绪

REM ---- Step 2: 确保后端依赖已安装 -------------------------------------------
cd /d "%BACKEND_DIR%"

echo [INFO] 检查后端依赖...
uv sync 2>nul
if %ERRORLEVEL% neq 0 (
    echo [WARN] uv sync 失败，尝试 pip install...
    pip install -e .
)

echo [OK] 后端依赖已就绪

REM ---- Step 3: 运行 PyInstaller --------------------------------------------
echo.
echo [INFO] 开始打包后端 (PyInstaller)...
echo [INFO] 这将需要 1-5 分钟...

pyinstaller pack.spec --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo [FAIL] PyInstaller 打包失败，请检查错误信息
    pause
    exit /b 1
)

echo [OK] PyInstaller 打包成功
echo [INFO] 输出目录: %BACKEND_DIR%\dist\research-backend\

REM ---- Step 4: 拷贝到 Tauri sidecar 目录 ------------------------------------
echo.
echo [INFO] 拷贝到 Tauri sidecar 目录...

REM Tauri v2 sidecar 命名规则: {binary_name}-{target_triple}.exe
REM Windows x64 的目标三元组: x86_64-pc-windows-msvc
set SIDECAR_NAME=research-backend-x86_64-pc-windows-msvc.exe

if not exist "%TAURI_BIN_DIR%" mkdir "%TAURI_BIN_DIR%"

REM 使用 --onedir 模式，需要拷贝整个目录
REM 实际上 Tauri sidecar 只需要主 .exe，但 --onedir 的 exe 依赖同目录的 .pyd
REM 所以我们要拷贝整个目录
if exist "%TAURI_BIN_DIR%\%SIDECAR_NAME%" del /q "%TAURI_BIN_DIR%\%SIDECAR_NAME%"
xcopy /E /I /Y "%BACKEND_DIR%\dist\research-backend" "%TAURI_BIN_DIR%\research-backend\"

REM 主 exe 改名以匹配 sidecar 命名规则
if exist "%TAURI_BIN_DIR%\research-backend\research-backend.exe" (
    rename "%TAURI_BIN_DIR%\research-backend\research-backend.exe" "%SIDECAR_NAME%"
)

echo [OK] 已复制到 %TAURI_BIN_DIR%\

REM ---- Step 5: 验证 ---------------------------------------------------------
echo.
echo [INFO] 验证 sidecar 文件...
if exist "%TAURI_BIN_DIR%\research-backend\%SIDECAR_NAME%" (
    echo [OK] Sidecar 就绪: %TAURI_BIN_DIR%\research-backend\%SIDECAR_NAME%
) else (
    echo [WARN] 未找到 %SIDECAR_NAME%，检查目录内容...
    dir "%TAURI_BIN_DIR%\research-backend\" /B
    echo.
    echo 你可能需要手动将 .exe 重命名为 %SIDECAR_NAME%
)

REM ---- Step 6: 快速测试（可选）----------------------------------------------
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║   打包完成！                                              ║
echo ║                                                          ║
echo ║   接下来运行:                                            ║
echo ║     cd frontend & cargo tauri build                      ║
echo ║                                                          ║
echo ║   这会生成一个 .msi 或 .exe 安装包                         ║
echo ║   用户安装后双击即可使用                                   ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

pause
