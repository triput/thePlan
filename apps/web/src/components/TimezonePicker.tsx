import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import {
  filterIanaTimeZones,
  listIanaTimeZonesWithCurrent,
} from "../timezones";

interface TimezonePickerProps {
  value: string;
  onChange: (timezone: string) => void;
  disabled?: boolean;
  id?: string;
}

/**
 * Searchable IANA timezone combobox. Options from Intl.supportedValuesOf
 * (or fallback list); keeps exotic current values selectable.
 */
export function TimezonePicker({
  value,
  onChange,
  disabled = false,
  id,
}: TimezonePickerProps) {
  const autoId = useId();
  const listboxId = `${autoId}-listbox`;
  const inputId = id ?? `${autoId}-input`;

  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const zones = useMemo(() => listIanaTimeZonesWithCurrent(value), [value]);

  const [query, setQuery] = useState(value);
  /** Empty while open until the user types — so focus shows the full catalog. */
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  const filtered = useMemo(
    () => filterIanaTimeZones(zones, filter),
    [zones, filter],
  );

  useEffect(() => {
    if (!open) return;
    if (filter === "") {
      const idx = zones.indexOf(value);
      setActiveIndex(idx >= 0 ? idx : 0);
    } else {
      setActiveIndex(0);
    }
  }, [filter, open, zones, value]);

  useEffect(() => {
    if (!open || !listRef.current) return;
    const active = listRef.current.querySelector<HTMLElement>(
      ".timezone-picker-option.active",
    );
    active?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open, filtered]);

  const selectZone = (zone: string) => {
    onChange(zone);
    setQuery(zone);
    setFilter("");
    setOpen(false);
  };

  const commitOrRevert = () => {
    const trimmed = query.trim();
    if (trimmed && zones.includes(trimmed)) {
      if (trimmed !== value) onChange(trimmed);
      setQuery(trimmed);
      setFilter("");
      return;
    }
    const match = zones.find((z) => z.toLowerCase() === trimmed.toLowerCase());
    if (match) {
      if (match !== value) onChange(match);
      setQuery(match);
      setFilter("");
      return;
    }
    setQuery(value);
    setFilter("");
  };

  const close = () => {
    commitOrRevert();
    setOpen(false);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setQuery(value);
      setFilter("");
      setOpen(false);
      inputRef.current?.blur();
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        setFilter("");
        return;
      }
      if (filtered.length === 0) return;
      setActiveIndex((i) => (i + 1) % filtered.length);
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!open || filtered.length === 0) return;
      setActiveIndex((i) => (i <= 0 ? filtered.length - 1 : i - 1));
      return;
    }

    if (e.key === "Enter") {
      if (open) {
        e.preventDefault();
        if (filtered.length > 0) {
          selectZone(filtered[Math.min(activeIndex, filtered.length - 1)]);
        }
      }
      return;
    }

    if (e.key === "Tab") {
      close();
    }
  };

  const showList = open && !disabled;

  return (
    <div className="timezone-picker" ref={rootRef}>
      <input
        ref={inputRef}
        id={inputId}
        type="text"
        className="timezone-picker-input"
        value={query}
        disabled={disabled}
        spellCheck={false}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={listboxId}
        aria-activedescendant={
          showList && filtered[activeIndex]
            ? `${listboxId}-opt-${activeIndex}`
            : undefined
        }
        placeholder="Search timezones…"
        onChange={(e) => {
          setQuery(e.target.value);
          setFilter(e.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          setOpen(true);
          setFilter("");
        }}
        onBlur={() => {
          window.setTimeout(() => {
            if (!rootRef.current?.contains(document.activeElement)) {
              close();
            }
          }, 0);
        }}
        onKeyDown={handleKeyDown}
      />
      {showList && (
        <ul
          ref={listRef}
          id={listboxId}
          className="timezone-picker-list"
          role="listbox"
        >
          {filtered.length === 0 ? (
            <li className="timezone-picker-empty muted small" role="presentation">
              No matching timezone
            </li>
          ) : (
            filtered.map((zone, index) => (
              <li key={zone} role="presentation">
                <button
                  type="button"
                  id={`${listboxId}-opt-${index}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  className={`timezone-picker-option${
                    index === activeIndex ? " active" : ""
                  }${zone === value ? " current" : ""}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => selectZone(zone)}
                >
                  {zone}
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
