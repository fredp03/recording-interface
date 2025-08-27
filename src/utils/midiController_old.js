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
      console.log(`MIDI Port: ${data.midi_port}`);
      
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

  handleMIDIStateChange() {
    // Not needed for HTTP implementation
  }

  handleMIDIMessage() {
    // Not needed for HTTP implementation  
  }
}

// Export singleton instance
export const midiController = new MIDIController();
        this.inputPort = input;
        this.inputPort.onmidimessage = this.handleMIDIMessage.bind(this);
        console.log('Connected to MIDI input:', input.name);
        break;
      }
    }
    
    // Find IAC Driver fader-mcu output
    for (const output of outputs.values()) {
      if (output.name.toLowerCase().includes('iac') && 
          output.name.toLowerCase().includes('fader-mcu')) {
        this.outputPort = output;
        console.log('Connected to MIDI output:', output.name);
        break;
      }
    }
    
    this.isConnected = !!(this.inputPort && this.outputPort);
    
    if (!this.isConnected) {
      console.warn('IAC Driver fader-mcu port not found. Available ports:');
      console.log('Inputs:', Array.from(inputs.values()).map(p => p.name));
      console.log('Outputs:', Array.from(outputs.values()).map(p => p.name));
    }
    
    return this.isConnected;
  }

  handleMIDIStateChange(event) {
    console.log('MIDI state changed:', event.port.name, event.port.state);
    
    // Attempt to reconnect if a port becomes available
    if (event.port.state === 'connected') {
      this.connectToIACDriver();
    }
  }

  handleMIDIMessage(message) {
    const [status, data1, data2] = message.data;
    
    console.log('MIDI message received:', {
      status: status.toString(16),
      data1: data1.toString(16),
      data2: data2.toString(16)
    });
    
    // Handle MCU play/stop messages
    if (status === this.MCU_COMMANDS.NOTE_ON || status === this.MCU_COMMANDS.NOTE_OFF) {
      const isPressed = status === this.MCU_COMMANDS.NOTE_ON && data2 > 0;
      
      switch (data1) {
        case this.MCU_COMMANDS.PLAY:
          if (this.playStateCallback) {
            this.playStateCallback(isPressed);
          }
          console.log('Play button:', isPressed ? 'pressed' : 'released');
          break;
          
        case this.MCU_COMMANDS.STOP:
          if (this.playStateCallback) {
            this.playStateCallback(false); // Stop means not playing
          }
          console.log('Stop button pressed');
          break;
          
        case this.MCU_COMMANDS.RECORD:
          console.log('Record button:', isPressed ? 'pressed' : 'released');
          break;
      }
    }
  }

  // Send play button press to Ableton
  sendPlayPress() {
    if (!this.isConnected || !this.outputPort) {
      console.warn('MIDI not connected');
      return;
    }
    
    // Send note on for play button
    this.outputPort.send([this.MCU_COMMANDS.NOTE_ON, this.MCU_COMMANDS.PLAY, 127]);
    
    // Send note off after short delay
    setTimeout(() => {
      this.outputPort.send([this.MCU_COMMANDS.NOTE_OFF, this.MCU_COMMANDS.PLAY, 0]);
    }, 50);
    
    console.log('Sent play command to Ableton');
  }

  // Register callback for play state changes from Ableton
  onPlayStateChange(callback) {
    this.playStateCallback = callback;
  }

  // Get connection status
  getConnectionStatus() {
    return {
      isConnected: this.isConnected,
      inputPort: this.inputPort?.name || null,
      outputPort: this.outputPort?.name || null
    };
  }

  // Cleanup
  disconnect() {
    if (this.inputPort) {
      this.inputPort.onmidimessage = null;
    }
    this.inputPort = null;
    this.outputPort = null;
    this.isConnected = false;
  }
}

// Create singleton instance
export const midiController = new MIDIController();
