# Single User Access Implementation

## Overview

The web application now supports **single user access only**, meaning only one user can be logged in and use the system at any given time. When a new user logs in, any previously logged-in user will be automatically logged out.

## How It Works

### 1. Session Management
- Each login creates a unique session ID
- Only one session can be active at a time
- When a new user logs in, the previous session is invalidated

### 2. Token Validation
- Every API request checks if the token's session ID matches the current active session
- If sessions don't match, the request is rejected with a "session_invalidated" error

### 3. Automatic Logout
- Users are automatically logged out when another user logs in
- Session monitoring checks every 30 seconds for session validity
- Users receive an alert when their session is invalidated

## Features

### Backend Features
- **Session Tracking**: Global session management with unique session IDs
- **Automatic Invalidation**: Previous sessions are invalidated on new login
- **API Endpoints**:
  - `POST /api/logout` - Logout current user
  - `GET /api/session-status` - Get current session information

### Frontend Features
- **Session Monitor**: Automatic detection of session invalidation
- **Graceful Logout**: Proper cleanup when logging out
- **Session Status Display**: Dashboard shows current active user
- **Auto-redirect**: Automatic redirect to login when session is invalidated

## User Experience

### When Logging In
1. User enters credentials and clicks login
2. If another user was logged in, they are automatically logged out
3. New user gets access to the system

### When Session is Invalidated
1. User receives alert: "다른 사용자가 로그인했습니다. 다시 로그인해주세요."
2. User is automatically redirected to login page
3. Local storage is cleared

### Dashboard Information
The dashboard now shows:
- **사용자 세션**: Active/Inactive status
- **현재 사용자**: Username of currently logged-in user

## Technical Implementation

### Backend Changes
- `backend/auth.py`: Added session management with global session tracking
- `backend/app.py`: Added logout and session-status endpoints
- Session validation in `token_required` decorator

### Frontend Changes
- `frontend/src/lib/api.jsx`: Added logout and session status functions
- `frontend/src/components/SessionMonitor.jsx`: Monitors session validity
- `frontend/src/App.jsx`: Includes SessionMonitor globally
- Updated logout handlers in all components

## Configuration

No additional configuration is required. The single user access is enabled by default.

## Benefits

1. **Resource Protection**: Prevents multiple users from interfering with each other
2. **Data Integrity**: Ensures only one user can modify system state at a time
3. **Hardware Safety**: Prevents conflicting commands to physical equipment
4. **Clear Ownership**: Always know who is currently using the system

## Limitations

1. **No Concurrent Access**: Only one user can use the system at a time
2. **Forced Logout**: Users may be logged out without warning when another user logs in
3. **No User Queue**: No mechanism to queue users waiting for access

## Troubleshooting

### Session Not Updating
- Check browser console for session monitor errors
- Verify backend `/api/session-status` endpoint is working

### Automatic Logout Not Working
- Ensure SessionMonitor is included in App.jsx
- Check that session checking interval is running (every 30 seconds)

### Multiple Users Still Able to Login
- Verify backend session management is working
- Check that `current_active_session` global variable is being updated

## Future Enhancements

Possible improvements for the future:
1. **User Queue System**: Allow users to queue for access
2. **Session Timeout**: Automatic logout after inactivity
3. **Admin Override**: Allow admin users to force logout other users
4. **Session Notifications**: Real-time notifications about session changes 