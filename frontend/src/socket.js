import { io } from 'socket.io-client';

// Raspberry Pi's IP address
const SOCKET_URL = 'http://192.168.0.37:5001'; 

export const socket = io(SOCKET_URL, {
  autoConnect: true,
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionAttempts: 5,
  timeout: 20000,
});

// Optional: Add listeners for connect/disconnect/error for debugging
socket.on('connect', () => {
  console.log('Socket connected:', socket.id);
});

socket.on('disconnect', (reason) => {
  console.log('Socket disconnected:', reason);
  if (reason === 'io server disconnect') {
    // the disconnection was initiated by the server, you need to reconnect manually
    socket.connect();
  }
  // else the socket will automatically try to reconnect
});

socket.on('connect_error', (err) => {
  console.error('Socket connection error:', err.message, err.description, err.data);
}); 