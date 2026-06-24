// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use tauri::Emitter;
use tauri::Manager;
use tauri::WindowEvent;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Unified type: sidecar (production) or uvicorn (dev).
enum BackendProcess {
    Sidecar(CommandChild),
    Uvicorn(Child),
}

struct BackendChild(Mutex<Option<BackendProcess>>);

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

#[cfg(windows)]
fn kill_process_tree(pid: u32) {
    let pid_arg = pid.to_string();
    let _ = Command::new("taskkill")
        .args(["/PID", pid_arg.as_str(), "/T", "/F"])
        .creation_flags(CREATE_NO_WINDOW)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

#[cfg(not(windows))]
fn kill_process_tree(_pid: u32) {}

fn kill_backend(app_handle: &tauri::AppHandle) {
    let state = app_handle.state::<BackendChild>();
    let Some(process) = state.0.lock().ok().and_then(|mut guard| guard.take()) else {
        return;
    };

    match process {
        BackendProcess::Sidecar(child) => {
            let pid = child.pid();
            kill_process_tree(pid);
            let _ = child.kill();
        }
        BackendProcess::Uvicorn(mut child) => {
            let pid = child.id();
            kill_process_tree(pid);
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Try sidecar (production); fall back to uvicorn (dev).
fn spawn_backend(app: &tauri::AppHandle) -> Result<BackendProcess, String> {
    // Strategy 1: sidecar (bundled in installer)
    if let Ok(cmd) = app.shell().sidecar("research-backend") {
        println!("[backend] spawning sidecar...");
        match cmd
            .args(["--port", "8787", "--host", "127.0.0.1"])
            .spawn()
        {
            // spawn() returns (Receiver<CommandEvent>, CommandChild)
            Ok((mut rx, child)) => {
                println!("[backend] sidecar started OK");
                let handle = app.clone();
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line) => {
                                let text = String::from_utf8_lossy(&line);
                                if !text.trim().is_empty() {
                                    println!("[backend stdout] {}", text.trim_end());
                                }
                            }
                            CommandEvent::Stderr(line) => {
                                let text = String::from_utf8_lossy(&line);
                                if !text.trim().is_empty() {
                                    eprintln!("[backend stderr] {}", text.trim_end());
                                }
                            }
                            CommandEvent::Error(error) => {
                                eprintln!("[backend] sidecar event error: {error}");
                                let _ = handle.emit("backend-error", error);
                            }
                            CommandEvent::Terminated(payload) => {
                                let message = format!("Backend process exited with code {:?}", payload.code);
                                eprintln!("[backend] {message}");
                                let _ = handle.emit("backend-error", message);
                                break;
                            }
                            _ => {}
                        }
                    }
                });
                return Ok(BackendProcess::Sidecar(child));
            }
            Err(e) => println!("[backend] sidecar spawn failed: {e}"),
        }
    }

    // Strategy 2: uvicorn (dev mode, Python must be on PATH)
    println!("[backend] falling back to uvicorn...");
    let child = Command::new("uvicorn")
        .args(["app.main:app", "--port", "8787", "--host", "127.0.0.1"])
        .current_dir("../backend")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("uvicorn failed: {e}"))?;

    Ok(BackendProcess::Uvicorn(child))
}

fn backend_is_ready_once() -> bool {
    if let Ok(mut s) = TcpStream::connect_timeout(
        &"127.0.0.1:8787".parse().unwrap(),
        Duration::from_millis(500),
    ) {
        let _ = s.write_all(b"GET /api/v1/health HTTP/1.0\r\nHost: localhost\r\n\r\n");
        let mut buf = [0u8; 256];
        if s.read(&mut buf).is_ok() {
            return String::from_utf8_lossy(&buf).contains("200 OK");
        }
    }
    false
}

/// Block until port 8787 responds to a health-check GET.
fn wait_for_backend() -> bool {
    for i in 0..180 {
        if let Ok(mut s) = TcpStream::connect_timeout(
            &"127.0.0.1:8787".parse().unwrap(),
            Duration::from_secs(2),
        ) {
            let _ = s.write_all(b"GET /api/v1/health HTTP/1.0\r\nHost: localhost\r\n\r\n");
            let mut buf = [0u8; 256];
            if s.read(&mut buf).is_ok() {
                let resp = String::from_utf8_lossy(&buf);
                if resp.contains("200 OK") {
                    println!("[backend] health check passed (attempt {})", i + 1);
                    return true;
                }
            }
        }
        std::thread::sleep(Duration::from_secs(1));
    }
    false
}

fn main() {
    tauri::Builder::default()
        .manage(BackendChild(Mutex::new(None)))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();

            // Diagnostic build: open WebView DevTools automatically so packaged-only
            // fetch/CORS/resource failures can be inspected from Console/Network.
            if let Some(window) = app.get_webview_window("main") {
                window.open_devtools();
            }

            // Launch backend exactly once in a background thread.
            std::thread::spawn(move || {
                if backend_is_ready_once() {
                    println!("[backend] existing service detected on http://127.0.0.1:8787");
                    let _ = handle.emit("backend-ready", ());
                    return;
                }

                let process = match spawn_backend(&handle) {
                    Ok(p) => p,
                    Err(e) => {
                        eprintln!("[backend] launch failed: {e}");
                        let _ = handle.emit("backend-error", e);
                        return;
                    }
                };

                // Store into managed state so we can kill it on exit.
                let state = handle.state::<BackendChild>();
                if let Ok(mut guard) = state.0.lock() {
                    *guard = Some(process);
                }

                // Wait for readiness.
                if wait_for_backend() {
                    println!("[backend] ready on http://127.0.0.1:8787");
                    let _ = handle.emit("backend-ready", ());
                } else {
                    eprintln!("[backend] health check timed out; backend process will be kept alive");
                    let _ = handle.emit(
                        "backend-error",
                        "Backend is still starting or did not answer health checks on port 8787",
                    );
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. } | WindowEvent::Destroyed) {
                kill_backend(window.app_handle());
            }
        })
        .build(tauri::generate_context!())
        .expect("error building tauri application")
        .run(|app_handle, event| {
            if matches!(event, tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit) {
                kill_backend(app_handle);
            }
        });
}
