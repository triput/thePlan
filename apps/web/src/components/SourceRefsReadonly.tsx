import type { SourceRef } from "../api";

interface SourceRefsReadonlyProps {
  sourceRefs: SourceRef[] | null | undefined;
}

export function SourceRefsReadonly({ sourceRefs }: SourceRefsReadonlyProps) {
  if (!sourceRefs?.length) return null;
  return (
    <div className="field source-refs-readonly">
      <span>Source references</span>
      <ul className="source-ref-list">
        {sourceRefs.map((ref) => (
          <li key={`${ref.system}:${ref.id}`}>
            <span className="source-ref-system">{ref.system}</span>
            {ref.url ? (
              <a href={ref.url} target="_blank" rel="noreferrer">
                {ref.id}
              </a>
            ) : (
              <span>{ref.id}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
