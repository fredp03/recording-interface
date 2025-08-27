import { useState, useEffect } from 'react';

const BACKEND_URL = 'http://localhost:3001';

const useMIDIController = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [backingVolume, setBackingVolume] = useState(0.0);
  const [trackDiscoveryComplete, setTrackDiscoveryComplete] = useState(false);

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

    const pollTrackVolumes = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/track-volumes`);
        const data = await response.json();
        setBackingVolume(data.backing);
        setTrackDiscoveryComplete(data.backing_track_discovered);
      } catch (error) {
        console.error('Failed to get track volumes:', error);
      }
    };

    // Initial connection check
    checkConnection();

    // Poll for connection status every 5 seconds
    const connectionInterval = setInterval(checkConnection, 5000);

    // Poll for play state every 500ms for responsive UI updates
    const playStateInterval = setInterval(pollPlayState, 500);

    // Poll for track volumes every 1 second
    const volumeInterval = setInterval(pollTrackVolumes, 1000);

    // Cleanup function
    return () => {
      clearInterval(connectionInterval);
      clearInterval(playStateInterval);
      clearInterval(volumeInterval);
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

  const sendFaderChange = async (trackName, value) => {
    console.log(`Attempting to send fader change for ${trackName}: ${value}`);
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/fader`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          track: trackName.toLowerCase(),
          value: value
        })
      });

      const data = await response.json();
      console.log('Fader API response:', data);
      
      if (data.status === 'ok') {
        console.log(`Fader changed for ${trackName}: ${value}`);
        return true;
      } else {
        console.error('Failed to send fader change:', data.message);
        return false;
      }
    } catch (error) {
      console.error('Failed to send fader change:', error);
      return false;
    }
  };

  const triggerTrackDiscovery = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/discover-tracks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      const data = await response.json();
      
      if (data.status === 'ok') {
        console.log('Track discovery triggered');
        return true;
      } else {
        console.error('Failed to trigger track discovery:', data.message);
        return false;
      }
    } catch (error) {
      console.error('Failed to trigger track discovery:', error);
      return false;
    }
  };

  return {
    isConnected,
    isPlaying,
    backingVolume,
    trackDiscoveryComplete,
    togglePlayPause,
    sendFaderChange,
    triggerTrackDiscovery
  };
};

export default useMIDIController;
