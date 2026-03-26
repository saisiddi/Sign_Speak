import { useState, useEffect } from 'react';

const DEFAULT_MAPPING = {
  "Open_Palm": "Hello",
  "Thumb_Up": "Yes",
  "Thumb_Down": "No",
  "Victory": "Thank you",
  "Pointing_Up": "I need help",
  "Closed_Fist": "Please stop",
  "ILoveYou": "I love you"
};

export default function GestureRef() {
  const [mapping, setMapping] = useState(DEFAULT_MAPPING);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('signspeask_snippets');
      if (stored) {
        setMapping(JSON.parse(stored));
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  return (
    <div className="panel-row">
      <div className="section-label">Gesture Index</div>
      <div className="ref-table">
        {Object.entries(mapping).map(([gesture, phrase]) => (
          <div style={{ display: 'contents' }} key={gesture}>
            <div className="ref-cell gesture">{gesture.replace('_', ' ')}</div>
            <div className="ref-cell phrase">{phrase}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
