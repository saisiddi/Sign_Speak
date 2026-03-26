import { useState, useEffect } from 'react';

const LIBRARY = {
  Meeting: [
    "Good morning everyone", "I have a question", "Can you repeat that please", 
    "I agree with that", "I disagree respectfully", "Can you speak slower please", 
    "I need a moment to think", "Can you share your screen", "My connection is unstable", 
    "Let me get back to you on that"
  ],
  Personal: [
    "How are you", "I am fine thank you", "Nice to meet you", "I did not understand", 
    "Can you write it down", "I am hungry", "I am tired", "I need help", 
    "Please be patient with me", "I use sign language to communicate"
  ],
  Interview: [
    "Thank you for this opportunity", "I am passionate about this field", 
    "Can you please repeat the question", "I need a moment to answer", 
    "I have experience in this area", "My strength is problem solving", 
    "I am a quick learner", "I look forward to joining your team"
  ],
  Emergency: [
    "I need medical help", "Please call someone", "I am in pain", 
    "Call my family", "I cannot breathe properly"
  ]
};

const GESTURES = [
  { id: "Open_Palm", name: "Open Palm" },
  { id: "Thumb_Up", name: "Thumbs Up" },
  { id: "Thumb_Down", name: "Thumbs Down" },
  { id: "Victory", name: "Victory" },
  { id: "Pointing_Up", name: "Pointing Up" },
  { id: "Closed_Fist", name: "Closed Fist" },
  { id: "ILoveYou", name: "ILoveYou" }
];

const DEFAULT_MAPPING = {
  "Open_Palm": "Hello",
  "Thumb_Up": "Yes",
  "Thumb_Down": "No",
  "Victory": "Thank you",
  "Pointing_Up": "I need help",
  "Closed_Fist": "Please stop",
  "ILoveYou": "I love you"
};

export default function Snippets() {
  const [activeTab, setActiveTab] = useState('Meeting');
  const [assignments, setAssignments] = useState(DEFAULT_MAPPING);
  const [customPhrase, setCustomPhrase] = useState('');
  const [customGesture, setCustomGesture] = useState('Open_Palm');

  useEffect(() => {
    try {
      const stored = localStorage.getItem('signspeask_snippets');
      if (stored) {
        setAssignments(JSON.parse(stored));
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const handleAssign = (gestureId, phrase) => {
    const newAssignments = { ...assignments, [gestureId]: phrase };
    setAssignments(newAssignments);
  };

  const handleSave = () => {
    localStorage.setItem('signspeask_snippets', JSON.stringify(assignments));
    alert('Snippets saved successfully!');
  };

  const handleReset = () => {
    setAssignments(DEFAULT_MAPPING);
    localStorage.removeItem('signspeask_snippets');
  };

  const handleCustomAssign = () => {
    if (customPhrase.trim()) {
      handleAssign(customGesture, customPhrase.trim());
      setCustomPhrase('');
    }
  };

  return (
    <div className="page-container">
      <h1 className="page-title">Snippets</h1>
      
      <div className="heavy-divider" />
      
      <div className="section-label">Library</div>
      <div className="tabs-header">
        {Object.keys(LIBRARY).map(tab => (
          <button 
            key={tab} 
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="phrase-grid">
        {LIBRARY[activeTab].map((phrase, idx) => (
          <div key={idx} className="phrase-card hard-shadow" onClick={() => setCustomPhrase(phrase)}>
            {phrase}
          </div>
        ))}
      </div>

      <div className="heavy-divider" />

      <div className="section-label">Custom Assignment</div>
      <div className="assignment-row" style={{ borderBottom: 'none' }}>
        <select 
          value={customGesture} 
          onChange={(e) => setCustomGesture(e.target.value)}
        >
          {GESTURES.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input 
            type="text" 
            placeholder="Type custom phrase or click a phrase above..." 
            value={customPhrase}
            onChange={(e) => setCustomPhrase(e.target.value)}
          />
          <button className="btn-secondary" onClick={handleCustomAssign}>Assign</button>
        </div>
      </div>

      <div className="heavy-divider" />

      <div className="section-label">Current Assignments</div>
      <div className="assignment-grid">
        {GESTURES.map(g => (
          <div key={g.id} className="assignment-row">
            <span className="gesture-label">{g.name}</span>
            <select 
              value={assignments[g.id] || ''}
              onChange={(e) => handleAssign(g.id, e.target.value)}
            >
              <option value={assignments[g.id]}>{assignments[g.id]}</option>
              {Object.values(LIBRARY).flat().filter(p => p !== assignments[g.id]).map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '16px', marginTop: '32px' }}>
        <button className="btn-primary" onClick={handleSave}>Save Changes</button>
        <button className="btn-danger" onClick={handleReset}>Reset Defaults</button>
      </div>

    </div>
  );
}
