/**
 * Smoke: spawn uvicorn the same way the Tauri shell does, wait for /health, tear down.
 * Does not launch the GUI. Requires Compose Postgres (or reachable DATABASE_URL).
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const API_HOST = "127.0.0.1";
const API_PORT = 18765;
const HEALTH_URL = `http://${API_HOST}:${API_PORT}/health`;
const HEALTH_TIMEOUT_MS = 30_000;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const apiDir = path.resolve(__dirname, "../../api");

function portFree(host, port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, host);
  });
}

function resolvePython() {
  if (process.env.THEPLAN_API_PYTHON) {
    return process.env.THEPLAN_API_PYTHON;
  }
  const venvCandidates =
    process.platform === "win32"
      ? [
          path.join(apiDir, ".venv", "Scripts", "python.exe"),
          path.join(apiDir, "venv", "Scripts", "python.exe"),
        ]
      : [
          path.join(apiDir, ".venv", "bin", "python"),
          path.join(apiDir, "venv", "bin", "python"),
        ];
  for (const candidate of venvCandidates) {
    if (existsSync(candidate)) return candidate;
  }
  return process.platform === "win32" ? "python" : "python3";
}

async function waitForHealth(timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(HEALTH_URL);
      if (res.ok) {
        const body = await res.json();
        if (body?.status === "ok") return;
      }
    } catch {
      // retry
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`Timed out after ${timeoutMs}ms waiting for ${HEALTH_URL}`);
}

function killProcessTree(child) {
  if (!child.pid) return;
  if (process.platform === "win32") {
    spawn("taskkill.exe", ["/F", "/T", "/PID", String(child.pid)], {
      stdio: "ignore",
      shell: false,
    });
  } else {
    try {
      process.kill(-child.pid, "SIGTERM");
    } catch {
      child.kill("SIGTERM");
    }
  }
}

const free = await portFree(API_HOST, API_PORT);
if (!free) {
  console.error(
    `[smoke] Port ${API_PORT} is already in use. Free it (fixed port per ADR-009) and retry.`,
  );
  process.exit(1);
}

const python = resolvePython();
const corsOrigins = JSON.stringify([
  "http://127.0.0.1:18765",
  "http://localhost:18765",
  "http://tauri.localhost",
  "https://tauri.localhost",
  "tauri://localhost",
]);

console.log(`[smoke] api dir: ${apiDir}`);
console.log(`[smoke] python: ${python}`);

const child = spawn(
  python,
  ["-m", "uvicorn", "app.main:app", "--host", API_HOST, "--port", String(API_PORT)],
  {
    cwd: apiDir,
    env: {
      ...process.env,
      DATABASE_URL:
        process.env.DATABASE_URL ??
        "postgresql+psycopg://theplan:theplan@127.0.0.1:5432/theplan",
      CORS_ORIGINS: corsOrigins,
      FRONTEND_ORIGIN: "http://127.0.0.1:18765",
      SESSION_HTTPS_ONLY: "false",
    },
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
    detached: process.platform !== "win32",
  },
);

child.stdout.on("data", (d) => process.stdout.write(`[uvicorn] ${d}`));
child.stderr.on("data", (d) => process.stderr.write(`[uvicorn] ${d}`));

let exitedEarly = false;
child.on("exit", (code, signal) => {
  exitedEarly = true;
  console.error(`[smoke] uvicorn exited early code=${code} signal=${signal}`);
});

try {
  await waitForHealth(HEALTH_TIMEOUT_MS);
  console.log("[smoke] GET /health OK");
  process.exitCode = 0;
} catch (err) {
  console.error(`[smoke] FAIL: ${err.message || err}`);
  process.exitCode = 1;
} finally {
  if (!exitedEarly) {
    killProcessTree(child);
  }
  // give taskkill a moment on Windows
  await new Promise((r) => setTimeout(r, 500));
  process.exit(process.exitCode ?? 0);
}
