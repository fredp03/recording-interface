import { useState, useEffect, useCallback } from 'react';
import { midiController } from '../utils/midiController';

export const useMIDIController = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState({
    isConnected: false,
    inputPort: null,
    outputPort: null
  });

  // Initialize MIDI controller
  useEffect(() => {
    const initializeMIDI = async () => {
      try {
        const success = await midiController.initialize();
        const status = midiController.getConnectionStatus();
        
        setIsConnected(success);
        setConnectionStatus(status);
        
        if (success) {
          console.log('MIDI Controller initialized successfully');
        }
      } catch (error) {
        console.error('Failed to initialize MIDI controller:', error);
      }
    };

    initializeMIDI();

    // Cleanup on unmount
    return () => {
      midiController.disconnect();
    };
  }, []);

  // Set up play state callback
  useEffect(() => {
    const handlePlayStateChange = (playing) => {
      setIsPlaying(playing);
      console.log('Play state changed from Ableton:', playing);
    };

    midiController.onPlayStateChange(handlePlayStateChange);

    return () => {
      midiController.onPlayStateChange(null);
    };
  }, []);

  // Function to toggle play/pause
  const togglePlayPause = useCallback(() => {
    midiController.sendPlayPress();
    // Note: The actual state change will come from Ableton via MIDI feedback
  }, []);

  // Function to manually reconnect
  const reconnect = useCallback(async () => {
    try {
      const success = await midiController.initialize();
      const status = midiController.getConnectionStatus();
      
      setIsConnected(success);
      setConnectionStatus(status);
      
      return success;
    } catch (error) {
      console.error('Failed to reconnect MIDI:', error);
      return false;
    }
  }, []);

  return {
    isConnected,
    isPlaying,
    connectionStatus,
    togglePlayPause,
    reconnect
  };
};
