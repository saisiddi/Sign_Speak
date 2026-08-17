import { useEffect, useState } from 'react';
import VideoFeed from '../components/VideoFeed';
import SignDisplay from '../components/SignDisplay';
import Transcript from '../components/Transcript';
import EventLog from '../components/EventLog';
import GestureRef from '../components/GestureRef';
import { useOutletContext } from 'react-router-dom';

const MODES = [
  { id: 'snippets', label: 'Gestures' },
  { id: 'asl', label: 'ASL Spell' },
  { id: 'both', label: 'Both' },
];

export default function Live() {
  const { currentSign, displayText, transcript, lastSpoken, eventLog, speak, clearTranscript } = useOutletContext();
  const [mode, setMode] = useState('both');

  useEffect(() => {
    fetch('http://localhost:8001/mode')
      .then(r => r.json())
      .then(d => d.mode && setMode(d.mode))
      .catch(() => {});
  }, []);

  const changeMode = (m) => {
    setMode(m);
    fetch('http://localhost:8001/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: m }),
    }).catch(() => {});
  };

  return (
    <div className="layout-grid">
      <div className="camera-section">
        <div className="mode-switcher">
          {MODES.map(m => (
            <button
              key={m.id}
              className={`mode-btn ${mode === m.id ? 'mode-btn-active' : ''}`}
              onClick={() => changeMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
        <VideoFeed />
        <SignDisplay displayText={displayText} lastSpoken={lastSpoken} />
      </div>
      <div className="controls-section">
        <Transcript transcript={transcript} onSpeak={speak} onClear={clearTranscript} />
        <GestureRef />
        <EventLog logs={eventLog} />
      </div>
    </div>
  );
}
