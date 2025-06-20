# Raspberry Pi Setup Guide for INU Logistics System with Multi-Camera Adapter

## Prerequisites
- Fresh Raspberry Pi OS installation
- Multi-camera adapter hardware connected
- Internet connection
- SSH access or direct terminal access

## Step 1: System Update and Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-venv python3-dev libcap-dev python3-libcamera python3-kms++ git nodejs npm

# Install camera and I2C tools
sudo apt install -y libcamera-dev libcamera-tools libcamera-apps i2c-tools

# Enable camera and I2C interfaces
sudo raspi-config nonint do_camera 0
sudo raspi-config nonint do_i2c 0

# Reboot to apply interface changes
sudo reboot
```

## Step 2: Get the Project Code

```bash
# Navigate to your project directory
cd ~/INU_final

# Or if you need to copy/clone the project:
# git clone <your-repo-url> INU_final
# cd INU_final
```

## Step 3: Backend Setup

```bash
cd ~/INU_final/backend

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install additional packages for multi-camera support
pip install RPi.GPIO opencv-python

# Create symbolic links for system camera libraries
ln -sf /usr/lib/python3/dist-packages/libcamera venv/lib/python3.*/site-packages/ 2>/dev/null || true
ln -sf /usr/lib/python3/dist-packages/pykms venv/lib/python3.*/site-packages/ 2>/dev/null || true

# Initialize database
python -c "from db import init_db; init_db()"

# Add initial user
python add_user.py
```

## Step 4: Multi-Camera Hardware Verification

```bash
# Check system setup
python check_setup.py

# Test I2C communication
sudo i2cdetect -y 1
# Should show device at address 0x70

# Test cameras
python test_cameras.py
```

## Step 5: Frontend Setup

```bash
cd ~/INU_final/frontend

# Install Node.js dependencies
npm install

# Build production version
npm run build

# Install serve globally for serving the built frontend
sudo npm install -g serve
```

## Step 6: Configure User Permissions

```bash
# Add user to necessary groups
sudo usermod -a -G dialout $USER
sudo usermod -a -G gpio $USER
sudo usermod -a -G i2c $USER

# Create udev rule for USB devices
sudo tee /etc/udev/rules.d/99-usb-serial.rules > /dev/null <<EOF
SUBSYSTEM=="tty", ATTRS{idVendor}=="*", GROUP="dialout", MODE="0666"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Logout and login again for group changes to take effect
# Or reboot the system
sudo reboot
```

## Step 7: Quick Start Commands

After system reboot, use these commands to start the application:

```bash
# Navigate to project
cd ~/INU_final

# Start backend
cd backend
source venv/bin/activate
python app.py

# In another terminal, start frontend
cd ~/INU_final/frontend
serve -s dist -l 80
```

## Step 8: Configure Services (Optional - for auto-start)

### Backend Service

```bash
sudo tee /etc/systemd/system/inu-backend.service > /dev/null <<EOF
[Unit]
Description=INU Logistics Backend with Multi-Camera
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/INU_final/backend
Environment=PATH=$HOME/INU_final/backend/venv/bin
ExecStart=$HOME/INU_final/backend/venv/bin/python app.py
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
User=$USER
WorkingDirectory=$HOME/INU_final/frontend
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

## Step 9: Access the System

1. **Find your Pi's IP address:**
   ```bash
   hostname -I
   ```

2. **Access the web interface:**
   - If using systemd services: `http://[PI_IP_ADDRESS]`
   - If running manually: `http://[PI_IP_ADDRESS]:3000`

3. **Camera feeds:**
   - Camera A: `http://[PI_IP_ADDRESS]:5001/api/camera/0/live_feed`
   - Camera B: `http://[PI_IP_ADDRESS]:5001/api/camera/1/live_feed`
   - Camera C: `http://[PI_IP_ADDRESS]:5001/api/camera/2/live_feed`
   - Camera D: `http://[PI_IP_ADDRESS]:5001/api/camera/3/live_feed`

## Multi-Camera Hardware Setup

Your system uses a multi-camera adapter with the following configuration:

| Camera | I2C Command | GPIO Pins (7,11,12) | Name |
|--------|-------------|---------------------|------|
| 0 | `i2cset -y 1 0x70 0x00 0x04` | (False,False,True) | Camera A |
| 1 | `i2cset -y 1 0x70 0x00 0x05` | (True,False,True) | Camera B |
| 2 | `i2cset -y 1 0x70 0x00 0x06` | (False,True,False) | Camera C |
| 3 | `i2cset -y 1 0x70 0x00 0x07` | (True,True,False) | Camera D |

## Troubleshooting

### Camera Issues
```bash
# Check camera detection
libcamera-hello --list-cameras

# Test camera capture
libcamera-still -o test.jpg --timeout 2000

# Check I2C device
sudo i2cdetect -y 1
```

### Permission Issues
```bash
# Check groups
groups $USER

# If missing groups, add them:
sudo usermod -a -G dialout,gpio,i2c $USER
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
```

## Features Enabled

✅ **4-Camera Multi-Adapter Support** - Hardware switching between cameras  
✅ **Single User Access** - Only one user can be logged in at a time  
✅ **Dynamic IP Configuration** - Automatically adapts to network changes  
✅ **Reset Functionality** - Complete system reset via UI  
✅ **Live Camera Switching** - Real-time camera feed switching  
✅ **Serial Communication** - USB device communication for hardware  
✅ **Real-time Updates** - Socket.IO for live data updates  
✅ **Task Management** - CSV upload and batch processing  
✅ **Inventory Tracking** - Real-time inventory management  

## Quick Startup Sequence (After Initial Setup)

```bash
# 1. Check hardware
cd ~/INU_final/backend
source venv/bin/activate
python check_setup.py

# 2. Test cameras (optional)
python test_cameras.py

# 3. Start backend
python app.py

# 4. In another terminal, start frontend
cd ~/INU_final/frontend
serve -s dist -l 80
```

Your INU Logistics system with 4-camera support is now ready for production use! 