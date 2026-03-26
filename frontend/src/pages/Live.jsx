import VideoFeed from '../components/VideoFeed';
import SignDisplay from '../components/SignDisplay';
import Transcript from '../components/Transcript';
import EventLog from '../components/EventLog';
import GestureRef from '../components/GestureRef';
import { useOutletContext } from 'react-router-dom';

export default function Live() {
  const { currentSign, transcript, lastSpoken, eventLog, speak, clearTranscript } = useOutletContext();

  return (
    <div className="layout-grid">
      <div className="camera-section">
        <VideoFeed currentSign={currentSign} />
        <SignDisplay lastSpoken={lastSpoken} />
      </div>
      <div className="controls-section">
        <Transcript transcript={transcript} onSpeak={speak} onClear={clearTranscript} />
        <GestureRef />
        <EventLog logs={eventLog} />
      </div>
    </div>
  );
}
