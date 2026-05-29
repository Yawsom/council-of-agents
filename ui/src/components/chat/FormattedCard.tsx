import type { FormattedSection } from "@/data/formatTranscript";

export function FormattedCard({
  stepLabel,
  sections,
}: {
  stepLabel: string;
  sections: FormattedSection[];
}) {
  return (
    <article className="fmt-card">
      <header className="fmt-card-header">{stepLabel}</header>
      <div className="fmt-card-body">
        {sections.map((section, si) => (
          <div key={si} className="fmt-section">
            {section.heading && <h4 className="fmt-heading">{section.heading}</h4>}
            <ul className="fmt-list">
              {section.items.map((item, ii) => (
                <li key={ii} className={`fmt-item fmt-${item.kind} fmt-tone-${item.tone ?? "neutral"}`}>
                  {item.kind === "claim" && <span className="fmt-tag">claim</span>}
                  {item.kind === "evidence" && <span className="fmt-tag">evidence</span>}
                  {item.kind === "edge" && <span className="fmt-tag">link</span>}
                  {item.kind === "update" && <span className="fmt-tag">update</span>}
                  {item.kind === "badge" && (
                    <span className={`fmt-badge fmt-badge-${item.tone ?? "neutral"}`}>
                      {item.text}
                    </span>
                  )}
                  {item.kind !== "badge" && <p className="fmt-text">{item.text}</p>}
                  {item.meta && <p className="fmt-meta">{item.meta}</p>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </article>
  );
}
