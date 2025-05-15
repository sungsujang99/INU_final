import React from 'react';
import { CircularProgressbar, buildStyles } from 'react-circular-progressbar';
import 'react-circular-progressbar/dist/styles.css';

export const RackAProgress = ({ percentage }) => {
  // The parent container (.overlap-group-2) defines the size (153x95)
  // Let this component fill that container
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <CircularProgressbar
        value={percentage}
        circleRatio={0.5} // Half circle
        strokeWidth={22} // Adjusted stroke width
        styles={buildStyles({
          rotation: 0.75, // Starts from bottom-left, goes counter-clockwise
          strokeLinecap: 'round',
          pathTransitionDuration: 0.5,
          pathColor: '#65c4c4', // Updated color for A, B, C progress
          trailColor: '#F5F6F8', // White background trail
          // Let the SVG fill the container, maybe adjust vertical alignment
          root: { width: '100%', height: '100%', verticalAlign: 'bottom' },
          text: {
            display: 'none', // No text inside
          },
        })}
      />
    </div>
  );
}; 