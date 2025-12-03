# Reels Module - Comprehensive Documentation

## Table of Contents
1. [Overview](#overview)
2. [What is the Reels Module?](#what-is-the-reels-module)
3. [Architecture & Design](#architecture--design)
4. [Database Schema](#database-schema)
5. [API Reference](#api-reference)
6. [Mobile Application Flow](#mobile-application-flow)
7. [Edge Cases & Validations](#edge-cases--validations)
8. [Production Readiness Features](#production-readiness-features)
9. [Advanced Features](#advanced-features)
10. [Implementation Details](#implementation-details)
11. [Error Handling](#error-handling)
12. [Performance Optimizations](#performance-optimizations)
13. [Security Features](#security-features)
14. [Testing Guide](#testing-guide)

---

## Overview

The **Reels Module** is a comprehensive video content management system designed for the AOIN mobile application. It enables merchants to create short-form video content (reels) showcasing their products, and provides users with personalized feeds, trending content, and social interaction features.

### Key Features
- **Video Upload & Management**: Merchants can upload product showcase videos
- **Immediate Visibility**: Reels are visible to the public immediately upon upload (no admin approval required)
- **Personalized Feeds**: Algorithm-based recommendation system with multiple tiers
- **Social Interactions**: Like, share, view tracking with user-specific data
- **Analytics**: Comprehensive analytics for merchants
- **Search & Discovery**: Full-text search and filtering capabilities
- **Batch Operations**: Efficient bulk operations for merchants
- **Admin Moderation**: Post-upload moderation capabilities

---

## What is the Reels Module?

The Reels Module is a **short-form video content platform** integrated into the AOIN e-commerce application. It serves multiple purposes:

### For Merchants:
1. **Product Marketing**: Create engaging video content to showcase products
2. **Brand Building**: Build brand presence through video storytelling
3. **Performance Tracking**: Monitor reel performance through analytics
4. **Customer Engagement**: Interact with customers through video content

### For Users:
1. **Product Discovery**: Discover products through engaging video content
2. **Entertainment**: Consume short-form video content similar to TikTok/Instagram Reels
3. **Personalized Experience**: Receive content tailored to their preferences
4. **Social Interaction**: Like, share, and follow favorite merchants

### Core Functionality:
- **Video Storage**: Cloud-based video storage with CDN delivery (Cloudinary/AWS S3)
- **Real-time Visibility**: Dynamic visibility based on product stock and status
- **Recommendation Engine**: Multi-tier algorithmic recommendation system using rule-based scoring, collaborative filtering, and time decay
- **Interaction Tracking**: Comprehensive tracking of user interactions for personalization
- **Content Moderation**: Admin tools for content moderation (optional)

---

## Architecture & Design

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Mobile Application                        │
│                    (React Native)                            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ HTTP/REST API
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                    Flask Backend API                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Routes     │  │ Controllers  │  │   Services   │      │
│  │  (Endpoints)│→ │  (Business   │→ │ (Logic &     │      │
│  │              │  │   Logic)     │  │  Algorithms) │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                 │
│  ┌─────────────────────────▼─────────────────────────────┐ │
│  │                    Models Layer                         │ │
│  │  (SQLAlchemy ORM - Database Abstraction)               │ │
│  └─────────────────────────┬─────────────────────────────┘ │
└────────────────────────────┼─────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼──────┐    ┌────────▼────────┐  ┌───────▼──────┐
│   MySQL      │    │     Redis       │  │  Cloudinary/  │
│  Database    │    │     Cache       │  │   AWS S3     │
│              │    │                 │  │   Storage    │
└──────────────┘    └──────────────────┘  └──────────────┘
```

### Module Structure

```
Ecommerce_Backend/
├── models/
│   ├── reel.py                          # Reel model
│   ├── user_reel_like.py                # User-reel like tracking
│   ├── user_reel_view.py                # User-reel view tracking
│   ├── user_reel_share.py               # User-reel share tracking
│   ├── user_merchant_follow.py         # Merchant follow system
│   └── user_category_preference.py      # Category preferences
│
├── controllers/
│   ├── reels_controller.py              # Main reels business logic
│   ├── follow_controller.py             # Follow/unfollow logic
│   ├── recommendation_controller.py     # Feed endpoints
│   └── reels_errors.py                  # Error handling
│
├── routes/
│   ├── reels_routes.py                  # Reels API endpoints
│   ├── follow_routes.py                 # Follow API endpoints
│   └── recommendation_routes.py       # Feed API endpoints
│
├── services/
│   ├── recommendation_service.py        # Recommendation algorithm
│   └── storage/
│       ├── base_storage_service.py       # Storage abstraction
│       ├── cloudinary_storage_service.py # Cloudinary implementation
│       ├── aws_storage_service.py       # AWS S3 implementation
│       └── storage_factory.py           # Storage factory
│
└── migrations/
    └── sql/
        └── 001_create_reels_system_complete.sql   # Complete reels system migration (all tables, indexes, fulltext)
```

### Design Patterns Used

1. **MVC Pattern**: Routes → Controllers → Models
2. **Service Layer Pattern**: Business logic separated into services
3. **Factory Pattern**: Storage service factory for provider switching
4. **Strategy Pattern**: Different recommendation strategies (tiers)
5. **Repository Pattern**: Model layer abstracts database access
6. **Decorator Pattern**: Rate limiting, authentication decorators

---

## Database Schema

### Core Tables

#### 1. `reels` Table
Stores all reel information.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `reel_id` | INT | Primary key | AUTO_INCREMENT |
| `merchant_id` | INT | Merchant who created reel | NOT NULL, FK |
| `product_id` | INT | Linked product | NOT NULL, FK |
| `video_url` | VARCHAR(512) | CDN video URL | NOT NULL |
| `video_public_id` | VARCHAR(255) | Storage provider ID | NULL |
| `thumbnail_url` | VARCHAR(512) | Thumbnail image URL | NULL |
| `thumbnail_public_id` | VARCHAR(255) | Thumbnail storage ID | NULL |
| `description` | TEXT | Reel description | NOT NULL |
| `duration_seconds` | INT | Video duration | NULL |
| `file_size_bytes` | BIGINT | File size | NULL |
| `video_format` | VARCHAR(10) | Format (mp4, mov, etc.) | NULL |
| `resolution` | VARCHAR(20) | Video resolution | NULL |
| `views_count` | INT | Total views | DEFAULT 0 |
| `likes_count` | INT | Total likes | DEFAULT 0 |
| `shares_count` | INT | Total shares | DEFAULT 0 |
| `is_active` | BOOLEAN | Active status | DEFAULT TRUE |
| `approval_status` | VARCHAR(20) | Approval status | DEFAULT 'approved' |
| `approved_at` | DATETIME | Approval timestamp | NULL |
| `approved_by` | INT | Admin who approved | NULL, FK |
| `rejection_reason` | VARCHAR(255) | Rejection reason | NULL |
| `created_at` | DATETIME | Creation timestamp | NOT NULL |
| `updated_at` | DATETIME | Update timestamp | NOT NULL |
| `deleted_at` | DATETIME | Soft delete timestamp | NULL |

**Indexes:**
- Primary: `reel_id`
- Foreign Keys: `merchant_id`, `product_id`, `approved_by`
- Composite: `idx_reels_trending` (created_at, views_count, likes_count, shares_count)
- Composite: `idx_reels_merchant_created` (merchant_id, created_at)
- Composite: `idx_reels_product_visibility` (product_id, deleted_at, is_active)
- Composite: `idx_reels_merchant_feed` (merchant_id, created_at, is_active, deleted_at)

#### 2. `user_reel_likes` Table
Tracks which users like which reels.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | INT | Primary key | AUTO_INCREMENT |
| `user_id` | INT | User who liked | NOT NULL, FK |
| `reel_id` | INT | Liked reel | NOT NULL, FK |
| `created_at` | DATETIME | Like timestamp | NOT NULL |

**Constraints:**
- Unique: `(user_id, reel_id)` - Prevents duplicate likes

#### 3. `user_reel_views` Table
Tracks user views and watch time.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | INT | Primary key | AUTO_INCREMENT |
| `user_id` | INT | User who viewed | NOT NULL, FK |
| `reel_id` | INT | Viewed reel | NOT NULL, FK |
| `viewed_at` | DATETIME | View timestamp | NOT NULL |
| `view_duration` | INT | Watch time in seconds | NULL |

**Constraints:**
- Unique: `(user_id, reel_id)` - One record per user-reel pair

#### 4. `user_reel_shares` Table
Tracks user shares.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | INT | Primary key | AUTO_INCREMENT |
| `user_id` | INT | User who shared | NOT NULL, FK |
| `reel_id` | INT | Shared reel | NOT NULL, FK |
| `shared_at` | DATETIME | Share timestamp | NOT NULL |

**Constraints:**
- Unique: `(user_id, reel_id)` - Prevents duplicate share tracking

#### 5. `user_merchant_follows` Table
Tracks merchant follow relationships.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | INT | Primary key | AUTO_INCREMENT |
| `user_id` | INT | User who follows | NOT NULL, FK |
| `merchant_id` | INT | Followed merchant | NOT NULL, FK |
| `followed_at` | DATETIME | Follow timestamp | NOT NULL |

**Constraints:**
- Unique: `(user_id, merchant_id)` - Prevents duplicate follows

#### 6. `user_category_preferences` Table
Stores calculated user category preferences.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | INT | Primary key | AUTO_INCREMENT |
| `user_id` | INT | User ID | NOT NULL, FK |
| `category_id` | INT | Category ID | NOT NULL, FK |
| `preference_score` | DECIMAL(5,2) | Preference score (0-1) | DEFAULT 0.0 |
| `interaction_count` | INT | Total interactions | DEFAULT 0 |
| `last_interaction_at` | DATETIME | Last interaction time | NULL |

**Constraints:**
- Unique: `(user_id, category_id)` - One preference per user-category

### Relationships

```
User ──┬──> UserReelLike ──> Reel
       ├──> UserReelView ──> Reel
       ├──> UserReelShare ──> Reel
       ├──> UserMerchantFollow ──> MerchantProfile
       └──> UserCategoryPreference ──> Category

MerchantProfile ──> Reel ──> Product ──> Category
```

---

## API Reference

### Base URL
```
http://127.0.0.1:5110/api
```

### Authentication
Most endpoints require JWT authentication. Include token in header:
```
Authorization: Bearer <jwt_token>
```

---

### Reels Management APIs

#### 1. Upload Reel
**POST** `/api/reels`

Upload a new reel video.

**Authentication:** Required (Merchant only)

**Rate Limit:** 10 uploads per hour

**Request:**
- **Content-Type:** `multipart/form-data`
- **Body:**
  - `video` (file, required): Video file (MP4, MOV, AVI, MKV)
    - Max size: 100MB
    - Max duration: 60 seconds
  - `product_id` (integer, required): Product ID to link
    - Must be approved product
    - Must belong to merchant
    - Must have stock > 0
    - Must be parent product (not variant)
  - `description` (string, required): Reel description
    - Max length: 5000 characters
    - Cannot be empty

**Validations:**
1. User must be authenticated
2. User must be a merchant
3. Video file must be provided
4. Video file must have valid extension (.mp4, .mov, .avi, .mkv)
5. Video file size ≤ 100MB
6. Video duration ≤ 60 seconds
7. Video MIME type validation (file header check)
8. Product ID must be provided
9. Product must exist and not be deleted
10. Product must belong to merchant
11. Product must be approved
12. Product must be active
13. Product must be parent (not variant)
14. Product must have stock > 0
15. Description must be provided
16. Description length ≤ 5000 characters

**Response (201 Created):**
```json
{
  "status": "success",
  "message": "Reel uploaded successfully.",
  "data": {
    "reel_id": 1,
    "merchant_id": 1,
    "product_id": 1,
    "video_url": "https://res.cloudinary.com/...",
    "thumbnail_url": "https://res.cloudinary.com/...",
    "description": "Check out this amazing product!",
    "duration_seconds": 30,
    "file_size_bytes": 9840497,
    "video_format": "mp4",
    "views_count": 0,
    "likes_count": 0,
    "shares_count": 0,
    "is_active": true,
    "is_visible": true,
    "disabling_reasons": [],
    "product": {
      "product_id": 1,
      "product_name": "Redmi 15 5G",
      "category_id": 2,
      "category_name": "Mobile Phones",
      "stock_qty": 30,
      "selling_price": 9999.98
    },
    "created_at": "2025-11-24T09:59:01",
    "updated_at": "2025-11-24T09:59:01"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Validation errors
- `403 Forbidden`: Not a merchant
- `404 Not Found`: User not found
- `500 Internal Server Error`: Server errors

---

#### 2. Get Single Reel
**GET** `/api/reels/{reel_id}`

Get a single reel by ID. Automatically tracks view if user is authenticated.

**Authentication:** Optional

**Query Parameters:**
- `track_view` (boolean, optional): Whether to increment view count (default: true)
- `view_duration` (integer, optional): View duration in seconds (for tracking watch time)
- `fields` (string, optional): Comma-separated list of fields to include

**Validations:**
1. Reel ID must be valid integer
2. Reel must exist
3. If `view_duration` provided:
   - Must be ≥ 0
   - Must be ≤ reel duration (if reel has duration)
4. If user authenticated and `track_view=true`:
   - Creates/updates UserReelView record
   - Updates category preference based on watch percentage
   - Increments view count (only for first view or significant re-watch)

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "reel_id": 1,
    "merchant_id": 1,
    "product_id": 1,
    "video_url": "https://res.cloudinary.com/...",
    "thumbnail_url": "https://res.cloudinary.com/...",
    "description": "Check out this amazing product!",
    "duration_seconds": 30,
    "views_count": 150,
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
    },
    "created_at": "2025-11-24T09:59:01",
    "updated_at": "2025-11-24T10:30:15"
  }
}
```

**Error Responses:**
- `404 Not Found`: Reel not found

---

#### 3. Get Merchant's Reels
**GET** `/api/reels/merchant/my`

Get current merchant's reels.

**Authentication:** Required (Merchant only)

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)
- `include_all` (boolean, optional): Include non-visible reels (default: false)
- `category_id` (integer, optional): Filter by category
- `start_date` (string, optional): Start date filter (ISO format)
- `end_date` (string, optional): End date filter (ISO format)
- `sort_by` (string, optional): Sort field (newest, likes, views, shares)
- `fields` (string, optional): Comma-separated fields to include

**Validations:**
1. User must be authenticated
2. User must be a merchant
3. Page must be ≥ 1
4. Per page must be ≤ 100
5. Date formats must be valid ISO format
6. Sort field must be valid

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [
    {
      "reel_id": 1,
      "product_id": 1,
      "description": "Check out this amazing product!",
      "views_count": 150,
      "likes_count": 25,
      "shares_count": 10,
      "is_visible": true,
      "disabling_reasons": [],
      "product": { ... },
      "created_at": "2025-11-24T09:59:01"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 45,
    "pages": 3
  }
}
```

---

#### 4. Get Merchant's Public Reels
**GET** `/api/reels/merchant/{merchant_id}`

Get public visible reels for a specific merchant.

**Authentication:** Not required

**Query Parameters:**
- `merchant_id` (path parameter): Merchant ID
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)
- `fields` (string, optional): Comma-separated fields to include

**Validations:**
1. Merchant ID must be valid integer
2. Merchant must exist
3. Only visible reels are returned

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [ ... ],
  "pagination": { ... }
}
```

---

#### 5. Get Public Reels Feed
**GET** `/api/reels/public`

Get all public visible reels (for general feed).

**Authentication:** Not required

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)
- `category_id` (integer, optional): Filter by category
- `merchant_id` (integer, optional): Filter by merchant
- `start_date` (string, optional): Start date filter (ISO format)
- `end_date` (string, optional): End date filter (ISO format)
- `sort_by` (string, optional): Sort field (newest, likes, views, shares)
- `fields` (string, optional): Comma-separated fields to include

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [ ... ],
  "pagination": { ... },
  "filters_applied": {
    "category_id": null,
    "merchant_id": null,
    "start_date": null,
    "end_date": null,
    "sort_by": "newest"
  }
}
```

---

#### 6. Update Reel Description
**PUT** `/api/reels/{reel_id}`

Update reel description.

**Authentication:** Required (Merchant owner only)

**Request Body:**
```json
{
  "description": "Updated description"
}
```

**Validations:**
1. User must be authenticated
2. User must be a merchant
3. Reel must exist
4. Reel must belong to merchant
5. Description must be provided
6. Description cannot be empty
7. Description length ≤ 5000 characters

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel updated successfully",
  "data": { ... }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid description
- `403 Forbidden`: Not owner
- `404 Not Found`: Reel not found

---

#### 7. Delete Reel
**DELETE** `/api/reels/{reel_id}`

Soft delete a reel.

**Authentication:** Required (Merchant owner only)

**Validations:**
1. User must be authenticated
2. User must be a merchant
3. Reel must exist
4. Reel must belong to merchant

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel deleted successfully"
}
```

**Note:** 
- Performs soft delete (sets `deleted_at`)
- Deletes video from storage (non-critical, logs warning if fails)
- Reel becomes invisible immediately

---

#### 8. Get Available Products
**GET** `/api/reels/products/available`

Get merchant's approved products with stock > 0 that can be used for reel upload.

**Authentication:** Required (Merchant only)

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [
    {
      "product_id": 1,
      "product_name": "Redmi 15 5G",
      "category_id": 2,
      "category_name": "Mobile Phones",
      "stock_qty": 30,
      "selling_price": 9999.98
    }
  ]
}
```

---

### Interaction APIs

#### 9. Like Reel
**POST** `/api/reels/{reel_id}/like`

Like a reel (increment like count with user tracking).

**Authentication:** Required

**Validations:**
1. User must be authenticated
2. Reel must exist
3. Reel must be visible
4. User must not have already liked this reel

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel liked successfully",
  "data": {
    "reel_id": 1,
    "likes_count": 26,
    "is_liked": true
  }
}
```

**Side Effects:**
- Creates UserReelLike record
- Increments reel.likes_count
- Updates user's category preference (+0.3 score)
- Invalidates user's recommendation cache

---

#### 10. Unlike Reel
**POST** `/api/reels/{reel_id}/unlike`

Unlike a reel (decrement like count).

**Authentication:** Required

**Validations:**
1. User must be authenticated
2. Reel must exist
3. User must have liked this reel

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel unliked successfully",
  "data": {
    "reel_id": 1,
    "likes_count": 25,
    "is_liked": false
  }
}
```

**Side Effects:**
- Removes UserReelLike record
- Decrements reel.likes_count (won't go below 0)
- Updates user's category preference (-0.15 score)
- Invalidates user's recommendation cache

---

#### 11. Share Reel
**POST** `/api/reels/{reel_id}/share`

Track reel share (increment share count).

**Authentication:** Optional (tracks user if authenticated)

**Validations:**
1. Reel must exist
2. Reel must be visible

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel share tracked successfully",
  "data": {
    "reel_id": 1,
    "shares_count": 11,
    "user_tracked": true
  }
}
```

**Side Effects:**
- Creates UserReelShare record (if authenticated)
- Increments reel.shares_count

---

### Analytics & Stats APIs

#### 12. Get User Reel Stats
**GET** `/api/reels/user/stats`

Get user's reel interaction statistics.

**Authentication:** Required

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "likes_count": 45,
    "views_count": 120,
    "follows_count": 8,
    "total_interactions": 173,
    "is_new_user": false,
    "account_age_days": 45
  }
}
```

**Use Case:** Mobile app uses this to determine which feed to show:
- New users (< 3 interactions): Show trending feed
- Existing users: Show personalized feed

---

#### 13. Get Merchant Reel Analytics
**GET** `/api/reels/merchant/my/analytics`

Get merchant's reel analytics with aggregated stats and per-reel statistics.

**Authentication:** Required (Merchant only)

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)
- `start_date` (string, optional): Start date filter (ISO format)
- `end_date` (string, optional): End date filter (ISO format)
- `sort_by` (string, optional): Sort field (created_at, views, likes, shares, engagement)

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "aggregated_stats": {
      "total_reels": 45,
      "total_views": 15000,
      "total_likes": 2500,
      "total_shares": 800,
      "average_engagement_rate": 22.0,
      "average_views_per_reel": 333.33,
      "average_likes_per_reel": 55.56
    },
    "reel_stats": [
      {
        "reel_id": 1,
        "product_id": 1,
        "product_name": "Redmi 15 5G",
        "description": "Check out this amazing product!",
        "views_count": 150,
        "likes_count": 25,
        "shares_count": 10,
        "engagement_rate": 23.33,
        "is_visible": true,
        "disabling_reasons": [],
        "created_at": "2025-11-24T09:59:01"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 45,
      "pages": 3
    },
    "filters_applied": {
      "start_date": null,
      "end_date": null,
      "sort_by": "created_at"
    }
  }
}
```

---

#### 14. Get User's Shared Reels
**GET** `/api/reels/user/shared`

Get reels that the current user has shared.

**Authentication:** Required

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)
- `fields` (string, optional): Comma-separated fields to include

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [
    {
      "reel_id": 1,
      "product_id": 1,
      "video_url": "...",
      "shared_at": "2025-11-24T10:15:30",
      ...
    }
  ],
  "pagination": { ... }
}
```

---

### Search & Discovery APIs

#### 15. Search Reels
**GET** `/api/reels/search`

Search reels by description, product name, or merchant name.

**Authentication:** Not required

**Query Parameters:**
- `q` (string, required): Search query
- `category_id` (integer, optional): Filter by category
- `merchant_id` (integer, optional): Filter by merchant
- `start_date` (string, optional): Start date filter (ISO format)
- `end_date` (string, optional): End date filter (ISO format)
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)
- `fields` (string, optional): Comma-separated fields to include

**Validations:**
1. Search query must be provided
2. Search query cannot be empty
3. Date formats must be valid ISO format

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [ ... ],
  "pagination": { ... },
  "search_info": {
    "query": "amazing product",
    "filters": {
      "category_id": null,
      "merchant_id": null,
      "start_date": null,
      "end_date": null
    }
  }
}
```

---

### Batch Operations APIs

#### 16. Batch Delete Reels
**POST** `/api/reels/batch/delete`

Delete multiple reels in a batch operation.

**Authentication:** Required (Merchant only)

**Rate Limit:** 5 batch operations per hour

**Request Body:**
```json
{
  "reel_ids": [1, 2, 3]
}
```

**Validations:**
1. User must be authenticated
2. User must be a merchant
3. `reel_ids` array must be provided
4. `reel_ids` must be an array
5. Array length ≤ 50
6. Array cannot be empty
7. All reels must exist
8. All reels must belong to merchant

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Batch delete completed: 3/3 reels deleted",
  "data": {
    "results": [
      {
        "reel_id": 1,
        "status": "success",
        "message": "Reel deleted successfully"
      },
      {
        "reel_id": 2,
        "status": "success",
        "message": "Reel deleted successfully"
      }
    ],
    "summary": {
      "total": 3,
      "successful": 3,
      "failed": 0
    }
  }
}
```

---

### Follow System APIs

#### 18. Follow Merchant
**POST** `/api/merchants/{merchant_id}/follow`

Follow a merchant to see their reels in following feed.

**Authentication:** Required

**Validations:**
1. User must be authenticated
2. Merchant must exist
3. User must not already be following merchant

**Response (201 Created):**
```json
{
  "status": "success",
  "message": "Merchant followed successfully",
  "data": {
    "merchant_id": 1,
    "is_following": true
  }
}
```

**Side Effects:**
- Creates UserMerchantFollow record
- Invalidates user's recommendation and following feed caches

---

#### 19. Unfollow Merchant
**POST** `/api/merchants/{merchant_id}/unfollow`

Unfollow a merchant.

**Authentication:** Required

**Validations:**
1. User must be authenticated
2. Merchant must exist
3. User must be following merchant

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Merchant unfollowed successfully",
  "data": {
    "merchant_id": 1,
    "is_following": false
  }
}
```

**Side Effects:**
- Removes UserMerchantFollow record
- Invalidates user's recommendation and following feed caches

---

#### 20. Get Following Merchants
**GET** `/api/merchants/following`

Get list of merchants the user follows.

**Authentication:** Required

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [
    {
      "merchant_id": 1,
      "business_name": "Tech Store",
      "followed_at": "2025-11-20T10:00:00"
    }
  ],
  "pagination": { ... }
}
```

---

### Recommendation Feed APIs

#### 21. Get Recommended Feed
**GET** `/api/reels/feed/recommended`

Get personalized recommendation feed for authenticated user.

**Authentication:** Required

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)
- `fields` (string, optional): Comma-separated fields to include

**Algorithm:**
- **Cold Start** (< 3 interactions): 70% trending + 30% category diversity
- **Personalized** (≥ 3 interactions):
  - 40% followed merchants
  - 30% category-based
  - 20% trending
  - 10% similar users
  - Fill with general feed

**Diversity Constraints:**
- Max 3 reels per merchant
- Max 5 reels per category

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [ ... ],
  "pagination": { ... },
  "feed_info": {
    "feed_type": "recommended",
    "tiers_used": ["followed", "category", "trending", "similar_users"],
    "generated_at": "2025-11-24T10:30:00"
  }
}
```

**Caching:** 5 minutes TTL

---

#### 22. Get Trending Feed
**GET** `/api/reels/feed/trending`

Get trending reels feed (public, optional auth for is_liked).

**Authentication:** Optional

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)
- `time_window` (string, optional): Time window (24h, 7d, 30d) (default: 24h)
- `fields` (string, optional): Comma-separated fields to include

**Trending Score Formula:**
```
trending_score = (engagement_score * time_decay) / (hours_old + 1)

Where:
- engagement_score = (likes * 2) + (shares * 3) + (views * 0.1)
- time_decay = 1.0 for < 6 hours, 0.8 for < 24 hours, 0.5 for < 7 days
- Boost: 1.5x for reels < 6 hours old
```

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [ ... ],
  "pagination": { ... },
  "feed_info": {
    "feed_type": "trending",
    "time_window": "24h",
    "generated_at": "2025-11-24T10:30:00"
  }
}
```

**Caching:** 10 minutes TTL

---

#### 23. Get Following Feed
**GET** `/api/reels/feed/following`

Get reels from followed merchants only.

**Authentication:** Required

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)
- `fields` (string, optional): Comma-separated fields to include

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [ ... ],
  "pagination": { ... },
  "feed_info": {
    "feed_type": "following",
    "followed_merchants_count": 8,
    "generated_at": null
  }
}
```

**Caching:** 5 minutes TTL

---

### Admin Moderation APIs

#### 24. Approve Reel (Admin)
**POST** `/api/admin/reels/{reel_id}/approve`

Approve a reel (admin only). Note: Reels are auto-approved, this is for future use.

**Authentication:** Required (Admin only)

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel approved successfully",
  "data": { ... }
}
```

---

#### 25. Reject Reel (Admin)
**POST** `/api/admin/reels/{reel_id}/reject`

Reject a reel with reason (admin only).

**Authentication:** Required (Admin only)

**Request Body:**
```json
{
  "rejection_reason": "Violates community guidelines"
}
```

**Validations:**
1. User must be authenticated
2. User must be admin
3. Reel must exist
4. Rejection reason must be provided
5. Rejection reason length ≤ 255 characters

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel rejected successfully",
  "data": { ... }
}
```

---

#### 26. Hide Reel (Admin)
**POST** `/api/admin/reels/{reel_id}/hide`

Hide a reel from public view (admin only).

**Authentication:** Required (Admin only)

**Validations:**
1. User must be authenticated
2. User must be admin
3. Reel must exist

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel hidden successfully",
  "data": { ... }
}
```

**Side Effects:**
- Sets `is_active = False`
- Invalidates all feed caches

---

#### 27. Get Pending Reels (Admin)
**GET** `/api/admin/reels/pending`

Get pending reels for moderation (admin only). Note: Currently returns empty as reels are auto-approved.

**Authentication:** Required (Admin only)

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page, max 100 (default: 20)

**Response (200 OK):**
```json
{
  "status": "success",
  "data": [ ... ],
  "pagination": { ... }
}
```

---

## Mobile Application Flow

### User Journey Flows

#### 1. New User Onboarding Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    App Launch                               │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│         Check User Stats: GET /api/reels/user/stats        │
└───────────────────────┬─────────────────────────────────────┘
                        │
            ┌───────────┴───────────┐
            │                       │
    is_new_user = true      is_new_user = false
    (< 3 interactions)      (≥ 3 interactions)
            │                       │
            ▼                       ▼
┌───────────────────┐    ┌──────────────────────┐
│  Show Trending    │    │  Show Recommended    │
│  Feed             │    │  Feed                │
│  GET /api/reels/  │    │  GET /api/reels/     │
│  feed/trending    │    │  feed/recommended    │
└───────────────────┘    └──────────────────────┘
```

#### 2. Reel Viewing Flow

```
┌─────────────────────────────────────────────────────────────┐
│              User Swipes to Next Reel                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    GET /api/reels/{reel_id}?track_view=true                │
│    (Automatically tracks view)                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    Display Reel:                                            │
│    - Video player                                           │
│    - Product info                                           │
│    - Like/Share buttons                                     │
│    - Merchant info                                          │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ User Likes   │ │ User Shares  │ │ User Watches │
│ POST /api/   │ │ POST /api/   │ │ (Tracked     │
│ reels/{id}/  │ │ reels/{id}/  │ │ automatically│
│ like         │ │ share        │ │ with view_   │
│              │ │              │ │ duration)    │
└──────────────┘ └──────────────┘ └──────────────┘
```

#### 3. Merchant Upload Flow

```
┌─────────────────────────────────────────────────────────────┐
│         Merchant Opens Upload Screen                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    GET /api/reels/products/available                       │
│    (Get list of eligible products)                          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    Merchant:                                                │
│    1. Selects product                                       │
│    2. Records/selects video                                 │
│    3. Enters description                                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    POST /api/reels (multipart/form-data)                   │
│    - video: File                                            │
│    - product_id: Integer                                    │
│    - description: String                                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    Backend Processing:                                      │
│    1. Validates file (size, format, MIME type)             │
│    2. Validates product                                    │
│    3. Uploads to Cloudinary/AWS                            │
│    4. Generates thumbnail                                   │
│    5. Extracts metadata (duration, size)                   │
│    6. Creates reel record (auto-approved)                   │
│    7. Reel immediately visible to public                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    Success Response: Reel data with URLs                   │
│    Reel is now visible in all feeds                         │
└─────────────────────────────────────────────────────────────┘
```

#### 4. Feed Navigation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Feed Screen                               │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Recommended │ │   Trending   │ │   Following   │
│  Feed        │ │   Feed       │ │   Feed        │
│  (Personal)  │ │  (Public)    │ │  (Followed)   │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    User Swipes Through Reels                                │
│    - Each swipe loads next reel                             │
│    - View automatically tracked                            │
│    - Watch time tracked (if provided)                       │
└─────────────────────────────────────────────────────────────┘
```

#### 5. Search & Discovery Flow

```
┌─────────────────────────────────────────────────────────────┐
│         User Enters Search Query                            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    GET /api/reels/search?q={query}&category_id={id}        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│    Display Search Results:                                  │
│    - Filtered reels                                        │
│    - Pagination support                                    │
│    - Category/Merchant filters                              │
└─────────────────────────────────────────────────────────────┘
```

### State Management in Mobile App

#### Recommended State Structure

```javascript
{
  // User State
  user: {
    id: number,
    isAuthenticated: boolean,
    stats: {
      likes_count: number,
      views_count: number,
      follows_count: number,
      is_new_user: boolean
    }
  },
  
  // Feed State
  feeds: {
    recommended: {
      reels: Reel[],
      page: number,
      loading: boolean,
      hasMore: boolean
    },
    trending: {
      reels: Reel[],
      page: number,
      loading: boolean,
      hasMore: boolean,
      timeWindow: '24h' | '7d' | '30d'
    },
    following: {
      reels: Reel[],
      page: number,
      loading: boolean,
      hasMore: boolean
    }
  },
  
  // Current Reel
  currentReel: {
    reel: Reel | null,
    isLiked: boolean,
    viewDuration: number
  },
  
  // Followed Merchants
  followedMerchants: Merchant[],
  
  // Cache
  cache: {
    lastFeedUpdate: timestamp,
    reelCache: Map<reel_id, Reel>
  }
}
```

---

## Edge Cases & Validations

### Upload Edge Cases

#### 1. Product Stock Changes
**Scenario:** Merchant uploads reel when product has stock > 0, but stock becomes 0 later.

**Handling:**
- Reel visibility is **dynamically calculated** on every request
- If product stock becomes 0, reel automatically becomes invisible
- `is_visible` property returns `false`
- `disabling_reasons` includes `'PRODUCT_OUT_OF_STOCK'`
- Reel reappears automatically when stock increases

**Implementation:**
```python
# In Reel model
@property
def is_visible(self):
    return len(self.get_disabling_reasons()) == 0

def get_disabling_reasons(self):
    reasons = []
    # ... other checks ...
    stock_qty = self.product.stock.stock_qty if self.product.stock else 0
    if stock_qty <= 0:
        reasons.append('PRODUCT_OUT_OF_STOCK')
    return reasons
```

#### 2. Product Deletion
**Scenario:** Product linked to reel is deleted.

**Handling:**
- Reel becomes invisible immediately
- `disabling_reasons` includes `'PRODUCT_DELETED'`
- Reel data is preserved (soft delete)
- Merchant can still see reel in their analytics

#### 3. Product Approval Status Change
**Scenario:** Product approval status changes after reel upload.

**Handling:**
- Reel visibility updates dynamically
- If product becomes `pending` or `rejected`, reel becomes invisible
- `disabling_reasons` reflects current product status

#### 4. Concurrent Like/Unlike
**Scenario:** User rapidly clicks like/unlike button.

**Handling:**
- Database unique constraint prevents duplicate likes
- Server-side validation checks existing like before creating
- Returns appropriate error if already liked/unliked
- Transaction ensures data consistency

**Implementation:**
```python
# Check if already liked
if UserReelLike.user_has_liked(user_id, reel_id):
    return error_response("Already liked")

# Create like in transaction
like = UserReelLike.create_like(user_id, reel_id)
reel.increment_likes()
db.session.commit()
```

#### 5. Video Upload Failure
**Scenario:** Video uploads to storage but database insert fails.

**Handling:**
- Transaction rollback on database failure
- Attempts to delete uploaded video from storage (cleanup)
- Returns error with suggestion to retry
- Logs error for monitoring

**Implementation:**
```python
try:
    # Upload to storage
    upload_result = storage_service.upload_video(...)
    
    # Create reel record
    reel = Reel(...)
    db.session.add(reel)
    db.session.commit()
except Exception as e:
    db.session.rollback()
    # Cleanup uploaded video
    if upload_result.get('public_id'):
        storage_service.delete_video(upload_result['public_id'])
    raise
```

#### 6. Invalid Video File
**Scenario:** User uploads file with wrong extension or corrupted file.

**Handling:**
- Validates file extension
- Validates MIME type by reading file header (not just extension)
- Validates file size (max 100MB)
- Validates duration (max 60 seconds)
- Returns detailed error message

**Implementation:**
```python
# Read file header to detect actual MIME type
file_header = video_file.read(12)
detected_mime = detect_mime_from_header(file_header)

# Validate MIME type
if detected_mime not in ALLOWED_VIDEO_MIME_TYPES:
    return error_response("Invalid video file type")
```

#### 7. View Count Accuracy
**Scenario:** Multiple views from same user or bot traffic.

**Handling:**
- Only counts first view per user (UserReelView unique constraint)
- Re-watch only counted if view_duration increases significantly (≥25%)
- View count increment happens in transaction
- Prevents duplicate counting

**Implementation:**
```python
has_viewed = UserReelView.has_user_viewed(user_id, reel_id)

if not has_viewed:
    # First view - increment count
    should_increment_view_count = True
elif view_duration:
    # Re-watch: Check if duration increased significantly
    existing_view = UserReelView.query.filter_by(...).first()
    if existing_view.view_duration:
        duration_increase = view_duration - existing_view.view_duration
        if duration_increase >= (existing_view.view_duration * 0.25):
            should_increment_view_count = True
```

#### 8. Storage Provider Failure
**Scenario:** Cloudinary/AWS is down during upload.

**Handling:**
- Catches storage service exceptions
- Returns appropriate error message
- Logs error for monitoring
- Does not create partial reel record

#### 9. Large Batch Operations
**Scenario:** Merchant tries to delete/update 100+ reels at once.

**Handling:**
- Limits batch size to 50 items
- Validates all items before processing
- Processes in transaction
- Returns per-item results
- Continues processing even if some items fail

#### 10. Cache Invalidation Race Condition
**Scenario:** Multiple users like same reel simultaneously, causing cache issues.

**Handling:**
- Cache invalidation is non-blocking
- Silently fails if Redis unavailable
- Cache TTL ensures eventual consistency
- Feed regeneration handles missing cache gracefully

### Validation Summary

| Validation | Location | Error Code |
|------------|----------|------------|
| User authentication | All protected endpoints | 401 Unauthorized |
| Merchant role check | Upload/update/delete | 403 Forbidden |
| File size ≤ 100MB | Upload | FILE_VALIDATION_ERROR |
| File duration ≤ 60s | Upload | FILE_VALIDATION_ERROR |
| Valid video format | Upload | FILE_VALIDATION_ERROR |
| Valid MIME type | Upload | FILE_VALIDATION_ERROR |
| Product exists | Upload | PRODUCT_VALIDATION_ERROR |
| Product belongs to merchant | Upload | PRODUCT_VALIDATION_ERROR |
| Product approved | Upload | PRODUCT_VALIDATION_ERROR |
| Product has stock > 0 | Upload | PRODUCT_VALIDATION_ERROR |
| Product is parent (not variant) | Upload | PRODUCT_VALIDATION_ERROR |
| Description length ≤ 5000 | Upload/update | VALIDATION_ERROR |
| Reel exists | All reel operations | NOT_FOUND_ERROR |
| Reel belongs to merchant | Update/delete | AUTHORIZATION_ERROR |
| Reel is visible | Like/share | VALIDATION_ERROR |
| Already liked | Like | VALIDATION_ERROR |
| Not liked | Unlike | VALIDATION_ERROR |
| Batch size ≤ 50 | Batch operations | VALIDATION_ERROR |
| Rate limit exceeded | All endpoints | RATE_LIMIT_ERROR |

---

## Production Readiness Features

### 1. Error Handling

#### Structured Error Responses
All errors follow consistent format:
```json
{
  "error": "User-friendly message",
  "code": "ERROR_CODE",
  "details": {
    "field": "field_name",
    "additional_info": "..."
  }
}
```

#### Error Codes
- `REEL_UPLOAD_FAILED`: Upload operation failed
- `STORAGE_ERROR`: Storage service error
- `VALIDATION_ERROR`: Input validation error
- `PRODUCT_VALIDATION_ERROR`: Product validation failed
- `FILE_VALIDATION_ERROR`: File validation failed
- `AUTHORIZATION_ERROR`: Permission denied
- `NOT_FOUND_ERROR`: Resource not found
- `RATE_LIMIT_ERROR`: Rate limit exceeded
- `TRANSACTION_ERROR`: Database transaction error
- `CACHE_ERROR`: Cache operation error

#### Error Logging
- All errors logged with context
- Stack traces for debugging
- Error monitoring integration ready

### 2. Rate Limiting

| Endpoint | Limit | Window | Key |
|----------|-------|--------|-----|
| Upload Reel | 10 | 1 hour | `reel_upload` |
| Batch Delete | 5 | 1 hour | `reel_batch_delete` |

**Note:** Rate limits are only applied to resource-intensive operations (uploads and batch operations). View, like, and share operations do not have rate limits to support high-traffic scenarios and ensure smooth user experience.

**Implementation:**
- Redis-based rate limiting
- Per-user tracking
- Graceful degradation if Redis unavailable

### 3. Database Optimizations

#### Indexes
- **Primary indexes**: All primary keys
- **Foreign key indexes**: All foreign keys
- **Composite indexes**:
  - `idx_reels_trending`: (created_at DESC, views_count DESC, likes_count DESC, shares_count DESC)
  - `idx_reels_merchant_created`: (merchant_id, created_at DESC)
  - `idx_reels_product_visibility`: (product_id, deleted_at, is_active)
  - `idx_reels_merchant_feed`: (merchant_id, created_at DESC, is_active, deleted_at)
  - `idx_user_reel_views_user_reel`: (user_id, reel_id, viewed_at DESC)
  - `idx_user_reel_likes_user_reel`: (user_id, reel_id, created_at DESC)

#### Query Optimizations
- **Eager loading**: Prevents N+1 queries
  ```python
  query = query.options(
      joinedload(Reel.product).joinedload(Product.category),
      joinedload(Reel.merchant)
  )
  ```
- **Pagination**: All list endpoints support pagination
- **Selective field loading**: `fields` parameter for field selection

### 4. Caching Strategy

#### Redis Caching
- **Recommended Feed**: 5 minutes TTL
- **Trending Feed**: 10 minutes TTL
- **Following Feed**: 5 minutes TTL
- **Category Preferences**: 1 hour TTL

#### Cache Invalidation
- **On like/unlike**: Invalidates user's recommendation feed
- **On upload**: Invalidates trending and recommendation feeds
- **On follow/unfollow**: Invalidates user's recommendation and following feeds
- **On admin hide**: Invalidates all feed caches

#### Cache Keys
```
feed:recommended:{user_id}:{page}:{per_page}
feed:trending:{time_window}:{page}:{per_page}
feed:following:{user_id}:{page}:{per_page}
preferences:{user_id}
```

### 5. Transaction Management

#### ACID Compliance
- All write operations use database transactions
- Rollback on any error
- Consistent state guaranteed

#### Example:
```python
try:
    reel = Reel(...)
    db.session.add(reel)
    
    like = UserReelLike(...)
    db.session.add(like)
    
    reel.increment_likes()
    db.session.commit()
except Exception as e:
    db.session.rollback()
    raise
```

### 6. Security Features

#### File Upload Security
1. **MIME Type Validation**: Reads file header, not just extension
2. **File Size Limits**: 100MB maximum
3. **File Type Whitelist**: Only allowed video formats
4. **Secure Filenames**: Uses `secure_filename()` for storage
5. **Virus Scanning**: Ready for integration (placeholder)

#### Authentication & Authorization
- JWT-based authentication
- Role-based access control (Merchant, Admin)
- Ownership verification for update/delete operations

#### Input Validation
- All inputs validated and sanitized
- SQL injection prevention (SQLAlchemy ORM)
- XSS prevention (output encoding)
- CSRF protection (Flask-CORS)

### 7. Monitoring & Logging

#### Logging Levels
- **ERROR**: Critical failures, exceptions
- **WARNING**: Non-critical issues, validation warnings
- **INFO**: Important operations (upload, delete, etc.)
- **DEBUG**: Detailed debugging information

#### Key Metrics to Monitor
- Upload success/failure rate
- Average upload time
- Storage service availability
- Cache hit/miss ratio
- API response times
- Error rates by endpoint
- Rate limit hits

### 8. Scalability Considerations

#### Horizontal Scaling
- Stateless API design (JWT tokens)
- Redis for shared cache
- Database connection pooling
- CDN for video delivery

#### Vertical Scaling
- Database query optimization
- Index usage monitoring
- Cache warming strategies

---

## Advanced Features

### 1. Multi-Tier Recommendation System

#### Tier 1: Followed Merchants (40% weight)
- Reels from merchants user follows
- Highest priority in personalized feed
- Boost for new reels (< 24 hours old)

#### Tier 2: Category-Based (30% weight)
- Based on user's category preferences
- Preference score calculated from:
  - Likes: +0.3 per like
  - Views: +0.05 to +0.1 (based on watch percentage)
  - Unlikes: -0.15 per unlike
- Time decay applied (older interactions weigh less)

#### Tier 3: Trending (20% weight)
- Calculated using engagement score and time decay
- Formula: `(engagement * time_decay) / (hours_old + 1)`
- Engagement = (likes × 2) + (shares × 3) + (views × 0.1)

#### Tier 4: Similar Users (10% weight)
- Collaborative filtering approach
- Finds users with similar likes (≥3 common likes)
- Shows reels liked by similar users

#### Tier 5: General Feed (Fill remaining)
- Recent reels from all merchants
- Ensures feed never runs out of content

### 2. Time Decay for Preferences

#### Implementation
```python
# Calculate time decay factor
days_since_interaction = (now - last_interaction_at).days

if days_since_interaction <= 7:
    decay_factor = 1.0  # Full weight
elif days_since_interaction <= 30:
    # Linear decay from 1.0 to 0.5
    decay_factor = 1.0 - (days_since_interaction - 7) / 46.0
else:
    # Further decay to 0.1
    decay_factor = max(0.1, 0.5 - (days_since_interaction - 30) / 120.0)

final_score = base_score * decay_factor
```

#### Benefits
- Recent interactions have more weight
- Preferences adapt to changing user interests
- Prevents stale preferences from dominating

### 3. View Duration Weighting

#### Watch Percentage Calculation
```python
watch_percentage = min(1.0, view_duration / reel.duration_seconds)
```

#### Score Boosts
- **Full watch (≥80%)**: +0.2 to category preference
- **Partial watch (50-80%)**: +0.1 to category preference
- **Minimal watch (<50%)**: +0.02 to category preference

#### Use Case
- Users who watch full reels show stronger interest
- Better personalization based on engagement depth

### 4. Diversity Constraints

#### Merchant Diversity
- Maximum 3 reels per merchant per feed page
- Prevents feed from being dominated by one merchant
- Ensures variety in content

#### Category Diversity
- Maximum 5 reels per category per feed page
- Prevents category over-saturation
- Maintains balanced content mix

#### Implementation
```python
merchant_counts = {}
category_counts = {}

for reel in scored_reels:
    if merchant_counts.get(reel.merchant_id, 0) >= 3:
        continue  # Skip if merchant limit reached
    
    if category_counts.get(reel.category_id, 0) >= 5:
        continue  # Skip if category limit reached
    
    # Add reel to feed
    feed_reels.append(reel)
    merchant_counts[reel.merchant_id] += 1
    category_counts[reel.category_id] += 1
```

### 5. Cold Start Handling

#### Problem
New users have no interaction history, making personalization impossible.

#### Solution
- **Detection**: Check total interactions (likes + views + follows)
- **Threshold**: < 3 interactions = new user
- **Feed Strategy**: 70% trending + 30% category diversity
- **Transition**: Automatically switches to personalized feed after 3 interactions

#### Implementation
```python
total_interactions = likes_count + views_count + follows_count

if total_interactions < 3:
    return _get_cold_start_feed(user_id, page, per_page)
else:
    return get_personalized_feed(user_id, page, per_page)
```

### 6. Dynamic Visibility System

#### Real-Time Calculation
Reel visibility is calculated on every request, not stored:
```python
@property
def is_visible(self):
    return len(self.get_disabling_reasons()) == 0

def get_disabling_reasons(self):
    reasons = []
    # Check product stock
    if self.product.stock.stock_qty <= 0:
        reasons.append('PRODUCT_OUT_OF_STOCK')
    # Check product status
    if self.product.deleted_at:
        reasons.append('PRODUCT_DELETED')
    # ... more checks ...
    return reasons
```

#### Benefits
- No need to update reels when product stock changes
- Automatic visibility updates
- Multiple disabling reasons can be returned
- Real-time accuracy

### 7. Storage Abstraction Layer

#### Design Pattern
Factory pattern for storage provider switching:
```python
def get_storage_service():
    provider = config.get('VIDEO_STORAGE_PROVIDER', 'cloudinary')
    
    if provider == 'cloudinary':
        return CloudinaryStorageService()
    elif provider == 'aws':
        return AWSStorageService()
```

#### Benefits
- Easy migration between providers
- Consistent interface
- No code changes needed when switching
- Supports multiple providers simultaneously

### 8. Field Selection API

#### Purpose
Allow clients to request only needed fields, reducing payload size.

#### Usage
```
GET /api/reels/1?fields=reel_id,video_url,description,likes_count
```

#### Implementation
```python
fields_param = request.args.get('fields')
fields = None
if fields_param:
    fields = [f.strip() for f in fields_param.split(',')]

reel_data = reel.serialize(fields=fields)
```

#### Benefits
- Reduced bandwidth usage
- Faster response times
- Better mobile app performance
- Flexible API usage

### 9. Batch Operations

#### Batch Delete
- Delete up to 50 reels in one request
- Transaction-based for consistency
- Per-item results and summary
- Continues processing even if some items fail

#### Use Cases
- Merchant cleanup operations
- Efficient management of multiple reels

**Note:** Batch update functionality has been removed. Reel descriptions should be updated individually using the `PUT /api/reels/{reel_id}` endpoint for better reliability and clearer user experience.

### 10. Re-Watch Detection

#### Logic
- First view: Always increments count
- Re-watch: Only increments if view duration increases by ≥25%
- Prevents accidental duplicate counting
- Accounts for users who re-watch content

#### Implementation
```python
if not has_viewed:
    should_increment_view_count = True
elif view_duration:
    existing_view = UserReelView.query.filter_by(...).first()
    if existing_view.view_duration:
        duration_increase = view_duration - existing_view.view_duration
        if duration_increase >= (existing_view.view_duration * 0.25):
            should_increment_view_count = True
```

---

## Implementation Details

### 1. Upload Flow Implementation

#### Step-by-Step Process

**Step 1: Authentication & Authorization**
```python
current_user_id = get_jwt_identity()
merchant = MerchantProfile.query.filter_by(user_id=current_user_id).first()
if not merchant:
    return error_response("Only merchants can upload reels")
```

**Step 2: File Validation**
```python
# Check file exists
if 'video' not in request.files:
    return error_response("Video file required")

video_file = request.files['video']

# Validate extension
if not allowed_file(video_file.filename, ALLOWED_VIDEO_EXTENSIONS):
    return error_response("Invalid file extension")

# Read file header for MIME type detection
file_header = video_file.read(12)
detected_mime = detect_mime_from_header(file_header)

# Validate MIME type
if detected_mime not in ALLOWED_VIDEO_MIME_TYPES:
    return error_response("Invalid video file type")
```

**Step 3: Product Validation**
```python
product_id = request.form.get('product_id')
is_valid, product, error = validate_product_for_reel(product_id, merchant.id)

if not is_valid:
    return error_response(error)
```

**Step 4: Upload to Storage**
```python
storage_service = get_storage_service()
upload_result = storage_service.upload_video(
    video_file,
    folder=f"reels/merchant_{merchant.id}/product_{product_id}",
    resource_type="video"
)
```

**Step 5: Generate Thumbnail**
```python
thumbnail_url = storage_service.generate_thumbnail(
    upload_result['public_id'],
    width=640,
    height=360
)
```

**Step 6: Create Reel Record**
```python
reel = Reel(
    merchant_id=merchant.id,
    product_id=product_id,
    video_url=upload_result['url'],
    video_public_id=upload_result['public_id'],
    thumbnail_url=thumbnail_url,
    description=description,
    duration_seconds=upload_result.get('duration'),
    file_size_bytes=upload_result.get('bytes'),
    video_format=upload_result.get('format'),
    approval_status='approved',  # Auto-approved
    is_active=True
)

db.session.add(reel)
db.session.commit()
```

**Step 7: Cache Invalidation**
```python
redis_client = get_redis_client()
if redis_client:
    # Invalidate trending feeds
    pattern = "feed:trending:*"
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)
    
    # Invalidate recommendation feeds
    pattern = "feed:recommended:*"
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)
```

### 2. Recommendation Algorithm Implementation

#### Personalized Feed Generation

**Step 1: Check Cache**
```python
cache_key = f"feed:recommended:{user_id}:{page}:{per_page}"
cached = redis_client.get(cache_key)
if cached:
    return deserialize_cached_feed(cached)
```

**Step 2: Check Cold Start**
```python
total_interactions = get_user_interaction_count(user_id)
if total_interactions < 3:
    return _get_cold_start_feed(user_id, page, per_page)
```

**Step 3: Gather Reels from All Tiers**
```python
seen_reel_ids = set()
feed_reels = []

# Tier 1: Followed (40%)
followed_limit = int(per_page * 0.4)
followed_reels = get_followed_merchant_reels(user_id, limit=followed_limit)
feed_reels.extend(followed_reels)
seen_reel_ids.update([r.reel_id for r in followed_reels])

# Tier 2: Category (30%)
category_limit = int(per_page * 0.3)
category_reels = get_category_based_reels(user_id, limit=category_limit, 
                                         exclude_reel_ids=seen_reel_ids)
feed_reels.extend(category_reels)
seen_reel_ids.update([r.reel_id for r in category_reels])

# Tier 3: Trending (20%)
trending_limit = int(per_page * 0.2)
trending_reels = get_trending_reels(limit=trending_limit, 
                                   exclude_reel_ids=seen_reel_ids)
feed_reels.extend(trending_reels)
seen_reel_ids.update([r.reel_id for r in trending_reels])

# Tier 4: Similar Users (10%)
similar_limit = int(per_page * 0.1)
similar_reels = get_similar_user_reels(user_id, limit=similar_limit,
                                      exclude_reel_ids=seen_reel_ids)
feed_reels.extend(similar_reels)
seen_reel_ids.update([r.reel_id for r in similar_reels])

# Tier 5: General (fill remaining)
remaining = per_page - len(feed_reels)
if remaining > 0:
    general_reels = get_general_reels(limit=remaining, 
                                     exclude_reel_ids=seen_reel_ids)
    feed_reels.extend(general_reels)
```

**Step 4: Calculate Scores**
```python
scored_reels = []
for reel in feed_reels:
    context = build_reel_context(reel, user_id)
    score = calculate_final_reel_score(reel, user_id, context)
    scored_reels.append((score, reel))

# Sort by score
scored_reels.sort(key=lambda x: x[0], reverse=True)
```

**Step 5: Apply Diversity Constraints**
```python
final_reels = []
merchant_counts = {}
category_counts = {}

for score, reel in scored_reels:
    # Check merchant diversity
    if merchant_counts.get(reel.merchant_id, 0) >= 3:
        continue
    
    # Check category diversity
    if category_counts.get(reel.category_id, 0) >= 5:
        continue
    
    final_reels.append(reel)
    merchant_counts[reel.merchant_id] = merchant_counts.get(reel.merchant_id, 0) + 1
    category_counts[reel.category_id] = category_counts.get(reel.category_id, 0) + 1
    
    if len(final_reels) >= per_page:
        break
```

**Step 6: Cache Result**
```python
cache_data = {
    'reel_ids': [r.reel_id for r in final_reels],
    'feed_info': feed_info
}
redis_client.setex(cache_key, CACHE_TTL_RECOMMENDED, json.dumps(cache_data))
```

### 3. View Tracking Implementation

#### Automatic View Tracking
```python
def get_reel(reel_id, track_view=True, view_duration=None):
    reel = Reel.query.filter_by(reel_id=reel_id).first()
    
    # Get current user
    current_user_id = get_jwt_identity()  # Returns None if not authenticated
    
    if current_user_id and track_view and reel.is_visible:
        # Check if user has viewed
        has_viewed = UserReelView.has_user_viewed(current_user_id, reel_id)
        
        should_increment_view_count = False
        
        if not has_viewed:
            # First view
            should_increment_view_count = True
        elif view_duration:
            # Re-watch: Check if duration increased significantly
            existing_view = UserReelView.query.filter_by(
                user_id=current_user_id,
                reel_id=reel_id
            ).first()
            
            if existing_view and existing_view.view_duration:
                duration_increase = view_duration - existing_view.view_duration
                if duration_increase >= (existing_view.view_duration * 0.25):
                    should_increment_view_count = True
        
        # Track/update view
        UserReelView.track_view(current_user_id, reel_id, view_duration=view_duration)
        
        # Update view count
        if should_increment_view_count:
            reel.increment_views()
        
        # Update category preference
        if reel.product and reel.product.category_id:
            watch_percentage = calculate_watch_percentage(view_duration, reel.duration_seconds)
            score_delta = calculate_preference_score_delta(watch_percentage)
            UserCategoryPreference.update_preference(
                current_user_id,
                reel.product.category_id,
                score_delta,
                'view'
            )
        
        db.session.commit()
```

### 4. Category Preference Update

#### Preference Score Calculation
```python
def update_preference(user_id, category_id, score_delta, interaction_type):
    """
    Update user's category preference score.
    
    Args:
        user_id: User ID
        category_id: Category ID
        score_delta: Score change (+0.3 for like, -0.15 for unlike, etc.)
        interaction_type: Type of interaction ('like', 'unlike', 'view')
    """
    pref = UserCategoryPreference.query.filter_by(
        user_id=user_id,
        category_id=category_id
    ).first()
    
    if pref:
        # Update existing preference
        pref.preference_score = max(0.0, min(1.0, pref.preference_score + score_delta))
        pref.interaction_count += 1
        pref.last_interaction_at = datetime.now(timezone.utc)
    else:
        # Create new preference
        pref = UserCategoryPreference(
            user_id=user_id,
            category_id=category_id,
            preference_score=max(0.0, min(1.0, score_delta)),
            interaction_count=1,
            last_interaction_at=datetime.now(timezone.utc)
        )
        db.session.add(pref)
    
    db.session.commit()
```

#### Score Deltas by Interaction
- **Like**: +0.3
- **Unlike**: -0.15
- **Full watch (≥80%)**: +0.2
- **Partial watch (50-80%)**: +0.1
- **Minimal watch (<50%)**: +0.02
- **Default view**: +0.05

### 5. Trending Score Calculation

#### Formula
```python
def calculate_trending_score(reel, time_window_hours=24):
    # Calculate hours since creation
    hours_old = (datetime.now(timezone.utc) - reel.created_at).total_seconds() / 3600
    
    # Engagement score
    engagement_score = (
        reel.likes_count * 2.0 +
        reel.shares_count * 3.0 +
        reel.views_count * 0.1
    )
    
    # Time decay
    if hours_old < 6:
        time_decay = 1.0
    elif hours_old < 24:
        time_decay = 0.8
    elif hours_old < 168:  # 7 days
        time_decay = 0.5
    else:
        time_decay = 0.2
    
    # Trending score
    trending_score = (engagement_score * time_decay) / (hours_old + 1)
    
    # Boost for very recent reels
    if hours_old < 6:
        trending_score *= 1.5
    
    return trending_score
```

### 6. Storage Service Implementation

#### Base Storage Service Interface
```python
class BaseStorageService(ABC):
    @abstractmethod
    def upload_video(self, file, folder, resource_type="video"):
        """Upload video file and return URL and metadata."""
        pass
    
    @abstractmethod
    def generate_thumbnail(self, public_id, width=640, height=360):
        """Generate thumbnail from video."""
        pass
    
    @abstractmethod
    def delete_video(self, public_id):
        """Delete video from storage."""
        pass
    
    @abstractmethod
    def get_video_url(self, public_id):
        """Get video URL from public ID."""
        pass
```

#### Cloudinary Implementation
```python
class CloudinaryStorageService(BaseStorageService):
    def __init__(self, config):
        cloudinary.config(
            cloud_name=config['CLOUDINARY_CLOUD_NAME'],
            api_key=config['CLOUDINARY_API_KEY'],
            api_secret=config['CLOUDINARY_API_SECRET']
        )
    
    def upload_video(self, file, folder, resource_type="video"):
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            resource_type=resource_type,
            eager=[{"width": 640, "height": 360, "crop": "fill"}]
        )
        return {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'duration': result.get('duration'),
            'bytes': result.get('bytes'),
            'format': result.get('format')
        }
```

### 7. Cache Implementation

#### Cache Key Patterns
```python
# Recommended feed
f"feed:recommended:{user_id}:{page}:{per_page}"

# Trending feed
f"feed:trending:{time_window}:{page}:{per_page}"

# Following feed
f"feed:following:{user_id}:{page}:{per_page}"

# Category preferences
f"preferences:{user_id}"
```

#### Cache Invalidation Patterns
```python
# Invalidate user's recommendation feed
pattern = f"feed:recommended:{user_id}:*"
keys = redis_client.keys(pattern)
if keys:
    redis_client.delete(*keys)

# Invalidate all trending feeds
pattern = "feed:trending:*"
keys = redis_client.keys(pattern)
if keys:
    redis_client.delete(*keys)
```

---

## Error Handling

### Error Response Structure

All errors follow this format:
```json
{
  "error": "User-friendly error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "field_name",
    "additional_info": "..."
  }
}
```

### Error Codes Reference

| Code | Description | HTTP Status | Example |
|------|-------------|-------------|---------|
| `REEL_UPLOAD_FAILED` | Upload operation failed | 500 | Storage service error |
| `STORAGE_ERROR` | Storage service error | 500 | Cloudinary API error |
| `VALIDATION_ERROR` | Input validation failed | 400 | Invalid description length |
| `PRODUCT_VALIDATION_ERROR` | Product validation failed | 400 | Product not approved |
| `FILE_VALIDATION_ERROR` | File validation failed | 400 | File too large |
| `AUTHORIZATION_ERROR` | Permission denied | 403 | Not reel owner |
| `NOT_FOUND_ERROR` | Resource not found | 404 | Reel not found |
| `RATE_LIMIT_ERROR` | Rate limit exceeded | 429 | Too many requests |
| `TRANSACTION_ERROR` | Database error | 500 | Transaction rollback |
| `CACHE_ERROR` | Cache operation error | 500 | Redis unavailable |

### Error Handling Best Practices

1. **Always log errors** with context
2. **Return user-friendly messages** (don't expose internals)
3. **Include error codes** for client-side handling
4. **Provide actionable details** when possible
5. **Use appropriate HTTP status codes**
6. **Handle partial failures gracefully** (batch operations)

---

## Performance Optimizations

### 1. Database Query Optimization

#### Eager Loading
Prevents N+1 query problem:
```python
# Bad: N+1 queries
reels = Reel.query.all()
for reel in reels:
    print(reel.product.name)  # Query for each product

# Good: Eager loading
reels = Reel.query.options(
    joinedload(Reel.product).joinedload(Product.category),
    joinedload(Reel.merchant)
).all()
for reel in reels:
    print(reel.product.name)  # No additional queries
```

#### Index Usage
All frequently queried fields are indexed:
- Foreign keys
- Composite indexes for common query patterns
- Full-text indexes for search

### 2. Caching Strategy

#### Multi-Level Caching
1. **Application Cache (Redis)**: Feed results, preferences
2. **CDN Cache**: Video files, thumbnails
3. **Browser Cache**: Static assets

#### Cache Warming
- Pre-compute trending feeds
- Cache popular reels
- Warm cache on user login

### 3. Pagination

#### Efficient Pagination
```python
# Use database-level pagination
pagination = query.paginate(
    page=page,
    per_page=per_page,
    error_out=False
)

# Return only needed data
reels_data = [reel.serialize() for reel in pagination.items]
```

#### Benefits
- Reduces memory usage
- Faster response times
- Better user experience

### 4. Field Selection

#### Reduce Payload Size
```python
# Client requests only needed fields
GET /api/reels/1?fields=reel_id,video_url,description

# Server returns only requested fields
{
  "reel_id": 1,
  "video_url": "...",
  "description": "..."
}
```

### 5. Async Operations

#### Non-Blocking Cache Invalidation
```python
try:
    redis_client.delete(*keys)
except Exception:
    pass  # Don't block request if cache fails
```

#### Background Tasks (Future)
- Thumbnail generation
- Video processing
- Analytics aggregation

---

## Security Features

### 1. File Upload Security

#### MIME Type Validation
```python
# Read actual file header, not just extension
file_header = video_file.read(12)
detected_mime = detect_mime_from_header(file_header)

# Validate against whitelist
if detected_mime not in ALLOWED_VIDEO_MIME_TYPES:
    return error_response("Invalid file type")
```

#### File Size Limits
- Maximum: 100MB
- Validated before upload
- Prevents DoS attacks

#### File Type Whitelist
- Only allowed: MP4, MOV, AVI, MKV
- Extension and MIME type must match
- Rejects suspicious files

### 2. Authentication & Authorization

#### JWT Authentication
- Token-based authentication
- Stateless design
- Secure token storage required on client

#### Role-Based Access Control
```python
@jwt_required()
@admin_role_required
def admin_endpoint():
    # Only admins can access
    pass
```

#### Ownership Verification
```python
# Verify merchant owns reel
if reel.merchant_id != merchant.id:
    return error_response("Not authorized")
```

### 3. Input Validation

#### SQL Injection Prevention
- SQLAlchemy ORM (parameterized queries)
- No raw SQL queries
- Input sanitization

#### XSS Prevention
- Output encoding
- Content Security Policy headers
- Sanitize user inputs

#### CSRF Protection
- Flask-CORS configuration
- Origin validation
- Token-based protection

### 4. Rate Limiting

#### Per-Endpoint Limits
- Prevents abuse on resource-intensive operations
- Protects against DoS
- Fair resource usage
- **Note:** Rate limits are only applied to uploads and batch operations. View, like, and share operations are unlimited to support high-traffic scenarios.

#### Implementation
```python
@rate_limit(limit=10, per=3600, key_prefix='reel_upload')
def upload_reel():
    # Maximum 10 uploads per hour
    pass
```

---

## Testing Guide

### 1. Unit Testing

#### Test Upload Validation
```python
def test_upload_invalid_file_type():
    response = client.post('/api/reels', 
        data={'video': invalid_file, 'product_id': 1, 'description': 'Test'})
    assert response.status_code == 400
    assert 'FILE_VALIDATION_ERROR' in response.json['code']
```

#### Test Product Validation
```python
def test_upload_without_stock():
    product = create_product(stock_qty=0)
    response = client.post('/api/reels',
        data={'video': valid_file, 'product_id': product.id, 'description': 'Test'})
    assert response.status_code == 400
    assert 'PRODUCT_VALIDATION_ERROR' in response.json['code']
```

### 2. Integration Testing

#### Test Upload Flow
```python
def test_complete_upload_flow():
    # 1. Authenticate merchant
    token = login_merchant()
    
    # 2. Get available products
    products = get_available_products(token)
    assert len(products) > 0
    
    # 3. Upload reel
    reel = upload_reel(token, products[0].id, test_video)
    assert reel['status'] == 'success'
    
    # 4. Verify reel is visible
    reel_data = get_reel(reel['data']['reel_id'])
    assert reel_data['data']['is_visible'] == True
```

#### Test Recommendation Flow
```python
def test_recommendation_feed():
    # 1. Create user with interactions
    user = create_user()
    like_reels(user, count=5)
    follow_merchants(user, count=3)
    
    # 2. Get recommended feed
    feed = get_recommended_feed(user.token)
    assert len(feed['data']) > 0
    
    # 3. Verify feed contains followed merchant reels
    followed_merchant_ids = get_followed_merchants(user.token)
    feed_merchant_ids = [r['merchant_id'] for r in feed['data']]
    assert any(mid in feed_merchant_ids for mid in followed_merchant_ids)
```

### 3. Performance Testing

#### Load Testing
- Test with 1000+ concurrent users
- Measure response times
- Monitor database query performance
- Check cache hit rates

#### Stress Testing
- Test with maximum file sizes
- Test with maximum batch operations
- Test rate limiting effectiveness

### 4. Security Testing

#### File Upload Security
- Test with malicious file types
- Test with oversized files
- Test MIME type spoofing

#### Authorization Testing
- Test unauthorized access attempts
- Test ownership verification
- Test admin-only endpoints

### 5. Edge Case Testing

#### Product Stock Changes
```python
def test_reel_visibility_on_stock_change():
    # 1. Upload reel with stock > 0
    reel = upload_reel(product_with_stock)
    assert reel['is_visible'] == True
    
    # 2. Set stock to 0
    update_product_stock(product_id, stock_qty=0)
    
    # 3. Verify reel is invisible
    reel_data = get_reel(reel['reel_id'])
    assert reel_data['is_visible'] == False
    assert 'PRODUCT_OUT_OF_STOCK' in reel_data['disabling_reasons']
```

#### Concurrent Operations
```python
def test_concurrent_likes():
    # Multiple users like same reel simultaneously
    threads = []
    for i in range(10):
        thread = threading.Thread(target=like_reel, args=(reel_id, user_tokens[i]))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    # Verify like count is correct
    reel = get_reel(reel_id)
    assert reel['likes_count'] == 10
```

---

## Summary

The Reels Module is a **production-ready, feature-rich video content management system** with:

### Core Capabilities
- ✅ Video upload and storage (Cloudinary/AWS S3)
- ✅ Immediate public visibility (no approval required)
- ✅ Real-time visibility based on product status
- ✅ Comprehensive analytics
- ✅ Search and discovery
- ✅ Batch delete operations

### Advanced Features
- ✅ Multi-tier recommendation system
- ✅ Time decay for preferences
- ✅ View duration weighting
- ✅ Diversity constraints
- ✅ Cold start handling
- ✅ Field selection API

### Production Readiness
- ✅ Comprehensive error handling
- ✅ Rate limiting
- ✅ Database optimizations
- ✅ Caching strategy
- ✅ Transaction management
- ✅ Security features
- ✅ Performance optimizations

### Mobile App Integration
- ✅ RESTful API design
- ✅ JWT authentication
- ✅ Pagination support
- ✅ Field selection
- ✅ Real-time updates
- ✅ Offline-friendly design

The module is **fully documented, tested, and ready for production deployment**.