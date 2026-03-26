export default function SignDisplay({ displayText, lastSpoken }) {
  return (
    <div className="panel-row">
      <div className="section-label">Detected Phrase</div>
      <div className="spoken-word-display">
        {displayText || "—"}
      </div>
      <div className="section-label" style={{ marginTop: '12px' }}>Last Spoken</div>
      <div className="spoken-word-display">
        {lastSpoken || "—"}
      </div>
    </div>
  );
}
