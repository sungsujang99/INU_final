import React from 'react';

export const TotalRackBProgress = ({ percentage }) => {
  return (
    <svg width="153" height="95" viewBox="0 0 153 95" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path 
        d={`M6.95362e-06 95C5.40364e-06 ${95 - (95 * percentage / 100)} 4.96149 59.8943 14.3232 44.8377C23.6849 29.7811 37.0733 17.6447 52.9738 9.80142C68.8743 1.95811 86.6524 -1.27909 104.297 0.456001C121.942 2.19109 138.749 8.82923 152.817 19.6195L95 95L6.95362e-06 95Z`} 
        fill="#5B49FF"
      />
    </svg>
  );
}; 