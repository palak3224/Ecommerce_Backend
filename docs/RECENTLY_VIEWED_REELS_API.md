# Recently Viewed Reels API Documentation

## Overview

The Recently Viewed Reels API allows authenticated users (both regular users and merchants) to retrieve a paginated list of reels they have previously viewed, ordered by most recently viewed first.

---

## Endpoint

**`GET /api/reels/recently-viewed`**

**Base URL:** `https://api.example.com`

---

## Authentication

**Required:** Yes (JWT Token)

Include the JWT token in the Authorization header:
```
Authorization: Bearer YOUR_JWT_TOKEN
```

**Access:** Available to both regular users and merchants

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number for pagination |
| `per_page` | integer | No | 20 | Number of items per page (max: 100) |
| `fields` | string | No | - | Comma-separated list of fields to include in response |

### Examples

- `GET /api/reels/recently-viewed?page=1&per_page=20`
- `GET /api/reels/recently-viewed?page=2&per_page=50`
- `GET /api/reels/recently-viewed?fields=reel_id,video_url,description,viewed_at`

---

## Response Format

### Success Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "reels": [
      {
        "reel_id": 123,
        "merchant_id": 45,
        "product_id": 789,
        "video_url": "https://cdn.example.com/reels/video_123.mp4",
        "thumbnail_url": "https://cdn.example.com/reels/thumb_123.jpg",
        "description": "Check out this amazing product!",
        "duration_seconds": 30,
        "views_count": 1500,
        "likes_count": 250,
        "shares_count": 50,
        "is_liked": false,
        "viewed_at": "2025-01-05T14:30:00Z",
        "view_duration": 28,
        "created_at": "2025-01-01T10:00:00Z",
        "product": {
          "product_id": 789,
          "product_name": "Amazing Product",
          "category_id": 12,
          "category_name": "Electronics",
          "stock_qty": 100,
          "selling_price": 99.99
        }
      }
    ],
    "pagination": {
      "total": 50,
      "pages": 3,
      "current_page": 1,
      "per_page": 20,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

### Response Fields

#### Reel Object

| Field | Type | Description |
|-------|------|-------------|
| `reel_id` | integer | Unique reel identifier |
| `merchant_id` | integer | ID of the merchant who created the reel |
| `product_id` | integer | ID of the product featured in the reel |
| `video_url` | string | URL to the reel video file |
| `thumbnail_url` | string | URL to the reel thumbnail image |
| `description` | string | Reel description/caption |
| `duration_seconds` | integer | Video duration in seconds |
| `views_count` | integer | Total number of views |
| `likes_count` | integer | Total number of likes |
| `shares_count` | integer | Total number of shares |
| `is_liked` | boolean | Whether the current user has liked this reel |
| `viewed_at` | string (ISO 8601) | Timestamp when user viewed this reel |
| `view_duration` | integer | Duration user watched the reel (in seconds, if available) |
| `created_at` | string (ISO 8601) | When the reel was created |
| `product` | object | Product information (if `include_product=true`) |

#### Pagination Object

| Field | Type | Description |
|-------|------|-------------|
| `total` | integer | Total number of viewed reels |
| `pages` | integer | Total number of pages |
| `current_page` | integer | Current page number |
| `per_page` | integer | Items per page |
| `has_next` | boolean | Whether there is a next page |
| `has_prev` | boolean | Whether there is a previous page |

---

## Error Responses

### 401 Unauthorized

```json
{
  "error": "Authentication required"
}
```

**Cause:** Missing or invalid JWT token

---

### 500 Internal Server Error

```json
{
  "error": "Failed to get recently viewed reels: [error details]"
}
```

**Cause:** Server error during processing

---

## Usage Examples

### cURL

```bash
# Get first page of recently viewed reels
curl -X GET "https://api.example.com/api/reels/recently-viewed?page=1&per_page=20" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"

# Get second page with 50 items per page
curl -X GET "https://api.example.com/api/reels/recently-viewed?page=2&per_page=50" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"

# Get specific fields only
curl -X GET "https://api.example.com/api/reels/recently-viewed?fields=reel_id,video_url,description,viewed_at" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

### JavaScript/TypeScript

```typescript
async function getRecentlyViewedReels(page: number = 1, perPage: number = 20) {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch(
    `${API_BASE_URL}/api/reels/recently-viewed?page=${page}&per_page=${perPage}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to fetch recently viewed reels');
  }
  
  return await response.json();
}

// Usage
try {
  const result = await getRecentlyViewedReels(1, 20);
  console.log('Recently viewed reels:', result.data.reels);
  console.log('Pagination:', result.data.pagination);
} catch (error) {
  console.error('Error:', error);
}
```

### Python

```python
import requests

def get_recently_viewed_reels(token, page=1, per_page=20):
    url = f"https://api.example.com/api/reels/recently-viewed"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {
        "page": page,
        "per_page": per_page
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

# Usage
token = "YOUR_JWT_TOKEN"
result = get_recently_viewed_reels(token, page=1, per_page=20)
print(f"Total reels: {result['data']['pagination']['total']}")
for reel in result['data']['reels']:
    print(f"Reel {reel['reel_id']} viewed at {reel['viewed_at']}")
```

---

## Behavior & Notes

### Filtering

The API automatically filters out:
- Deleted reels (`deleted_at` is not null)
- Inactive reels (`is_active = false`)
- Unapproved reels (`approval_status != 'approved'`)
- Reels with disabling reasons (e.g., product out of stock)

### Ordering

Reels are ordered by `viewed_at` timestamp in **descending order** (most recently viewed first).

### View Tracking

- Views are automatically tracked when a user watches a reel via `GET /api/reels/{reel_id}`
- Each user-reel combination has a unique view record
- If a user views the same reel again, the `viewed_at` timestamp is updated
- The `view_duration` field is optional and may not be present for all views

### Pagination

- Default: 20 items per page
- Maximum: 100 items per page
- If `per_page` exceeds 100, it's automatically capped at 100
- Empty results return pagination info with `total: 0`

### Field Selection

Use the `fields` parameter to limit the response to specific fields:
- Format: Comma-separated field names
- Example: `fields=reel_id,video_url,description,viewed_at`
- If not specified, all fields are returned

---

## Integration Tips

1. **Caching:** Consider caching recently viewed reels on the client side to reduce API calls
2. **Pagination:** Always check `has_next` before loading the next page
3. **Error Handling:** Handle 401 errors by redirecting to login
4. **Loading States:** Show loading indicators while fetching data
5. **Empty States:** Display a friendly message when `total: 0`

---

## Related APIs

- **Get Single Reel:** `GET /api/reels/{reel_id}` - Automatically tracks view
- **Get Public Reels:** `GET /api/reels/public` - Browse all public reels
- **Get Recommended Reels:** `GET /api/reels/feed/recommended` - Personalized recommendations
- **Get Trending Reels:** `GET /api/reels/feed/trending` - Trending reels feed

---

## Changelog

### Version 1.0.0 (2025-01-05)
- Initial release
- Pagination support
- Field selection support
- View duration tracking
- Works for both regular users and merchants

---

## Support

For issues or questions regarding the Recently Viewed Reels API, please contact the development team or refer to the main API documentation.

