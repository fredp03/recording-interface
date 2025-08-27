#!/usr/bin/env python3
"""
Recording Interface - Full Stack Flask Application

A Flask web application that serves the React frontend and provides 
HTTP endpoints for controlling Ableton Live via MIDI using the MCU protocol.
Prevents feedback loops with aggressive message filtering.
"""

import os
import logging
import time
import subprocess
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import mido
from mido import Message
import threading

# Configuration
MIDI_OUTPUT_PORT_NAME = os.getenv('MIDI_OUTPUT_PORT', 'IAC Driver fader-mcu')     # For sending commands to Ableton
MIDI_INPUT_PORT_NAME = os.getenv('MIDI_INPUT_PORT', 'IAC Driver fader-mcu-out')   # For receiving track info from Ableton
HOST = '0.0.0.0'  # Listen on all network interfaces  
PORT = int(os.getenv('PORT', 3001))  # Single server port for both frontend and API
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)  # Enable CORS for development

# Global MIDI ports
midi_out = None
midi_in = None

# MCU protocol constants - Complete command set
MCU_COMMANDS = {
    'PLAY': 0x5E,
    'STOP': 0x5D, 
    'RECORD': 0x5F,
    'REWIND': 0x5B,
    'FAST_FORWARD': 0x5C,
    'LOOP': 0x56,
    'CONTROL_CHANGE': 0xB0,
    'NOTE_ON': 0x90,
    'NOTE_OFF': 0x80
}

# Comprehensive list of MCU CC messages that should be ignored to prevent feedback
# These are status/feedback messages FROM Ableton TO the controller
MCU_IGNORE_CC = {
    # Fader positions (channels 0-7 for tracks, channel 8 for master)
    0x07, 0x27, 0x47, 0x67, 0x87, 0xA7, 0xC7, 0xE7,  # Channel volumes
    
    # Encoder positions and LED rings
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,  # V-Pot positions
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,  # V-Pot LED rings
    
    # Time code and position display
    0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47,  # Time display
    0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F,  # Time display continued
    
    # Transport and status LEDs
    0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F,  # Transport button LEDs
    
    # Channel meters and indicators  
    0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67,  # Channel meters
    0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F,  # More indicators
}

# Global state with enhanced tracking
current_play_state = False
play_state_callbacks = []
last_outgoing_command = None
last_outgoing_time = 0
message_debounce_time = 0.2  # Increased debounce time
midi_silence_period = False  # Flag to ignore incoming messages briefly after sending

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

        # Open output port for sending commands to Ableton
        midi_out = open_port(MIDI_OUTPUT_PORT_NAME, output_ports, 'output')
        
        # Open input port for receiving status updates from Ableton
        midi_in = open_port(MIDI_INPUT_PORT_NAME, input_ports, 'input')
        
        if midi_in:
            # Set up MIDI input callback
            midi_in.callback = handle_midi_message
            logger.info("MIDI input callback set up")
            
        # Send MCU initialization sequence
        if midi_out:
            send_mcu_initialization()

        return midi_out is not None

    except Exception as e:
        logger.error(f"Failed to initialize MIDI: {e}")
        return False

def send_mcu_initialization():
    """Send MCU initialization sequence to establish proper communication."""
    try:
        logger.info("Sending MCU initialization sequence...")
        
        # MCU Device Query - tell Ableton we're a Mackie Control
        # This helps establish proper two-way communication
        sysex_device_query = Message('sysex', data=[0x7E, 0x7F, 0x06, 0x01])
        if midi_out:
            midi_out.send(sysex_device_query)
            logger.debug("Sent MCU device query")
            
        time.sleep(0.1)
        
        # MCU Host Connection Response
        sysex_host_response = Message('sysex', data=[0x7E, 0x00, 0x06, 0x02, 0x00, 0x20, 0x32, 0x41, 0x00, 0x00, 0x00, 0x00])
        if midi_out:
            midi_out.send(sysex_host_response)
            logger.debug("Sent MCU host response")
            
        logger.info("MCU initialization complete")
        
    except Exception as e:
        logger.error(f"Error during MCU initialization: {e}")

def handle_midi_message(message):
    """Handle incoming MIDI messages with aggressive feedback loop prevention."""
    global current_play_state, midi_silence_period
    
    try:
        current_time = time.time()
        
        # If we're in a silence period after sending a command, ignore all messages
        if midi_silence_period:
            logger.debug(f"Ignoring message during silence period: {message}")
            return
            
        # Completely ignore all control_change messages - these are status/feedback only
        if message.type == 'control_change':
            logger.debug(f"Ignoring CC message: CC{message.control}={message.value}")
            return
            
        # Completely ignore sysex messages - these are device communication
        if message.type == 'sysex':
            logger.debug("Ignoring SysEx message")
            return
            
        # Only process note_on messages that represent button presses
        # Ignore note_off and note_on with velocity 0 (button releases)
        if message.type == 'note_on' and message.velocity > 0:
            
            # Additional check: if this matches our last outgoing command recently, ignore it
            if (last_outgoing_command and 
                message.note == last_outgoing_command and 
                current_time - last_outgoing_time < message_debounce_time):
                logger.debug(f"Ignoring echo of our own command: note {message.note}")
                return
                
            # Process transport commands
            if message.note == MCU_COMMANDS['PLAY']:
                if not current_play_state:  # Only update if state actually changed
                    logger.info("Transport: PLAY received from Ableton")
                    current_play_state = True
                    notify_play_state_change(True)
                    
            elif message.note == MCU_COMMANDS['STOP']:
                if current_play_state:  # Only update if state actually changed  
                    logger.info("Transport: STOP received from Ableton")
                    current_play_state = False
                    notify_play_state_change(False)
                    
            elif message.note == MCU_COMMANDS['RECORD']:
                logger.info("Transport: RECORD received from Ableton")
                # Handle record if needed
                
            else:
                logger.debug(f"Unhandled note_on: note {message.note} velocity {message.velocity}")
        else:
            logger.debug(f"Ignoring message type {message.type}")
            
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
    """Send MCU command with enhanced feedback loop prevention."""
    global last_outgoing_command, last_outgoing_time, midi_silence_period
    
    if not midi_out:
        logger.error("MIDI output not initialized")
        return False

    try:
        current_time = time.time()
        
        # Track what we're sending to prevent echo processing
        last_outgoing_command = command
        last_outgoing_time = current_time
        
        # Enter silence period to ignore immediate feedback
        midi_silence_period = True
        
        # MCU uses note_on messages for transport controls
        msg = Message('note_on', channel=0, note=command, velocity=velocity)
        midi_out.send(msg)
        logger.info(f"Sent MCU command: 0x{command:02X} (velocity={velocity})")
        
        # Send note_off after short delay to complete button press
        time.sleep(0.01)  # 10ms delay
        msg_off = Message('note_off', channel=0, note=command, velocity=0)
        midi_out.send(msg_off)
        logger.debug(f"Sent MCU note_off: 0x{command:02X}")
        
        # Schedule end of silence period
        def end_silence():
            global midi_silence_period
            time.sleep(message_debounce_time)
            midi_silence_period = False
            logger.debug("Ended MIDI silence period")
            
        threading.Thread(target=end_silence, daemon=True).start()
        
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

# Frontend serving routes

@app.route('/')
def serve_index():
    """Serve the main React application."""
    try:
        return send_file(os.path.join(app.static_folder, 'index.html'))
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return f"<h1>Recording Interface</h1><p>Frontend build not found. Run 'npm run build' first.</p><p>Error: {e}</p>", 404

@app.route('/<path:path>')
def serve_static(path):
    """Serve static assets from the dist folder."""
    try:
        return send_from_directory(app.static_folder, path)
    except Exception as e:
        logger.warning(f"Static file not found: {path}")
        # For SPA routing, fallback to index.html
        return serve_index()

# API Routes

@app.route('/api/status')
def get_status():
    """Get MIDI connection status."""
    return jsonify({
        "midi_output_port": MIDI_OUTPUT_PORT_NAME,
        "midi_input_port": MIDI_INPUT_PORT_NAME,
        "connected": midi_out is not None and midi_in is not None,
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

def build_frontend():
    """Build the React frontend if not already built."""
    dist_path = os.path.join(os.getcwd(), 'dist')
    index_path = os.path.join(dist_path, 'index.html')
    
    # Check if build already exists
    if os.path.exists(index_path):
        logger.info("Frontend build found")
        return True
        
    logger.info("Frontend build not found, building...")
    
    try:
        # Install dependencies if node_modules doesn't exist
        if not os.path.exists('node_modules'):
            logger.info("Installing Node.js dependencies...")
            subprocess.run(['npm', 'install'], check=True, cwd=os.getcwd())
            
        # Build the frontend
        logger.info("Building React frontend...")
        result = subprocess.run(['npm', 'run', 'build'], 
                              check=True, 
                              cwd=os.getcwd(),
                              capture_output=True,
                              text=True)
        
        logger.info("Frontend build completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Frontend build failed: {e}")
        if e.stdout:
            logger.error(f"Build stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"Build stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("npm not found. Please install Node.js and npm.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during frontend build: {e}")
        return False

if __name__ == '__main__':
    try:
        logger.info("Starting Recording Interface - Full Stack Server")
        logger.info(f"Looking for MIDI output port: {MIDI_OUTPUT_PORT_NAME}")
        logger.info(f"Looking for MIDI input port: {MIDI_INPUT_PORT_NAME}")
        
        # Build frontend if needed
        if not build_frontend():
            logger.warning("Frontend build failed - serving backend API only")
            
        # Initialize MIDI
        if not initialize_midi():
            logger.error("Failed to initialize MIDI - continuing anyway")
            logger.error("The server will start but MIDI functionality will not work")
        else:
            logger.info("MIDI initialized successfully")
        
        # Start Flask server
        logger.info(f"Starting server on http://{HOST}:{PORT}")
        logger.info("Access the interface at http://localhost:3001")
        app.run(host=HOST, port=PORT, debug=DEBUG)
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error starting server: {e}")
    finally:
        cleanup()
