/*
We're constantly improving the code you see. 
Please share your feedback here: https://form.asana.com/?k=uvp-HPgd3_hyoXRBw1IcNg&d=1152665201300829
*/

import PropTypes from "prop-types";
import React from "react";
import { Ic162Thone } from "../../icons/Ic162Thone";
import "./style.css";

export const Menu = ({
  menu,
  className,
  icon = <Ic162Thone className="ic-thone" color="#0177FB" />,
  text = "menu 1",
  text1 = "menu 2",
  onClick,
}) => {
  return (
    <div className={`menu ${menu} ${className}`} onClick={onClick} style={{ cursor: 'pointer' }}>
      <div className="ic-wrapper">{icon}</div>

      <div className="div">
        {menu === "selected" && <>{text}</>}

        {menu === "default" && <>{text1}</>}
      </div>
    </div>
  );
};

Menu.propTypes = {
  menu: PropTypes.oneOf(["selected", "default"]),
  text: PropTypes.string,
  text1: PropTypes.string,
  onClick: PropTypes.func,
};
