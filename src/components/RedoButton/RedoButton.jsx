import React from "react";
import "./style.css";

export const RedoButton = ({ className, onClick }) => {
  return (
    <button 
      className={`redo-button ${className}`} 
      onClick={onClick}
      aria-label="Redo"
    />
  );
};
