/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";
import { Ic322Tone2 } from "../../icons/Ic322Tone2";
import { Property1Password } from "../../icons/Property1Password";
import "./style.css";

export const IcTone = ({ property1, propertyAreaClassName }) => {
  return (
    <>
      {property1 === "area" && (
        <div className={`ic-tone ${propertyAreaClassName}`} />
      )}

      {property1 === "id" && <Ic322Tone2 className="instance-node" />}

      {property1 === "password" && (
        <Property1Password className="instance-node" />
      )}
    </>
  );
};

IcTone.propTypes = {
  property1: PropTypes.oneOf(["area", "password", "id"]),
};
