# Session ID Mismatch Troubleshooting Guide

## What Happened

You experienced a **session ID mismatch** that caused a forced logout. Here's what the logs showed:

### The Problem
1. **Working session**: `48e73e76-3871-44eb-8b13-42d572bce201`
2. **Conflicting session**: `4d9af5a1-e915-447a-85d7-f229dfe1b093`

### Root Cause
The most likely cause was **multiple browser tabs or windows** where:
1. You were logged in with the first session ID
2. You opened another tab or refreshed the page, triggering a new login
3. The new login created a new session ID, invalidating the first one
4. When the first tab tried to make API calls, it was rejected because its session was no longer active

## How the System Works

### Single User Access
- Only **one user session** can be active at a time
- When a new login occurs, the previous session is **automatically invalidated**
- This prevents multiple users from accessing the system simultaneously

### Session Validation
- Every API request checks if the token's session ID matches the current active session
- If they don't match, the request is rejected with a "session_invalidated" error
- The frontend detects this and shows an alert before redirecting to login

## New Feature: Precise Equipment Timing

### Exact Timestamp Capture
The system now captures **microsecond-precise timestamps** for equipment operations:

- **시작시간 (Start Time)**: The exact moment when a command is sent to the equipment via serial communication
- **종료시간 (End Time)**: The exact moment when the "done" signal is received from the equipment

### How It Works
1. **Command Sent**: When `serial_mgr.send()` transmits a command to equipment, it records `command_sent_time`
2. **Done Signal**: When the equipment responds with "done" or "fin", it records `done_received_time`
3. **Database Storage**: These precise timestamps are stored in the `work_tasks` table
4. **Frontend Display**: The Camera screen shows these times with millisecond precision

### Technical Implementation
- **Backend**: `serial_io.py` captures exact timestamps using `datetime.now().isoformat(timespec="microseconds")`
- **Database**: `work_tasks.start_time` and `work_tasks.end_time` store the precise timing
- **API**: `/api/activity-logs` joins `product_logs` with `work_tasks` to provide precise timing
- **Frontend**: Times are displayed with millisecond precision and helpful tooltips

### Benefits
- **Accurate Performance Monitoring**: See exactly how long equipment operations take
- **Troubleshooting**: Identify timing issues in equipment communication
- **Process Optimization**: Analyze equipment response times for efficiency improvements

## Prevention Measures Added

### 1. Enhanced Logging
- Added emoji-based logging to easily identify session issues:
  - 🔄 Multiple login detection
  - ❌ Session validation failures
  - ✅ Successful operations
  - 🔍 Debug information

### 2. Frontend Improvements
- **Token replacement detection**: Warns when a token is being replaced
- **Login state management**: Prevents duplicate login attempts
- **Multi-tab warning**: Shows warning about multiple tabs during login
- **Better error messages**: More descriptive alerts about session conflicts
- **Precise timing display**: Shows exact equipment operation times with tooltips

### 3. Backend Improvements
- **Multiple login detection**: Logs when a new login invalidates an existing session
- **Clearer error messages**: Mentions "other tabs" in session invalidation messages
- **Better session tracking**: More detailed logging of session state changes
- **Precise timing capture**: Records exact moments of equipment communication

## Best Practices

### For Users
1. **Use only one browser tab** for the INU system
2. **Don't refresh** the page unnecessarily during login
3. **Close other tabs** before logging in
4. **Wait for login to complete** before opening new tabs
5. **Check timing tooltips** to understand equipment operation precision

### For Developers
1. **Monitor session logs** for multiple login patterns
2. **Check for component re-mounting** issues
3. **Validate navigation logic** to prevent duplicate login attempts
4. **Consider session persistence** strategies if needed
5. **Use precise timing data** for performance analysis

## Troubleshooting Steps

### If You Get "Session Invalidated" Error
1. **Check for multiple tabs**: Close all other tabs with the INU system
2. **Clear browser cache**: Sometimes cached tokens cause conflicts
3. **Wait a moment**: Let any pending requests complete
4. **Login again**: Use a single tab for the new login

### If Multiple Logins Keep Happening
1. **Check browser settings**: Disable auto-refresh extensions
2. **Check network**: Unstable connections can cause duplicate requests
3. **Check for bookmarks**: Multiple bookmarks might open multiple tabs
4. **Check browser history**: Don't use "restore tabs" feature

### If Timing Seems Incorrect
1. **Check tooltips**: Hover over time labels to understand what they represent
2. **Compare with logs**: Backend logs show detailed timing information
3. **Check equipment status**: Ensure equipment is responding properly
4. **Monitor serial communication**: Look for communication delays or errors

## Monitoring

The system now logs detailed information about:
- When multiple logins are detected
- Which session IDs are involved
- Whether the issue is due to server restart or actual multiple logins
- Token replacement events in the frontend
- **Precise equipment timing** for each operation
- **Serial communication delays** and response times

Look for these log patterns:
- `🔄 MULTIPLE LOGIN DETECTED`
- `⚠️⚠️⚠️ WARNING: Token is being replaced`
- `❌ Session validation failed`
- `⏱️ Command sent at [timestamp]`
- `✅ Done signal received at [timestamp]`

## Summary

The session ID mismatch was likely caused by multiple browser tabs or login attempts. The system is now better equipped to detect and handle these situations, with clearer error messages and prevention measures in place.

**Key takeaways**: 
1. Use only one browser tab when working with the INU logistics system to avoid session conflicts
2. The new precise timing feature shows **exact equipment operation times** - hover over time labels for details
3. Start time = when command is sent to equipment, End time = when "done" signal is received 