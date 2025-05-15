import React from 'react';
import { CircularProgressbar, buildStyles } from 'react-circular-progressbar';
import 'react-circular-progressbar/dist/styles.css';

export const RackBProgress = ({ percentage }) => {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <CircularProgressbar
        value={percentage}
        circleRatio={0.5}
        strokeWidth={22}
        styles={buildStyles({
          rotation: 0.75,
          strokeLinecap: 'round',
          pathTransitionDuration: 0.5,
          pathColor: '#65c4c4',
          trailColor: '#F5F6F8',
          root: { width: '100%', height: '100%', verticalAlign: 'bottom' },
          text: {
            display: 'none',
          },
        })}
      />
    </div>
  );
}; 