import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createSection } from "../api";

interface CreateSectionFormProps {
  projectId: string;
}

export function CreateSectionForm({ projectId }: CreateSectionFormProps) {
  const [expanded, setExpanded] = useState(false);
  const [title, setTitle] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: createSection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sections", projectId] });
      setTitle("");
      setExpanded(false);
    },
  });

  if (!expanded) {
    return (
      <button type="button" className="link-btn" onClick={() => setExpanded(true)}>
        + Add section
      </button>
    );
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    mutation.mutate({ project_id: projectId, title: trimmed });
  };

  return (
    <form className="inline-form section-form" onSubmit={handleSubmit}>
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Section name"
        autoFocus
      />
      <button type="submit" className="btn primary small" disabled={mutation.isPending}>
        Add
      </button>
      <button
        type="button"
        className="btn secondary small"
        onClick={() => {
          setExpanded(false);
          setTitle("");
        }}
      >
        Cancel
      </button>
      {mutation.isError && (
        <span className="form-error inline">{(mutation.error as Error).message}</span>
      )}
    </form>
  );
}
