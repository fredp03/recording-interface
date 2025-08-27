#!/usr/bin/env python3
"""
MIDI Controller Backend for Recording Interface

A Flask web application that provides HTTP endpoints for controlling 
Ableton Live via MIDI using the MCU protocol over IAC Driver.

Based on the working implementation from web-interface-luna.
"""

import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
import mido
from mido import Message
import threading
import time

# Configuration
MIDI_PORT_NAME = os.getenv('MIDI_PORT', 'IAC Driver fader-mcu')
HOST = '0.0.0.0'  # Listen on all network interfaces
PORT = int(os.getenv('PORT', 3001))  # Backend server port
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Global MIDI ports
midi_out = None
midi_in = None

# MCU protocol constants
MCU_COMMANDS = {
    'PLAY': 0x5E,
    'STOP': 0x5D,
    'RECORD': 0x5F,
    'CONTROL_CHANGE': 0xB0,
    'NOTE_ON': 0x90,
    'NOTE_OFF': 0x80
}

# Global state
current_play_state = False
play_state_callbacks = []

def initialize_midi():
    """Initialize virtual MIDI input/output ports."""
    global midi_out, midi_in

    try:
        # List available MIDI ports
        input_ports = mido.get_input_names()
        output_ports = mido.get_output_names()
        
        logger.info(f"Available MIDI input ports: {input_ports}")
        logger.info(f"Available MIDI output ports: {output_ports}")

        def open_port(port_name, port_list, port_type='output'):
            """Open MIDI port with fuzzy matching."""
            if port_name in port_list:
                logger.info(f"Successfully opened MIDI {port_type} port: {port_name}")
                if port_type == 'output':
                    return mido.open_output(port_name)
                else:
                    return mido.open_input(port_name)
            
            # Try fuzzy matching
            matching_ports = [p for p in port_list if port_name.lower() in p.lower()]
            if matching_ports:
                logger.info(f"Opened MIDI {port_type} port with partial match: {matching_ports[0]}")
                if port_type == 'output':
                    return mido.open_output(matching_ports[0])
                else:
                    return mido.open_input(matching_ports[0])
            
            logger.error(f"MIDI {port_type} port '{port_name}' not found!")
            logger.error("Please create a virtual MIDI port or check the port name.")
            logger.error(f"Available {port_type} ports: " + ", ".join(port_list) if port_list else "None")
            return None

        # Open output port for sending commands
        midi_out = open_port(MIDI_PORT_NAME, output_ports, 'output')
        
        # Open input port for receiving status updates
        midi_in = open_port(MIDI_PORT_NAME, input_ports, 'input')
        
        if midi_in:
            # Set up MIDI input callback
            midi_in.callback = handle_midi_message
            logger.info("MIDI input callback set up")

        return midi_out is not None

    except Exception as e:
        logger.error(f"Failed to initialize MIDI: {e}")
        return False

def handle_midi_message(message):
    """Handle incoming MIDI messages from Ableton Live."""
    global current_play_state
    
    try:
        if message.type == 'note_on':
            if message.note == MCU_COMMANDS['PLAY']:
                # Play button pressed in Ableton
                current_play_state = True
                logger.info("Received PLAY from Ableton Live")
                notify_play_state_change(True)
            elif message.note == MCU_COMMANDS['STOP']:
                # Stop button pressed in Ableton
                current_play_state = False
                logger.info("Received STOP from Ableton Live")
                notify_play_state_change(False)
        elif message.type == 'note_off':
            # Button released - we don't need to handle this for play/stop
            pass
            
    except Exception as e:
        logger.error(f"Error handling MIDI message: {e}")

def notify_play_state_change(is_playing):
    """Notify all registered callbacks about play state change."""
    for callback in play_state_callbacks:
        try:
            callback(is_playing)
        except Exception as e:
            logger.error(f"Error in play state callback: {e}")

def send_mcu_message(command, velocity=127):
    """Send a MCU protocol message."""
    if not midi_out:
        logger.error("MIDI output not initialized")
        return False

    try:
        # MCU uses note_on messages for transport controls
        msg = Message('note_on', channel=0, note=command, velocity=velocity)
        midi_out.send(msg)
        logger.info(f"Sent MCU command: 0x{command:02X} (velocity={velocity})")
        return True
    except Exception as e:
        logger.error(f"Error sending MCU message: {e}")
        return False

def send_play_press():
    """Send a play button press to Ableton Live."""
    return send_mcu_message(MCU_COMMANDS['PLAY'])

def send_stop_press():
    """Send a stop button press to Ableton Live."""
    return send_mcu_message(MCU_COMMANDS['STOP'])

# API Routes

@app.route('/api/status')
def get_status():
    """Get MIDI connection status."""
    return jsonify({
        "midi_port": MIDI_PORT_NAME,
        "connected": midi_out is not None,
        "available_input_ports": mido.get_input_names(),
        "available_output_ports": mido.get_output_names(),
        "is_playing": current_play_state
    })

@app.route('/api/play', methods=['POST'])
def toggle_play():
    """Toggle play/pause state in Ableton Live."""
    global current_play_state
    
    try:
        data = request.get_json() or {}
        should_play = data.get('play', not current_play_state)
        
        if should_play and not current_play_state:
            # Start playback
            success = send_play_press()
            if success:
                current_play_state = True
                return jsonify({"status": "ok", "is_playing": True, "action": "play"})
        elif not should_play and current_play_state:
            # Stop playback
            success = send_stop_press()
            if success:
                current_play_state = False
                return jsonify({"status": "ok", "is_playing": False, "action": "stop"})
        else:
            # Already in the requested state
            return jsonify({
                "status": "ok", 
                "is_playing": current_play_state, 
                "action": "no_change"
            })
            
        return jsonify({
            "status": "error",
            "message": "Failed to send MIDI message"
        }), 500
        
    except Exception as e:
        logger.error(f"Error in toggle_play: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/play-state')
def get_play_state():
    """Get current play state."""
    return jsonify({
        "is_playing": current_play_state
    })

def cleanup():
    """Clean up MIDI connections."""
    global midi_out, midi_in
    
    try:
        if midi_out:
            midi_out.close()
            midi_out = None
        if midi_in:
            midi_in.close()
            midi_in = None
        logger.info("MIDI connections closed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

if __name__ == '__main__':
    try:
        logger.info("Starting MIDI Controller Backend")
        logger.info(f"Looking for MIDI port: {MIDI_PORT_NAME}")
        
        # Initialize MIDI
        if not initialize_midi():
            logger.error("Failed to initialize MIDI - continuing anyway")
            logger.error("The server will start but MIDI functionality will not work")
        else:
            logger.info("MIDI initialized successfully")
        
        # Start Flask server
        logger.info(f"Starting server on http://{HOST}:{PORT}")
        app.run(host=HOST, port=PORT, debug=DEBUG)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        cleanup()
