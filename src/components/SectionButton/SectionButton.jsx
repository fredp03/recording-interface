/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

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
