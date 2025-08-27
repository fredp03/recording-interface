import React from "react";
import { FaderComponent } from "../../components/FaderComponent";
import { PlayButton } from "../../components/PlayButton";
import { RedoButton } from "../../components/RedoButton";
import { SectionButton } from "../../components/SectionButton";
import { UndoButton } from "../../components/UndoButton";
import { RecordButton } from "../../icons/RecordButton";
import useMIDIController from "../../utils/useMIDIController";
import "./style.css";

export const IphoneFrame = () => {
  const { 
    isConnected, 
    isPlaying, 
    backingVolume,
    trackDiscoveryComplete,
    togglePlayPause, 
    sendFaderChange,
    triggerTrackDiscovery 
  } = useMIDIController();

  const handleBackingFaderChange = (value) => {
    console.log('Backing fader changed:', value);
    sendFaderChange('Backing', value);
  };

  const handleMeFaderChange = (value) => {
    console.log('Me fader changed:', value);
    // TODO: Implement "Me" fader when ready
  };

  return (
    <div className="iphone-frame">
      {/* MIDI Connection Status Indicator */}
      <div className="midi-status">
        <div className={`connection-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '● MIDI Connected' : '○ MIDI Disconnected'}
        </div>
        {isConnected && (
          <div className="track-status">
            <div className={`track-discovery ${trackDiscoveryComplete ? 'found' : 'searching'}`}>
              {trackDiscoveryComplete ? '♪ Backing Track Found' : '🔍 Finding Backing Track...'}
            </div>
          </div>
        )}
      </div>
      
      <div className="frame-contents">
        <div className="section-buttons">
          <SectionButton
            button="/img/button-1.svg"
            className="section-button-instance"
          />
          <SectionButton
            button="/img/button-2.svg"
            className="section-button-instance"
          />
          <SectionButton
            button="/img/button-3.svg"
            className="section-button-instance"
          />
        </div>

        <div className="fader-section">
          <div className="spacer" />

          <FaderComponent
            className="fader-component-instance"
            value={backingVolume}
            faderName="Backing"
            onChange={handleBackingFaderChange}
          />
          <div className="spacer" />

          <FaderComponent
            className="fader-component-instance"
            initialValue={0.7}
            faderName="Me"
            onChange={handleMeFaderChange}
          />
          <div className="spacer" />
        </div>

        <div className="controls">
          <div className="playback-controls">
            <div className="spacer" />

            <PlayButton 
              className="play-button-instance" 
              isPlaying={isPlaying}
              onToggle={togglePlayPause}
            />
            <div className="spacer" />

            <RecordButton className="record-button" />
            <div className="spacer" />
          </div>

          <div className="undo-buttons">
            <div className="spacer" />

            <UndoButton className="undo-button-instance" />
            <div className="spacer" />

            <RedoButton className="redo-button-instance" />
            <div className="spacer" />
          </div>
        </div>
      </div>
    </div>
  );
};
