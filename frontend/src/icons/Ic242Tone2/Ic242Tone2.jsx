/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";

export const Ic242Tone2 = ({ color = "#39424A", className }) => {
  return (
    <svg
      className={`ic-24-2tone-2 ${className}`}
      fill="none"
      height="24"
      viewBox="0 0 24 24"
      width="24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g className="g" clipPath="url(#clip0_2049_176)">
        <g className="g" clipPath="url(#clip1_2049_176)">
          <path
            className="path"
            d="M12 10L16 6H13V2H11V6H8L12 10ZM18.92 4.36L17.48 5.9L20.62 7.35L19.04 9.02L16.09 7.62L14.66 9.16L17.6 10.55L12.07 12.98L11.97 12.96L11.94 12.98L6.42 10.56L9.36 9.18L7.92 7.63L4.97 9.03L3.39 7.36L6.39 5.98L4.95 4.44L0 6.7L3 9.85V17.94L11.07 21.77C11.37 21.93 11.69 22 12.02 22C12.35 22 12.64 21.93 12.9 21.79L21 17.94V9.85L24 6.7L18.92 4.36ZM5 12.11L11 14.74V19.52L5 16.67V12.1V12.11ZM19 12.11V16.67L13 19.49V14.74L19 12.11Z"
            fill={color}
          />
        </g>
      </g>

      <defs className="defs">
        <clipPath className="clip-path" id="clip0_2049_176">
          <rect className="rect" fill="white" height="24" width="24" />
        </clipPath>

        <clipPath className="clip-path" id="clip1_2049_176">
          <rect
            className="rect"
            fill="white"
            height="20"
            transform="translate(0 2)"
            width="24"
          />
        </clipPath>
      </defs>
    </svg>
  );
};

Ic242Tone2.propTypes = {
  color: PropTypes.string,
};
