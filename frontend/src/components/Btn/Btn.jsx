/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";
import "./style.css";

export const Btn = ({ property1, className, divClassName, text = "Next", onClick }) => {
  return (
    <button className={`btn ${property1} ${className}`} onClick={onClick}>
      <div className={`next ${divClassName}`}>{text}</div>
    </button>
  );
};

Btn.propTypes = {
  property1: PropTypes.oneOf(["deactive", "active"]),
  text: PropTypes.string,
  onClick: PropTypes.func,
};
