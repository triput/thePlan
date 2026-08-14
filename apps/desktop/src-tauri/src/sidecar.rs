//! FastAPI uvicorn sidecar lifecycle (fixed port 18765 per ADR-009 / Slice 3 mission).

use std::io::{Read, Write};
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

pub const API_HOST: &str = "127.0.0.1";
pub const API_PORT: u16 = 18765;
const HEALTH_TIMEOUT: Duration = Duration::from_secs(30);
const HEALTH_POLL: Duration = Duration::from_millis(250);

pub struct SidecarState(pub Mutex<Option<Child>>);

pub fn native_error_dialog(title: &str, message: &str) {
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        #[link(name = "user32")]
        extern "system" {
            fn MessageBoxW(
                hwnd: *mut core::ffi::c_void,
                text: *const u16,
                caption: *const u16,
                flags: u32,
            ) -> i32;
        }
        fn wide(s: &str) -> Vec<u16> {
            std::ffi::OsStr::new(s)
                .encode_wide()
                .chain(std::iter::once(0))
                .collect()
        }
        let text = wide(message);
        let caption = wide(title);
        unsafe {
            MessageBoxW(
                std::ptr::null_mut(),
                text.as_ptr(),
                caption.as_ptr(),
                0x00000010, // MB_ICONERROR
            );
        }
    }
    #[cfg(not(windows))]
    {
        let _ = (title, message);
    }
}

fn api_dir() -> Result<PathBuf, String> {
    if let Ok(override_dir) = std::env::var("THEPLAN_API_DIR") {
        let path = PathBuf::from(override_dir);
        if is_api_dir(&path) {
            return Ok(path);
        }
        return Err(format!(
            "THEPLAN_API_DIR is set but does not look like apps/api: {}",
            path.display()
        ));
    }

    // apps/desktop/src-tauri → ../../api
    let manifest_api = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../api");
    if let Ok(canonical) = manifest_api.canonicalize() {
        if is_api_dir(&canonical) {
            return Ok(canonical);
        }
    }

    Err(format!(
        "Could not find apps/api (looked for {}). Set THEPLAN_API_DIR.",
        manifest_api.display()
    ))
}

fn resolve_python(api_dir: &Path) -> Result<PathBuf, String> {
    if let Ok(override_py) = std::env::var("THEPLAN_API_PYTHON") {
        let path = PathBuf::from(override_py);
        if path.exists() {
            return Ok(path);
        }
        return Err(format!(
            "THEPLAN_API_PYTHON is set but not found: {}",
            path.display()
        ));
    }

    // Prefer repo venv — PATH `python` often points at unrelated envs (e.g. other tools).
    let venv_candidates = [
        api_dir.join(".venv").join("Scripts").join("python.exe"),
        api_dir.join(".venv").join("bin").join("python"),
        api_dir.join("venv").join("Scripts").join("python.exe"),
        api_dir.join("venv").join("bin").join("python"),
    ];
    for candidate in &venv_candidates {
        if candidate.is_file() && python_runs(candidate.as_os_str()) {
            return Ok(candidate.clone());
        }
    }

    for candidate in ["python", "python3"] {
        if python_runs(std::ffi::OsStr::new(candidate)) {
            return Ok(PathBuf::from(candidate));
        }
    }

    Err(format!(
        "No usable Python for the sidecar. Create apps/api/.venv with project deps, or set \
         THEPLAN_API_PYTHON (e.g. {}).",
        api_dir
            .join(".venv")
            .join("Scripts")
            .join("python.exe")
            .display()
    ))
}

fn python_runs(bin: &std::ffi::OsStr) -> bool {
    Command::new(bin)
        .args([
            "-c",
            "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)",
        ])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

pub fn assert_port_free() -> Result<(), String> {
    match TcpListener::bind((API_HOST, API_PORT)) {
        Ok(listener) => {
            drop(listener);
            Ok(())
        }
        Err(_) => Err(format!(
            "Port {API_PORT} on {API_HOST} is already in use. thePlan desktop uses a fixed \
             sidecar port (ADR-009). Stop the other process and try again."
        )),
    }
}

fn health_ok() -> bool {
    let Ok(mut stream) = std::net::TcpStream::connect((API_HOST, API_PORT)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    let request = format!(
        "GET /health HTTP/1.1\r\nHost: {API_HOST}:{API_PORT}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut buf = Vec::new();
    let _ = stream.read_to_end(&mut buf);
    let body = String::from_utf8_lossy(&buf);
    body.contains("200") && body.contains("ok")
}

pub fn wait_for_health(timeout: Duration) -> Result<(), String> {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if health_ok() {
            return Ok(());
        }
        std::thread::sleep(HEALTH_POLL);
    }
    Err(format!(
        "API sidecar did not become healthy at http://{API_HOST}:{API_PORT}/health \
         within {}s. Check Compose Postgres, Python deps (apps/api), and logs.",
        timeout.as_secs()
    ))
}

fn cors_origins_json() -> String {
    // Tauri 2 WebView may present as tauri.localhost or asset.localhost (custom protocol).
    serde_json_ish(&[
        "http://127.0.0.1:18765",
        "http://localhost:18765",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
        "http://asset.localhost",
        "https://asset.localhost",
    ])
}

/// Absolute path to apps/web/dist for THEPLAN_WEB_DIST (same-origin UI).
fn web_dist_dir() -> Option<PathBuf> {
    let from_manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../web/dist");
    from_manifest.canonicalize().ok().filter(|p| p.join("index.html").is_file())
}

/// Minimal JSON string array without pulling serde_json.
fn serde_json_ish(items: &[&str]) -> String {
    let parts: Vec<String> = items.iter().map(|s| format!("\"{s}\"")).collect();
    format!("[{}]", parts.join(","))
}

pub fn start_sidecar() -> Result<Child, String> {
    assert_port_free()?;

    let api_dir = api_dir()?;
    let python = resolve_python(&api_dir)?;
    let web_dist = web_dist_dir();

    eprintln!(
        "[thePlan desktop] starting sidecar: {} -m uvicorn app.main:app --host {API_HOST} --port {API_PORT}",
        python.display()
    );
    eprintln!("[thePlan desktop] cwd: {}", api_dir.display());
    if let Some(ref dist) = web_dist {
        eprintln!("[thePlan desktop] THEPLAN_WEB_DIST: {}", dist.display());
    } else {
        eprintln!(
            "[thePlan desktop] WARNING: apps/web/dist missing — UI navigate may 404; run build:web"
        );
    }

    let mut command = Command::new(&python);
    command
        .args([
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            API_HOST,
            "--port",
            &API_PORT.to_string(),
        ])
        .current_dir(&api_dir)
        .env(
            "DATABASE_URL",
            std::env::var("DATABASE_URL").unwrap_or_else(|_| {
                "postgresql+psycopg://theplan:theplan@127.0.0.1:5432/theplan".into()
            }),
        )
        .env("CORS_ORIGINS", cors_origins_json())
        .env("FRONTEND_ORIGIN", format!("http://{API_HOST}:{API_PORT}"))
        .env("SESSION_HTTPS_ONLY", "false");
    if let Some(dist) = web_dist {
        command.env("THEPLAN_WEB_DIST", dist);
    }
    command
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // Detach from the GUI console in release; keep output visible when debugging.
        if !cfg!(debug_assertions) {
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }
    }

    let mut child = command.spawn().map_err(|err| {
        format!(
            "Failed to spawn uvicorn with '{}': {err}. \
             Use PATH Python with apps/api deps installed, or set THEPLAN_API_PYTHON \
             (e.g. apps/api/.venv/Scripts/python.exe).",
            python.display()
        )
    })?;

    if let Err(err) = wait_for_health(HEALTH_TIMEOUT) {
        let _ = terminate_child(&mut child);
        return Err(err);
    }

    eprintln!("[thePlan desktop] sidecar healthy on http://{API_HOST}:{API_PORT}");
    Ok(child)
}

pub fn stop_sidecar(state: &SidecarState) {
    let Ok(mut guard) = state.0.lock() else {
        return;
    };
    if let Some(mut child) = guard.take() {
        eprintln!("[thePlan desktop] stopping sidecar pid={}", child.id());
        let _ = terminate_child(&mut child);
    }
}

fn terminate_child(child: &mut Child) -> Result<(), String> {
    let pid = child.id();
    #[cfg(windows)]
    {
        let status = Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map_err(|e| e.to_string())?;
        if !status.success() {
            let _ = child.kill();
        }
        let _ = child.wait();
        return Ok(());
    }
    #[cfg(not(windows))]
    {
        let _ = pid;
        let _ = child.kill();
        let _ = child.wait();
        Ok(())
    }
}

fn is_api_dir(path: &Path) -> bool {
    path.join("app").join("main.py").is_file()
}
