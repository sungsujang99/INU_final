# Raspberry Pi Setup Guide for INU Logistics System

## Prerequisites
- Fresh Raspberry Pi OS installation
- Internet connection
- SSH access or direct terminal access

## Step 1: System Update and Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-venv python3-dev libcap-dev python3-libcamera python3-kms++ git nodejs npm

# Install additional camera dependencies
sudo apt install -y libcamera-dev libcamera-tools

# Enable camera interface
sudo raspi-config nonint do_camera 0
```

## Step 2: Get the Project Code

```bash
# Clone or copy your project to the Pi
# If using git:
# git clone <your-repo-url> inu_upgrade
# cd inu_upgrade

# Or if copying from another source, ensure the project is in ~/inu_upgrade
```

## Step 3: Backend Setup

```bash
cd ~/inu_upgrade/backend

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Create symbolic links for system camera libraries
ln -sf /usr/lib/python3/dist-packages/libcamera venv/lib/python3.*/site-packages/
ln -sf /usr/lib/python3/dist-packages/pykms venv/lib/python3.*/site-packages/

# Initialize database
python -c "from db import init_db; init_db()"

# Add initial user (replace with your credentials)
python add_user.py
```

## Step 4: Frontend Setup

```bash
cd ~/inu_upgrade/frontend

# Install Node.js dependencies
npm install

# Build production version
npm run build

# Install serve globally for serving the built frontend
sudo npm install -g serve
```

## Step 5: Configure Network and IP

```bash
# Get current IP address
hostname -I

# Note: Update the IP address in the configuration if needed
# The system now uses dynamic IP detection, but you can set a static IP if desired
```

## Step 6: Configure Services (Optional - for auto-start)

Create systemd services for automatic startup:

### Backend Service

```bash
sudo tee /etc/systemd/system/inu-backend.service > /dev/null <<EOF
[Unit]
Description=INU Logistics Backend
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/inu_upgrade/backend
Environment=PATH=/home/pi/inu_upgrade/backend/venv/bin
ExecStart=/home/pi/inu_upgrade/backend/venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

### Frontend Service

```bash
sudo tee /etc/systemd/system/inu-frontend.service > /dev/null <<EOF
[Unit]
Description=INU Logistics Frontend
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/inu_upgrade/frontend
ExecStart=/usr/local/bin/serve -s dist -l 80
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

### Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable inu-backend.service
sudo systemctl enable inu-frontend.service

# Start services
sudo systemctl start inu-backend.service
sudo systemctl start inu-frontend.service

# Check status
sudo systemctl status inu-backend.service
sudo systemctl status inu-frontend.service
```

## Step 7: Configure USB Serial Permissions

```bash
# Add user to dialout group for USB serial access
sudo usermod -a -G dialout $USER

# Create udev rule for USB devices
sudo tee /etc/udev/rules.d/99-usb-serial.rules > /dev/null <<EOF
SUBSYSTEM=="tty", ATTRS{idVendor}=="*", GROUP="dialout", MODE="0666"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Step 8: Test the Installation

```bash
# Test backend manually
cd ~/inu_upgrade/backend
source venv/bin/activate
python app.py

# In another terminal, test if backend is responding
curl http://localhost:5001/api/ping

# Test frontend (if not using systemd service)
cd ~/inu_upgrade/frontend
serve -s dist -l 3000
```

## Step 9: Access the System

1. **Find your Pi's IP address:**
   ```bash
   hostname -I
   ```

2. **Access the web interface:**
   - If using systemd services: `http://[PI_IP_ADDRESS]`
   - If running manually: `http://[PI_IP_ADDRESS]:3000`

3. **API endpoint:**
   - `http://[PI_IP_ADDRESS]:5001/api/ping`

## Troubleshooting

### Camera Issues
```bash
# Check camera detection
libcamera-hello --list-cameras

# Test camera capture
libcamera-still -o test.jpg
```

### Serial Device Issues
```bash
# List USB devices
lsusb

# List serial devices
ls -la /dev/ttyUSB*
ls -la /dev/ttyACM*

# Check permissions
groups $USER
```

### Service Issues
```bash
# Check service logs
sudo journalctl -u inu-backend.service -f
sudo journalctl -u inu-frontend.service -f

# Restart services
sudo systemctl restart inu-backend.service
sudo systemctl restart inu-frontend.service
```

### Network Issues
```bash
# Check if ports are open
sudo netstat -tlnp | grep :5001
sudo netstat -tlnp | grep :80

# Check firewall (if enabled)
sudo ufw status
```

## Environment Configuration

Create environment file for custom backend URL if needed:

```bash
# Create frontend/.env.local
cd ~/inu_upgrade/frontend
echo "VITE_BACKEND_URL=http://$(hostname -I | awk '{print $1}'):5001" > .env.local
```

## Security Notes

1. **Change default passwords** for any user accounts
2. **Enable SSH key authentication** instead of password auth
3. **Configure firewall** if needed:
   ```bash
   sudo ufw enable
   sudo ufw allow 22    # SSH
   sudo ufw allow 80    # HTTP
   sudo ufw allow 5001  # Backend API
   ```

## Quick Start Commands

After initial setup, use these commands:

```bash
# Start backend manually
cd ~/inu_upgrade/backend && source venv/bin/activate && python app.py

# Start frontend manually
cd ~/inu_upgrade/frontend && serve -s dist -l 80

# Or use systemd services
sudo systemctl start inu-backend.service
sudo systemctl start inu-frontend.service
```

## Features Enabled

✅ **Single User Access** - Only one user can be logged in at a time  
✅ **Dynamic IP Configuration** - Automatically adapts to network changes  
✅ **Reset Functionality** - Complete system reset via UI  
✅ **Camera Integration** - Live camera feed and monitoring  
✅ **Serial Communication** - USB device communication for hardware  
✅ **Real-time Updates** - Socket.IO for live data updates  
✅ **Task Management** - CSV upload and batch processing  
✅ **Inventory Tracking** - Real-time inventory management  

Your INU Logistics system is now ready for production use! 