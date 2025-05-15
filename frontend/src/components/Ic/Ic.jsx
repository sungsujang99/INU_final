/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";
import { Ic242Tone2 } from "../../icons/Ic242Tone2";
import { Ic242Tone6 } from "../../icons/Ic242Tone6";
import { Property1Variant2 } from "../../icons/Property1Variant2";
import { Property1Variant5 } from "../../icons/Property1Variant5";
import "./style.css";

export const Ic = ({ property1 }) => {
  return (
    <>
      {property1 === "areai" && <div className="ic" />}

      {property1 === "variant-3" && (
        <Ic242Tone6 className="property" color="#39424A" />
      )}

      {property1 === "variant-4" && (
        <Ic242Tone2 className="property" color="#39424A" />
      )}

      {property1 === "variant-5" && (
        <Property1Variant5 className="property" color="#39424A" />
      )}

      {property1 === "variant-2" && <Property1Variant2 className="property" />}
    </>
  );
};

Ic.propTypes = {
  property1: PropTypes.oneOf([
    "variant-5",
    "variant-2",
    "variant-3",
    "variant-4",
    "areai",
  ]),
};
