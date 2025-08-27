import PropTypes from "prop-types";
import React, { useState, useRef, useCallback } from "react";
import "./style.css";

export const FaderComponent = ({
  faderName = "Backing",
  className,
  initialValue = 0.5, // Value between 0 and 1
  onChange,
}) => {
  const [value, setValue] = useState(initialValue);
  const [isDragging, setIsDragging] = useState(false);
  const trackRef = useRef(null);

  const handleMouseDown = useCallback((e) => {
    setIsDragging(true);
    e.preventDefault();
    e.stopPropagation(); // Prevent the track click from firing
  }, []);

  const handleTrackClick = useCallback((e) => {
    if (!trackRef.current) return;

    const rect = trackRef.current.getBoundingClientRect();
    const totalTrackHeight = 576; // Available track space
    const relativeY = e.clientY - rect.top; // Position from top of container
    
    // Clamp the value between 0 and 1, inverted since fader goes from top to bottom
    const newValue = Math.max(0, Math.min(1, 1 - (relativeY / totalTrackHeight)));
    
    setValue(newValue);
    onChange && onChange(newValue);
  }, [onChange]);

  const handleMouseMove = useCallback((e) => {
    if (!isDragging || !trackRef.current) return;

    const rect = trackRef.current.getBoundingClientRect();
    const totalTrackHeight = 576; // Available track space
    const relativeY = e.clientY - rect.top; // Position from top of container
    
    // Clamp the value between 0 and 1, inverted since fader goes from top to bottom
    const newValue = Math.max(0, Math.min(1, 1 - (relativeY / totalTrackHeight)));
    
    setValue(newValue);
    onChange && onChange(newValue);
  }, [isDragging, onChange]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Add global mouse event listeners
  React.useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // Calculate positions based on value
  const totalTrackHeight = 576; // Total available track space (596 - 20 for handle)
  const handlePosition = (1 - value) * totalTrackHeight; // Handle position from top
  const topTrackHeight = handlePosition; // Top track goes from 0 to handle position
  const bottomTrackHeight = totalTrackHeight - handlePosition; // Bottom track goes from handle to end

  return (
    <div className={`fader-component ${className}`}>
      <div 
        className="fader-track-container" 
        ref={trackRef}
        onClick={handleTrackClick}
      >
        {/* Top track (empty/muted) - dynamically sized */}
        <div 
          className="fader-track fader-track-top" 
          style={{ height: `${topTrackHeight}px` }}
        />
        
        {/* Draggable handle - positioned at the boundary */}
        <div 
          className={`fader-handle ${isDragging ? 'dragging' : ''}`}
          style={{ top: `${handlePosition}px` }}
          onMouseDown={handleMouseDown}
        />
        
        {/* Bottom track (active/filled) - dynamically sized */}
        <div 
          className="fader-track fader-track-bottom" 
          style={{ 
            height: `${bottomTrackHeight}px`,
            top: `${handlePosition + 20}px` // Position after the handle
          }}
        />
      </div>

      <div className="backing">{faderName}</div>
    </div>
  );
};

FaderComponent.propTypes = {
  faderName: PropTypes.string,
  initialValue: PropTypes.number,
  onChange: PropTypes.func,
};
