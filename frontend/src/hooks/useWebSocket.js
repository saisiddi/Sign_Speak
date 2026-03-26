import { useState, useEffect, useCallback, useRef } from 'react';

const WEBSOCKET_URL = 'ws://localhost:8001/ws';

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [ttsBackend, setTtsBackend] = useState('');
  const [currentSign, setCurrentSign] = useState(null);
  const [displayText, setDisplayText] = useState('');
  const [transcript, setTranscript] = useState('');
  const [lastSpoken, setLastSpoken] = useState('');
  const [eventLog, setEventLog] = useState([]);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const addLog = useCallback((msg, type = 'normal') => {
    const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    setEventLog(prev => [{ id: Date.now() + Math.random(), time: timestamp, msg, type }, ...prev].slice(0, 50));
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WEBSOCKET_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      addLog('Connected to SignSpeak backend', 'important');
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };

    ws.onclose = () => {
      setIsConnected(false);
      addLog('Disconnected from backend. Retrying...', 'important');
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 2000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket Error', error);
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case 'init':
            setTtsBackend(data.tts_backend || '');
            break;
          case 'sign':
            setCurrentSign({
              sign: data.sign,
              confidence: data.confidence || 0,
            });
            setDisplayText(data.text || data.sign || '');
            break;
          case 'text':
            setTranscript(data.text);
            setDisplayText(data.text || '');
            break;
          case 'speak':
            setLastSpoken(data.word);
            addLog(`SPOKE: ${data.word}`, 'important');
            break;
          default:
            addLog(`Unknown event: ${data.type}`);
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
  }, [addLog]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  const speak = async (text) => {
    try {
      await fetch('http://localhost:8001/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
    } catch (e) {
      console.error('Failed to trigger speak', e);
    }
  };

  const clearTranscript = async () => {
    try {
      await fetch('http://localhost:8001/reset', { method: 'POST' });
      setTranscript('');
      addLog('Cleared transcript');
    } catch (e) {
      console.error('Failed to clear', e);
    }
  };

  return {
    isConnected,
    ttsBackend,
    currentSign,
    displayText,
    transcript,
    lastSpoken,
    eventLog,
    speak,
    clearTranscript
  };
}
