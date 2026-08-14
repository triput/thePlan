/**
 * Build apps/web for the desktop shell with API URL pinned to the sidecar.
 */
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webDir = path.resolve(__dirname, "../../web");

const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
const child = spawn(npmCmd, ["run", "build"], {
  cwd: webDir,
  env: {
    ...process.env,
    VITE_API_URL: "http://127.0.0.1:18765",
  },
  stdio: "inherit",
  shell: false,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
