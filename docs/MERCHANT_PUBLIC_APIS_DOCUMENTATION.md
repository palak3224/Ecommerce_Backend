# Merchant Public APIs Documentation

This document describes the public APIs available for viewing merchant profile information, statistics, and content. These APIs are accessible without authentication and can be used by users to view merchant profiles in the application.

---

## Table of Contents

1. [Overview](#overview)
2. [Public Merchant Profile](#1-public-merchant-profile)
3. [Merchant Reel Statistics](#2-merchant-reel-statistics)
4. [Merchant Follower Count](#3-merchant-follower-count)
5. [Error Responses](#error-responses)
6. [Usage Examples](#usage-examples)

---

## Overview

These APIs provide public access to merchant information that should be visible to users. All endpoints:
- **Do not require authentication** (public access)
- **Support CORS** (can be called from frontend)
- **Return JSON responses**
- **Use standard HTTP status codes**

---

## 1. Public Merchant Profile

Get public merchant profile information including business details, location, and verification status.

### Endpoint

```
GET /api/merchants/<merchant_id>/public-profile
```

### Parameters

| Parameter | Type | Location | Required | Description |
|-----------|------|----------|----------|-------------|
| merchant_id | integer | path | Yes | The ID of the merchant |

### Response

**Status Code:** `200 OK`

```json
{
  "merchant_id": 123,
  "business_name": "ABC Stores",
  "business_description": "Premium quality products for all your needs",
  "business_email": "contact@abcstores.com",
  "business_phone": "+91-9876543210",
  "business_address": "123 Main Street, Downtown",
  "location": {
    "country_code": "IN",
    "state_province": "Maharashtra",
    "city": "Mumbai",
    "postal_code": "400001"
  },
  "is_verified": true,
  "verification_status": "approved",
  "gstin": "27ABCDE1234F1Z5",
  "tax_id": null
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| merchant_id | integer | Unique merchant identifier |
| business_name | string | Name of the business |
| business_description | string | Business description/about section |
| business_email | string | Business contact email |
| business_phone | string | Business contact phone number |
| business_address | string | Full business address |
| location | object | Location details |
| location.country_code | string | Country code (e.g., "IN", "US") |
| location.state_province | string | State or province name |
| location.city | string | City name |
| location.postal_code | string | Postal/ZIP code |
| is_verified | boolean | Whether merchant is verified |
| verification_status | string | Verification status: "approved", "pending", "rejected" |
| gstin | string\|null | GSTIN number (India) - may be null |
| tax_id | string\|null | Tax ID number (Global) - may be null |

### Error Responses

**404 Not Found**
```json
{
  "error": "Merchant not found"
}
```

**500 Internal Server Error**
```json
{
  "error": "Failed to retrieve merchant profile"
}
```

---

## 2. Merchant Reel Statistics

Get aggregated statistics for all reels posted by a merchant (total counts of reels, likes, views, and shares).

### Endpoint

```
GET /api/reels/merchant/<merchant_id>/stats
```

### Parameters

| Parameter | Type | Location | Required | Description |
|-----------|------|----------|----------|-------------|
| merchant_id | integer | path | Yes | The ID of the merchant |

### Notes

- Only counts **visible reels** (excludes deleted, inactive, or reels with products out of stock)
- Statistics are aggregated from all visible reels
- Counts are real-time and accurate

### Response

**Status Code:** `200 OK`

```json
{
  "status": "success",
  "data": {
    "merchant_id": 123,
    "total_reels": 45,
    "total_likes": 5420,
    "total_views": 125000,
    "total_shares": 234
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| status | string | Response status (always "success" for 200) |
| data | object | Statistics data |
| data.merchant_id | integer | Merchant ID |
| data.total_reels | integer | Total number of visible reels |
| data.total_likes | integer | Sum of all likes across all visible reels |
| data.total_views | integer | Sum of all views across all visible reels |
| data.total_shares | integer | Sum of all shares across all visible reels |

### Error Responses

**404 Not Found**
```json
{
  "error": "Merchant not found"
}
```

**500 Internal Server Error**
```json
{
  "error": "Failed to get reel stats: <error message>"
}
```

---

## 3. Merchant Follower Count

Get the total number of followers for a merchant.

### Endpoint

```
GET /api/merchants/<merchant_id>/followers/count
```

### Parameters

| Parameter | Type | Location | Required | Description |
|-----------|------|----------|----------|-------------|
| merchant_id | integer | path | Yes | The ID of the merchant |

### Response

**Status Code:** `200 OK`

```json
{
  "status": "success",
  "merchant_id": 123,
  "follower_count": 456
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| status | string | Response status (always "success" for 200) |
| merchant_id | integer | Merchant ID |
| follower_count | integer | Total number of users following this merchant |

### Error Responses

**404 Not Found**
```json
{
  "error": "Merchant not found"
}
```

**500 Internal Server Error**
```json
{
  "error": "Failed to get follower count: <error message>"
}
```

---

## Error Responses

All endpoints follow standard HTTP status codes:

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 404 | Resource not found (merchant doesn't exist) |
| 500 | Internal server error |

All error responses follow this format:
```json
{
  "error": "Error message description"
}
```

---

## Usage Examples

### Example 1: Display Merchant Profile Page

When a user clicks on a merchant profile, you can fetch all information using these APIs:

```javascript
// Fetch merchant profile information
const merchantId = 123;

// 1. Get merchant profile
const profileResponse = await fetch(
  `/api/merchants/${merchantId}/public-profile`
);
const profile = await profileResponse.json();

// 2. Get reel statistics
const statsResponse = await fetch(
  `/api/reels/merchant/${merchantId}/stats`
);
const stats = await statsResponse.json();

// 3. Get follower count
const followersResponse = await fetch(
  `/api/merchants/${merchantId}/followers/count`
);
const followers = await followersResponse.json();

// 4. Get all reels (existing endpoint)
const reelsResponse = await fetch(
  `/api/reels/merchant/${merchantId}?page=1&per_page=20`
);
const reels = await reelsResponse.json();

// Combine data for display
const merchantData = {
  profile: profile,
  stats: stats.data,
  followerCount: followers.follower_count,
  reels: reels.data
};
```

### Example 2: Using Axios

```javascript
import axios from 'axios';

const merchantId = 123;
const baseURL = 'https://api.example.com';

async function getMerchantPublicInfo(merchantId) {
  try {
    const [profile, stats, followers, reels] = await Promise.all([
      axios.get(`${baseURL}/api/merchants/${merchantId}/public-profile`),
      axios.get(`${baseURL}/api/reels/merchant/${merchantId}/stats`),
      axios.get(`${baseURL}/api/merchants/${merchantId}/followers/count`),
      axios.get(`${baseURL}/api/reels/merchant/${merchantId}`, {
        params: { page: 1, per_page: 20 }
      })
    ]);

    return {
      profile: profile.data,
      stats: stats.data.data,
      followerCount: followers.data.follower_count,
      reels: reels.data.data,
      pagination: reels.data.pagination
    };
  } catch (error) {
    console.error('Error fetching merchant info:', error);
    throw error;
  }
}
```

### Example 3: React Component Example

```jsx
import React, { useState, useEffect } from 'react';

function MerchantProfilePage({ merchantId }) {
  const [merchantData, setMerchantData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchMerchantData() {
      try {
        const [profile, stats, followers] = await Promise.all([
          fetch(`/api/merchants/${merchantId}/public-profile`).then(r => r.json()),
          fetch(`/api/reels/merchant/${merchantId}/stats`).then(r => r.json()),
          fetch(`/api/merchants/${merchantId}/followers/count`).then(r => r.json())
        ]);

        setMerchantData({
          profile,
          stats: stats.data,
          followerCount: followers.follower_count
        });
      } catch (error) {
        console.error('Error:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchMerchantData();
  }, [merchantId]);

  if (loading) return <div>Loading...</div>;
  if (!merchantData) return <div>Merchant not found</div>;

  return (
    <div>
      <h1>{merchantData.profile.business_name}</h1>
      <p>{merchantData.profile.business_description}</p>
      <div>
        <span>Reels: {merchantData.stats.total_reels}</span>
        <span>Followers: {merchantData.followerCount}</span>
        <span>Total Likes: {merchantData.stats.total_likes}</span>
      </div>
    </div>
  );
}
```

---

## Additional Notes

1. **Caching**: Consider implementing client-side caching for these endpoints as the data doesn't change frequently.

2. **Rate Limiting**: While these are public APIs, ensure appropriate rate limiting is implemented on the backend to prevent abuse.

3. **Performance**: These endpoints are optimized for performance:
   - Reel stats use efficient database aggregations
   - Follower count uses indexed database queries
   - Profile data is lightweight

4. **Reel Visibility**: The reel statistics endpoint only counts visible reels. A reel is considered visible if:
   - It's not deleted
   - It's active
   - The associated product is approved and active
   - The product has stock > 0

5. **Related Endpoints**: 
   - To get the actual list of reels, use: `GET /api/reels/merchant/<merchant_id>`
   - This endpoint supports pagination: `?page=1&per_page=20`

---

## API Base URL

All endpoints are relative to your API base URL. For example:
- Development: `http://localhost:5000/api/merchants/...`
- Production: `https://api.yourdomain.com/api/merchants/...`

---

**Last Updated:** December 2024

