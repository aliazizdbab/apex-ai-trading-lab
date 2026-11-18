#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

#[tauri::command]
fn desktop_runtime_info() -> &'static str {
    "APEX AI Trading Lab Desktop Shell (Local FastAPI Sidecar)"
}

fn spawn_local_backend() -> Option<Child> {
    let candidates = [
        ("..\\backend\\.venv\\Scripts\\uvicorn.exe", vec!["app.main:app", "--host", "127.0.0.1", "--port", "8000"]),
        ("../backend/.venv/bin/uvicorn", vec!["app.main:app", "--host", "127.0.0.1", "--port", "8000"]),
    ];
    for (bin, args) in candidates {
        if let Ok(child) = Command::new(bin).args(&args).current_dir("../backend").spawn() {
            return Some(child);
        }
    }
    None
}

fn main() {
    let backend = BackendProcess(Mutex::new(spawn_local_backend()));

    tauri::Builder::default()
        .manage(backend)
        .invoke_handler(tauri::generate_handler![desktop_runtime_info])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = window.state::<BackendProcess>();
                if let Ok(mut guard) = state.0.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running APEX AI Trading Lab desktop shell");
}
