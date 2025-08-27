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
    'NOTE_OFF': 0x80,
    # Banking and navigation commands
    'BANK_LEFT': 0x2E,   # Navigate to previous bank
    'BANK_RIGHT': 0x2F,  # Navigate to next bank
    'TRACK_LEFT': 0x30,  # Navigate tracks within bank
    'TRACK_RIGHT': 0x31, # Navigate tracks within bank
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

# Track discovery and banking state
current_bank = 0
original_bank = 0  # User's preferred bank
backing_track_bank = None    # Which bank contains "Backing"
backing_track_channel = None # Which channel (0-7) within that bank
track_discovery_complete = False
track_names_cache = {}  # Cache of all discovered track names by bank
backing_track_volume = 0.0  # Current backing track volume (0.0 to 1.0)
discovery_in_progress = False

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
            
            # Start track discovery after initialization with proper handshake reset
            threading.Thread(target=lambda: (time.sleep(3), discover_backing_track()), daemon=True).start()

        return midi_out is not None

    except Exception as e:
        logger.error(f"Failed to initialize MIDI: {e}")
        return False

def send_mcu_initialization():
    """Send comprehensive MCU initialization sequence to force LCD updates."""
    try:
        logger.info("Sending comprehensive MCU initialization sequence...")
        
        if not midi_out:
            logger.error("No MIDI output available for initialization")
            return
        
        # Step 1: MCU Device Query - identify as Mackie Control
        sysex_device_query = Message('sysex', data=[0x7E, 0x7F, 0x06, 0x01])
        midi_out.send(sysex_device_query)
        logger.debug("Sent MCU device query")
        time.sleep(0.1)
        
        # Step 2: MCU Host Connection Response - complete handshake
        sysex_host_response = Message('sysex', data=[0x7E, 0x00, 0x06, 0x02, 0x00, 0x20, 0x32, 0x41, 0x00, 0x00, 0x00, 0x00])
        midi_out.send(sysex_host_response)
        logger.debug("Sent MCU host response")
        time.sleep(0.1)
        
        # Step 3: Initialize all faders to 0 to establish channel mapping
        for channel in range(8):
            # Send fader touch (channel 0-7, touch on)
            touch_msg = Message('note_on', channel=0, note=0x68 + channel, velocity=0x7F)
            midi_out.send(touch_msg)
            time.sleep(0.01)
            
            # Set fader position to establish communication
            fader_msg = Message('pitchwheel', channel=channel, pitch=0)
            midi_out.send(fader_msg)
            time.sleep(0.01)
            
            # Release fader touch
            touch_off_msg = Message('note_off', channel=0, note=0x68 + channel, velocity=0x00)
            midi_out.send(touch_off_msg)
            time.sleep(0.01)
        
        # Step 4: Request LCD updates for all channels by clearing and requesting refresh
        for channel in range(8):
            # Clear LCD first - specifically target the track name area
            clear_lcd_msg = Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x12, channel * 7, 0x00])
            midi_out.send(clear_lcd_msg)
            time.sleep(0.02)
            
            # Request track name by selecting track (this forces name display)
            track_select_msg = Message('note_on', channel=0, note=0x18 + channel, velocity=0x7F)
            midi_out.send(track_select_msg)
            time.sleep(0.05)  # Longer wait for track name response
            track_select_off_msg = Message('note_off', channel=0, note=0x18 + channel, velocity=0x00)
            midi_out.send(track_select_off_msg)
            time.sleep(0.02)
        
        # Step 5: Force track name display by sending track name line requests
        # Track names appear at offsets: 0, 7, 14, 21, 28, 35, 42, 49 for channels 0-7
        track_name_offsets = [0, 7, 14, 21, 28, 35, 42, 49]
        for offset in track_name_offsets:
            # Request specific track name LCD line
            track_name_request = Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x12, offset, 0x00])
            midi_out.send(track_name_request)
            time.sleep(0.03)
        
        # Step 6: Send special track name display request command
        # This is a specific MCU command to force track name display
        track_name_display = Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x0F])  # Force track name display
        midi_out.send(track_name_display)
        time.sleep(0.1)
        
        # Step 7: Navigate banks to force complete LCD refresh
        # Bank right then left to force all track names to update
        bank_right_msg = Message('note_on', channel=0, note=0x2F, velocity=0x7F)  # Bank right
        midi_out.send(bank_right_msg)
        time.sleep(0.05)
        bank_right_off_msg = Message('note_off', channel=0, note=0x2F, velocity=0x00)
        midi_out.send(bank_right_off_msg)
        time.sleep(0.3)  # Wait for bank change to complete
        
        # Return to bank 0 - this should trigger track name display
        bank_left_msg = Message('note_on', channel=0, note=0x2E, velocity=0x7F)  # Bank left
        midi_out.send(bank_right_msg)
        time.sleep(0.05)
        bank_right_off_msg = Message('note_off', channel=0, note=0x2F, velocity=0x00)
        midi_out.send(bank_right_off_msg)
        time.sleep(0.2)  # Wait for bank change to complete
        
        # Return to bank 0
        bank_left_msg = Message('note_on', channel=0, note=0x2E, velocity=0x7F)  # Bank left
        midi_out.send(bank_left_msg)
        time.sleep(0.05)
        bank_left_off_msg = Message('note_off', channel=0, note=0x2E, velocity=0x00)
        midi_out.send(bank_left_off_msg)
        time.sleep(0.2)  # Wait for return to bank 0
        
        logger.info("Comprehensive MCU initialization complete - LCD updates should be forced")
        
    except Exception as e:
        logger.error(f"Error during MCU initialization: {e}")

def reset_mcu_handshake():
    """Comprehensive MCU handshake reset with proper state clearing."""
    global track_names_cache, current_bank, track_discovery_complete, discovery_in_progress, midi_silence_period
    
    try:
        logger.info("Performing comprehensive MCU handshake reset...")
        
        # Clear all cached data
        track_names_cache.clear()
        track_discovery_complete = False
        discovery_in_progress = False
        
        # Set longer silence period for complete reset
        midi_silence_period = time.time() + 3.0
        
        if midi_out:
            # Step 1: Close any existing connections gracefully
            close_msg = Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x00])
            midi_out.send(close_msg)
            time.sleep(0.2)
            
            # Step 2: Send device inquiry to establish connection
            sysex_device_query = Message('sysex', data=[0x7E, 0x7F, 0x06, 0x01])
            midi_out.send(sysex_device_query)
            time.sleep(0.15)
            
            # Step 3: Send MCU initialization sequence
            send_mcu_initialization()
            time.sleep(0.2)
                
            # Step 4: Send enhanced handshake sequence
            sysex_device_query = Message('sysex', data=[0x7E, 0x7F, 0x06, 0x01])
            midi_out.send(sysex_device_query)
            time.sleep(0.15)
            
            # Send host response with correct MCU protocol
            sysex_host_response = Message('sysex', data=[0x7E, 0x00, 0x06, 0x02, 0x00, 0x20, 0x32, 0x41, 0x00, 0x00, 0x00, 0x00])
            midi_out.send(sysex_host_response)
            time.sleep(0.15)
            
            # Step 5: Reset to bank 0 with verification
            reset_attempts = 0
            while current_bank > 0 and reset_attempts < 10:
                send_bank_command('BANK_LEFT')
                time.sleep(0.3)
                reset_attempts += 1
            current_bank = 0  # Force set to 0
            
            # Step 6: Clear LCD displays and force refresh
            for channel in range(8):
                # Send LCD clear command
                lcd_clear = Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x12, channel*7, 0x00])
                midi_out.send(lcd_clear)
                time.sleep(0.02)
                
            # Step 7: Force LCD refresh by requesting text updates
            time.sleep(0.3)
            for channel in range(8):
                lcd_request = Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x12, channel*7, 0x00])
                midi_out.send(lcd_request)
                time.sleep(0.02)
                
        logger.info("MCU handshake reset complete - ready for track discovery")
        time.sleep(0.8)  # Longer wait for complete reset processing
        
    except Exception as e:
        logger.error(f"Error resetting MCU handshake: {e}")
        
    except Exception as e:
        logger.error(f"Error resetting MCU handshake: {e}")

def handle_midi_message(message):
    """Handle incoming MIDI messages with aggressive feedback loop prevention and track discovery."""
    global current_play_state, midi_silence_period, current_bank, backing_track_volume
    
    try:
        current_time = time.time()
        
        # Handle SysEx messages first (before silence period check) for MCU handshake
        if message.type == 'sysex':
            logger.info(f"Received SysEx message: {[hex(x) for x in message.data]}")
            logger.debug(f"SysEx data raw: {message.data}")
            logger.debug(f"SysEx data types: {[type(x) for x in message.data]}")
            logger.debug(f"SysEx length: {len(message.data)}")
            
            # Handle MCU handshake - acknowledge ping messages (bypass silence period)
            if (len(message.data) >= 7 and 
                message.data[:4] == [0x00, 0x00, 0x66, 0x14] and 
                message.data[4] == 0x20):  # MCU ping
                logger.info("MCU handshake condition matched!")
                # Send acknowledgment with command 0x21
                ack_message = mido.Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x21, 0x00, 0x01])
                midi_out.send(ack_message)
                logger.info("Sent MCU handshake acknowledgment")
                return
            else:
                logger.debug(f"Handshake condition not met: len={len(message.data)}, header={message.data[:4] if len(message.data) >= 4 else 'N/A'}, cmd={message.data[4] if len(message.data) > 4 else 'N/A'}")
            
            # Parse LCD text messages
            parse_lcd_message(message)
            return
        
        # If we're in a silence period after sending a command, ignore all messages
        if midi_silence_period:
            logger.debug(f"Ignoring message during silence period: {message}")
            return
        
        # Log all incoming messages for debugging
        logger.debug(f"Received MIDI message: {message}")
        
        # Handle volume feedback from Ableton (CC7 messages)
        if message.type == 'control_change':
            handle_volume_feedback(message)
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
                
            # Process banking commands
            elif message.note == MCU_COMMANDS['BANK_LEFT']:
                current_bank = max(0, current_bank - 1)
                logger.info(f"Bank changed to: {current_bank}")
                
            elif message.note == MCU_COMMANDS['BANK_RIGHT']:
                current_bank += 1
                logger.info(f"Bank changed to: {current_bank}")
                
            else:
                logger.debug(f"Unhandled note_on: note {message.note} velocity {message.velocity}")
        else:
            logger.debug(f"Ignoring message type {message.type}")
            
    except Exception as e:
        logger.error(f"Error handling MIDI message: {e}")

def parse_lcd_message(message):
    """Parse MCU LCD SysEx messages to extract track names."""
    global track_names_cache, current_bank
    
    try:
        data = message.data
        logger.debug(f"Parsing LCD message: {[hex(b) for b in data]}")
        
        # MCU LCD update format: F0 00 00 66 14 12 [offset] [text...] F7
        if (len(data) >= 7 and 
            data[0] == 0x00 and data[1] == 0x00 and data[2] == 0x66 and 
            data[3] == 0x14 and data[4] == 0x12):
            
            offset = data[5]
            text_data = data[6:]
            
            # Convert bytes to text, handling null termination
            try:
                text = ''.join([chr(b) for b in text_data if b != 0 and b < 128])
                logger.info(f"LCD Text at offset {offset}: '{text}'")
                
                # Track names typically appear at specific offset ranges
                # Upper LCD line (offsets 0x00-0x37) contains track names
                # Lower LCD line (offsets 0x38-0x6F) contains meters/status
                if 0x00 <= offset <= 0x37 and text.strip():  # Upper line only for track names
                    # Determine which channel this text belongs to based on offset
                    # Each channel gets 7 characters: offset 0-6=ch0, 7-13=ch1, etc.
                    channel = offset // 7
                    
                    if 0 <= channel <= 7:  # Valid channel range
                        # Store track name in cache
                        if current_bank not in track_names_cache:
                            track_names_cache[current_bank] = {}
                        
                        # Clean track name - remove extra spaces and control chars
                        clean_name = text.strip()
                        if clean_name and not clean_name.isspace() and len(clean_name) > 1:
                            track_names_cache[current_bank][channel] = clean_name
                            logger.info(f"Track Name - Bank {current_bank}, Channel {channel}: '{clean_name}'")
                            
                            # Check if this is the "Backing" track we're looking for
                            check_for_backing_track(current_bank, channel, clean_name)
                        else:
                            logger.debug(f"Ignoring empty/invalid track name: '{text}' at offset {offset}")
                else:
                    logger.debug(f"LCD message at offset {offset} is not a track name area: '{text}'")
                        
            except (ValueError, UnicodeDecodeError):
                # Handle invalid text data
                pass
                
    except Exception as e:
        logger.error(f"Error parsing LCD message: {e}")

def determine_channel_from_offset(offset):
    """Determine MCU channel from LCD offset position."""
    # MCU LCD layout: 8 channels, each with name and value display
    # This is a simplified mapping - may need adjustment based on actual MCU implementation
    if 0 <= offset <= 55:  # Track name area
        return offset // 7  # Approximate channel calculation
    return None

def handle_volume_feedback(message):
    """Handle volume feedback from Ableton via CC7 messages."""
    global backing_track_volume, backing_track_channel, current_bank
    
    try:
        # Only process CC7 (volume) messages
        if message.control == 7:
            channel = message.channel
            value = message.value / 127.0  # Convert to 0.0-1.0 range
            
            # Check if this is feedback for the backing track
            if (backing_track_bank == current_bank and 
                backing_track_channel == channel):
                backing_track_volume = value
                logger.debug(f"Backing track volume updated: {value:.2f}")
                
    except Exception as e:
        logger.error(f"Error handling volume feedback: {e}")

def check_for_backing_track(bank, channel, track_name):
    """Check if discovered track is the 'Backing' track we're looking for."""
    global backing_track_bank, backing_track_channel, track_discovery_complete
    
    # Use flexible matching for truncated names
    if ("backing" in track_name.lower() or 
        "backng" in track_name.lower() or  # Handle truncated version
        track_name.lower().startswith("back")):  # Partial match
        backing_track_bank = bank
        backing_track_channel = channel
        track_discovery_complete = True
        logger.info(f"Found 'Backing' track ('{track_name}') at Bank {bank}, Channel {channel}")
        
        # Optionally navigate back to original bank
        if bank != original_bank:
            threading.Thread(target=return_to_original_bank, daemon=True).start()

def return_to_original_bank():
    """Navigate back to the user's original bank view."""
    global current_bank, original_bank
    
    try:
        time.sleep(1)  # Brief delay to allow track discovery to complete
        
        if current_bank != original_bank:
            # Navigate back to original bank
            while current_bank > original_bank:
                send_bank_command('BANK_LEFT')
                time.sleep(0.2)  # Brief delay between commands
                
            while current_bank < original_bank:
                send_bank_command('BANK_RIGHT')
                time.sleep(0.2)
                
            logger.info(f"Returned to original bank: {original_bank}")
            
    except Exception as e:
        logger.error(f"Error returning to original bank: {e}")

def send_bank_command(command):
    """Send MCU banking navigation command."""
    global current_bank
    
    if not midi_out:
        logger.error("MIDI output not initialized")
        return False
        
    try:
        command_code = MCU_COMMANDS.get(command)
        if command_code is None:
            logger.error(f"Unknown bank command: {command}")
            return False
            
        # Send note_on for bank command
        msg = Message('note_on', channel=0, note=command_code, velocity=127)
        midi_out.send(msg)
        
        # Send note_off after short delay
        time.sleep(0.01)
        msg_off = Message('note_off', channel=0, note=command_code, velocity=0)
        midi_out.send(msg_off)
        
        # Update current bank tracking
        if command == 'BANK_LEFT':
            current_bank = max(0, current_bank - 1)
        elif command == 'BANK_RIGHT':
            current_bank += 1
            
        logger.debug(f"Sent bank command: {command}, current bank: {current_bank}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending bank command: {e}")
        return False

def discover_backing_track():
    """Discover the 'Backing' track across all banks."""
    global track_discovery_complete, discovery_in_progress, original_bank, current_bank
    
    if discovery_in_progress or track_discovery_complete:
        return
        
    discovery_in_progress = True
    original_bank = current_bank
    
    try:
        # Reset MCU handshake for clean state before discovery
        reset_mcu_handshake()
        
        logger.info("Starting track discovery for 'Backing' track...")
        
        # Start from bank 0 (already done in reset_mcu_handshake)
        current_bank = 0
            
        # Scan through banks looking for "Backing"
        max_banks_to_scan = 10  # Reasonable limit
        
        for bank_num in range(max_banks_to_scan):
            logger.info(f"Scanning bank {bank_num} for 'Backing' track...")
            
            # Request LCD text updates for all channels in current bank
            try:
                for channel in range(8):
                    # Send LCD text request (SysEx message to request track names)
                    lcd_request = Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x12, channel*7, 0x00])
                    midi_out.send(lcd_request)
                    time.sleep(0.02)  # Slightly longer delay for better reliability
            except Exception as e:
                logger.debug(f"Error sending LCD requests: {e}")
            
            # Wait longer for LCD updates to populate after reset
            time.sleep(1.2)  # Increased wait time for better reliability
            
            # Check if we found "Backing" in current bank
            if track_discovery_complete:
                logger.info(f"Track discovery complete! Found 'Backing' in bank {backing_track_bank}")
                break
                
            # Move to next bank
            if bank_num < max_banks_to_scan - 1:
                send_bank_command('BANK_RIGHT')
                time.sleep(0.4)  # Longer wait for bank changes
                
        if not track_discovery_complete:
            logger.warning("Could not find 'Backing' track in any bank")
            
    except Exception as e:
        logger.error(f"Error during track discovery: {e}")
    finally:
        discovery_in_progress = False
        # Return to original bank if discovery failed
        if not track_discovery_complete:
            threading.Thread(target=return_to_original_bank, daemon=True).start()

def send_backing_fader_command(value):
    """Send volume command to the Backing track."""
    global backing_track_bank, backing_track_channel, current_bank
    
    if not track_discovery_complete or backing_track_channel is None:
        logger.warning("Backing track not discovered yet, triggering discovery...")
        threading.Thread(target=discover_backing_track, daemon=True).start()
        return False
        
    try:
        # Check if we need to navigate to the backing track's bank
        original_user_bank = current_bank
        need_to_navigate = (backing_track_bank != current_bank)
        
        if need_to_navigate:
            # Navigate to backing track's bank
            while current_bank != backing_track_bank:
                if current_bank < backing_track_bank:
                    send_bank_command('BANK_RIGHT')
                else:
                    send_bank_command('BANK_LEFT')
                time.sleep(0.1)
                
        # Send CC7 (volume) command to the backing track
        cc_value = int(value * 127)  # Convert 0.0-1.0 to 0-127
        msg = Message('control_change', channel=backing_track_channel, control=7, value=cc_value)
        midi_out.send(msg)
        
        logger.info(f"Sent volume {value:.2f} to Backing track (Bank {backing_track_bank}, Channel {backing_track_channel})")
        
        # Navigate back to user's preferred bank if needed
        if need_to_navigate and original_user_bank != backing_track_bank:
            time.sleep(0.1)  # Brief delay
            while current_bank != original_user_bank:
                if current_bank < original_user_bank:
                    send_bank_command('BANK_RIGHT')
                else:
                    send_bank_command('BANK_LEFT')
                time.sleep(0.1)
                
        return True
        
    except Exception as e:
        logger.error(f"Error sending backing fader command: {e}")
        return False

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

@app.route('/api/fader', methods=['POST'])
def control_fader():
    """Control fader volume for the Backing track."""
    try:
        data = request.get_json()
        if not data or 'value' not in data:
            return jsonify({
                "status": "error",
                "message": "Missing 'value' parameter"
            }), 400
            
        fader_value = float(data['value'])
        if not 0.0 <= fader_value <= 1.0:
            return jsonify({
                "status": "error", 
                "message": "Value must be between 0.0 and 1.0"
            }), 400
            
        track_name = data.get('track', 'Backing')  # Default to Backing for now
        
        if track_name.lower() == 'backing':
            success = send_backing_fader_command(fader_value)
            
            if success:
                return jsonify({
                    "status": "ok",
                    "track": track_name,
                    "value": fader_value,
                    "bank": backing_track_bank,
                    "channel": backing_track_channel
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": "Failed to send fader command"
                }), 500
        else:
            return jsonify({
                "status": "error",
                "message": f"Track '{track_name}' not supported yet"
            }), 400
            
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "Invalid value format"
        }), 400
    except Exception as e:
        logger.error(f"Error in control_fader: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/track-volumes')
def get_track_volumes():
    """Get current track volumes."""
    return jsonify({
        "backing": backing_track_volume,
        "backing_track_discovered": track_discovery_complete,
        "backing_track_bank": backing_track_bank,
        "backing_track_channel": backing_track_channel
    })

@app.route('/api/track-names')
def get_track_names():
    """Get discovered track names (for debugging)."""
    return jsonify({
        "track_names_cache": track_names_cache,
        "current_bank": current_bank,
        "backing_track_bank": backing_track_bank,
        "backing_track_channel": backing_track_channel,
        "discovery_complete": track_discovery_complete
    })

@app.route('/api/discover-tracks', methods=['POST'])
def trigger_track_discovery():
    """Manually trigger track discovery."""
    try:
        threading.Thread(target=discover_backing_track, daemon=True).start()
        return jsonify({
            "status": "ok",
            "message": "Track discovery started"
        })
    except Exception as e:
        logger.error(f"Error triggering track discovery: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/reset-handshake', methods=['POST'])
def trigger_handshake_reset():
    """Manually reset MCU handshake and trigger track discovery."""
    try:
        # Reset the handshake and start fresh discovery
        threading.Thread(target=lambda: (reset_mcu_handshake(), time.sleep(1), discover_backing_track()), daemon=True).start()
        return jsonify({
            "status": "ok",
            "message": "MCU handshake reset and track discovery started"
        })
    except Exception as e:
        logger.error(f"Error resetting handshake: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/current-bank')
def get_current_bank():
    """Get current MCU bank information."""
    return jsonify({
        "current_bank": current_bank,
        "original_bank": original_bank,
        "backing_track_bank": backing_track_bank
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
