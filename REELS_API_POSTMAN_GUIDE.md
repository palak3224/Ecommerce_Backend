# Reels API - Postman Testing Guide

## Quick Reference - All Endpoints

| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| `POST` | `/api/reels` | ✅ Yes (Merchant) | Upload a new reel |
| `GET` | `/api/reels/{reel_id}` | ❌ No | Get reel by ID (auto-increments views) |
| `GET` | `/api/reels/merchant/my` | ✅ Yes (Merchant) | Get merchant's own reels |
| `GET` | `/api/reels/merchant/{id}` | ❌ No | Get merchant's public reels |
| `GET` | `/api/reels/public` | ❌ No | Get public visible reels (feed) |
| `PUT` | `/api/reels/{reel_id}` | ✅ Yes (Owner) | Update reel description |
| `DELETE` | `/api/reels/{reel_id}` | ✅ Yes (Owner) | Delete a reel |
| `GET` | `/api/reels/products/available` | ✅ Yes (Merchant) | Get available products for upload |
| `POST` | `/api/reels/{reel_id}/like` | ✅ Yes (User) | Like a reel (increment likes, tracks user) |
| `POST` | `/api/reels/{reel_id}/unlike` | ✅ Yes (User) | Unlike a reel (decrement likes, tracks user) |
| `POST` | `/api/reels/{reel_id}/share` | ❌ No | Share a reel (increment shares) |

---

## Prerequisites

1. **Backend Server Running**: Ensure your Flask backend is running
   ```bash
   python app.py
   # or
   flask run
   ```

2. **Database Migration**: Run the migration to create the reels table
   ```bash
   flask db upgrade
   ```

3. **Merchant Account**: You need a merchant account with:
   - At least one approved product
   - Product must have stock > 0
   - Product must be active

4. **JWT Token**: Get your authentication token from the login endpoint

---

## Step 1: Get Authentication Token

### Endpoint: `POST /api/auth/login` (or your login endpoint)

**Note**: Login works for both **Users** and **Merchants**. However, to upload reels, you need a **Merchant** account. Regular users can view reels but cannot upload them.

**Request:**
- Method: `POST`
- URL: `http://localhost:5000/api/auth/login`
- Headers:
  ```
  Content-Type: application/json
  ```

**Option 1: Email/Password Login**

**For Regular Users:**
- Body (JSON):
  ```json
  {
    "email": "user@example.com",
    "password": "your_password"
  }
  ```

**For Merchants (Important!):**
- Body (JSON):
  ```json
  {
    "business_email": "merchant@example.com",
    "password": "your_password"
  }
  ```
  ⚠️ **Note**: Merchants must use `business_email` (not `email`). Using `email` will return an error: "Merchants must sign in through the merchant dashboard."

**Option 2: Mobile OTP Login**

**For Regular Users:**
- Body (JSON):
  ```json
  {
    "phone": "+1234567890",
    "otp": "123456"
  }
  ```

**For Merchants:**
- ⚠️ **Note**: Merchants cannot use phone number login. You'll get an error: "Merchants cannot use phone number login"
- Merchants must use `business_email` with password login (Option 1)

**Option 3: Google OAuth Login (Works for both Users and Merchants)**
- Follow your Google OAuth flow endpoint
- Typically involves redirecting to Google and receiving a callback with token

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "..."
}
```

**Copy the `access_token` for use in subsequent requests.**

**Important Notes:**
- **For Regular Users**: Use `email` field in login request
- **For Merchants**: Use `business_email` field in login request (NOT `email`)
- **Merchants cannot use phone OTP login** - must use `business_email` + password
- **For Uploading Reels**: You must be logged in as a **Merchant** account
- **For Viewing Reels**: Any authenticated **User** or **Merchant** can view reels
- **For Getting Available Products**: Only **Merchants** can access this endpoint
- The system automatically determines your role (user/merchant) from your account

**Common Error:**
If you get `"Merchants must sign in through the merchant dashboard."` error:
- You're using `email` instead of `business_email`
- Change `email` to `business_email` in your request body

---

## Step 2: Get Available Products (Optional but Recommended)

### Endpoint: `GET /api/reels/products/available`

**Request:**
- Method: `GET`
- URL: `http://localhost:5000/api/reels/products/available`
- Headers:
  ```
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
  ```

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "product_id": 123,
      "product_name": "Amazing Product",
      "category_id": 5,
      "category_name": "Electronics",
      "stock_qty": 50,
      "selling_price": 99.99
    }
  ]
}
```

**Note the `product_id` you want to use for the reel upload.**

---

## Step 3: Upload a Reel

### Endpoint: `POST /api/reels`

**Request Configuration:**

1. **Method**: `POST`
2. **URL**: `http://localhost:5000/api/reels`
3. **Headers**:
   ```
   Authorization: Bearer YOUR_ACCESS_TOKEN
   ```
   ⚠️ **Important**: Do NOT set `Content-Type` header manually. Postman will set it automatically to `multipart/form-data` when you select form-data.

4. **Body**:
   - Select **`form-data`** (not `raw` or `x-www-form-urlencoded`)
   - Add the following fields:

   | Key | Type | Value | Required |
   |-----|------|-------|----------|
   | `video` | File | Select a video file (MP4, MOV, AVI, MKV) | ✅ Yes |
   | `product_id` | Text | `123` (use product_id from Step 2) | ✅ Yes |
   | `description` | Text | `Check out this amazing product!` | ✅ Yes |

   **Video File Requirements:**
   - Format: MP4, MOV, AVI, or MKV
   - Max Size: 100MB
   - Max Duration: 60 seconds

5. **Screenshot Guide for Postman**:
   ```
   Body Tab → Select "form-data"
   - Key: video → Change type to "File" → Click "Select Files" → Choose video
   - Key: product_id → Type: Text → Value: 123
   - Key: description → Type: Text → Value: "Your description here"
   ```

**Expected Response (201 Created):**
```json
{
  "status": "success",
  "message": "Reel uploaded successfully.",
  "data": {
    "reel_id": 1,
    "merchant_id": 45,
    "product_id": 123,
    "video_url": "https://res.cloudinary.com/.../video.mp4",
    "thumbnail_url": "https://res.cloudinary.com/.../thumb.jpg",
    "description": "Check out this amazing product!",
    "duration_seconds": 30,
    "file_size_bytes": 5242880,
    "video_format": "mp4",
    "views_count": 0,
    "likes_count": 0,
    "shares_count": 0,
    "is_active": true,
    "approval_status": "approved",
    "is_visible": true,
    "disabling_reasons": [],
    "product": {
      "product_id": 123,
      "product_name": "Amazing Product",
      "category_id": 5,
      "category_name": "Electronics",
      "stock_qty": 50,
      "selling_price": 99.99
    },
    "created_at": "2024-01-01T12:00:00Z"
  }
}
```

**Error Responses:**

**400 Bad Request - Missing Fields:**
```json
{
  "error": "product_id is required"
}
```
OR
```json
{
  "error": "description is required"
}
```

**400 Bad Request - Invalid Product:**
```json
{
  "error": "Product must be approved by admin. Current status: pending"
}
```
OR
```json
{
  "error": "Product must have stock quantity greater than 0"
}
```

**403 Forbidden:**
```json
{
  "error": "Only merchants can upload reels"
}
```

---

## Step 4: Get a Reel by ID

### Endpoint: `GET /api/reels/{reel_id}`

**Request Configuration:**

1. **Method**: `GET`
2. **URL**: `http://localhost:5000/api/reels/1`
   - Replace `1` with the actual `reel_id` from Step 3 response
3. **Headers**:
   ```
   Content-Type: application/json
   ```
   ⚠️ **Note**: This endpoint does NOT require authentication (public endpoint)

4. **Query Parameters** (optional):
   - `track_view` (default: `true`): Whether to automatically increment the view count when the reel is fetched
   - Example: `http://localhost:5000/api/reels/1?track_view=false` to view without incrementing count

**Important**: 
- By default, viewing a reel automatically increments the `views_count`. This happens every time someone fetches the reel data.
- If you're authenticated (include `Authorization` header), the response will include `is_liked: true/false` to indicate whether you've liked this reel.

**Expected Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "reel_id": 1,
    "merchant_id": 45,
    "product_id": 123,
    "video_url": "https://res.cloudinary.com/.../video.mp4",
    "thumbnail_url": "https://res.cloudinary.com/.../thumb.jpg",
    "description": "Check out this amazing product!",
    "duration_seconds": 30,
    "file_size_bytes": 5242880,
    "video_format": "mp4",
    "views_count": 0,
    "likes_count": 0,
    "shares_count": 0,
    "is_active": true,
    "approval_status": "approved",
    "is_visible": true,
    "disabling_reasons": [],
    "is_liked": false,
    "product": {
      "product_id": 123,
      "product_name": "Amazing Product",
      "category_id": 5,
      "category_name": "Electronics",
      "stock_qty": 50,
      "selling_price": 99.99
    },
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z"
  }
}
```

**Note**: The `is_liked` field is included when authenticated. If not authenticated, it defaults to `false`.

**Error Response (404 Not Found):**
```json
{
  "error": "Reel not found"
}
```

---

## Additional Endpoints for Testing

### Get My Reels (Merchant's Own Reels)
**Endpoint**: `GET /api/reels/merchant/my`

**Request:**
- Method: `GET`
- URL: `http://localhost:5000/api/reels/merchant/my?page=1&per_page=20`
- Headers:
  ```
  Authorization: Bearer YOUR_ACCESS_TOKEN
  ```

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 20, max: 100)
- `include_all` (optional): Include non-visible reels (default: false)

---

### Get Public Reels (Feed)
**Endpoint**: `GET /api/reels/public`

**Request:**
- Method: `GET`
- URL: `http://localhost:5000/api/reels/public?page=1&per_page=20`
- Headers:
  ```
  Content-Type: application/json
  ```
  ⚠️ **Note**: No authentication required

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 20, max: 100)

---

### Update Reel Description
**Endpoint**: `PUT /api/reels/{reel_id}`

**Request:**
- Method: `PUT`
- URL: `http://localhost:5000/api/reels/1`
- Headers:
  ```
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
  ```
- Body (JSON):
  ```json
  {
    "description": "Updated description for the reel"
  }
  ```

---

### Delete Reel
**Endpoint**: `DELETE /api/reels/{reel_id}`

**Request:**
- Method: `DELETE`
- URL: `http://localhost:5000/api/reels/1`
- Headers:
  ```
  Authorization: Bearer YOUR_ACCESS_TOKEN
  ```

---

### Like a Reel
**Endpoint**: `POST /api/reels/{reel_id}/like`

**Request:**
- Method: `POST`
- URL: `http://localhost:5000/api/reels/1/like`
- Headers:
  ```
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
  ```
  ⚠️ **Note**: **Authentication is REQUIRED** - This endpoint tracks which user likes which reel for future recommendations.

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel liked successfully",
  "data": {
    "reel_id": 1,
    "likes_count": 1,
    "is_liked": true
  }
}
```

**Error Response (400 Bad Request - Already Liked):**
```json
{
  "error": "You have already liked this reel",
  "data": {
    "reel_id": 1,
    "likes_count": 1,
    "is_liked": true
  }
}
```

**Error Response (401 Unauthorized):**
```json
{
  "msg": "Missing Authorization Header"
}
```

**Note**: 
- This endpoint requires authentication to track user-reel interactions for recommendations.
- Each user can only like a reel once. Attempting to like again will return a 400 error.
- The `likes_count` is incremented and the like is stored in the database for future recommendation algorithms.

---

### Unlike a Reel
**Endpoint**: `POST /api/reels/{reel_id}/unlike`

**Request:**
- Method: `POST`
- URL: `http://localhost:5000/api/reels/1/unlike`
- Headers:
  ```
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
  ```
  ⚠️ **Note**: **Authentication is REQUIRED** - This endpoint tracks which user unlikes which reel.

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel unliked successfully",
  "data": {
    "reel_id": 1,
    "likes_count": 0,
    "is_liked": false
  }
}
```

**Error Response (400 Bad Request - Not Liked):**
```json
{
  "error": "You have not liked this reel",
  "data": {
    "reel_id": 1,
    "likes_count": 1,
    "is_liked": false
  }
}
```

**Error Response (401 Unauthorized):**
```json
{
  "msg": "Missing Authorization Header"
}
```

**Note**: 
- This endpoint requires authentication to track user-reel interactions.
- You can only unlike a reel that you have previously liked. Attempting to unlike a reel you haven't liked will return a 400 error.
- The `likes_count` is decremented (won't go below 0) and the like record is removed from the database.

---

### Share a Reel
**Endpoint**: `POST /api/reels/{reel_id}/share`

**Request:**
- Method: `POST`
- URL: `http://localhost:5000/api/reels/1/share`
- Headers:
  ```
  Content-Type: application/json
  ```
  ⚠️ **Note**: No authentication required (public endpoint)

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Reel share tracked successfully",
  "data": {
    "reel_id": 1,
    "shares_count": 1
  }
}
```

**Note**: This increments the `shares_count` when a user shares the reel.

---

## Common Issues & Troubleshooting

### Issue 1: "Only merchants can upload reels"
**Solution**: Ensure you're logged in with a merchant account, not a regular user account.

### Issue 2: "Product must be approved by admin"
**Solution**: 
- Check product approval status in database
- Use `GET /api/reels/products/available` to see only approved products

### Issue 3: "Product must have stock quantity greater than 0"
**Solution**: 
- Update product stock in database
- Use `GET /api/reels/products/available` to see only products with stock > 0

### Issue 4: "Invalid file type"
**Solution**: 
- Ensure video file is MP4, MOV, AVI, or MKV
- Check file extension is correct

### Issue 5: "Video file size must be less than 100MB"
**Solution**: 
- Compress video or use a smaller file
- Current limit is 100MB

### Issue 6: "401 Unauthorized"
**Solution**: 
- Check if JWT token is valid and not expired
- Ensure `Authorization: Bearer TOKEN` header is set correctly
- Re-login to get a new token

### Issue 7: CORS Error
**Solution**: 
- Ensure backend CORS is configured correctly
- Check `ALLOWED_ORIGINS` in `app.py`
- For Postman, CORS shouldn't be an issue, but check if testing from browser

---

## Postman Collection Setup Tips

1. **Create Environment Variables**:
   - `base_url`: `http://127.0.0.1:5110`
   - `access_token`: Your JWT token (update after login)
   - `reel_id`: Store reel_id after upload for testing

2. **Use Variables in URLs**:
   ```
   {{base_url}}/api/reels
   {{base_url}}/api/reels/{{reel_id}}
   ```

3. **Set Authorization at Collection Level**:
   - Go to Collection → Authorization
   - Type: Bearer Token
   - Token: `{{access_token}}`
   - This applies to all requests in the collection

4. **Create Pre-request Script** (Optional):
   ```javascript
   // Auto-refresh token if expired
   // Add your token refresh logic here
   ```

---

## Testing Checklist

- [ ] Get authentication token
- [ ] Get available products
- [ ] Upload reel with valid video file
- [ ] Upload reel with invalid product_id (should fail)
- [ ] Upload reel without description (should fail)
- [ ] Upload reel without video file (should fail)
- [ ] Get reel by ID (check if views_count increments)
- [ ] Get reel by ID with `track_view=false` (check views_count doesn't increment)
- [ ] Get non-existent reel (should return 404)
- [ ] Get merchant's own reels
- [ ] Get public reels feed
- [ ] Update reel description
- [ ] Delete reel
- [ ] Like a reel with authentication (check likes_count increments and is_liked becomes true)
- [ ] Try to like the same reel again (should return 400 error)
- [ ] Unlike a reel with authentication (check likes_count decrements and is_liked becomes false)
- [ ] Try to unlike a reel you haven't liked (should return 400 error)
- [ ] Share a reel (check shares_count increments)

---

## Example Video File for Testing

If you don't have a test video:
1. Create a short MP4 video (< 60 seconds, < 100MB)
2. Use online video generators
3. Download sample videos from free stock sites

**Recommended Test Video Specs:**
- Format: MP4
- Duration: 10-30 seconds
- Size: < 10MB
- Resolution: 720p or 1080p

---

## Notes

- **Approval Status**: Reels don't require approval - they are active immediately after upload with `approval_status: "approved"`
- **Disabling Reasons**: The `disabling_reasons` array shows why a reel is not visible (e.g., product out of stock, product not approved, etc.)
- **View Tracking**: View count is automatically incremented when fetching a reel via `GET /api/reels/{reel_id}`. Use `?track_view=false` to disable this.
- **Like Tracking**: Likes are now tracked per user for recommendation purposes. Authentication is required for like/unlike endpoints. Each user can only like a reel once. The `is_liked` field in the reel response indicates whether the authenticated user has liked the reel.
- **Share Tracking**: Shares are tracked as simple counters (no user-specific tracking yet).
- **Counters**: All counters (`views_count`, `likes_count`, `shares_count`) start at 0 for new reels and increment as users interact with the reel.
- **User-Reel Interactions**: The `user_reel_likes` table stores which users like which reels, enabling future recommendation algorithms based on user preferences.
- **Storage Provider**: Currently using Cloudinary. To switch to AWS, set `VIDEO_STORAGE_PROVIDER=aws` in environment variables
- **Thumbnail**: Thumbnail is auto-generated during upload if not provided

---

## Support

If you encounter issues:
1. Check backend logs for detailed error messages
2. Verify database migration ran successfully
3. Ensure all required environment variables are set
4. Check that merchant account has approved products with stock > 0
