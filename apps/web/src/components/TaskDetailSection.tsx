import type { ReactNode } from "react";

export type DetailSectionId =
  | "scheduling"
  | "recurrence"
  | "dependencies"
  | "labels"
  | "advanced";

export function TaskDetailSection({
  id,
  title,
  open,
  onToggle,
  children,
}: {
  id: DetailSectionId;
  title: string;
  open: boolean;
  onToggle: (id: DetailSectionId) => void;
  children: ReactNode;
}) {
  const toggleId = `detail-section-toggle-${id}`;
  const bodyId = `detail-section-${id}`;
  return (
    <section className={`detail-section${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="detail-section-toggle"
        id={toggleId}
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => onToggle(id)}
      >
        <span className="detail-section-chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
        <span className="detail-section-title">{title}</span>
      </button>
      {open ? (
        <div className="detail-section-body" id={bodyId} role="region" aria-labelledby={toggleId}>
          {children}
        </div>
      ) : null}
    </section>
  );
}
