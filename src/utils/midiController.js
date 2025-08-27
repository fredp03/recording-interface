// HTTP-based MIDI Controller for Flask Backend Communication
class MIDIController {
  constructor() {
    this.baseURL = window.location.origin; // Use same origin as the UI
    this.isConnected = false;
    this.playStateCallback = null;
    this.playStatePollingInterval = null;
    this.connectionPollingInterval = null;
    
    console.log(`MIDI Controller initialized with backend at ${this.baseURL}`);
  }

  async initialize() {
    try {
      console.log('Initializing HTTP MIDI controller...');
      
      // Check connection to backend
      const connected = await this.checkConnection();
      
      if (connected) {
        // Start polling for play state changes
        this.startPlayStatePolling();
        // Start polling for connection status
        this.startConnectionPolling();
        console.log('HTTP MIDI Controller initialized successfully');
      }
      
      return connected;
    } catch (error) {
      console.error('Failed to initialize HTTP MIDI controller:', error);
      return false;
    }
  }

  async checkConnection() {
    try {
      const response = await fetch(`${this.baseURL}/api/status`);
      const data = await response.json();
      
      this.isConnected = data.connected;
      console.log(`Backend connection: ${this.isConnected ? 'Connected' : 'Disconnected'}`);
      console.log(`MIDI Output Port (Commands): ${data.midi_output_port}`);
      console.log(`MIDI Input Port (Track Info): ${data.midi_input_port}`);
      
      return response.ok;
    } catch (error) {
      console.error('Failed to check backend connection:', error);
      this.isConnected = false;
      return false;
    }
  }

  startPlayStatePolling() {
    // Poll play state every 200ms for responsive UI
    this.playStatePollingInterval = setInterval(async () => {
      try {
        const response = await fetch(`${this.baseURL}/api/play-state`);
        const data = await response.json();
        
        if (this.playStateCallback && response.ok) {
          this.playStateCallback(data.is_playing);
        }
      } catch (error) {
        console.error('Error polling play state:', error);
      }
    }, 200);
  }

  startConnectionPolling() {
    // Check connection status every 5 seconds
    this.connectionPollingInterval = setInterval(async () => {
      await this.checkConnection();
    }, 5000);
  }

  stopPolling() {
    if (this.playStatePollingInterval) {
      clearInterval(this.playStatePollingInterval);
      this.playStatePollingInterval = null;
    }
    if (this.connectionPollingInterval) {
      clearInterval(this.connectionPollingInterval);
      this.connectionPollingInterval = null;
    }
  }

  async sendPlay() {
    try {
      console.log('Sending PLAY command to backend...');
      const response = await fetch(`${this.baseURL}/api/play`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ play: true }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        console.log('PLAY command sent successfully:', data);
        return true;
      } else {
        console.error('Failed to send PLAY command:', data.message);
        return false;
      }
    } catch (error) {
      console.error('Error sending PLAY command:', error);
      return false;
    }
  }

  async sendStop() {
    try {
      console.log('Sending STOP command to backend...');
      const response = await fetch(`${this.baseURL}/api/play`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ play: false }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        console.log('STOP command sent successfully:', data);
        return true;
      } else {
        console.error('Failed to send STOP command:', data.message);
        return false;
      }
    } catch (error) {
      console.error('Error sending STOP command:', error);
      return false;
    }
  }

  async togglePlay() {
    try {
      console.log('Toggling play state...');
      const response = await fetch(`${this.baseURL}/api/play`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}), // Empty body means toggle current state
      });
      
      const data = await response.json();
      
      if (response.ok) {
        console.log('Play state toggled successfully:', data);
        return true;
      } else {
        console.error('Failed to toggle play state:', data.message);
        return false;
      }
    } catch (error) {
      console.error('Error toggling play state:', error);
      return false;
    }
  }

  async sendFaderChange(trackName, value) {
    try {
      console.log(`Sending fader change for ${trackName}: ${value}`);
      const response = await fetch(`${this.baseURL}/api/fader`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          track: trackName,
          value: value 
        }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        console.log('Fader command sent successfully:', data);
        return true;
      } else {
        console.error('Failed to send fader command:', data.message);
        return false;
      }
    } catch (error) {
      console.error('Error sending fader command:', error);
      return false;
    }
  }

  async getTrackVolumes() {
    try {
      const response = await fetch(`${this.baseURL}/api/track-volumes`);
      const data = await response.json();
      
      if (response.ok) {
        return data;
      } else {
        console.error('Failed to get track volumes');
        return null;
      }
    } catch (error) {
      console.error('Error getting track volumes:', error);
      return null;
    }
  }

  async triggerTrackDiscovery() {
    try {
      console.log('Triggering track discovery...');
      const response = await fetch(`${this.baseURL}/api/discover-tracks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      const data = await response.json();
      
      if (response.ok) {
        console.log('Track discovery triggered:', data.message);
        return true;
      } else {
        console.error('Failed to trigger track discovery:', data.message);
        return false;
      }
    } catch (error) {
      console.error('Error triggering track discovery:', error);
      return false;
    }
  }

  getConnectionStatus() {
    return {
      isConnected: this.isConnected,
      inputPort: this.isConnected ? 'HTTP Backend' : null,
      outputPort: this.isConnected ? 'HTTP Backend' : null,
    };
  }

  setPlayStateCallback(callback) {
    this.playStateCallback = callback;
  }

  disconnect() {
    console.log('Disconnecting HTTP MIDI controller...');
    this.stopPolling();
    this.isConnected = false;
    this.playStateCallback = null;
  }

  // Legacy methods for compatibility
  async connectToIACDriver() {
    return await this.checkConnection();
  }

  // Compatibility methods that are no-ops in HTTP mode
  handleMIDIStateChange() {
    // Not needed for HTTP implementation
  }

  handleMIDIMessage() {
    // Not needed for HTTP implementation  
  }

  sendPlayPress() {
    return this.sendPlay();
  }

  onPlayStateChange(callback) {
    this.setPlayStateCallback(callback);
  }
}

// Export singleton instance
export const midiController = new MIDIController();
