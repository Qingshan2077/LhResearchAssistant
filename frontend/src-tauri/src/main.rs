// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

struct PythonBackend(Mutex<Option<Child>>);

/// Try to launch the backend sidecar (production) or uvicorn (dev fallback).
fn launch_backend(app: &tauri::AppHandle) -> Result<Child, String> {
    // ── Strategy 1: Sidecar (production build) ──
    let sidecar_path = app
        .path()
        .resolve("binaries/research-backend", tauri::path::BaseDirectory::Resource)
        .ok();

    if let Some(ref path) = sidecar_path {
        if path.exists() {
            println!("[backend] Launching sidecar: {:?}", path);
            let (_, child) = app
                .shell()
                .sidecar("research-backend")
                .map_err(|e| format!("sidecar creation: {}", e))?
                .args(["--port", "8787", "--host", "127.0.0.1"])
                .spawn()
                .map_err(|e| format!("sidecar spawn: {}", e))?;
            println!("[backend] Sidecar launched OK");
            return Ok(child);
        }
    }

    // ── Strategy 2: uvicorn (dev mode, needs Python installed) ──
    println!("[backend] Falling back to uvicorn (dev mode)");
    let child = Command::new("uvicorn")
        .args(["app.main:app", "--port", "8787", "--host", "127.0.0.1"])
        .current_dir("../backend")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Failed to start uvicorn: {}", e))?;

    println!("[backend] uvicorn launched OK");
    Ok(child)
}

/// Health check via TCP connect (no extra dependencies needed).
fn wait_for_backend() -> bool {
    for i in 0..30 {
        // Try raw TCP connect to port 8787
        if TcpStream::connect_timeout(
            &"127.0.0.1:8787".parse().unwrap(),
            Duration::from_secs(2),
        )
        .is_ok()
        {
            // Also send a minimal HTTP GET to confirm it's FastAPI, not something else
            if let Ok(mut stream) = TcpStream::connect_timeout(
                &"127.0.0.1:8787".parse().unwrap(),
                Duration::from_secs(1),
            ) {
                let _ = stream.write_all(b"GET /api/v1/health HTTP/1.0\r\nHost: localhost\r\n\r\n");
                let mut buf = [0u8; 256];
                if stream.read(&mut buf).is_ok() {
                    let resp = String::from_utf8_lossy(&buf);
                    if resp.contains("200 OK") || resp.contains("ok") || resp.contains("healthy") {
                        println!("[backend] Health check passed (attempt {})", i + 1);
                        return true;
                    }
                }
            }
        }
        std::thread::sleep(Duration::from_secs(1));
    }
    false
}

#[tauri::command]
fn start_backend(app: tauri::AppHandle, state: tauri::State<PythonBackend>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if guard.is_some() {
        return Ok(()); // already running
    }

    let child = launch_backend(&app)?;

    // Wait for backend to be ready
    if wait_for_backend() {
        *guard = Some(child);
        println!("[backend] Ready on http://127.0.0.1:8787");
        Ok(())
    } else {
        // Kill the child if health check failed
        let _ = child.wait_with_output();
        Err("Backend health check timed out after 30s. Check that port 8787 is free.".to_string())
    }
}

#[tauri::command]
fn stop_backend(state: tauri::State<PythonBackend>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = guard.take() {
        child.kill().map_err(|e| format!("Failed to stop backend: {}", e))?;
        child.wait().ok();
        println!("[backend] Stopped");
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
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                // Give the window a moment to render
                std::thread::sleep(Duration::from_secs(2));

                let state = handle.state::<PythonBackend>();
                if let Err(e) = start_backend(handle.clone(), state.into_inner()) {
                    eprintln!("[backend] Launch failed: {}", e);
                    let _ = handle.emit("backend-error", e);
                } else {
                    let _ = handle.emit("backend-ready", ());
                }
            });

            Ok(())
        })
        .on_event(|app, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                let state = app.state::<PythonBackend>();
                if let Ok(mut guard) = state.0.lock() {
                    if let Some(mut child) = guard.take() {
                        child.kill().ok();
                        child.wait().ok();
                        println!("[backend] Cleaned up on exit");
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![start_backend, stop_backend])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
