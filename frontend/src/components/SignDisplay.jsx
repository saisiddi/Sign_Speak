export default function SignDisplay({ lastSpoken }) {
  return (
    <div className="panel-row">
      <div className="section-label">Last Spoken</div>
      <div className="spoken-word-display">
        {lastSpoken || "—"}
      </div>
    </div>
  );
}
