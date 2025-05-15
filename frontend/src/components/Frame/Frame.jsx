/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";
// import { useReducer } from "react"; // No longer using useReducer for property1
import "./style.css";

export const Frame = ({ 
  property1 = "default", // Provide default directly in props
  className, 
  frameClassName, 
  text = "1",
  productName,
  cargoOwner
}) => {

  // Debugging logs for Frame component
  // Log the prop value directly
  console.log(`Frame Component - Received prop property1: '${property1}', productName: '${productName}'`);

  return (
    <div
      // className={`frame ${state.property1} ${className}`} // Use prop directly
      className={`frame ${property1} ${className}`}
      // onClick={() => { // onClick is still disabled for now
      //   // dispatch("click");
      // }}
    >
      <div className={`element-2 ${frameClassName}`}>
        {/* Use prop directly in conditions */} 
        {["default", "hover"].includes(property1) && <>{text}</>}

        {property1 === "variant-3" && (
          <>
            <div className="text-wrapper-3">{productName}</div>
            <div className="text-wrapper-4">관리자: {cargoOwner || ''}</div>
          </>
        )}
      </div>
    </div>
  );
};

// Reducer is no longer needed for property1's core logic
// function reducer(state, action) {
//   switch (action) {
//     case "click":
//       console.log("Frame clicked, but state change is disabled for debugging.");
//       return state;
//   }
//   return state;
// }

Frame.propTypes = {
  property1: PropTypes.oneOf(["variant-3", "hover", "default"]),
  text: PropTypes.string,
  productName: PropTypes.string,
  cargoOwner: PropTypes.string
};
