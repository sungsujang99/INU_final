/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";

export const Property1Variant5 = ({ color = "#39424A", className }) => {
  return (
    <svg
      className={`property-1-variant5 ${className}`}
      fill="none"
      height="24"
      viewBox="0 0 24 24"
      width="24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g className="g" clipPath="url(#clip0_2151_1562)">
        <path
          className="path"
          d="M12.0001 3.0293C11.4369 3.0293 10.8739 3.29174 10.5587 3.81641L1.76178 18.4512C1.11355 19.5292 1.94293 21 3.20123 21H20.7969C22.0549 21 22.8866 19.5292 22.2383 18.4512L13.4415 3.81641C13.1262 3.29174 12.5632 3.0293 12.0001 3.0293ZM12.0001 5.29883L20.2364 19H3.76373L12.0001 5.29883ZM11.0001 9V14H13.0001V9H11.0001ZM11.0001 16V18H13.0001V16H11.0001Z"
          fill={color}
        />
      </g>

      <defs className="defs">
        <clipPath className="clip-path" id="clip0_2151_1562">
          <rect className="rect" fill="white" height="24" width="24" />
        </clipPath>
      </defs>
    </svg>
  );
};

Property1Variant5.propTypes = {
  color: PropTypes.string,
};
