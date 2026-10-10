// ==============================================================================
//  File: apps/web/src/components/ImportPanel.tsx
//  Description: Unified import shell — Coursera templates and custom outline under one modal.
//  Component: F5 Import
//  Version: 1.0
//  Created: 2026-10-10
//  Last Update: 2026-10-10
// ==============================================================================

import { useEffect, useState } from "react";
import { Modal } from "./Modal";
import { OutlineImportPanel } from "./OutlineImportPanel";
import { TemplatesPanel } from "./TemplatesPanel";

export type ImportPanelMode = "templates" | "outline";

const IMPORT_QUERY_VALUES: Record<string, ImportPanelMode> = {
  templates: "templates",
  template: "templates",
  outline: "outline",
  custom: "outline",
};

function parseImportMode(raw: string | null): ImportPanelMode | null {
  if (!raw) return null;
  return IMPORT_QUERY_VALUES[raw.toLowerCase()] ?? null;
}

export function ImportPanel({
  onApplied,
}: {
  onApplied?: (epicId: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<ImportPanelMode>("templates");

  const openWithMode = (next: ImportPanelMode) => {
    setMode(next);
    setOpen(true);
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fromQuery = parseImportMode(params.get("import"));
    if (fromQuery) {
      openWithMode(fromQuery);
      params.delete("import");
      const rest = params.toString();
      window.history.replaceState({}, "", `${window.location.pathname}${rest ? `?${rest}` : ""}`);
    }
  }, []);

  useEffect(() => {
    const onOpenImport = (event: Event) => {
      const detail = (event as CustomEvent<string | undefined>).detail;
      const parsed = typeof detail === "string" ? parseImportMode(detail) : null;
      openWithMode(parsed ?? "templates");
    };
    window.addEventListener("theplan:open-import", onOpenImport);
    return () => window.removeEventListener("theplan:open-import", onOpenImport);
  }, []);

  return (
    <div className="import-panel">
      <button
        type="button"
        className="btn secondary small import-toggle"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => openWithMode(mode)}
      >
        Import
      </button>
      <Modal
        open={open}
        title="Import structure"
        onClose={() => setOpen(false)}
        className="import-modal"
      >
        <div className="import-mode-tabs" role="tablist" aria-label="Import source">
          <button
            type="button"
            role="tab"
            id="import-tab-templates"
            aria-selected={mode === "templates"}
            aria-controls="import-panel-templates"
            className={`btn secondary small${mode === "templates" ? " import-tab-active" : ""}`}
            onClick={() => setMode("templates")}
          >
            Templates
          </button>
          <button
            type="button"
            role="tab"
            id="import-tab-outline"
            aria-selected={mode === "outline"}
            aria-controls="import-panel-outline"
            className={`btn secondary small${mode === "outline" ? " import-tab-active" : ""}`}
            onClick={() => setMode("outline")}
          >
            Custom outline
          </button>
        </div>

        <div
          id="import-panel-templates"
          role="tabpanel"
          aria-labelledby="import-tab-templates"
          hidden={mode !== "templates"}
        >
          <TemplatesPanel
            embedded
            shellOpen={open}
            active={mode === "templates"}
            onApplied={onApplied}
          />
        </div>
        <div
          id="import-panel-outline"
          role="tabpanel"
          aria-labelledby="import-tab-outline"
          hidden={mode !== "outline"}
        >
          <OutlineImportPanel
            embedded
            shellOpen={open}
            active={mode === "outline"}
            onApplied={onApplied}
            onRequestClose={() => setOpen(false)}
          />
        </div>
      </Modal>
    </div>
  );
}
