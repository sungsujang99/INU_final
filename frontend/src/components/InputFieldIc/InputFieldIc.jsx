/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React, { useState } from "react";
import { IcTone } from "../IcTone";
import "./style.css";

export const InputFieldIc = ({
  property1,
  className,
  override = <IcTone property1="area" propertyAreaClassName="ic-32-2tone" />,
  frameClassName,
  text = "login id",
  hasDiv = true,
  onChange,
  value,
  type = "text"
}) => {
  const [inputValue, setInputValue] = useState(value || "");

  const handleChange = (e) => {
    setInputValue(e.target.value);
    if (onChange) {
      onChange(e.target.value);
    }
  };

  return (
    <div className={`input-field-ic property-1-${property1} ${className}`}>
      <div className={`frame-2 ${frameClassName}`}>
        <div className="frame-3">
          {override}
          <div className="login-id">
            <input
              type={type}
              value={inputValue}
              onChange={handleChange}
              placeholder={text}
              className="input-field"
            />
          </div>
        </div>

        {hasDiv && <div className="text-wrapper">@inulogistics.co.kr</div>}
      </div>
    </div>
  );
};

InputFieldIc.propTypes = {
  property1: PropTypes.oneOf([
    "disalbe",
    "active",
    "default",
    "focus",
    "error",
  ]),
  text: PropTypes.string,
  hasDiv: PropTypes.bool,
  onChange: PropTypes.func,
  value: PropTypes.string,
  type: PropTypes.string
};
