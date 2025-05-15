/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";
import { Property1Variant41 } from "../../icons/Property1Variant41";
import "./style.css";

export const Group = ({ property1, className }) => {
  return (
    <div className={`group ${property1} ${className}`}>
      <div className="frame-4">
        {property1 === "default" && <Property1Variant41 className="icons" />}

        {property1 === "variant-2" && (
          <img className="icons" alt="Icons" src="/img/icons8-1.svg" />
        )}

        <div className="text-wrapper-2">다운로드</div>
      </div>
    </div>
  );
};

Group.propTypes = {
  property1: PropTypes.oneOf(["variant-2", "default"]),
};
