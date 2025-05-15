/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";

export const Ic242Tone6 = ({ color = "#00BB80", className }) => {
  return (
    <svg
      className={`ic-24-2tone-6 ${className}`}
      fill="none"
      height="24"
      viewBox="0 0 24 24"
      width="24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g className="g" clipPath="url(#clip0_2150_1429)">
        <path
          className="path"
          d="M12 2L8 6H11V10H13V6H16L12 2ZM18.916 4.35547L17.4805 5.89648L20.623 7.34375L19.0391 9.01172L16.0859 7.60938L14.6562 9.14453L17.5957 10.5391L12.0625 12.9688L11.9668 12.9512L11.9336 12.9688L6.41211 10.5449L9.35547 9.16016L7.91211 7.60938L4.96094 9.01172L3.37695 7.34375L6.38086 5.96289L4.94531 4.41992L0 6.69727L3 9.85156V17.9395L11.0664 21.7676C11.3634 21.9236 11.6907 22 12.0117 22C12.3227 22 12.6275 21.9282 12.8965 21.7852L21 17.9375V9.85156L24 6.69727L18.916 4.35547ZM5 12.1074L11 14.7383V19.5215L5 16.6738V12.1074ZM19 12.1074V16.6699L13 19.4902V14.7402L19 12.1074Z"
          fill={color}
        />
      </g>

      <defs className="defs">
        <clipPath className="clip-path" id="clip0_2150_1429">
          <rect className="rect" fill="white" height="24" width="24" />
        </clipPath>
      </defs>
    </svg>
  );
};

Ic242Tone6.propTypes = {
  color: PropTypes.string,
};
