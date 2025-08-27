import React from "react";
import "./style.css";

export const UndoButton = ({ className, onClick }) => {
  return (
    <button 
      className={`undo-button ${className}`} 
      onClick={onClick}
      aria-label="Undo"
    />
  );
};
