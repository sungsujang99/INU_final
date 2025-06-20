#!/bin/bash

# Setup script to configure INU Logistics system to start automatically on boot
# Run this script on the Raspberry Pi as the pi user

set -e

echo "Setting up INU Logistics system for automatic startup..."

# Get the current user and home directory
CURRENT_USER=$(whoami)
HOME_DIR=$(eval echo ~$CURRENT_USER)
PROJECT_DIR="$HOME_DIR/inu_upgrade"

echo "Current user: $CURRENT_USER"
echo "Home directory: $HOME_DIR"
echo "Project directory: $PROJECT_DIR"

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "ERROR: Project directory $PROJECT_DIR does not exist!"
    echo "Please ensure the inu_upgrade project is located at $PROJECT_DIR"
    exit 1
fi

# Create systemd service files with correct paths
echo "Creating systemd service files..."

# Backend service
sudo tee /etc/systemd/system/inu-logistics-backend.service > /dev/null <<EOF
[Unit]
Description=INU Logistics Backend Server
After=network.target
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR/backend
Environment=PATH=$PROJECT_DIR/backend/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$PROJECT_DIR/backend/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Give the service time to start up
TimeoutStartSec=60

# Environment variables
Environment=PYTHONPATH=$PROJECT_DIR/backend
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
EOF

# Frontend service
sudo tee /etc/systemd/system/inu-logistics-frontend.service > /dev/null <<EOF
[Unit]
Description=INU Logistics Frontend Server
After=network.target inu-logistics-backend.service
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR/frontend
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=NODE_ENV=production
ExecStart=/usr/bin/npm run dev -- --host 0.0.0.0
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Give the service time to start up
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF

echo "Service files created successfully."

# Reload systemd to recognize new services
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable services to start on boot
echo "Enabling services to start on boot..."
sudo systemctl enable inu-logistics-backend.service
sudo systemctl enable inu-logistics-frontend.service

echo "Services enabled successfully."

# Check if virtual environment exists for backend
if [ ! -d "$PROJECT_DIR/backend/venv" ]; then
    echo "WARNING: Python virtual environment not found at $PROJECT_DIR/backend/venv"
    echo "Creating virtual environment..."
    cd "$PROJECT_DIR/backend"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    echo "Virtual environment created and dependencies installed."
fi

# Check if node_modules exists for frontend
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
    echo "WARNING: Node modules not found at $PROJECT_DIR/frontend/node_modules"
    echo "Installing frontend dependencies..."
    cd "$PROJECT_DIR/frontend"
    npm install
    echo "Frontend dependencies installed."
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "The INU Logistics system will now start automatically when the Raspberry Pi boots."
echo ""
echo "Service management commands:"
echo "  Start services:    sudo systemctl start inu-logistics-backend inu-logistics-frontend"
echo "  Stop services:     sudo systemctl stop inu-logistics-backend inu-logistics-frontend"
echo "  Restart services:  sudo systemctl restart inu-logistics-backend inu-logistics-frontend"
echo "  Check status:      sudo systemctl status inu-logistics-backend inu-logistics-frontend"
echo "  View logs:         sudo journalctl -u inu-logistics-backend -f"
echo "                     sudo journalctl -u inu-logistics-frontend -f"
echo "  Disable autostart: sudo systemctl disable inu-logistics-backend inu-logistics-frontend"
echo ""
echo "To test the services now, run:"
echo "  sudo systemctl start inu-logistics-backend"
echo "  sudo systemctl start inu-logistics-frontend"
echo ""
echo "The system will be available at:"
echo "  Backend:  http://$(hostname -I | awk '{print $1}'):5001"
echo "  Frontend: http://$(hostname -I | awk '{print $1}'):5173" 