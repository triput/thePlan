/**
 * F5 template picker — built-in Coursera packs via /api/v1/templates (handoff apply + receipts).
 */

import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applyTemplate,
  fetchEpics,
  fetchProjects,
  fetchSections,
  fetchTemplate,
  fetchTemplates,
  proposeTemplate,
  type BuiltinTemplateId,
  type HandoffEntity,
  type HandoffGraphPayload,
  type OutlineAttachUnder,
  type OutlineProposeSummary,
  type HandoffResolvedDefault,
  type TemplateApplyResult,
  type TemplateProposeResponse,
} from "../api";
import { formatDuration } from "../view";
import { Modal } from "./Modal";
import { emitToast } from "./ToastHost";

const TEMPLATE_ORDER: BuiltinTemplateId[] = [
  "coursera_specialization",
  "coursera_course",
  "coursera_module",
];

type InputMode = "form" | "json";

type ReviewEntity = HandoffEntity & { clientId: string };

interface CertFormFields {
  title: string;
  provider: string;
  platform: string;
  sourceUrl: string;
  notes: string;
}

interface CourseFormFields {
  title: string;
  url: string;
  estimatedHours: string;
}

interface ModuleFormFields {
  title: string;
  estimatedHours: string;
}

function withClientIds(entities: HandoffEntity[]): ReviewEntity[] {
  return entities.map((entity) => ({
    ...entity,
    clientId: crypto.randomUUID(),
  }));
}

function entityKindLabel(kind: HandoffEntity["kind"]): string {
  switch (kind) {
    case "epic":
      return "Epic";
    case "project":
      return "Project";
    case "section":
      return "Section";
    case "task":
      return "Task";
  }
}

function entityBadgeClass(kind: HandoffEntity["kind"]): string {
  const map: Record<HandoffEntity["kind"], string> = {
    epic: "outline-type-create_epic",
    project: "outline-type-create_project",
    section: "outline-type-create_section",
    task: "outline-type-create_task",
  };
  return map[kind];
}

function formatSummary(summary: OutlineProposeSummary): string {
  const parts = [
    `${summary.epic_count} epic${summary.epic_count === 1 ? "" : "s"}`,
    `${summary.project_count} project${summary.project_count === 1 ? "" : "s"}`,
    `${summary.section_count} section${summary.section_count === 1 ? "" : "s"}`,
    `${summary.task_count} task${summary.task_count === 1 ? "" : "s"}`,
  ];
  if (summary.optional_skipped > 0) {
    parts.push(`${summary.optional_skipped} optional skipped`);
  }
  return parts.join(" · ");
}

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function readCertForm(outline: Record<string, unknown>): CertFormFields {
  const cert = (outline.certificate ?? {}) as Record<string, unknown>;
  return {
    title: String(cert.title ?? ""),
    provider: String(cert.provider ?? ""),
    platform: String(cert.platform ?? ""),
    sourceUrl: String(cert.source_url ?? cert.url ?? ""),
    notes: String(cert.notes ?? ""),
  };
}

function writeCertForm(outline: Record<string, unknown>, form: CertFormFields): Record<string, unknown> {
  const next = structuredClone(outline);
  const cert = { ...((next.certificate as Record<string, unknown>) ?? {}) };
  cert.title = form.title;
  if (form.provider.trim()) cert.provider = form.provider.trim();
  else delete cert.provider;
  if (form.platform.trim()) cert.platform = form.platform.trim();
  else delete cert.platform;
  if (form.sourceUrl.trim()) cert.source_url = form.sourceUrl.trim();
  else delete cert.source_url;
  if (form.notes.trim()) cert.notes = form.notes.trim();
  else delete cert.notes;
  next.certificate = cert;
  return next;
}

function readCourseForm(outline: Record<string, unknown>): CourseFormFields {
  let course = outline.course as Record<string, unknown> | undefined;
  if (!course && Array.isArray(outline.courses) && outline.courses[0]) {
    course = outline.courses[0] as Record<string, unknown>;
  }
  course = course ?? {};
  return {
    title: String(course.title ?? ""),
    url: String(course.url ?? ""),
    estimatedHours:
      course.estimated_hours != null && course.estimated_hours !== ""
        ? String(course.estimated_hours)
        : "",
  };
}

function writeCourseForm(outline: Record<string, unknown>, form: CourseFormFields): Record<string, unknown> {
  const next = structuredClone(outline);
  const course = { ...((next.course as Record<string, unknown>) ?? {}) };
  course.title = form.title;
  if (form.url.trim()) course.url = form.url.trim();
  else delete course.url;
  const hours = form.estimatedHours.trim();
  if (hours) {
    const parsed = Number(hours);
    if (!Number.isNaN(parsed)) course.estimated_hours = parsed;
  } else {
    delete course.estimated_hours;
  }
  next.course = course;
  delete next.certificate;
  delete next.courses;
  return next;
}

function readModuleForm(outline: Record<string, unknown>): ModuleFormFields {
  const module = (outline.module ?? {}) as Record<string, unknown>;
  return {
    title: String(module.title ?? ""),
    estimatedHours:
      module.estimated_hours != null && module.estimated_hours !== ""
        ? String(module.estimated_hours)
        : "",
  };
}

function writeModuleForm(outline: Record<string, unknown>, form: ModuleFormFields): Record<string, unknown> {
  const next = structuredClone(outline);
  const module = { ...((next.module as Record<string, unknown>) ?? {}) };
  module.title = form.title;
  const hours = form.estimatedHours.trim();
  if (hours) {
    const parsed = Number(hours);
    if (!Number.isNaN(parsed)) module.estimated_hours = parsed;
  } else {
    delete module.estimated_hours;
  }
  next.module = module;
  return next;
}

function taskDurationDisclosure(
  entity: ReviewEntity,
  resolvedDefaults: HandoffResolvedDefault[] | undefined,
): { minutes: number; defaulted: boolean; sourceLabel: string | null } | null {
  if (entity.kind !== "task") return null;
  const defaulted = resolvedDefaults?.find(
    (d) => d.entity_key === entity.key && d.field === "estimated_duration_minutes",
  );
  if (defaulted != null) {
    const minutes = Number(defaulted.value);
    if (!Number.isFinite(minutes) || minutes < 1) return null;
    const sourceLabel =
      defaulted.source === "user_settings" || defaulted.source === "settings"
        ? "from scheduling settings"
        : defaulted.source
          ? String(defaulted.source)
          : "from scheduling settings";
    return { minutes, defaulted: true, sourceLabel };
  }
  const explicit = entity.estimated_duration_minutes;
  if (explicit != null && explicit >= 1) {
    return { minutes: explicit, defaulted: false, sourceLabel: null };
  }
  return null;
}

function EntityReviewRow({
  entity,
  index,
  resolvedDefaults,
  onChange,
}: {
  entity: ReviewEntity;
  index: number;
  resolvedDefaults: HandoffResolvedDefault[] | undefined;
  onChange: (index: number, next: ReviewEntity) => void;
}) {
  const duration = taskDurationDisclosure(entity, resolvedDefaults);
  return (
    <li className="outline-action">
      <div className="outline-action-main">
        <span className={`outline-type-badge ${entityBadgeClass(entity.kind)}`}>
          {entityKindLabel(entity.kind)}
        </span>
        <input
          className="outline-action-title"
          value={entity.title}
          aria-label={`Proposed ${entityKindLabel(entity.kind).toLowerCase()} ${index + 1} title`}
          onChange={(e) => onChange(index, { ...entity, title: e.target.value })}
        />
      </div>
      {duration ? (
        <div className="outline-action-meta muted small">
          Duration: {formatDuration(duration.minutes)}
          {duration.defaulted
            ? ` (${duration.sourceLabel ?? "default"})`
            : " (explicit in outline)"}
        </div>
      ) : entity.kind === "task" ? (
        <div className="outline-action-meta muted small">Duration: not set</div>
      ) : null}
      {(entity.label_names?.length ?? 0) > 0 ? (
        <div className="outline-action-meta muted small">Labels: {entity.label_names!.join(", ")}</div>
      ) : null}
    </li>
  );
}

function ReceiptBlock({ receipt, idempotencyKey }: { receipt: TemplateApplyResult; idempotencyKey: string }) {
  const counts = Object.entries(receipt.created_counts ?? {})
    .filter(([, n]) => n > 0)
    .map(([kind, n]) => `${n} ${kind}${n === 1 ? "" : "s"}`)
    .join(" · ");
  return (
    <div className="templates-receipt">
      <h3 className="templates-receipt-title">
        {receipt.replayed ? "Receipt (replay)" : "Receipt"}
      </h3>
      <dl className="templates-receipt-dl">
        <div>
          <dt>Receipt ID</dt>
          <dd>
            <code>{receipt.receipt_id}</code>
          </dd>
        </div>
        <div>
          <dt>Idempotency key</dt>
          <dd>
            <code>{idempotencyKey}</code>
          </dd>
        </div>
        {receipt.template_id ? (
          <div>
            <dt>Template</dt>
            <dd>
              {receipt.template_id}
              {receipt.template_version != null ? ` v${receipt.template_version}` : ""}
            </dd>
          </div>
        ) : null}
        {counts ? (
          <div>
            <dt>Created</dt>
            <dd>{counts}</dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}

export function TemplatesPanel({
  onApplied,
}: {
  onApplied?: (epicId: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [templateId, setTemplateId] = useState<BuiltinTemplateId>("coursera_specialization");
  const [inputMode, setInputMode] = useState<InputMode>("form");
  const [outline, setOutline] = useState<Record<string, unknown> | null>(null);
  const [jsonText, setJsonText] = useState("");
  const [certForm, setCertForm] = useState<CertFormFields>(() => readCertForm({}));
  const [courseForm, setCourseForm] = useState<CourseFormFields>(() => readCourseForm({}));
  const [moduleForm, setModuleForm] = useState<ModuleFormFields>(() => readModuleForm({}));
  const [skipOptional, setSkipOptional] = useState(false);
  const [attachRoot, setAttachRoot] = useState(true);
  const [attachEpicId, setAttachEpicId] = useState("");
  const [attachProjectId, setAttachProjectId] = useState("");
  const [attachSectionId, setAttachSectionId] = useState("");
  const [entities, setEntities] = useState<ReviewEntity[] | null>(null);
  const [payloadBase, setPayloadBase] = useState<HandoffGraphPayload | null>(null);
  const [summary, setSummary] = useState<OutlineProposeSummary | null>(null);
  const [proposeMeta, setProposeMeta] = useState<Pick<
    TemplateProposeResponse,
    "is_scaffold" | "warnings" | "resolved_defaults"
  > | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<TemplateApplyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const proposeGenerationRef = useRef(0);
  const queryClient = useQueryClient();

  const invalidateProposePreview = useCallback(() => {
    proposeGenerationRef.current += 1;
    setEntities(null);
    setPayloadBase(null);
    setSummary(null);
    setProposeMeta(null);
    setIdempotencyKey(null);
    setReceipt(null);
  }, []);

  const templatesQuery = useQuery({
    queryKey: ["templates", "catalog"],
    queryFn: fetchTemplates,
    enabled: open,
  });

  const detailQuery = useQuery({
    queryKey: ["templates", "detail", templateId],
    queryFn: () => fetchTemplate(templateId),
    enabled: open,
  });

  useEffect(() => {
    if (!open || !detailQuery.data || detailQuery.data.id !== templateId) return;
    const example = detailQuery.data.example_outline;
    setOutline(structuredClone(example));
    setJsonText(JSON.stringify(example, null, 2));
    setCertForm(readCertForm(example));
    setCourseForm(readCourseForm(example));
    setModuleForm(readModuleForm(example));
    setEntities(null);
    setPayloadBase(null);
    setSummary(null);
    setProposeMeta(null);
    setIdempotencyKey(null);
    setReceipt(null);
    setError(null);
  }, [open, detailQuery.data, templateId]);

  useEffect(() => {
    if (templateId === "coursera_module") {
      setAttachRoot(false);
    } else {
      setAttachRoot(true);
      setAttachProjectId("");
      setAttachSectionId("");
    }
  }, [templateId]);

  const moduleAttachKind =
    attachSectionId ? "section" : attachProjectId ? "project" : null;

  const epicsQuery = useQuery({
    queryKey: ["epics", "templates"],
    queryFn: () => fetchEpics({ archived: false, limit: 200 }),
    enabled: open && (templateId === "coursera_module" || !attachRoot),
  });

  const projectsQuery = useQuery({
    queryKey: ["projects", "templates", attachEpicId || "all"],
    queryFn: () =>
      fetchProjects({
        archived: false,
        limit: 200,
        epic_id: attachEpicId || undefined,
      }),
    enabled: open && (templateId === "coursera_module" || !attachRoot),
  });

  const sectionsQuery = useQuery({
    queryKey: ["sections", "templates", attachProjectId],
    queryFn: () => fetchSections(attachProjectId),
    enabled: open && templateId === "coursera_module" && Boolean(attachProjectId),
  });

  const buildAttachUnder = (): OutlineAttachUnder | null => {
    if (templateId === "coursera_module") {
      if (attachSectionId) return { kind: "section", id: attachSectionId };
      if (attachProjectId) return { kind: "project", id: attachProjectId };
      return null;
    }
    if (attachRoot) return null;
    if (!attachEpicId) return null;
    return { kind: "epic", id: attachEpicId };
  };

  const resolveOutlineForPropose = (): Record<string, unknown> | null => {
    if (inputMode === "json") {
      const trimmed = jsonText.trim();
      if (!trimmed) return null;
      try {
        const parsed = JSON.parse(trimmed) as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          setError("Outline must be a JSON object");
          return null;
        }
        return parsed as Record<string, unknown>;
      } catch {
        setError("Invalid JSON");
        return null;
      }
    }
    if (!outline) return null;
    if (templateId === "coursera_specialization") return writeCertForm(outline, certForm);
    if (templateId === "coursera_course") return writeCourseForm(outline, courseForm);
    return writeModuleForm(outline, moduleForm);
  };

  const syncJsonFromForm = () => {
    if (!outline) return;
    let next = outline;
    if (templateId === "coursera_specialization") next = writeCertForm(outline, certForm);
    else if (templateId === "coursera_course") next = writeCourseForm(outline, courseForm);
    else next = writeModuleForm(outline, moduleForm);
    setOutline(next);
    setJsonText(JSON.stringify(next, null, 2));
  };

  const syncFormFromJson = (): boolean => {
    const trimmed = jsonText.trim();
    if (!trimmed) return false;
    try {
      const parsed = JSON.parse(trimmed) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setError("Outline must be a JSON object");
        return false;
      }
      const record = parsed as Record<string, unknown>;
      setOutline(record);
      setCertForm(readCertForm(record));
      setCourseForm(readCourseForm(record));
      setModuleForm(readModuleForm(record));
      setError(null);
      return true;
    } catch {
      setError("Invalid JSON — fix Raw JSON before using Quick fields");
      return false;
    }
  };

  const proposeMutation = useMutation({
    mutationFn: (outlineBody: Record<string, unknown>) => {
      const attach_under = buildAttachUnder();
      if (templateId === "coursera_module" && !attach_under) {
        throw new Error("Pick a project or section before proposing");
      }
      if (!attachRoot && templateId !== "coursera_module" && !attach_under) {
        throw new Error("Pick an epic to attach under");
      }
      return proposeTemplate(templateId, {
        outline: outlineBody,
        skip_optional: skipOptional,
        attach_under,
      });
    },
    onMutate: () => {
      const generation = ++proposeGenerationRef.current;
      return { generation };
    },
    onSuccess: (data, _vars, context) => {
      if (!context || context.generation !== proposeGenerationRef.current) return;
      setEntities(withClientIds(data.payload.entities));
      setPayloadBase(data.payload);
      setSummary(data.summary);
      setProposeMeta({
        is_scaffold: data.is_scaffold,
        warnings: data.warnings,
        resolved_defaults: data.resolved_defaults,
      });
      setIdempotencyKey(null);
      setReceipt(null);
      setError(null);
      if (data.payload.entities.length === 0) {
        emitToast("Template produced no entities");
      }
    },
    onError: (err, _vars, context) => {
      if (context && context.generation !== proposeGenerationRef.current) return;
      setEntities(null);
      setPayloadBase(null);
      setSummary(null);
      setProposeMeta(null);
      setError(err instanceof Error ? err.message : "Propose failed");
    },
  });

  const applyMutation = useMutation({
    mutationFn: async ({ items, key }: { items: ReviewEntity[]; key: string }) => {
      if (!payloadBase) throw new Error("Nothing to apply");
      const entitiesOut = items.map(({ clientId: _c, ...entity }) => ({
        ...entity,
        title: entity.title.trim(),
      }));
      const result = await applyTemplate(templateId, {
        ...payloadBase,
        entities: entitiesOut,
        idempotency_key: key,
      });
      return { result, key };
    },
    onSuccess: ({ result: data, key }) => {
      setIdempotencyKey(key);
      emitToast(data.replayed ? "Apply replayed (idempotent)" : "Template applied");
      void queryClient.invalidateQueries({ queryKey: ["epics"] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["sections"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["labels"] });
      setReceipt(data);
      const epicRef =
        data.entities.find((e) => e.kind === "epic") ??
        (attachEpicId ? { kind: "epic" as const, id: attachEpicId, key: "" } : null);
      const epicId = epicRef?.kind === "epic" ? epicRef.id : null;
      if (!data.replayed) {
        onApplied?.(epicId);
      }
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Apply failed");
    },
  });

  const handlePropose = (e: FormEvent) => {
    e.preventDefault();
    const body = resolveOutlineForPropose();
    if (!body) {
      if (!error) setError("Add outline content before proposing");
      return;
    }
    if (inputMode === "form") syncJsonFromForm();
    proposeMutation.mutate(body);
  };

  const handleApply = () => {
    if (!entities || entities.length === 0 || !payloadBase) return;
    const cleaned = entities.filter((e) => e.title.trim().length > 0);
    if (cleaned.length === 0) {
      setError("Nothing left to apply");
      return;
    }
    const key = idempotencyKey ?? crypto.randomUUID();
    if (!idempotencyKey) setIdempotencyKey(key);
    applyMutation.mutate({ items: cleaned, key });
  };

  const handleFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      setJsonText(text);
      setInputMode("json");
      try {
        const parsed = JSON.parse(text) as Record<string, unknown>;
        setOutline(parsed);
        setCertForm(readCertForm(parsed));
        setCourseForm(readCourseForm(parsed));
        setModuleForm(readModuleForm(parsed));
      } catch {
        /* raw JSON mode only */
      }
      invalidateProposePreview();
      setError(null);
    };
    reader.onerror = () => setError("Could not read file");
    reader.readAsText(file);
  };

  const catalog = templatesQuery.data ?? [];
  const sortedCatalog = [...catalog].sort(
    (a, b) => TEMPLATE_ORDER.indexOf(a.id) - TEMPLATE_ORDER.indexOf(b.id),
  );
  const epics = epicsQuery.data?.items ?? [];
  const projects = projectsQuery.data?.items ?? [];
  const sections = sectionsQuery.data?.items ?? [];
  const selectedMeta = sortedCatalog.find((t) => t.id === templateId);

  const scaffoldBanner =
    proposeMeta?.is_scaffold === true ? (
      <p className="templates-banner templates-banner-scaffold" role="status">
        Blank scaffold — replace placeholder titles before apply. Imported syllabi show as ready to
        apply.
      </p>
    ) : proposeMeta?.is_scaffold === false ? (
      <p className="templates-banner templates-banner-imported" role="status">
        Imported syllabus detected — review entities below, then apply.
      </p>
    ) : detailQuery.data?.is_scaffold && !proposeMeta ? (
      <p className="templates-banner templates-banner-scaffold muted" role="status">
        Starting from blank example JSON. Fill fields or paste a full curriculum export.
      </p>
    ) : null;

  return (
    <div className="templates">
      <button
        type="button"
        className="btn secondary small templates-toggle"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        Templates
      </button>
      <Modal open={open} title="Coursera templates" onClose={() => setOpen(false)} className="templates-modal">
        <p className="outline-help muted small">
          Built-in specialization, course, and module packs. Propose previews the handoff graph;
          apply uses an idempotency key and returns a receipt.
        </p>
        <div className="outline-options">
          <label className="outline-option">
            <span className="outline-option-label">Template</span>
            <select
              value={templateId}
              onChange={(e) => {
                invalidateProposePreview();
                setTemplateId(e.target.value as BuiltinTemplateId);
              }}
              aria-label="Built-in template"
            >
              {sortedCatalog.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.title}
                </option>
              ))}
              {sortedCatalog.length === 0 &&
                TEMPLATE_ORDER.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
            </select>
          </label>
          {selectedMeta ? (
            <p className="outline-help muted small">{selectedMeta.description}</p>
          ) : null}
        </div>

        {templateId === "coursera_module" ? (
          <div className="outline-attach-targets">
            <label className="outline-option">
              <span className="outline-option-label">Epic (optional filter)</span>
              <select
                value={attachEpicId}
                onChange={(e) => {
                  invalidateProposePreview();
                  setAttachEpicId(e.target.value);
                  setAttachProjectId("");
                  setAttachSectionId("");
                }}
                aria-label="Epic for module attach"
              >
                <option value="">All projects (incl. standalone)…</option>
                {epics.map((epic) => (
                  <option key={epic.id} value={epic.id}>
                    {epic.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="outline-option">
              <span className="outline-option-label">Attach under project</span>
              <select
                value={attachProjectId}
                onChange={(e) => {
                  invalidateProposePreview();
                  setAttachProjectId(e.target.value);
                  setAttachSectionId("");
                }}
                aria-label="Target project"
              >
                <option value="">Select project…</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="outline-option">
              <span className="outline-option-label">Or attach under section</span>
              <select
                value={attachSectionId}
                onChange={(e) => {
                  invalidateProposePreview();
                  setAttachSectionId(e.target.value);
                }}
                disabled={!attachProjectId}
                aria-label="Target section"
              >
                <option value="">Optional section…</option>
                {sections.map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.title}
                  </option>
                ))}
              </select>
            </label>
            <p className="outline-help muted small">
              Module template requires a project or section parent.
              {moduleAttachKind ? ` Attaching under ${moduleAttachKind}.` : ""}
            </p>
          </div>
        ) : (
          <div className="outline-options">
            <label className="outline-option">
              <span className="outline-option-label">Attach</span>
              <select
                value={attachRoot ? "root" : "epic"}
                onChange={(e) => {
                  invalidateProposePreview();
                  const root = e.target.value === "root";
                  setAttachRoot(root);
                  if (root) setAttachEpicId("");
                }}
                aria-label="Attach template"
              >
                <option value="root">New epic (root)</option>
                <option value="epic">Existing epic</option>
              </select>
            </label>
            {!attachRoot && (
              <label className="outline-option">
                <span className="outline-option-label">Epic</span>
                <select
                  value={attachEpicId}
                  onChange={(e) => {
                    invalidateProposePreview();
                    setAttachEpicId(e.target.value);
                  }}
                  aria-label="Target epic"
                >
                  <option value="">Select epic…</option>
                  {epics.map((epic) => (
                    <option key={epic.id} value={epic.id}>
                      {epic.title}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}

        <div className="templates-input-tabs" role="tablist" aria-label="Outline input mode">
          <button
            type="button"
            role="tab"
            aria-selected={inputMode === "form"}
            className={`btn secondary small${inputMode === "form" ? " templates-tab-active" : ""}`}
            onClick={() => {
              if (inputMode === "json" && !syncFormFromJson()) return;
              setInputMode("form");
            }}
          >
            Quick fields
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={inputMode === "json"}
            className={`btn secondary small${inputMode === "json" ? " templates-tab-active" : ""}`}
            onClick={() => {
              if (inputMode === "form") syncJsonFromForm();
              setInputMode("json");
            }}
          >
            Raw JSON
          </button>
        </div>

        {scaffoldBanner}

        <form className="outline-form" onSubmit={handlePropose}>
          {inputMode === "form" ? (
            <div className="templates-form-fields">
              {templateId === "coursera_specialization" && (
                <>
                  <label className="outline-option">
                    <span className="outline-option-label">Program title</span>
                    <input
                      type="text"
                      value={certForm.title}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setCertForm((f) => ({ ...f, title: e.target.value }));
                      }}
                    />
                  </label>
                  <label className="outline-option">
                    <span className="outline-option-label">Provider</span>
                    <input
                      type="text"
                      value={certForm.provider}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setCertForm((f) => ({ ...f, provider: e.target.value }));
                      }}
                    />
                  </label>
                  <label className="outline-option">
                    <span className="outline-option-label">Platform</span>
                    <input
                      type="text"
                      value={certForm.platform}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setCertForm((f) => ({ ...f, platform: e.target.value }));
                      }}
                    />
                  </label>
                  <label className="outline-option">
                    <span className="outline-option-label">Source URL</span>
                    <input
                      type="url"
                      value={certForm.sourceUrl}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setCertForm((f) => ({ ...f, sourceUrl: e.target.value }));
                      }}
                    />
                  </label>
                  <label className="outline-option">
                    <span className="outline-option-label">Operator notes</span>
                    <input
                      type="text"
                      value={certForm.notes}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setCertForm((f) => ({ ...f, notes: e.target.value }));
                      }}
                    />
                  </label>
                </>
              )}
              {templateId === "coursera_course" && (
                <>
                  <label className="outline-option">
                    <span className="outline-option-label">Course title</span>
                    <input
                      type="text"
                      value={courseForm.title}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setCourseForm((f) => ({ ...f, title: e.target.value }));
                      }}
                    />
                  </label>
                  <label className="outline-option">
                    <span className="outline-option-label">Course URL</span>
                    <input
                      type="url"
                      value={courseForm.url}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setCourseForm((f) => ({ ...f, url: e.target.value }));
                      }}
                    />
                  </label>
                  <label className="outline-option">
                    <span className="outline-option-label">Estimated hours</span>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={courseForm.estimatedHours}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setCourseForm((f) => ({ ...f, estimatedHours: e.target.value }));
                      }}
                    />
                  </label>
                </>
              )}
              {templateId === "coursera_module" && (
                <>
                  <label className="outline-option">
                    <span className="outline-option-label">Module title</span>
                    <input
                      type="text"
                      value={moduleForm.title}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setModuleForm((f) => ({ ...f, title: e.target.value }));
                      }}
                    />
                  </label>
                  <label className="outline-option">
                    <span className="outline-option-label">Estimated hours</span>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={moduleForm.estimatedHours}
                      onChange={(e) => {
                        invalidateProposePreview();
                        setModuleForm((f) => ({ ...f, estimatedHours: e.target.value }));
                      }}
                    />
                  </label>
                </>
              )}
              <p className="outline-help muted small">
                Module and course scaffolds still include sample tasks in JSON — use Raw JSON or
                upload for full edits.
              </p>
            </div>
          ) : (
            <textarea
              className="outline-input"
              rows={8}
              value={jsonText}
              onChange={(e) => {
                invalidateProposePreview();
                setJsonText(e.target.value);
                setError(null);
              }}
              placeholder="Paste or edit outline JSON"
              aria-label="Template outline JSON"
            />
          )}

          <div className="outline-upload-row">
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              className="outline-file-input"
              onChange={handleFile}
              aria-label="Upload outline JSON file"
            />
            <button
              type="button"
              className="btn secondary small"
              onClick={() => fileInputRef.current?.click()}
            >
              Upload .json
            </button>
            <button
              type="button"
              className="btn secondary small"
              disabled={!detailQuery.data?.example_outline}
              onClick={() => {
                if (detailQuery.data?.example_outline) {
                  downloadJson(`${templateId}-example.json`, detailQuery.data.example_outline);
                }
              }}
            >
              Download example JSON
            </button>
            <label className="outline-skip">
              <input
                type="checkbox"
                checked={skipOptional}
                onChange={(e) => {
                  invalidateProposePreview();
                  setSkipOptional(e.target.checked);
                }}
              />
              Skip optional items (preview exclude)
            </label>
          </div>

          <div className="outline-actions-bar">
            <button type="submit" className="btn primary small" disabled={proposeMutation.isPending}>
              {proposeMutation.isPending ? "Proposing…" : "Propose preview"}
            </button>
            {entities && entities.length > 0 && (
              <button
                type="button"
                className="btn primary small"
                disabled={applyMutation.isPending}
                onClick={handleApply}
              >
                {applyMutation.isPending ? "Applying…" : "Apply"}
              </button>
            )}
            {entities && (
              <button
                type="button"
                className="btn secondary small"
                onClick={() => invalidateProposePreview()}
              >
                Clear preview
              </button>
            )}
          </div>
        </form>

        {proposeMeta?.warnings?.length ? (
          <ul className="templates-warnings">
            {proposeMeta.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        ) : null}

        {summary && entities && (
          <p className="outline-summary muted small">{formatSummary(summary)}</p>
        )}

        {entities && entities.length > 0 && (
          <ul className="outline-action-list">
            {entities.map((entity, index) => (
              <EntityReviewRow
                key={entity.clientId}
                entity={entity}
                index={index}
                resolvedDefaults={proposeMeta?.resolved_defaults}
                onChange={(i, next) =>
                  setEntities((prev) => (prev ? prev.map((a, j) => (j === i ? next : a)) : prev))
                }
              />
            ))}
          </ul>
        )}

        {receipt && idempotencyKey ? (
          <ReceiptBlock receipt={receipt} idempotencyKey={idempotencyKey} />
        ) : null}

        {error && <p className="form-error">{error}</p>}
      </Modal>
    </div>
  );
}
