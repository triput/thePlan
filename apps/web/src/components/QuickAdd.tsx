import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createTask,
  parseQuickAdd,
  type Project,
  type QuickAddParseResponse,
  type TaskPriority,
} from "../api";
import { formatDuration, viewKey, type ViewSelection } from "../view";
import { emitToast } from "./ToastHost";

export interface QuickAddHandle {
  focus: () => void;
}

interface QuickAddProps {
  view: ViewSelection;
  projects: Project[];
}

function resolveProjectId(
  parsed: QuickAddParseResponse,
  projects: Project[],
  defaultProjectId: string | null,
): string | null {
  if (parsed.project_id) return parsed.project_id;

  for (const token of parsed.unresolved) {
    if (token.startsWith("project:")) {
      const name = token.slice("project:".length);
      const match = projects.find((p) => p.title.toLowerCase() === name.toLowerCase());
      if (match) return match.id;
    }
  }

  return defaultProjectId;
}

function ParseChips({ parsed }: { parsed: QuickAddParseResponse }) {
  const chips: string[] = [];
  if (parsed.priority) chips.push(parsed.priority.toUpperCase());
  if (parsed.estimated_duration_minutes) {
    chips.push(formatDuration(parsed.estimated_duration_minutes));
  }
  if (parsed.due_at) {
    chips.push(new Date(parsed.due_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }));
  }
  if (parsed.project_id) chips.push("project");
  if (parsed.unresolved.length > 0) chips.push(`unresolved: ${parsed.unresolved.join(", ")}`);

  if (chips.length === 0) return null;

  return (
    <div className="parse-chips" aria-live="polite">
      {chips.map((chip) => (
        <span key={chip} className="chip">
          {chip}
        </span>
      ))}
    </div>
  );
}

export const QuickAdd = forwardRef<QuickAddHandle, QuickAddProps>(function QuickAdd(
  { view, projects },
  ref,
) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<QuickAddParseResponse | null>(null);
  const queryClient = useQueryClient();

  useImperativeHandle(ref, () => ({
    focus: () => inputRef.current?.focus(),
  }));

  const defaultProjectId = view.type === "project" ? view.projectId : null;

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setText("");
      setPreview(null);
    },
  });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;

    try {
      const parsed = await parseQuickAdd(trimmed);
      setPreview(parsed);

      const projectId = resolveProjectId(parsed, projects, defaultProjectId);
      const isInbox = view.type === "inbox" && !projectId;

      await createMutation.mutateAsync({
        title: parsed.title,
        priority: (parsed.priority ?? "p4") as TaskPriority,
        due_at: parsed.due_at,
        estimated_duration_minutes: parsed.estimated_duration_minutes ?? undefined,
        project_id: isInbox ? null : projectId,
        section_id: parsed.section_id,
      });

      queryClient.invalidateQueries({ queryKey: ["tasks", viewKey(view)] });
    } catch {
      setPreview(null);
      emitToast("Couldn't create task");
    }
  };

  return (
    <div className="quick-add">
      <div className="quick-add-primary">
        <form onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="text"
            className="quick-add-input"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setPreview(null);
            }}
            placeholder="Quick add task…"
            aria-label="Quick add task"
          />
          <kbd className="quick-add-kbd" title="Focus with Q">
            Q
          </kbd>
        </form>
      </div>
      <div className="quick-add-meta">
        {preview && <ParseChips parsed={preview} />}
        <p className="quick-add-hint">
          Try: <code>Draft spec 1.5h p1 tomorrow #Project</code>
        </p>
        {createMutation.isError && (
          <p className="form-error">{(createMutation.error as Error).message}</p>
        )}
      </div>
    </div>
  );
});
