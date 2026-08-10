import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { searchTasks, type SearchTask } from "../api";
import { formatDue } from "../view";

export interface SearchBoxHandle {
  focus: () => void;
}

interface SearchBoxProps {
  onSelectTask: (taskId: string) => void;
}

const DEBOUNCE_MS = 250;

export const SearchBox = forwardRef<SearchBoxHandle, SearchBoxProps>(function SearchBox(
  { onSelectTask },
  ref,
) {
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  useImperativeHandle(ref, () => ({
    focus: () => {
      inputRef.current?.focus();
      setOpen(true);
    },
  }));

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  const searchQuery = useQuery({
    queryKey: ["search", debouncedQuery],
    queryFn: () => searchTasks(debouncedQuery, 20),
    enabled: debouncedQuery.length > 0,
  });

  const results = searchQuery.data?.items ?? [];
  const showResults = open && debouncedQuery.length > 0;

  useEffect(() => {
    setActiveIndex(-1);
  }, [debouncedQuery]);

  useEffect(() => {
    if (!showResults) return;
    const onPointerDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [showResults]);

  const selectResult = (task: SearchTask) => {
    onSelectTask(task.id);
    setOpen(false);
    setQuery("");
    setDebouncedQuery("");
    inputRef.current?.blur();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      inputRef.current?.blur();
      return;
    }

    if (!showResults || results.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i <= 0 ? results.length - 1 : i - 1));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      selectResult(results[activeIndex]);
    }
  };

  return (
    <div className="search-box" ref={rootRef}>
      <div className="search-input-wrap">
        <input
          ref={inputRef}
          type="search"
          className="search-input"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search tasks…"
          aria-label="Search tasks"
          aria-expanded={showResults}
          aria-controls="search-results"
          role="combobox"
          autoComplete="off"
        />
        <kbd className="search-kbd" title="Focus with /">
          /
        </kbd>
      </div>

      {showResults && (
        <div id="search-results" className="search-results" role="listbox">
          {searchQuery.isLoading && <p className="search-status muted">Searching…</p>}
          {searchQuery.isError && (
            <p className="search-status form-error">
              {(searchQuery.error as Error).message}
            </p>
          )}
          {!searchQuery.isLoading &&
            !searchQuery.isError &&
            results.length === 0 && (
              <p className="search-status muted">No tasks found.</p>
            )}
          {results.map((task, index) => (
            <button
              key={task.id}
              type="button"
              role="option"
              aria-selected={index === activeIndex}
              className={`search-result${index === activeIndex ? " active" : ""}`}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => selectResult(task)}
            >
              <span className="search-result-title">{task.title}</span>
              {task.project_title && (
                <span className="search-result-project">{task.project_title}</span>
              )}
              {task.due_at && (
                <span className="search-result-due">{formatDue(task.due_at)}</span>
              )}
              {task.labels.length > 0 && (
                <span className="search-result-labels">
                  {task.labels.map((label) => (
                    <span
                      key={label.id}
                      className="label-chip"
                      style={{ borderColor: label.color_hex, color: label.color_hex }}
                    >
                      {label.name}
                    </span>
                  ))}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
});
