import PropTypes from "prop-types";
import React from "react";
import "./style.css";

export const SectionButton = ({
  sectionText = "Section 3",
  className,
  button = "/img/button.svg",
}) => {
  return (
    <div className={`section-button ${className}`}>
      <img className="button" alt="Button" src={button} />
    </div>
  );
};

SectionButton.propTypes = {
  sectionText: PropTypes.string,
  button: PropTypes.string,
};
