export default function EventLog({ logs }) {
  return (
    <div className="panel-row">
      <div className="section-label">Event Log</div>
      <div className="event-log">
        {logs.length === 0 && <div className="log-entry">No events yet</div>}
        {logs.map(log => (
          <div key={log.id} className={`log-entry ${log.type === 'important' ? 'important' : ''}`}>
            <span style={{ color: 'var(--neutral-400)', marginRight: '8px' }}>[{log.time}]</span>
            {log.msg}
          </div>
        ))}
      </div>
    </div>
  );
}
