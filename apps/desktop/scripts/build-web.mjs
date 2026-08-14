/**
 * Build apps/web for the desktop shell with API URL pinned to the sidecar.
 */
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webDir = path.resolve(__dirname, "../../web");

const env = {
  ...process.env,
  VITE_API_URL: "http://127.0.0.1:18765",
};

// Windows: bare `npm.cmd` spawn → EINVAL on modern Node; avoid shell+argv (DEP0190).
const child =
  process.platform === "win32"
    ? spawn("cmd.exe", ["/d", "/s", "/c", "npm run build"], {
        cwd: webDir,
        env,
        stdio: "inherit",
        windowsHide: true,
      })
    : spawn("npm", ["run", "build"], {
        cwd: webDir,
        env,
        stdio: "inherit",
      });

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
