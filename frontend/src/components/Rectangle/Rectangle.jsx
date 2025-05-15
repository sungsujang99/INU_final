/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";
import "./style.css";

export const Rectangle = ({ className, property1, text = "", onClick }) => {
  return (
    <div 
      className={`rectangle ${className}`} 
      onClick={onClick}
    >
      <div className="text">{text}</div>
    </div>
  );
};

Rectangle.propTypes = {
  property1: PropTypes.oneOf(["variant-2", "default"]),
  text: PropTypes.string,
  onClick: PropTypes.func,
};
