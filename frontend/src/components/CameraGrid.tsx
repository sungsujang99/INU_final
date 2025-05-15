import React from 'react';
import './CameraGrid.css'; // We'll create this for styles

// Placeholder for where actual video streams would go
const CameraFeedPlaceholder = ({ label, isPrimary }: { label: string; isPrimary: boolean }) => {
  return (
    <div className={`camera-feed ${isPrimary ? 'primary' : 'secondary'}`}>
      <div className="camera-label">{label}</div>
      {/* In a real scenario, this div would be replaced by a <video> tag or an <img> tag */}
      <div className="feed-placeholder-content">
        {/* You can add an SVG or a styled div for the checkered pattern if desired,
            or leave it to be styled by CSS background properties. */}
      </div>
    </div>
  );
};

const CameraGrid = () => {
  return (
    <div className="camera-grid-container">
      <h2 className="camera-grid-title">Camera</h2>
      <div className="camera-layout">
        <div className="primary-camera-wrapper">
          <CameraFeedPlaceholder label="운영 캠1" isPrimary={true} />
        </div>
        <div className="secondary-cameras-wrapper">
          <CameraFeedPlaceholder label="운영 캠2" isPrimary={false} />
          <CameraFeedPlaceholder label="운영 캠3" isPrimary={false} />
          <CameraFeedPlaceholder label="운영 캠4" isPrimary={false} />
        </div>
      </div>
    </div>
  );
};

export default CameraGrid; 