import { useOutletContext } from 'react-router-dom';
import { useState } from 'react';

export default function Settings() {
  const { ttsBackend } = useOutletContext();
  const [sensitivity, setSensitivity] = useState(8);
  const [cooldown, setCooldown] = useState(3);
  const [volume, setVolume] = useState(80);

  return (
    <div className="page-container">
      <h1 className="page-title">Settings</h1>
      
      <div className="heavy-divider" />

      <div className="settings-section">
        <div className="section-label">System Info</div>
        <div className="settings-row">
          <span className="settings-label">TTS Backend</span>
          <span className="font-mono">{ttsBackend || 'Unknown'}</span>
        </div>
      </div>

      <div className="settings-section">
        <div className="section-label">Detection Preferences</div>
        
        <div className="settings-row">
          <span className="settings-label">Gesture Hold Sensitivity ({sensitivity} frames)</span>
          <input 
            type="range" 
            min="4" max="12" step="1" 
            className="settings-control"
            value={sensitivity}
            onChange={(e) => setSensitivity(e.target.value)}
          />
        </div>

        <div className="settings-row">
          <span className="settings-label">Cooldown Duration ({cooldown}s)</span>
          <input 
            type="range" 
            min="1" max="5" step="0.5" 
            className="settings-control"
            value={cooldown}
            onChange={(e) => setCooldown(e.target.value)}
          />
        </div>
      </div>

      <div className="settings-section">
        <div className="section-label">Audio</div>
        <div className="settings-row">
          <span className="settings-label">Output Volume ({volume}%)</span>
          <input 
            type="range" 
            min="0" max="100" step="1" 
            className="settings-control"
            value={volume}
            onChange={(e) => setVolume(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
