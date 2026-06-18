// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Emitter;
use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Unified type: sidecar (production) or uvicorn (dev).
enum BackendProcess {
    Sidecar(CommandChild),
    Uvicorn(Child),
}

struct BackendChild(Mutex<Option<BackendProcess>>);

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
            Ok((_rx, child)) => {
                println!("[backend] sidecar started OK");
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

/// Block until port 8787 responds to a health-check GET.
fn wait_for_backend() -> bool {
    for i in 0..30 {
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

            // ── Launch backend exactly once in a background thread ──
            std::thread::spawn(move || {
                let process = match spawn_backend(&handle) {
                    Ok(p) => p,
                    Err(e) => {
                        eprintln!("[backend] launch failed: {e}");
                        let _ = handle.emit("backend-error", e);
                        return;
                    }
                };

                // Store into managed state so we can kill it on exit
                let state = handle.state::<BackendChild>();
                if let Ok(mut guard) = state.0.lock() {
                    *guard = Some(process);
                }

                // Wait for readiness
                if wait_for_backend() {
                    println!("[backend] ready on http://127.0.0.1:8787");
                    let _ = handle.emit("backend-ready", ());
                } else {
                    eprintln!("[backend] health check timed out");
                    let _ = handle.emit(
                        "backend-error",
                        "Timed out waiting for backend on port 8787",
                    );
                    // Kill the unresponsive process via the mutex
                    let state = handle.state::<BackendChild>();
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(p) = guard.take() {
                            match p {
                                BackendProcess::Sidecar(c) => { c.kill().ok(); },
                                BackendProcess::Uvicorn(c) => { c.kill().ok(); },
                            }
                        }
                    };
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building tauri application")
        .run(|app_handle, event| {
            // ── Kill backend on exit ──
            if let tauri::RunEvent::ExitRequested { .. } = event {
                let state = app_handle.state::<BackendChild>();
                if let Ok(mut guard) = state.0.lock() {
                    if let Some(p) = guard.take() {
                        match p {
                            BackendProcess::Sidecar(c) => { c.kill().ok(); },
                            BackendProcess::Uvicorn(c) => { c.kill().ok(); },
                        }
                    }
                };
            }
        });
}
