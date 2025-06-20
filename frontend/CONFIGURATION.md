# Frontend Configuration Guide

## Dynamic Backend URL Configuration

The frontend now supports dynamic backend URL configuration to work across different environments without hardcoding IP addresses.

## How It Works

The frontend automatically determines the backend URL based on:

1. **Environment Variables** (highest priority)
2. **Current browser location** (for production)
3. **Default fallback** (192.168.0.37:5001)

## Configuration Options

### Option 1: Environment Variables

Create a `.env.local` file in the frontend directory:

```bash
# .env.local
VITE_BACKEND_URL=http://192.168.0.37:5001
```

### Option 2: Environment-Specific Files

For different environments, create:

- `.env.development.local` - for development
- `.env.production.local` - for production

Example `.env.development.local`:
```bash
VITE_BACKEND_URL=http://localhost:5001
```

Example `.env.production.local`:
```bash
VITE_BACKEND_URL=http://192.168.1.100:5001
```

### Option 3: Automatic Detection (Production)

In production builds, the frontend will automatically detect the backend URL based on the current page URL:

- If running on `localhost` → backend at `http://localhost:5001`
- If running on IP (e.g., `192.168.1.50`) → backend at `http://192.168.1.50:5001`
- If running on domain → backend at `http://domain:5001`

## Common Scenarios

### Development on Mac/PC
```bash
# .env.local
VITE_BACKEND_URL=http://localhost:5001
```

### Development with Raspberry Pi Backend
```bash
# .env.local
VITE_BACKEND_URL=http://192.168.0.37:5001
```

### Production on Raspberry Pi
No configuration needed - will auto-detect the Pi's IP address.

### Production with Custom Domain
```bash
# .env.production.local
VITE_BACKEND_URL=https://your-domain.com:5001
```

## Troubleshooting

1. **Socket connection errors**: Check that `VITE_BACKEND_URL` matches your backend server
2. **API calls failing**: Verify the backend is running on the specified URL
3. **Camera stream not loading**: Ensure the backend URL is accessible from your browser

## Files Modified

- `frontend/src/config.js` - Dynamic URL configuration
- `frontend/src/socket.js` - Socket.IO connection
- `frontend/src/screens/Camera/Camera.jsx` - Camera stream and downloads
- `frontend/src/screens/DashboardOn/DashboardOn.jsx` - Reset functionality
- `frontend/src/screens/WorkStatus/WorkStatus.jsx` - Reset functionality
- `frontend/vite.config.js` - Development proxy

## Debug Information

The frontend logs configuration information to the browser console. Check the developer tools console for:

```
Frontend Config: {
  mode: "development",
  dev: true,
  prod: false,
  backendUrl: "http://192.168.0.37:5001",
  socketUrl: "http://192.168.0.37:5001",
  apiBaseUrl: "",
  customBackendUrl: "http://192.168.0.37:5001"
}
``` 