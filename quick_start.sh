#!/bin/bash

# Quick Start Script for INU Logistics Multi-Camera System
# This script helps you start the system quickly after initial setup

echo "=== INU Logistics Multi-Camera System Quick Start ==="
echo

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Please run this script from the INU_final directory"
    echo "   Expected structure: INU_final/backend and INU_final/frontend"
    exit 1
fi

echo "📁 Current directory: $(pwd)"
echo

# Function to check if a process is running on a port
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Check if backend is already running
if check_port 5001; then
    echo "⚠️  Backend appears to be already running on port 5001"
    read -p "Do you want to continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Startup cancelled."
        exit 1
    fi
fi

# Check if frontend is already running
if check_port 80; then
    echo "⚠️  Frontend appears to be already running on port 80"
    read -p "Do you want to continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Startup cancelled."
        exit 1
    fi
fi

echo "🔧 Step 1: Checking system setup..."
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run the full setup first."
    echo "   See RASPBERRY_PI_SETUP.md for complete setup instructions."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Run system check
echo "🔍 Running system verification..."
python check_setup.py
setup_result=$?

if [ $setup_result -ne 0 ]; then
    echo "❌ System check failed. Please fix the issues above."
    exit 1
fi

echo
echo "📷 Step 2: Testing cameras (optional)..."
read -p "Do you want to test cameras before starting? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧪 Testing cameras..."
    python test_cameras.py
    camera_result=$?
    
    if [ $camera_result -ne 0 ]; then
        echo "⚠️  Camera test had issues, but continuing..."
    else
        echo "✅ Camera test passed!"
    fi
    echo
fi

echo "🚀 Step 3: Starting backend server..."
echo "   Backend will run on: http://$(hostname -I | awk '{print $1}'):5001"
echo "   Press Ctrl+C to stop the backend"
echo

# Start backend in background and capture its PID
python app.py &
backend_pid=$!

# Give backend time to start
sleep 3

# Check if backend started successfully
if ! kill -0 $backend_pid 2>/dev/null; then
    echo "❌ Backend failed to start"
    exit 1
fi

echo "✅ Backend started successfully (PID: $backend_pid)"
echo

echo "🌐 Step 4: Starting frontend server..."
cd ../frontend

# Check if build exists
if [ ! -d "dist" ]; then
    echo "📦 Build directory not found. Building frontend..."
    npm run build
    if [ $? -ne 0 ]; then
        echo "❌ Frontend build failed"
        kill $backend_pid 2>/dev/null
        exit 1
    fi
fi

echo "   Frontend will run on: http://$(hostname -I | awk '{print $1}'):80"
echo "   You may need to run with sudo for port 80"
echo

# Check if we need sudo for port 80
if [ "$EUID" -ne 0 ] && [ ! -w /etc ]; then
    echo "🔐 Port 80 requires root privileges. Trying with sudo..."
    sudo serve -s dist -l 80 &
else
    serve -s dist -l 80 &
fi

frontend_pid=$!

# Give frontend time to start
sleep 2

echo "✅ Frontend started successfully"
echo

echo "🎉 System is now running!"
echo "================================"
echo "📱 Web Interface: http://$(hostname -I | awk '{print $1}'):80"
echo "🔧 Backend API:   http://$(hostname -I | awk '{print $1}'):5001"
echo "📷 Camera Feeds:"
echo "   Camera A: http://$(hostname -I | awk '{print $1}'):5001/api/camera/0/live_feed"
echo "   Camera B: http://$(hostname -I | awk '{print $1}'):5001/api/camera/1/live_feed"
echo "   Camera C: http://$(hostname -I | awk '{print $1}'):5001/api/camera/2/live_feed"
echo "   Camera D: http://$(hostname -I | awk '{print $1}'):5001/api/camera/3/live_feed"
echo "================================"
echo
echo "💡 Tips:"
echo "   - Access the web interface from any device on your network"
echo "   - Use the Camera page to switch between cameras"
echo "   - Press Ctrl+C to stop both servers"
echo

# Function to cleanup on exit
cleanup() {
    echo
    echo "🛑 Stopping servers..."
    kill $backend_pid 2>/dev/null
    kill $frontend_pid 2>/dev/null
    sudo pkill -f "serve -s dist -l 80" 2>/dev/null
    echo "✅ Servers stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Wait for user to stop
echo "Press Ctrl+C to stop the system..."
wait 