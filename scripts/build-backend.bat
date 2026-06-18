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
REM PyInstaller --onefile 模式输出为 dist\research-backend.exe
set SIDECAR_NAME=research-backend-x86_64-pc-windows-msvc.exe

if not exist "%TAURI_BIN_DIR%" mkdir "%TAURI_BIN_DIR%"

REM 直接拷贝 --onefile 生成的单 exe，不嵌套目录
copy /Y "%BACKEND_DIR%\dist\research-backend.exe" "%TAURI_BIN_DIR%\%SIDECAR_NAME%"

echo [OK] 已复制: %TAURI_BIN_DIR%\%SIDECAR_NAME%

REM ---- Step 5: 验证 ---------------------------------------------------------
echo.
echo [INFO] 验证 sidecar 文件...
if exist "%TAURI_BIN_DIR%\%SIDECAR_NAME%" (
    echo [OK] Sidecar 就绪: %TAURI_BIN_DIR%\%SIDECAR_NAME%
) else (
    echo [FAIL] Sidecar 未找到！
    dir "%TAURI_BIN_DIR%\" /B
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
