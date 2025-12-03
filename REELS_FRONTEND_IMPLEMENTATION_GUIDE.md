# Reels Module - Frontend Implementation Guide

## 📖 Table of Contents

1. [Overview](#overview)
2. [Understanding Watch Time and Reel Duration](#understanding-watch-time-and-reel-duration)
3. [Quick Start](#quick-start)
4. [Complete User Flows](#complete-user-flows)
5. [API Reference](#api-reference)
6. [Code Examples](#code-examples)
7. [State Management](#state-management)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)
10. [FAQ](#faq)

---

## Overview

### What is the Reels Module?

The Reels Module is a video-based feature where merchants can upload short videos (reels) showcasing their products. Users can:
- Watch reels in an Instagram/TikTok-like vertical feed
- Like, share, and interact with reels
- Discover products through personalized and trending feeds
- Follow merchants to see their latest reels

### Key Concepts

- **Reel**: A short video (max 60 seconds) linked to a product
- **Feed**: A list of reels displayed in a scrollable format
- **Watch Time**: Duration a user watches a reel (for recommendations)
- **Visibility**: Reels are automatically hidden if the linked product goes out of stock

---

## 📹 Understanding Watch Time and Reel Duration

### What is Watch Time?

**Watch Time** is the actual number of seconds a user watches a reel. This is different from the reel's total duration.

### Why is Watch Time Important?

Watch time is **crucial** for the recommendation system because:
1. **It shows user interest**: If someone watches 90% of a reel, they're more interested than someone who watched only 10%
2. **It improves recommendations**: The system learns what you like based on how long you watch each reel
3. **It updates category preferences**: Your preference for different product categories is updated based on watch time

### Two Types of Duration

1. **Reel Duration (`duration_seconds`)**: 
   - The total length of the reel video (e.g., 30 seconds)
   - Set by the merchant when uploading
   - Maximum: 60 seconds
   - This is a property of the reel itself

2. **Watch Time (`view_duration`)**:
   - How long a specific user watched this reel (e.g., 25 seconds)
   - Different for each user
   - Tracked per user per reel
   - Maximum: Cannot exceed reel duration

### How Watch Time Works

#### Example Scenario:

```
Reel Duration: 30 seconds (fixed)
User A watches: 25 seconds → 83% watched
User B watches: 10 seconds → 33% watched
User C watches: 30 seconds → 100% watched
```

The system stores:
- **For User A**: `view_duration = 25` seconds
- **For User B**: `view_duration = 10` seconds  
- **For User C**: `view_duration = 30` seconds

### When to Track Watch Time

**Track watch time when:**
1. ✅ User swipes to the next reel (send duration for previous reel)
2. ✅ User closes the feed (send duration for current reel)
3. ✅ User navigates away from the reel screen

**DO NOT track:**
1. ❌ On every second (creates too many API calls)
2. ❌ If user watched less than 1 second (not meaningful)
3. ❌ When video is paused (pause doesn't count)

### How to Calculate Watch Time

```javascript
// Step 1: Record start time when reel becomes visible
const startTime = Date.now();

// Step 2: When user swipes away, calculate duration
const endTime = Date.now();
const watchDuration = Math.floor((endTime - startTime) / 1000); // Convert to seconds

// Step 3: Send to API (only if > 0 seconds)
if (watchDuration > 0) {
  await trackWatchTime(reelId, watchDuration);
}
```

### Complete Flow Example

```
User Opens Feed
  ↓
Reel #1 Starts Playing → Record startTime = 1000ms
  ↓
User Watches for 15 seconds
  ↓
User Swipes to Reel #2
  ↓
Calculate: (currentTime - startTime) / 1000 = 15 seconds
  ↓
Send to API: GET /api/reels/1?view_duration=15&track_view=true
  ↓
Backend stores: User watched Reel #1 for 15 seconds
  ↓
Backend calculates: 15 / 30 = 50% watched
  ↓
Backend updates: User's category preference (moderate interest)
```

### Watch Time Impact on Recommendations

The backend uses watch time to calculate interest scores:

| Watch Percentage | Interest Level | Category Score |
|-----------------|----------------|----------------|
| ≥ 80% (full watch) | High | +0.1 points |
| 50-80% | Medium | +0.05 points |
| < 50% | Low | +0.02 points |

**Example:**
- You watch a "Mobile Phones" reel for 90% → Your interest in "Mobile Phones" increases
- Next time, you'll see more "Mobile Phones" reels in your feed

### Important Rules

1. **Watch time is stored PER USER per REEL**
   - Each user has their own watch time for each reel
   - Not shared between users

2. **Watch time can be updated**
   - If user watches the same reel again with longer duration, it updates
   - System only counts it as a "re-watch" if duration increases by 25% or more

3. **Watch time is optional**
   - If user is not logged in, watch time is not tracked
   - Feed still works, but recommendations won't improve

4. **Watch time affects view count**
   - First watch: Always increments view count
   - Re-watch: Only increments if watch duration increased significantly (25%+)

### Storing Watch Time

Watch time is stored in the `user_reel_views` table:
- `user_id`: Which user
- `reel_id`: Which reel
- `view_duration`: Watch time in seconds
- Unique per user-reel combination

---

## Quick Start

### Base URL

```
http://127.0.0.1:5110/api
```

### Authentication

Most APIs require a JWT token. Include it in the Authorization header:

```
Authorization: Bearer YOUR_JWT_TOKEN
```

### Get Your Feed

**For New Users (First Time):**
```javascript
GET /api/reels/feed/trending
// Shows popular reels - no login required
```

**For Existing Users:**
```javascript
GET /api/reels/feed/recommended
// Shows personalized reels - login required
```

---

## Complete User Flows

### Flow 1: User Opens the App and Watches Reels

```
Step 1: Check if user is logged in
  ↓
Step 2a: If NEW USER → Show Trending Feed
  GET /api/reels/feed/trending?page=1&per_page=10
  
Step 2b: If EXISTING USER → Check user stats
  GET /api/reels/user/stats
  
  → If is_new_user = true OR likes_count < 3
    → Show Trending Feed
  → Else
    → Show Recommended Feed
    
Step 3: User scrolls through reels
  For each reel displayed:
    - Show video from video_url
    - Show thumbnail from thumbnail_url
    - Display likes_count, views_count
    - Show is_liked status (if logged in)
    
Step 4: When user swipes to next reel
  Track watch time for previous reel:
    GET /api/reels/{reel_id}?view_duration=15&track_view=true
    (15 = seconds user watched)
    
Step 5: User interacts (like/share)
  POST /api/reels/{reel_id}/like
  POST /api/reels/{reel_id}/share
```

### Flow 2: Merchant Uploads a Reel

```
Step 1: Get available products
  GET /api/reels/products/available
  → Shows products merchant can create reels for
  
Step 2: Merchant selects product and video
  - Choose product_id from available list
  - Select video file (max 100MB, max 60s)
  - Write description (max 5000 chars)
  
Step 3: Upload reel
  POST /api/reels
  Body: multipart/form-data
    - video: File
    - product_id: Number
    - description: String
    
Step 4: Reel is immediately visible (no approval needed)
  - Reel appears in feeds right away
  - Will auto-hide if product stock becomes 0
```

### Flow 3: User Likes and Shares a Reel

```
Step 1: User taps like button
  POST /api/reels/{reel_id}/like
  Headers: Authorization: Bearer TOKEN
  
Step 2: Update UI immediately (optimistic update)
  - Change heart icon to filled
  - Increment likes_count in UI
  
Step 3: If API fails, revert UI changes
  
Step 4: User taps share button
  POST /api/reels/{reel_id}/share
  - Increment shares_count
  - Open native share dialog
```

### Flow 4: User Follows a Merchant

```
Step 1: User views merchant profile
  GET /api/reels/merchant/{merchant_id}
  → See merchant's public reels
  
Step 2: User taps "Follow" button
  POST /api/merchants/{merchant_id}/follow
  Headers: Authorization: Bearer TOKEN
  
Step 3: User can now see merchant's reels in "Following" feed
  GET /api/reels/feed/following
```

### Flow 5: Merchant Views Analytics

```
Step 1: Merchant opens analytics screen
  GET /api/reels/merchant/my/analytics
  
Step 2: Display aggregated stats
  - total_reels
  - total_views
  - total_likes
  - total_shares
  - engagement_rate
  
Step 3: Display per-reel stats
  - Each reel's views, likes, shares
  - Sort by views/likes/engagement
```

---

## API Reference

### 🔑 Authentication Levels

1. **Public**: No authentication required
2. **Optional Auth**: Works without login, but better with login
3. **Required Auth**: Must be logged in
4. **Merchant Only**: Must be logged in as merchant

---

### 📊 User Statistics API (Must Call First!)

#### 1. Get User Reel Stats

**When to Use:**
- **FIRST** API to call when user opens the app (if logged in)
- Check if user is new or has enough interactions
- **Decide which feed to show** (trending vs recommended)
- Show user's activity summary

**Endpoint:**
```
GET /api/reels/user/stats
```

**Authentication:** Required

**Request Example:**
```javascript
const response = await fetch('http://127.0.0.1:5110/api/reels/user/stats', {
  headers: {
    'Authorization': `Bearer ${userToken}`
  }
});
```

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "likes_count": 15,
    "views_count": 50,
    "follows_count": 5,
    "total_interactions": 70,
    "is_new_user": false,
    "account_age_days": 30
  }
}
```

**How to Use (Decision Logic):**
```javascript
const stats = response.data;

// Decision: Which feed should we show?
if (stats.is_new_user || stats.likes_count < 3) {
  // User is new or has few interactions → Show Trending Feed
  loadTrendingFeed();
} else {
  // User has enough interactions → Show Personalized Recommended Feed
  loadRecommendedFeed();
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `is_new_user` | boolean | `true` if user has < 3 interactions |
| `likes_count` | integer | Total reels user has liked |
| `views_count` | integer | Total reels user has viewed |
| `follows_count` | integer | Total merchants user follows |
| `total_interactions` | integer | Sum of all interactions |
| `account_age_days` | integer | Days since account creation |

**Important Notes:**
- This API should be called **BEFORE** loading any feed
- Use the response to decide which feed to show
- If user is not logged in, skip this API and show Trending Feed

---

### 📤 Feed APIs

#### 2. Get Recommended Feed

**When to Use:**
- User's main feed (personalized)
- Use after checking user stats
- Only for logged-in users

**Endpoint:**
```
GET /api/reels/feed/recommended
```

**Authentication:** Required

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page (max 100) |
| `fields` | string | null | Comma-separated fields to include (optional) |

**Request Example:**
```javascript
const response = await fetch('http://127.0.0.1:5110/api/reels/feed/recommended?page=1&per_page=10', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${userToken}`
  }
});
```

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "reels": [
      {
        "reel_id": 1,
        "merchant_id": 1,
        "product_id": 1,
        "video_url": "https://res.cloudinary.com/.../video.mp4",
        "thumbnail_url": "https://res.cloudinary.com/.../thumb.jpg",
        "description": "Check out this amazing product!",
        "duration_seconds": 30,
        "views_count": 150,
        "likes_count": 25,
        "shares_count": 10,
        "is_liked": false,
        "product": {
          "product_id": 1,
          "product_name": "Redmi 15 5G",
          "category_id": 2,
          "category_name": "Mobile Phones",
          "stock_qty": 30,
          "selling_price": 9999.98
        },
        "created_at": "2025-11-24T09:59:01"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 10,
      "total": 50,
      "pages": 5,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

**Error Responses:**
- `401 Unauthorized`: User not logged in
- `500 Internal Server Error`: Server error

---

#### 3. Get Trending Feed

**When to Use:**
- New users (first time opening app)
- Users with less than 3 interactions
- Public feed (no login required)

**Endpoint:**
```
GET /api/reels/feed/trending
```

**Authentication:** Optional

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page (max 100) |
| `time_window` | string | "24h" | "24h", "7d", or "30d" |

**Request Example:**
```javascript
// Without authentication (public)
const response = await fetch('http://127.0.0.1:5110/api/reels/feed/trending?page=1&per_page=10');

// With authentication (shows is_liked status)
const response = await fetch('http://127.0.0.1:5110/api/reels/feed/trending?page=1&per_page=10', {
  headers: {
    'Authorization': `Bearer ${userToken}`
  }
});
```

**Response:** Same structure as Recommended Feed

---

#### 4. Get Following Feed

**When to Use:**
- "Following" tab in app
- Show reels only from merchants user follows
- Only for logged-in users

**Endpoint:**
```
GET /api/reels/feed/following
```

**Authentication:** Required

**Query Parameters:** Same as Recommended Feed

**Request Example:**
```javascript
const response = await fetch('http://127.0.0.1:5110/api/reels/feed/following?page=1&per_page=10', {
  headers: {
    'Authorization': `Bearer ${userToken}`
  }
});
```

**Response:** Same structure as Recommended Feed

---

#### 5. Get Public Reels Feed

**When to Use:**
- Browse all public reels
- General discovery
- No login required

**Endpoint:**
```
GET /api/reels/public
```

**Authentication:** Optional

**Query Parameters:** Same as Trending Feed

---

### 🎬 Reel Management APIs

#### 6. Get Single Reel

**When to Use:**
- Track watch time when user finishes watching
- Load specific reel by ID
- Deep linking to a reel

**Endpoint:**
```
GET /api/reels/{reel_id}
```

**Authentication:** Optional

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_view` | boolean | true | Whether to increment view count |
| `view_duration` | integer | null | Watch time in seconds (for tracking) |

**Request Examples:**

```javascript
// Just get reel data (no tracking)
GET /api/reels/1?track_view=false

// Track view with watch time (when user swipes away)
GET /api/reels/1?track_view=true&view_duration=15
```

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "reel_id": 1,
    "merchant_id": 1,
    "product_id": 1,
    "video_url": "https://res.cloudinary.com/.../video.mp4",
    "thumbnail_url": "https://res.cloudinary.com/.../thumb.jpg",
    "description": "Check out this amazing product!",
    "duration_seconds": 30,
    "views_count": 151,
    "likes_count": 25,
    "shares_count": 10,
    "is_visible": true,
    "disabling_reasons": [],
    "is_liked": false,
    "product": {
      "product_id": 1,
      "product_name": "Redmi 15 5G",
      "category_id": 2,
      "category_name": "Mobile Phones",
      "stock_qty": 30,
      "selling_price": 9999.98
    }
  }
}
```

**Important Notes:**
- Feed APIs already return full reel data - you don't need to call this API for each reel in the feed
- Only use this API when you need to track watch time or load a specific reel

---

#### 7. Get Available Products (Merchant Only) - Call Before Upload

**When to Use:**
- **FIRST** step when merchant opens upload screen
- Load products before showing upload form
- Show dropdown/list of products merchant can use

**Endpoint:**
```
GET /api/reels/products/available
```

**Authentication:** Required (Merchant)

**Request Example:**
```javascript
const response = await fetch('http://127.0.0.1:5110/api/reels/products/available', {
  headers: {
    'Authorization': `Bearer ${merchantToken}`
  }
});
```

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "products": [
      {
        "product_id": 1,
        "product_name": "Redmi 15 5G",
        "category_id": 2,
        "category_name": "Mobile Phones",
        "stock_qty": 30,
        "selling_price": 9999.98,
        "thumbnail_url": "https://..."
      }
    ]
  }
}
```

**Important Notes:**
- Call this API **BEFORE** showing the upload form
- Only products with stock > 0 are returned
- Only approved products are shown
- Products must belong to the merchant

---

#### 8. Upload Reel (Merchant Only)

**When to Use:**
- Merchant upload screen
- After selecting product and video (from available products list)

**Endpoint:**
```
POST /api/reels
```

**Authentication:** Required (Merchant)

**Rate Limit:** 10 uploads per hour

**Content-Type:** `multipart/form-data`

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `video` | File | Yes | Video file (MP4, MOV, AVI, MKV) - Max 100MB, Max 60s |
| `product_id` | integer | Yes | Product ID (must be from available products) |
| `description` | string | Yes | Reel description (max 5000 characters) |

**Request Example (React Native):**
```javascript
const formData = new FormData();
formData.append('video', {
  uri: videoUri,
  type: 'video/mp4',
  name: 'reel.mp4'
});
formData.append('product_id', 1);
formData.append('description', 'Check out this amazing product!');

const response = await fetch('http://127.0.0.1:5110/api/reels', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${merchantToken}`,
    'Content-Type': 'multipart/form-data'
  },
  body: formData
});
```

**Response (201 Created):**
```json
{
  "status": "success",
  "message": "Reel uploaded successfully.",
  "data": {
    "reel_id": 1,
    "merchant_id": 1,
    "product_id": 1,
    "video_url": "https://res.cloudinary.com/.../video.mp4",
    "thumbnail_url": "https://res.cloudinary.com/.../thumb.jpg",
    "description": "Check out this amazing product!",
    "duration_seconds": 30,
    "views_count": 0,
    "likes_count": 0,
    "shares_count": 0,
    "is_visible": true,
    "product": {
      "product_id": 1,
      "product_name": "Redmi 15 5G",
      "category_id": 2,
      "category_name": "Mobile Phones",
      "stock_qty": 30,
      "selling_price": 9999.98
    }
  }
}
```

**Validations:**
- Video file required
- Video size ≤ 100MB
- Video duration ≤ 60 seconds
- Product must exist and belong to merchant
- Product must be approved and have stock > 0
- Description required (max 5000 characters)

**Error Responses:**
- `400 Bad Request`: Validation errors (check `error.details`)
- `403 Forbidden`: Not a merchant
- `429 Too Many Requests`: Rate limit exceeded (10 uploads/hour)

---

#### 9. Update Reel Description (Merchant Only)

**When to Use:**
- Edit reel screen
- Update description after upload

**Endpoint:**
```
PUT /api/reels/{reel_id}
```

**Authentication:** Required (Merchant - Owner)

**Request Body:**
```json
{
  "description": "Updated description"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel updated successfully.",
  "data": {
    "reel_id": 1,
    "description": "Updated description",
    "updated_at": "2025-11-24T10:30:00"
  }
}
```

---

#### 10. Delete Reel (Merchant Only)

**When to Use:**
- Delete button on reel
- Merchant's reel management screen

**Endpoint:**
```
DELETE /api/reels/{reel_id}
```

**Authentication:** Required (Merchant - Owner)

**Request Example:**
```javascript
const response = await fetch(`http://127.0.0.1:5110/api/reels/${reelId}`, {
  method: 'DELETE',
  headers: {
    'Authorization': `Bearer ${merchantToken}`
  }
});
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel deleted successfully."
}
```

---

#### 11. Get Merchant's Reels

**When to Use:**
- Merchant's profile/my reels screen
- View own reels with all details

**Endpoint:**
```
GET /api/reels/merchant/my
```

**Authentication:** Required (Merchant)

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page |
| `include_all` | boolean | false | Include non-visible reels |
| `sort_by` | string | "newest" | "newest", "likes", "views", "shares" |

**Response:** Same structure as feed APIs

---

#### 12. Get Merchant's Public Reels

**When to Use:**
- Merchant profile screen (viewed by others)
- Browse a specific merchant's reels

**Endpoint:**
```
GET /api/reels/merchant/{merchant_id}
```

**Authentication:** Optional

**Query Parameters:** Same as "Get Merchant's Reels" (except `include_all`)

---

### ❤️ Interaction APIs

#### 13. Like Reel

**When to Use:**
- User taps like/heart button
- Update like status

**Endpoint:**
```
POST /api/reels/{reel_id}/like
```

**Authentication:** Required

**Request Example:**
```javascript
const response = await fetch(`http://127.0.0.1:5110/api/reels/${reelId}/like`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`
  }
});
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel liked successfully.",
  "data": {
    "reel_id": 1,
    "likes_count": 26,
    "is_liked": true
  }
}
```

**Error Responses:**
- `400 Bad Request`: Already liked
- `401 Unauthorized`: Not logged in
- `404 Not Found`: Reel not found

---

#### 14. Unlike Reel

**When to Use:**
- User taps like button again (to unlike)
- Toggle like off

**Endpoint:**
```
POST /api/reels/{reel_id}/unlike
```

**Authentication:** Required

**Response:**
```json
{
  "status": "success",
  "message": "Reel unliked successfully.",
  "data": {
    "reel_id": 1,
    "likes_count": 25,
    "is_liked": false
  }
}
```

---

#### 15. Share Reel

**When to Use:**
- User taps share button
- Track share action

**Endpoint:**
```
POST /api/reels/{reel_id}/share
```

**Authentication:** Optional (tracks user if authenticated)

**Request Example:**
```javascript
const response = await fetch(`http://127.0.0.1:5110/api/reels/${reelId}/share`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}` // Optional
  }
});

// Then open native share dialog
await Share.share({
  message: `Check out this product: ${reelData.product.product_name}`,
  url: reelData.video_url
});
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel share tracked successfully.",
  "data": {
    "reel_id": 1,
    "shares_count": 11
  }
}
```

---

### 👥 Follow APIs

#### 16. Follow Merchant

**When to Use:**
- User taps "Follow" button on merchant profile
- Follow merchant to see their reels

**Endpoint:**
```
POST /api/merchants/{merchant_id}/follow
```

**Authentication:** Required

**Request Example:**
```javascript
const response = await fetch(`http://127.0.0.1:5110/api/merchants/${merchantId}/follow`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`
  }
});
```

**Response (201 Created):**
```json
{
  "status": "success",
  "message": "Merchant followed successfully.",
  "data": {
    "merchant_id": 1,
    "followed_at": "2025-11-24T10:00:00"
  }
}
```

---

#### 17. Unfollow Merchant

**When to Use:**
- User taps "Unfollow" button
- Remove merchant from following list

**Endpoint:**
```
POST /api/merchants/{merchant_id}/unfollow
```

**Authentication:** Required

---

#### 18. Get Following Merchants

**When to Use:**
- Show list of followed merchants
- Merchant selection screen

**Endpoint:**
```
GET /api/merchants/following
```

**Authentication:** Required

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page |

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "merchants": [
      {
        "merchant_id": 1,
        "business_name": "Tech Store",
        "followed_at": "2025-11-24T10:00:00"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 5,
      "pages": 1
    }
  }
}
```

---

### 📊 Analytics APIs

#### 19. Get Merchant Reel Analytics

**When to Use:**
- Merchant analytics dashboard
- View performance metrics

**Endpoint:**
```
GET /api/reels/merchant/my/analytics
```

**Authentication:** Required (Merchant)

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page (max 100) |
| `start_date` | string | null | ISO format (e.g., "2024-01-01T00:00:00Z") |
| `end_date` | string | null | ISO format |
| `sort_by` | string | "created_at" | "created_at", "views", "likes", "shares", "engagement" |

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "aggregated_stats": {
      "total_reels": 10,
      "total_views": 5000,
      "total_likes": 250,
      "total_shares": 100,
      "engagement_rate": 7.0
    },
    "reels": [
      {
        "reel_id": 1,
        "description": "Check out this product!",
        "views_count": 500,
        "likes_count": 25,
        "shares_count": 10,
        "engagement_rate": 7.0,
        "created_at": "2025-11-24T09:59:01"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 10,
      "pages": 1
    }
  }
}
```

---

### 🔍 Search & Discovery APIs

#### 20. Search Reels

**When to Use:**
- Search screen
- User searches for specific reels/products

**Endpoint:**
```
GET /api/reels/search
```

**Authentication:** Optional

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (searches in description) |
| `category_id` | integer | No | Filter by category |
| `merchant_id` | integer | No | Filter by merchant |
| `page` | integer | No | Page number (default: 1) |
| `per_page` | integer | No | Items per page (default: 20) |

**Request Example:**
```javascript
const query = encodeURIComponent('mobile phone');
const response = await fetch(`http://127.0.0.1:5110/api/reels/search?q=${query}&page=1&per_page=20`);
```

**Response:** Same structure as feed APIs

---

#### 21. Get User's Shared Reels

**When to Use:**
- "My Shared Reels" screen
- View reels user has shared

**Endpoint:**
```
GET /api/reels/user/shared
```

**Authentication:** Required

**Query Parameters:** Standard pagination (page, per_page)

---

### 🗑️ Batch Operations

#### 22. Batch Delete Reels (Merchant Only)

**When to Use:**
- Delete multiple reels at once
- Merchant management screen

**Endpoint:**
```
POST /api/reels/batch/delete
```

**Authentication:** Required (Merchant)

**Rate Limit:** 5 batch operations per hour

**Request Body:**
```json
{
  "reel_ids": [1, 2, 3]
}
```

**Validations:**
- Array length ≤ 50
- All reels must belong to merchant

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Batch delete completed.",
  "data": {
    "results": [
      {
        "reel_id": 1,
        "status": "deleted"
      }
    ],
    "summary": {
      "total": 3,
      "deleted": 3,
      "failed": 0
    }
  }
}
```

---

## Code Examples

This section provides **practical, ready-to-use** code examples for implementing the Reels module in React Native. Each example demonstrates real-world usage patterns and best practices.

### Helper Function: Watch Time Tracker

**Use this utility function to easily track watch time for any reel:**

```javascript
/**
 * Utility function to track reel watch time
 * @param {number} reelId - The reel ID being watched
 * @param {string} token - User authentication token
 * @param {number} duration - Watch duration in seconds
 */
const trackWatchTime = async (reelId, token, duration) => {
  // Don't track if duration is too short or user not logged in
  if (!token || duration < 1) return;

  try {
    const response = await fetch(
      `http://127.0.0.1:5110/api/reels/${reelId}?track_view=true&view_duration=${duration}`,
      {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` }
      }
    );
    
    // Don't throw error - watch time tracking should not break the app
    if (response.ok) {
      console.log(`Tracked ${duration}s watch time for reel ${reelId}`);
    }
  } catch (error) {
    console.warn('Failed to track watch time:', error);
    // Silent fail - don't show error to user
  }
};
```

### React Native - Feed Screen Example

```javascript
import React, { useState, useEffect } from 'react';
import { View, FlatList, ActivityIndicator } from 'react-native';
import { Video } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';

const ReelsFeedScreen = () => {
  const [reels, setReels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [currentWatchTimes, setCurrentWatchTimes] = useState({});

  // Determine which feed to load
  useEffect(() => {
    loadFeed();
  }, []);

  const loadFeed = async () => {
    try {
      const token = await AsyncStorage.getItem('userToken');
      
      // Check if user is new
      if (token) {
        const statsResponse = await fetch('http://127.0.0.1:5110/api/reels/user/stats', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const stats = await statsResponse.json();
        
        if (stats.data.is_new_user || stats.data.likes_count < 3) {
          loadTrendingFeed(token);
        } else {
          loadRecommendedFeed(token);
        }
      } else {
        loadTrendingFeed(null);
      }
    } catch (error) {
      console.error('Error loading feed:', error);
      setLoading(false);
    }
  };

  const loadRecommendedFeed = async (token) => {
    try {
      setLoading(true);
      const response = await fetch(
        `http://127.0.0.1:5110/api/reels/feed/recommended?page=${page}&per_page=10`,
        {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        }
      );
      const data = await response.json();
      
      if (data.status === 'success') {
        setReels(data.data.reels);
        setHasMore(data.data.pagination.has_next);
      }
    } catch (error) {
      console.error('Error loading recommended feed:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadTrendingFeed = async (token) => {
    try {
      setLoading(true);
      const response = await fetch(
        `http://127.0.0.1:5110/api/reels/feed/trending?page=${page}&per_page=10`,
        {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        }
      );
      const data = await response.json();
      
      if (data.status === 'success') {
        setReels(data.data.reels);
        setHasMore(data.data.pagination.has_next);
      }
    } catch (error) {
      console.error('Error loading trending feed:', error);
    } finally {
      setLoading(false);
    }
  };

  // Track watch time when user swipes away
  const trackWatchTime = async (reelId, duration) => {
    try {
      const token = await AsyncStorage.getItem('userToken');
      if (!token) return;

      await fetch(
        `http://127.0.0.1:5110/api/reels/${reelId}?track_view=true&view_duration=${duration}`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
    } catch (error) {
      console.error('Error tracking watch time:', error);
    }
  };

  // Handle like action
  const handleLike = async (reelId, isLiked) => {
    try {
      const token = await AsyncStorage.getItem('userToken');
      if (!token) {
        // Show login prompt
        return;
      }

      const endpoint = isLiked 
        ? `/api/reels/${reelId}/unlike`
        : `/api/reels/${reelId}/like`;

      const response = await fetch(`http://127.0.0.1:5110${endpoint}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const data = await response.json();
      if (data.status === 'success') {
        // Update local state
        setReels(reels.map(reel => 
          reel.reel_id === reelId 
            ? { ...reel, is_liked: !isLiked, likes_count: data.data.likes_count }
            : reel
        ));
      }
    } catch (error) {
      console.error('Error liking reel:', error);
    }
  };

  // Handle share action
  const handleShare = async (reel) => {
    try {
      const token = await AsyncStorage.getItem('userToken');
      
      // Track share
      await fetch(`http://127.0.0.1:5110/api/reels/${reel.reel_id}/share`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      });

      // Open native share
      const Share = require('react-native').Share;
      await Share.share({
        message: `Check out ${reel.product.product_name}: ${reel.description}`,
        url: reel.video_url
      });

      // Update local state
      setReels(reels.map(r => 
        r.reel_id === reel.reel_id 
          ? { ...r, shares_count: r.shares_count + 1 }
          : r
      ));
    } catch (error) {
      console.error('Error sharing reel:', error);
    }
  };

  const renderReel = ({ item: reel, index }) => {
    const [watchStartTime, setWatchStartTime] = useState(Date.now());

    // Track watch time when component unmounts or user swipes
    useEffect(() => {
      return () => {
        const watchDuration = Math.floor((Date.now() - watchStartTime) / 1000);
        if (watchDuration > 0) {
          trackWatchTime(reel.reel_id, watchDuration);
        }
      };
    }, []);

    return (
      <View style={{ height: '100%', width: '100%' }}>
        <Video
          source={{ uri: reel.video_url }}
          style={{ flex: 1 }}
          shouldPlay
          isLooping
          resizeMode="cover"
        />
        <View style={{ position: 'absolute', bottom: 0, padding: 16 }}>
          <Text style={{ color: 'white' }}>{reel.description}</Text>
          <View style={{ flexDirection: 'row', marginTop: 8 }}>
            <Button 
              title={`❤️ ${reel.likes_count}`}
              onPress={() => handleLike(reel.reel_id, reel.is_liked)}
            />
            <Button 
              title={`📤 ${reel.shares_count}`}
              onPress={() => handleShare(reel)}
            />
          </View>
        </View>
      </View>
    );
  };

  if (loading) {
    return <ActivityIndicator size="large" />;
  }

  return (
    <FlatList
      data={reels}
      renderItem={renderReel}
      keyExtractor={(item) => item.reel_id.toString()}
      pagingEnabled
      showsVerticalScrollIndicator={false}
      onEndReached={() => {
        if (hasMore) {
          setPage(page + 1);
          loadFeed();
        }
      }}
    />
  );
};

export default ReelsFeedScreen;
```

---

### React Native - Upload Reel Example

**Important:** This example shows the correct flow: Load available products FIRST, then allow upload.

```javascript
import React, { useState, useEffect } from 'react';
import { View, TextInput, Button, Picker, ActivityIndicator, Text } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import AsyncStorage from '@react-native-async-storage/async-storage';

const UploadReelScreen = () => {
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [description, setDescription] = useState('');
  const [videoUri, setVideoUri] = useState(null);
  const [products, setProducts] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);

  // STEP 1: Load available products FIRST (before showing upload form)
  useEffect(() => {
    loadAvailableProducts();
  }, []);

  const loadAvailableProducts = async () => {
    try {
      const token = await AsyncStorage.getItem('merchantToken');
      const response = await fetch('http://127.0.0.1:5110/api/reels/products/available', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      
      if (data.status === 'success') {
        setProducts(data.data.products);
      }
    } catch (error) {
      console.error('Error loading products:', error);
    } finally {
      setLoading(false);
    }
  };

  const pickVideo = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Videos,
        allowsEditing: true,
        quality: 1,
        videoMaxDuration: 60, // Max 60 seconds
      });

      if (!result.cancelled) {
        setVideoUri(result.uri);
      }
    } catch (error) {
      console.error('Error picking video:', error);
    }
  };

  const uploadReel = async () => {
    if (!videoUri || !selectedProduct || !description.trim()) {
      alert('Please select video, product, and enter description');
      return;
    }

    try {
      setUploading(true);
      const token = await AsyncStorage.getItem('merchantToken');

      const formData = new FormData();
      formData.append('video', {
        uri: videoUri,
        type: 'video/mp4',
        name: 'reel.mp4'
      });
      formData.append('product_id', selectedProduct);
      formData.append('description', description);

      const response = await fetch('http://127.0.0.1:5110/api/reels', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        },
        body: formData
      });

      const data = await response.json();

      if (data.status === 'success') {
        alert('Reel uploaded successfully!');
        // Navigate back or reset form
        setVideoUri(null);
        setDescription('');
        setSelectedProduct(null);
      } else {
        alert(data.message || 'Upload failed');
      }
    } catch (error) {
      console.error('Error uploading reel:', error);
      alert('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return <ActivityIndicator size="large" />;
  }

  return (
    <View style={{ padding: 16 }}>
      <Button title="Select Video" onPress={pickVideo} />
      {videoUri && <Text>Video selected</Text>}

      <Text>Select Product:</Text>
      <Picker
        selectedValue={selectedProduct}
        onValueChange={setSelectedProduct}
      >
        <Picker.Item label="Select a product..." value={null} />
        {products.map(product => (
          <Picker.Item 
            key={product.product_id}
            label={product.product_name}
            value={product.product_id}
          />
        ))}
      </Picker>

      <TextInput
        placeholder="Description (max 5000 characters)"
        value={description}
        onChangeText={setDescription}
        multiline
        maxLength={5000}
        style={{ borderWidth: 1, padding: 8, marginTop: 16, minHeight: 100 }}
      />

      <Button
        title={uploading ? 'Uploading...' : 'Upload Reel'}
        onPress={uploadReel}
        disabled={uploading}
      />
    </View>
  );
};

export default UploadReelScreen;
```

---

## State Management

### Recommended Structure

```javascript
// Reel State Management (using React Context or Redux)

const ReelsContext = createContext();

const ReelsProvider = ({ children }) => {
  const [feedType, setFeedType] = useState('trending'); // 'trending', 'recommended', 'following'
  const [reels, setReels] = useState([]);
  const [currentReelIndex, setCurrentReelIndex] = useState(0);
  const [watchTimes, setWatchTimes] = useState({}); // { reel_id: seconds }
  const [loading, setLoading] = useState(false);
  const [userStats, setUserStats] = useState(null);

  // Load initial feed based on user
  const initializeFeed = async () => {
    const token = await getToken();
    if (!token) {
      setFeedType('trending');
      loadTrendingFeed();
      return;
    }

    const stats = await getUserStats();
    setUserStats(stats);
    
    if (stats.is_new_user || stats.likes_count < 3) {
      setFeedType('trending');
      loadTrendingFeed();
    } else {
      setFeedType('recommended');
      loadRecommendedFeed();
    }
  };

  // Track watch time for a reel
  const startWatching = (reelId) => {
    setWatchTimes(prev => ({
      ...prev,
      [reelId]: { startTime: Date.now() }
    }));
  };

  const stopWatching = async (reelId) => {
    const watchData = watchTimes[reelId];
    if (!watchData) return;

    const duration = Math.floor((Date.now() - watchData.startTime) / 1000);
    await trackWatchTime(reelId, duration);

    setWatchTimes(prev => {
      const newTimes = { ...prev };
      delete newTimes[reelId];
      return newTimes;
    });
  };

  return (
    <ReelsContext.Provider value={{
      feedType,
      reels,
      currentReelIndex,
      loading,
      userStats,
      initializeFeed,
      startWatching,
      stopWatching,
      // ... other functions
    }}>
      {children}
    </ReelsContext.Provider>
  );
};
```

---

## Error Handling

### Standard Error Response Format

All APIs return errors in this format:

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input provided",
    "details": {
      "field": "product_id",
      "message": "Product not found"
    }
  }
}
```

### Common Error Codes

| Code | HTTP Status | Meaning | Action |
|------|-------------|---------|--------|
| `VALIDATION_ERROR` | 400 | Invalid input | Show validation message to user |
| `UNAUTHORIZED` | 401 | Not logged in | Redirect to login |
| `FORBIDDEN` | 403 | No permission | Show error message |
| `NOT_FOUND` | 404 | Resource not found | Show "not found" message |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests | Show rate limit message |
| `INTERNAL_ERROR` | 500 | Server error | Show generic error, retry |

### Error Handling Example

```javascript
const handleApiCall = async (apiCall) => {
  try {
    const response = await apiCall();
    const data = await response.json();

    if (data.status === 'success') {
      return data.data;
    } else {
      // Handle specific error
      const errorCode = data.error?.code;
      const errorMessage = data.error?.message;

      switch (errorCode) {
        case 'UNAUTHORIZED':
          // Redirect to login
          navigation.navigate('Login');
          break;
        case 'RATE_LIMIT_EXCEEDED':
          alert('Too many requests. Please wait a moment.');
          break;
        default:
          alert(errorMessage || 'Something went wrong');
      }
      throw new Error(errorMessage);
    }
  } catch (error) {
    console.error('API Error:', error);
    alert('Network error. Please check your connection.');
    throw error;
  }
};
```

---

## Best Practices

### 1. Watch Time Tracking

- **Start tracking** when reel becomes visible
- **Stop tracking** when user swipes away
- **Send duration** only when user moves to next reel (don't send on every second)
- **Batch watch times** if user watches multiple reels quickly

### 2. Feed Loading

- **Load 10-20 reels** at a time (not all at once)
- **Preload next page** when user reaches 80% of current feed
- **Cache feed data** to reduce API calls
- **Show loading indicator** while fetching

### 3. Like/Share Actions

- **Optimistic updates**: Update UI immediately, revert if API fails
- **Debounce rapid taps**: Prevent multiple API calls
- **Show feedback**: Visual confirmation (heart animation, etc.)

### 4. Video Playback

- **Lazy load videos**: Only load when reel is about to be viewed
- **Preload thumbnails**: Show thumbnail while video loads
- **Handle errors**: Show error message if video fails to load
- **Pause on swipe**: Stop current video when user swipes

### 5. Authentication

- **Store token securely**: Use AsyncStorage or SecureStore
- **Refresh token**: Handle token expiration
- **Handle logout**: Clear token and reset feed

### 6. Performance

- **Use field selection**: Request only needed fields
  ```javascript
  GET /api/reels/feed/recommended?fields=reel_id,video_url,thumbnail_url,likes_count
  ```
- **Image optimization**: Use thumbnail_url for list views
- **Pagination**: Never load all reels at once
- **Cache responses**: Store recent feeds locally

---

## FAQ

### Q1: Do I need to call GET /api/reels/{reel_id} for each reel in the feed?

**No!** Feed APIs (`/api/reels/feed/recommended`, `/api/reels/feed/trending`, etc.) already return complete reel data. Only call the single reel API when:
- You need to track watch time
- You're deep linking to a specific reel
- You need to refresh a single reel's data

### Q2: When should I track watch time?

Track watch time when:
- User swipes to the next reel (send duration for previous reel)
- User closes the feed (send duration for current reel)
- User navigates away from the reel screen

**Don't track:**
- On every second (too many API calls)
- If user watched less than 1 second

### Q3: Which feed should I show to new users?

1. Check user stats: `GET /api/reels/user/stats`
2. If `is_new_user = true` OR `likes_count < 3` → Show **Trending Feed**
3. Otherwise → Show **Recommended Feed**

### Q4: How do I know if a reel is visible?

Check the `is_visible` field in the reel data:
- `true`: Reel is visible and can be watched
- `false`: Reel is hidden (check `disabling_reasons` for why)

### Q5: Can users watch reels without logging in?

Yes! These feeds work without login:
- Trending Feed
- Public Feed
- Merchant's Public Reels

But users need to login to:
- Like reels
- Follow merchants
- Get personalized recommendations
- Track watch time (for better recommendations)

### Q6: What happens if a product goes out of stock?

The reel automatically becomes invisible (`is_visible = false`) and gets `PRODUCT_OUT_OF_STOCK` in `disabling_reasons`. The reel will automatically become visible again when stock is restored.

### Q7: How do I handle rate limits?

Only these endpoints have rate limits:
- Upload Reel: 10 per hour
- Batch Delete: 5 per hour

For uploads:
- Show progress indicator
- Warn user if approaching limit
- Queue uploads if limit reached

### Q8: Can I update reel video?

No, you cannot update the video. You can only:
- Update description (`PUT /api/reels/{reel_id}`)
- Delete and re-upload

### Q9: How do I implement pull-to-refresh?

```javascript
const [refreshing, setRefreshing] = useState(false);

const onRefresh = async () => {
  setRefreshing(true);
  setPage(1);
  await loadFeed();
  setRefreshing(false);
};

<FlatList
  refreshControl={
    <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
  }
  // ... other props
/>
```

### Q10: How do I implement infinite scroll?

```javascript
const loadMore = () => {
  if (!loading && hasMore) {
    setPage(page + 1);
    loadFeed(); // Append to existing reels
  }
};

<FlatList
  onEndReached={loadMore}
  onEndReachedThreshold={0.5}
  // ... other props
/>
```

---

## Complete API Quick Reference

| # | Endpoint | Method | Auth | Use Case |
|---|----------|--------|------|----------|
| 1 | `/api/reels/user/stats` | GET | Required | **First API to call** - Get user stats, decide feed type |
| 2 | `/api/reels/feed/recommended` | GET | Required | Personalized feed for logged-in users |
| 3 | `/api/reels/feed/trending` | GET | Optional | Popular reels (new users, public) |
| 4 | `/api/reels/feed/following` | GET | Required | Reels from followed merchants |
| 5 | `/api/reels/public` | GET | Optional | All public reels |
| 6 | `/api/reels/{reel_id}` | GET | Optional | Get single reel, track watch time |
| 7 | `/api/reels/products/available` | GET | Merchant | **First step for upload** - Get products for upload |
| 8 | `/api/reels` | POST | Merchant | Upload new reel |
| 9 | `/api/reels/{reel_id}` | PUT | Merchant | Update description |
| 10 | `/api/reels/{reel_id}` | DELETE | Merchant | Delete reel |
| 11 | `/api/reels/merchant/my` | GET | Merchant | Get own reels |
| 12 | `/api/reels/merchant/{merchant_id}` | GET | Optional | Get merchant's public reels |
| 13 | `/api/reels/{reel_id}/like` | POST | Required | Like a reel |
| 14 | `/api/reels/{reel_id}/unlike` | POST | Required | Unlike a reel |
| 15 | `/api/reels/{reel_id}/share` | POST | Optional | Share a reel |
| 16 | `/api/merchants/{merchant_id}/follow` | POST | Required | Follow merchant |
| 17 | `/api/merchants/{merchant_id}/unfollow` | POST | Required | Unfollow merchant |
| 18 | `/api/merchants/following` | GET | Required | Get followed merchants |
| 19 | `/api/reels/merchant/my/analytics` | GET | Merchant | Get analytics dashboard |
| 20 | `/api/reels/search` | GET | Optional | Search reels |
| 21 | `/api/reels/user/shared` | GET | Required | Get user's shared reels |
| 22 | `/api/reels/batch/delete` | POST | Merchant | Delete multiple reels |

---

## Summary

### Key Takeaways

1. **Feed APIs return complete reel data** - no need to call single reel API for each item
2. **Track watch time** when user swipes to next reel (send duration)
3. **New users** should see Trending Feed first
4. **Reels are immediately visible** after upload (no approval)
5. **Reels auto-hide** when product stock is 0
6. **Optimistic updates** for like/share for better UX
7. **Use pagination** - load 10-20 reels at a time

### Next Steps

1. Set up authentication (JWT token storage)
2. Implement feed screen with video playback
3. Add like/share functionality
4. Implement watch time tracking
5. Add merchant upload flow
6. Test with real data

---

**Need Help?** Check the comprehensive documentation: `REEL_MODULE_COMPREHENSIVE_DOCUMENTATION.md`

