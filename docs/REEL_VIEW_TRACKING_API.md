# Reel View Tracking API Documentation

## Table of Contents
1. [Overview](#overview)
2. [Understanding View Tracking](#understanding-view-tracking)
3. [How It Works](#how-it-works)
4. [API Endpoints](#api-endpoints)
5. [Mobile Application Integration](#mobile-application-integration)
6. [Implementation Strategy](#implementation-strategy)
7. [Data Storage and Cleanup](#data-storage-and-cleanup)
8. [Examples](#examples)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Reel View Tracking API is designed to track when users watch reels in your mobile application. This system enables you to:

- Track which reels users have viewed
- Record how long users watch each reel
- Maintain a "recently viewed reels" history
- Provide personalized recommendations based on viewing behavior
- Optimize database storage by automatically managing view history

### Key Concepts

**View Tracking**: The process of recording when a user watches a reel and how long they watch it.

**View Duration**: The amount of time (in seconds) a user actually watches a reel before scrolling away or the video ends.

**Recently Viewed**: A list of reels a user has recently watched, ordered by most recently viewed first.

**Automatic Cleanup**: The system automatically maintains only the 50 most recent views per user to optimize database performance.

---

## Understanding View Tracking

### Why Track Views?

View tracking serves multiple purposes in a reel-based application:

1. **User Experience**: Users can easily find reels they recently watched
2. **Recommendations**: The system can suggest similar reels based on viewing patterns
3. **Analytics**: Understand which reels are popular and how long users engage with content
4. **Personalization**: Improve the feed by learning user preferences

### What Gets Tracked?

For each view, the system stores:

- **User ID**: Who watched the reel
- **Reel ID**: Which reel was watched
- **Viewed At Timestamp**: When the reel was last viewed (updated on re-watches)
- **View Duration**: How many seconds the user watched (optional but recommended)

### View Duration Significance

View duration helps distinguish between:
- **Quick skips**: User scrolled past quickly (2-3 seconds)
- **Partial views**: User watched part of the reel (10-15 seconds)
- **Complete views**: User watched the entire reel (full duration)

This information is valuable for understanding user engagement and improving content recommendations.

---

## How It Works

### Architecture Overview

The view tracking system follows a simple, efficient pattern:

```
Mobile App → API Call → Backend Processing → Database Storage → Automatic Cleanup
```

### Tracking Flow

1. **User watches a reel**: The mobile app starts tracking locally (no API call yet)
2. **User scrolls away**: The app sends one API call with the view data
3. **Backend processes**: The system updates or creates a view record
4. **Cleanup runs**: If user has more than 50 views, oldest ones are automatically deleted
5. **Data persists**: The view is stored and available for recently viewed queries

### Re-watch Behavior

If a user watches the same reel multiple times:

- The system updates the `viewed_at` timestamp to the most recent time
- The view duration is updated to reflect the latest viewing session
- The reel moves to the top of the "recently viewed" list
- Only one record exists per user per reel (no duplicates)

### Automatic Cleanup Mechanism

To prevent unlimited database growth, the system automatically maintains only the 50 most recent views per user:

- When a new view is tracked, the system checks the total count
- If more than 50 views exist, the oldest views are deleted
- This happens automatically - no manual intervention needed
- The limit is configurable (default: 50, can be changed via `MAX_RECENT_REEL_VIEWS` config)

---

## API Endpoints

### Track Reel View

**Endpoint**: `POST /api/reels/{reel_id}/view`

**Purpose**: Record that a user has viewed a specific reel.

**Authentication**: Required (JWT Token)

**Request Headers**:
```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Path Parameters**:
- `reel_id` (integer, required): The ID of the reel being viewed

**Request Body**:
```json
{
  "view_duration": 15
}
```

**Request Body Parameters**:
- `view_duration` (integer, optional): Number of seconds the user watched the reel
  - Minimum: 0
  - Maximum: Reel's total duration (automatically capped if exceeded)
  - If not provided, tracking still works but without duration information

**Response (Success - 200 OK)**:
```json
{
  "status": "success",
  "message": "View tracked successfully"
}
```

**Response (Error - 401 Unauthorized)**:
```json
{
  "error": "Authentication required"
}
```

**Response (Error - 404 Not Found)**:
```json
{
  "error": "Reel not found"
}
```

**Response (Error - 400 Bad Request)**:
```json
{
  "error": "Reel is not available"
}
```

### Get Recently Viewed Reels

**Endpoint**: `GET /api/reels/recently-viewed`

**Purpose**: Retrieve a paginated list of reels the user has recently viewed.

**Authentication**: Required (JWT Token)

**Query Parameters**:
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page (default: 20, max: 100)
- `fields` (string, optional): Comma-separated list of fields to include

**Response (Success - 200 OK)**:
```json
{
  "status": "success",
  "data": {
    "reels": [
      {
        "reel_id": 123,
        "video_url": "https://...",
        "description": "Check out this product!",
        "viewed_at": "2025-01-15T10:30:00Z",
        "view_duration": 28,
        "likes_count": 250,
        "views_count": 1500,
        "is_liked": false
      }
    ],
    "pagination": {
      "total": 45,
      "pages": 3,
      "current_page": 1,
      "per_page": 20,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

---

## Mobile Application Integration

### Integration Strategy

The recommended approach for mobile applications is to track views efficiently by calling the API only when necessary, rather than making frequent periodic calls.

### Key Principles

1. **Track Locally First**: Start tracking when a reel appears on screen, but don't call the API immediately
2. **Call API on Scroll Away**: Only make an API call when the user scrolls away from a reel
3. **Send Final Duration**: Include the total viewing time in the API call
4. **Handle Errors Gracefully**: Don't block the user experience if tracking fails

### Implementation Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    User Opens Reel Feed                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│          Reel 1 Appears on Screen                            │
│          → Start local tracking (NO API CALL)                │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│          User Watches Reel 1 (tracks time locally)           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│          User Scrolls to Reel 2                              │
│          → Call API: POST /api/reels/1/view                  │
│          → Send: { view_duration: 15 }                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│          Reel 2 Appears on Screen                            │
│          → Start local tracking (NO API CALL)                │
└─────────────────────────────────────────────────────────────┘
```

### Why This Approach?

**Efficiency**: 
- Instead of calling the API every 5 seconds (12 calls per minute per user)
- Call only when scrolling away (2-3 calls per minute per user)
- Reduces API load by 80-90%

**User Experience**:
- No network delays during viewing
- Tracking happens in the background
- App remains responsive

**Accuracy**:
- Get the actual final viewing duration
- No need to estimate or interpolate
- More accurate data for analytics

---

## Implementation Strategy

### Step 1: Initialize Tracker

When your reel feed component loads, initialize a tracker instance:

```javascript
const tracker = new ReelViewTracker(userToken);
```

### Step 2: Start Tracking (No API Call)

When a reel appears on screen, start tracking locally:

```javascript
// User navigates to a reel
tracker.startTracking(reelId);
// At this point, NO API call is made
// The app just records the start time locally
```

### Step 3: Track Viewing Time

While the user watches, track time locally:

```javascript
// Video player updates
const currentTime = videoPlayer.currentTime;
// Store this locally, but don't call API yet
```

### Step 4: Send View Data (Single API Call)

When user scrolls to the next reel, send the view data:

```javascript
// User scrolls/swipes to next reel
const duration = Math.floor(videoPlayer.currentTime);
await tracker.trackView(currentReelId, duration);
// This is the ONLY API call made for this reel
```

### Complete Implementation Example

```javascript
class ReelViewTracker {
  constructor(token) {
    this.token = token;
    this.currentReelData = null;
  }
  
  // Start tracking a reel (local only, no API call)
  startTracking(reelId) {
    // If there's a previous reel, send its data first
    if (this.currentReelData) {
      this.sendViewData();
    }
    
    // Start tracking new reel
    this.currentReelData = {
      reelId: reelId,
      startTime: Date.now()
    };
  }
  
  // Send view data when user scrolls away
  async sendViewData() {
    if (!this.currentReelData) return;
    
    const duration = Math.floor(
      (Date.now() - this.currentReelData.startTime) / 1000
    );
    
    await this.callAPI(
      this.currentReelData.reelId,
      duration
    );
    
    this.currentReelData = null;
  }
  
  // Make API call
  async callAPI(reelId, duration) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/reels/${reelId}/view`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            view_duration: duration
          })
        }
      );
      
      if (!response.ok) {
        throw new Error('Failed to track view');
      }
    } catch (error) {
      // Log error but don't block user experience
      console.error('View tracking error:', error);
      // Optional: Queue for retry
    }
  }
  
  // Cleanup when user leaves feed
  cleanup() {
    if (this.currentReelData) {
      this.sendViewData();
    }
  }
}

// Usage in React Native / React
function ReelFeedScreen() {
  const trackerRef = useRef(null);
  
  useEffect(() => {
    trackerRef.current = new ReelViewTracker(userToken);
    
    return () => {
      // Cleanup on unmount
      trackerRef.current?.cleanup();
    };
  }, []);
  
  const handleReelChange = (newReelId) => {
    trackerRef.current?.startTracking(newReelId);
  };
  
  return (
    <ReelCarousel onReelChange={handleReelChange} />
  );
}
```

---

## Data Storage and Cleanup

### Database Structure

Views are stored in the `user_reel_views` table with the following structure:

- **id**: Unique record identifier
- **user_id**: User who viewed the reel
- **reel_id**: Reel that was viewed
- **viewed_at**: Timestamp of the view (updated on re-watches)
- **view_duration**: Duration in seconds (optional)
- **created_at**: When the record was first created
- **updated_at**: When the record was last updated

### Unique Constraint

The system enforces one view record per user per reel. If a user watches the same reel multiple times:
- The existing record is updated (not duplicated)
- The `viewed_at` timestamp is updated to the most recent time
- The view duration is updated to reflect the latest viewing session

### Automatic Cleanup

**Why Cleanup is Necessary**:
- Without cleanup, view history would grow indefinitely
- Large tables slow down queries
- Most users only need recent viewing history

**How Cleanup Works**:
1. After tracking a view, the system counts total views for the user
2. If count exceeds the limit (default: 50), cleanup is triggered
3. The system identifies the oldest views (ordered by `viewed_at`)
4. Views beyond the limit are deleted
5. Only the most recent 50 views are retained

**Cleanup Behavior**:
- Happens automatically after each view is tracked
- No performance impact (efficient query with index)
- Transparent to the user
- No data loss for recent views

**Configurable Limit**:
The cleanup limit can be adjusted via the `MAX_RECENT_REEL_VIEWS` configuration:
- Default: 50 views per user
- Can be changed in `config.py` or via environment variable
- Balance between storage and user experience

---

## Examples

### Example 1: Basic View Tracking

**Scenario**: User watches a reel for 15 seconds, then scrolls to the next reel.

**Mobile App Actions**:
1. Reel appears: Start local tracking (no API call)
2. User watches: Track time locally
3. User scrolls: Calculate duration (15 seconds)
4. Make API call: `POST /api/reels/123/view` with `{ "view_duration": 15 }`

**Backend Actions**:
1. Validate authentication
2. Verify reel exists
3. Create or update view record
4. Run cleanup if needed
5. Return success response

### Example 2: Quick Skip

**Scenario**: User quickly scrolls past a reel (only 2 seconds).

**Mobile App Actions**:
1. Reel appears: Start local tracking
2. User scrolls quickly: Calculate duration (2 seconds)
3. Make API call: `POST /api/reels/456/view` with `{ "view_duration": 2 }`

**Backend Actions**:
- Same as Example 1
- View duration of 2 seconds is recorded
- Useful for analytics (identifying skipped content)

### Example 3: Re-watching a Reel

**Scenario**: User watches reel 789 for 10 seconds, scrolls away, then watches the same reel again for 20 seconds.

**First View**:
- API call: `POST /api/reels/789/view` with `{ "view_duration": 10 }`
- Creates new view record

**Second View (Same Reel)**:
- API call: `POST /api/reels/789/view` with `{ "view_duration": 20 }`
- Updates existing record (not duplicated)
- `viewed_at` timestamp updated to current time
- View duration updated to 20 seconds
- Reel moves to top of recently viewed list

### Example 4: Full Video Watch

**Scenario**: User watches entire 30-second reel without scrolling.

**Mobile App Actions**:
1. Reel appears: Start local tracking
2. Video plays completely: Track full duration
3. User scrolls or video ends: Calculate duration (30 seconds)
4. Make API call: `POST /api/reels/321/view` with `{ "view_duration": 30 }`

**Backend Actions**:
- Records full view duration
- Useful for identifying engaging content
- May influence recommendation algorithm (full watches = high engagement)

---

## Best Practices

### 1. Call API Only When Necessary

✅ **Do**: Call API when user scrolls away from a reel
❌ **Don't**: Call API periodically (every 5 seconds) while watching

**Reason**: Reduces API load by 80-90% without losing accuracy.

### 2. Track Duration Locally First

✅ **Do**: Track viewing time locally, send final duration in API call
❌ **Don't**: Make API calls to update duration incrementally

**Reason**: Better performance and user experience.

### 3. Handle Errors Gracefully

✅ **Do**: Log errors but continue normal app flow
❌ **Don't**: Block user experience if tracking fails

**Reason**: View tracking is supplementary, not critical for core functionality.

### 4. Send Accurate Duration

✅ **Do**: Calculate duration from video player or timer
❌ **Don't**: Estimate or guess viewing duration

**Reason**: Accurate data improves analytics and recommendations.

### 5. Clean Up on App Close

✅ **Do**: Send pending view data when user exits the feed
❌ **Don't**: Lose tracking data if user closes app abruptly

**Reason**: Ensures all views are tracked.

### 6. Use Appropriate Timeout

✅ **Do**: Set reasonable timeout for API calls (5-10 seconds)
❌ **Don't**: Wait indefinitely for tracking API response

**Reason**: Prevents app from hanging if network is slow.

### 7. Batch Multiple Views (Future Enhancement)

✅ **Consider**: Implementing batch API endpoint for multiple views at once
❌ **Current**: Send one view at a time (acceptable for now)

**Reason**: Further optimization for high-traffic scenarios.

---

## Troubleshooting

### Issue: Recently Viewed API Returns Empty

**Possible Causes**:
1. Views haven't been tracked yet (user hasn't watched any reels)
2. Authentication token is invalid or expired
3. Views were cleaned up (user has more than 50 views)

**Solutions**:
1. Ensure view tracking API is being called when users watch reels
2. Verify JWT token is valid and included in requests
3. Check if user has viewed reels recently (cleanup may have removed older views)

### Issue: View Duration Not Accurate

**Possible Causes**:
1. Duration calculated incorrectly on mobile app
2. Video player time not properly tracked
3. App crashes or closes before sending data

**Solutions**:
1. Use video player's `currentTime` property for accurate duration
2. Implement proper error handling to ensure data is sent
3. Consider sending duration on video end event as well

### Issue: High API Load

**Possible Causes**:
1. Calling API periodically instead of on scroll
2. Not properly batching or debouncing calls
3. Too many concurrent users

**Solutions**:
1. Implement scroll-away strategy (call API only when scrolling)
2. Consider implementing batch endpoint for multiple views
3. Monitor API usage and optimize as needed

### Issue: Views Not Updating on Re-watch

**Possible Causes**:
1. Creating new records instead of updating existing ones
2. Database constraint issues
3. Transaction not committing properly

**Solutions**:
1. Verify unique constraint is working (one record per user per reel)
2. Check database logs for constraint violations
3. Ensure transactions are properly committed

---

## Related Documentation

- [Recently Viewed Reels API](./RECENTLY_VIEWED_REELS_API.md): Documentation for retrieving recently viewed reels
- [Reel Module Comprehensive Documentation](./REEL_MODULE_COMPREHENSIVE_DOCUMENTATION.md): Complete reel system documentation
- [Reels Frontend Implementation Guide](./REELS_FRONTEND_IMPLEMENTATION_GUIDE.md): Frontend integration guide

---

## Support

For issues or questions regarding the Reel View Tracking API, please contact the development team or refer to the main API documentation.

---

**Last Updated**: January 2025
**API Version**: 1.0.0
