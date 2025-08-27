import PropTypes from "prop-types";
import React from "react";
import "./style.css";

export const SectionButton = ({
  sectionText = "Section 3",
  className,
  button = "/img/button.svg",
  onClick,
}) => {
  return (
    <button className={`section-button ${className}`} onClick={onClick}>
      <img className="button" alt="Button" src={button} />
    </button>
  );
};

SectionButton.propTypes = {
  sectionText: PropTypes.string,
  button: PropTypes.string,
  onClick: PropTypes.func,
};
