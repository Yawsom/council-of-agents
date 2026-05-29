interface SpeechBubbleProps {
  text: string;
  visible?: boolean;
}

export function SpeechBubble({ text, visible = true }: SpeechBubbleProps) {
  if (!visible || !text) return null;
  return (
    <div className="speech-bubble" role="note">
      {text}
      <style>{`
        .speech-bubble {
          position: absolute;
          bottom: calc(100% + 8px);
          left: 50%;
          transform: translateX(-50%);
          max-width: 160px;
          padding: 0.4rem 0.55rem;
          font-size: 0.68rem;
          line-height: 1.3;
          color: var(--bg-deep);
          background: var(--parchment);
          border-radius: var(--radius-md);
          box-shadow: 0 4px 12px rgba(0,0,0,0.35);
          animation: bubbleIn 0.35s ease backwards;
          pointer-events: none;
          z-index: 2;
        }
        .speech-bubble::after {
          content: "";
          position: absolute;
          bottom: -6px;
          left: 50%;
          transform: translateX(-50%);
          border: 6px solid transparent;
          border-top-color: var(--parchment);
        }
      `}</style>
    </div>
  );
}
