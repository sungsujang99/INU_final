/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";

export const Ic162Thone = ({ color = "#0177FB", className }) => {
  return (
    <svg
      className={`ic-16-2thone ${className}`}
      fill="none"
      height="16"
      viewBox="0 0 16 16"
      width="16"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        className="path"
        d="M12.6666 7.33339V13.3334H9.33324V9.33339H6.66657V13.3334H3.33324V7.33339H2.3999L7.9999 2.26672L13.5999 7.33339H12.6666Z"
        fill={color}
        opacity="0.2"
      />

      <path
        className="path"
        d="M13.3332 14H8.6665V10H7.33317V14H2.6665V8.00002H0.666504L7.99984 1.40002L15.3332 8.00002H13.3332V14ZM9.99984 12.6667H11.9998V6.80002L7.99984 3.20002L3.99984 6.80002V12.6667H5.99984V8.66669H9.99984V12.6667Z"
        fill={color}
      />
    </svg>
  );
};

Ic162Thone.propTypes = {
  color: PropTypes.string,
};
