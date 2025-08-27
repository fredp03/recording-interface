import { useState, useEffect } from 'react';

const BACKEND_URL = 'http://localhost:3001';

const useMIDIController = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/status`);
        const data = await response.json();
        setIsConnected(data.connected);
        setIsPlaying(data.is_playing);
        console.log('MIDI Status:', data);
      } catch (error) {
        console.error('Failed to check MIDI status:', error);
        setIsConnected(false);
      }
    };

    const pollPlayState = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/play-state`);
        const data = await response.json();
        setIsPlaying(data.is_playing);
      } catch (error) {
        console.error('Failed to get play state:', error);
      }
    };

    // Initial connection check
    checkConnection();

    // Poll for connection status every 5 seconds
    const connectionInterval = setInterval(checkConnection, 5000);

    // Poll for play state every 500ms for responsive UI updates
    const playStateInterval = setInterval(pollPlayState, 500);

    // Cleanup function
    return () => {
      clearInterval(connectionInterval);
      clearInterval(playStateInterval);
    };
  }, []);

  const togglePlayPause = async () => {
    if (!isConnected) {
      console.warn('MIDI not connected');
      return;
    }

    try {
      const response = await fetch(`${BACKEND_URL}/api/play`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          play: !isPlaying
        })
      });

      const data = await response.json();
      
      if (data.status === 'ok') {
        setIsPlaying(data.is_playing);
        console.log(`Play state changed: ${data.action}`);
      } else {
        console.error('Failed to toggle play/pause:', data.message);
      }
    } catch (error) {
      console.error('Failed to toggle play/pause:', error);
    }
  };

  return {
    isConnected,
    isPlaying,
    togglePlayPause
  };
};

export default useMIDIController;
