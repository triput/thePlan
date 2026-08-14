//! thePlan desktop shell — spawn FastAPI (uvicorn) sidecar, load apps/web build.
//! ADR-009 / W3 Slice 3 prove-it: fixed loopback port 18765, Compose Postgres.

mod sidecar;

use sidecar::{start_sidecar, stop_sidecar, SidecarState};
use std::sync::Mutex;
use tauri::{Manager, RunEvent, WebviewWindow};

fn show_fatal(title: &str, message: &str) {
    eprintln!("[thePlan desktop] FATAL: {message}");
    sidecar::native_error_dialog(title, message);
}

fn show_main_window(window: &WebviewWindow) {
    let _ = window.set_title("thePlan");
    if let Err(err) = window.show() {
        eprintln!("[thePlan desktop] failed to show window: {err}");
    }
    let _ = window.set_focus();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let window = app
                .get_webview_window("main")
                .ok_or_else(|| "missing main window".to_string())?;

            let _ = window.set_title("thePlan — starting…");
            // Brief starting state so the operator knows we are alive while health waits.
            let _ = window.show();

            match start_sidecar() {
                Ok(child) => {
                    app.manage(SidecarState(Mutex::new(Some(child))));
                    show_main_window(&window);
                    Ok(())
                }
                Err(err) => {
                    show_fatal("thePlan — failed to start", &err);
                    app.handle().exit(1);
                    Ok(())
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building thePlan desktop");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = app_handle.try_state::<SidecarState>() {
                stop_sidecar(&state);
            }
        }
    });
}
