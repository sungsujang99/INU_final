import React from 'react';
import './style.css';

export const OffButton = ({ onClick }) => {
  return (
    <button className="off-button" onClick={onClick}>
      OFF
    </button>
  );
}; 