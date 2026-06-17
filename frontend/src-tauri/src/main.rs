// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

struct PythonBackend(Mutex<Option<Child>>);

#[tauri::command]
fn start_backend(state: tauri::State<PythonBackend>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;

    // 如果已启动，跳过
    if guard.is_some() {
        return Ok(());
    }

    // 从 backend/ 目录启动 uvicorn
    let child = Command::new("uvicorn")
        .args(["app.main:app", "--port", "8787", "--host", "localhost"])
        .current_dir("../backend")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Failed to start backend: {}", e))?;

    *guard = Some(child);
    Ok(())
}

#[tauri::command]
fn stop_backend(state: tauri::State<PythonBackend>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = guard.take() {
        child.kill().map_err(|e| format!("Failed to stop backend: {}", e))?;
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .manage(PythonBackend(Mutex::new(None)))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // 启动时拉起 Python 后端
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                // 稍等一会儿等窗口加载完
                std::thread::sleep(std::time::Duration::from_secs(1));
                let _ = handle.emit("backend-starting", ());
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![start_backend, stop_backend])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
