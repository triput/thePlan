import { useCallback, useEffect, useState } from "react";

const DISMISS_MS = 2500;

interface Toast {
  id: number;
  message: string;
}

let toastListener: ((message: string) => void) | null = null;

/** Subscribe from UndoStackProvider via onToast prop wired in App. */
export function emitToast(message: string) {
  toastListener?.(message);
}

export function ToastHost() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, DISMISS_MS);
  }, []);

  useEffect(() => {
    toastListener = showToast;
    return () => {
      if (toastListener === showToast) toastListener = null;
    };
  }, [showToast]);

  if (toasts.length === 0) return null;

  return (
    <div className="toast-host" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className="toast-item">
          {toast.message}
        </div>
      ))}
    </div>
  );
}
