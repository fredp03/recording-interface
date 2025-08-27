import React, { useState } from "react";
import PropTypes from "prop-types";
import "./style.css";

export const PlayButton = ({ className, isPlaying: controlledIsPlaying, onToggle }) => {
  const [internalIsPlaying, setInternalIsPlaying] = useState(false);
  
  // Use controlled state if provided, otherwise use internal state
  const isPlaying = controlledIsPlaying !== undefined ? controlledIsPlaying : internalIsPlaying;
  
  const handleClick = () => {
    if (controlledIsPlaying !== undefined) {
      // Controlled component - notify parent
      onToggle && onToggle(!isPlaying);
    } else {
      // Uncontrolled component - manage own state
      setInternalIsPlaying(!isPlaying);
    }
  };

  const PauseIcon = () => (
    <svg width="14" height="26" viewBox="0 0 14 26" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M1.4 0C2.1732 0 2.8 0.6467 2.8 1.44444V24.5556C2.8 25.3533 2.1732 26 1.4 26C0.626801 26 0 25.3533 0 24.5556V1.44444C0 0.6467 0.626801 0 1.4 0Z" fill="#DFDFDF" fillOpacity="0.8"/>
      <path d="M12.6 0C13.3732 0 14 0.6467 14 1.44444V24.5556C14 25.3533 13.3732 26 12.6 26C11.8268 26 11.2 25.3533 11.2 24.5556V1.44444C11.2 0.6467 11.8268 0 12.6 0Z" fill="#DFDFDF" fillOpacity="0.8"/>
    </svg>
  );

  if (isPlaying) {
    return (
      <button 
        className={`play-button pause-state ${className}`}
        onClick={handleClick}
        aria-label="Pause"
      >
        <PauseIcon />
      </button>
    );
  }

  return (
    <button 
      className={`play-button play-state ${className}`}
      onClick={handleClick}
    aria-label="Play"
  />
  );
};

PlayButton.propTypes = {
  className: PropTypes.string,
  isPlaying: PropTypes.bool,
  onToggle: PropTypes.func,
};