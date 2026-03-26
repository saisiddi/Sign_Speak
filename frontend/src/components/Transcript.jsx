export default function Transcript({ transcript, onSpeak, onClear }) {
  return (
    <div className="panel-row">
      <div className="section-label">Transcript</div>
      <div className="transcript-area">
        {transcript || <span className="font-sans" style={{ color: "var(--neutral-400)", fontSize: "14px" }}>Waiting for signs...</span>}
      </div>
      <div className="panel-row-controls">
        <button className="btn-primary" onClick={() => onSpeak(transcript)} disabled={!transcript}>Speak</button>
        <button className="btn-secondary" onClick={onClear}>Clear</button>
      </div>
    </div>
  );
}
