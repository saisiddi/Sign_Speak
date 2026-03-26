export default function VideoFeed({ currentSign }) {
  return (
    <div className="video-container">
      <img src="http://localhost:8001/video_feed" alt="Video Feed" className="video-feed" />
      {currentSign && currentSign.sign && (
        <>
          <div className="overlay-sign">{currentSign.sign}</div>
          <div className="overlay-confidence">{(currentSign.confidence * 100).toFixed(0)}%</div>
        </>
      )}
    </div>
  );
}
