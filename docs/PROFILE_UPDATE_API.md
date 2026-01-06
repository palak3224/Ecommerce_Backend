# Profile Update API Documentation

This document describes the profile update APIs for both **User** and **Merchant** profiles, including field restrictions, validation rules, and usage examples.

---

## Table of Contents

1. [User Profile Update](#user-profile-update)
   - [Get User Profile](#get-user-profile)
   - [Update User Profile](#update-user-profile)
   - [Upload User Profile Image](#upload-user-profile-image)
2. [Merchant Profile Update](#merchant-profile-update)
   - [Get Merchant Profile](#get-merchant-profile)
   - [Update Merchant Profile](#update-merchant-profile)
   - [Upload Merchant Profile Image](#upload-merchant-profile-image)
   - [Check Username Availability](#check-username-availability)
3. [Field Restrictions Summary](#field-restrictions-summary)
4. [Error Handling](#error-handling)

---

## User Profile Update

### Get User Profile

**Endpoint:** `GET /api/users/profile`

**Authentication:** Required (JWT Token)

**Description:** Retrieves the authenticated user's profile information.

**Response:**
```json
{
  "profile": {
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+1234567890",
    "profile_img": "https://example.com/profile.jpg",
    "is_email_verified": true,
    "is_phone_verified": false,
    "role": "user",
    "last_login": "2025-01-05T10:30:00Z",
    "auth_provider": "local",
    "date_of_birth": "15-03-1990",
    "gender": "male"
  }
}
```

**Status Codes:**
- `200 OK`: Profile retrieved successfully
- `401 Unauthorized`: Invalid or missing JWT token
- `404 Not Found`: User not found
- `500 Internal Server Error`: Server error

---

### Update User Profile

**Endpoint:** `PUT /api/users/profile`

**Authentication:** Required (JWT Token)

**Description:** Updates the authenticated user's profile information. **Email and phone cannot be updated through this endpoint.**

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "date_of_birth": "15-03-1990",
  "gender": "male"
}
```

**Field Details:**

| Field | Type | Required | Validation | Notes |
|-------|------|----------|------------|-------|
| `first_name` | string | No | 1-100 characters | Can be updated |
| `last_name` | string | No | 1-100 characters | Can be updated |
| `date_of_birth` | string | No | DD-MM-YYYY format | Can be updated, can be set to `null` |
| `gender` | string | No | One of: `male`, `female`, `other`, `prefer_not_to_say` | Can be updated, can be set to `null` |

**Restricted Fields (Cannot be updated):**
- `email` - Use separate email change flow
- `phone` - Use separate phone verification flow
- `id`, `password_hash`, `role`, `is_active`
- `is_email_verified`, `is_phone_verified`
- `auth_provider`, `provider_user_id`
- `created_at`, `updated_at`

**Response:**
```json
{
  "message": "Profile updated successfully",
  "profile": {
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+1234567890",
    "date_of_birth": "15-03-1990",
    "gender": "male"
  }
}
```

**Status Codes:**
- `200 OK`: Profile updated successfully
- `400 Bad Request`: Validation error or restricted field attempted
- `401 Unauthorized`: Invalid or missing JWT token
- `500 Internal Server Error`: Server error

**Example Request:**
```bash
curl -X PUT https://api.example.com/api/users/profile \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "15-03-1990",
    "gender": "male"
  }'
```

---

### Upload User Profile Image

**Endpoint:** `POST /api/users/profile/image`

**Authentication:** Required (JWT Token)

**Description:** Uploads or updates the user's profile image. The old image is automatically deleted from S3 if it exists.

**Request Format:** `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `profile_image` | file | Yes | Image file (PNG, JPG, JPEG, GIF, WebP) |

**Response:**
```json
{
  "message": "Profile image uploaded successfully",
  "profile_img_url": "https://cdn.example.com/assets/profile-images/123_uuid_filename.jpg"
}
```

**Status Codes:**
- `200 OK`: Image uploaded successfully
- `400 Bad Request`: No file provided or invalid file
- `401 Unauthorized`: Invalid or missing JWT token
- `404 Not Found`: User not found
- `500 Internal Server Error`: Upload failed

**Example Request:**
```bash
curl -X POST https://api.example.com/api/users/profile/image \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "profile_image=@/path/to/image.jpg"
```

---

## Merchant Profile Update

### Get Merchant Profile

**Endpoint:** `GET /api/merchants/profile`

**Authentication:** Required (JWT Token, Merchant Role)

**Description:** Retrieves the authenticated merchant's profile information.

**Response:**
```json
{
  "profile": {
    "business_name": "My Business",
    "business_description": "Business description",
    "business_email": "business@example.com",
    "business_phone": "+1234567890",
    "business_address": "123 Main St",
    "country_code": "IN",
    "state_province": "Maharashtra",
    "city": "Mumbai",
    "postal_code": "400001",
    "username": "mybusiness_1234",
    "profile_img": "https://example.com/profile.jpg",
    "gstin": "27ABCDE1234F1Z5",
    "pan_number": "ABCDE1234F",
    "tax_id": null,
    "vat_number": null,
    "sales_tax_number": null,
    "bank_account_number": "1234567890",
    "bank_name": "Bank Name",
    "bank_branch": "Branch Name",
    "bank_ifsc_code": "ABCD0123456",
    "bank_swift_code": null,
    "bank_routing_number": null,
    "bank_iban": null,
    "is_verified": true,
    "verification_status": "approved",
    "verification_submitted_at": "2025-01-01T10:00:00Z",
    "verification_completed_at": "2025-01-02T10:00:00Z",
    "verification_notes": null,
    "required_documents": ["pan_number", "gstin", "bank_details"],
    "submitted_documents": ["pan_number", "gstin"]
  }
}
```

**Status Codes:**
- `200 OK`: Profile retrieved successfully
- `401 Unauthorized`: Invalid or missing JWT token
- `403 Forbidden`: User is not a merchant
- `404 Not Found`: Merchant profile not found
- `500 Internal Server Error`: Server error

---

### Update Merchant Profile

**Endpoint:** `PUT /api/merchants/profile`

**Authentication:** Required (JWT Token, Merchant Role)

**Description:** Updates the merchant's profile information. **Business email and business phone cannot be updated through this endpoint.** Username can only be updated once per year.

**Request Body:**
```json
{
  "business_name": "My Business",
  "business_description": "Updated description",
  "business_address": "123 Main St",
  "username": "newusername_5678",
  "profile_img": "https://example.com/profile.jpg",
  "country_code": "IN",
  "state_province": "Maharashtra",
  "city": "Mumbai",
  "postal_code": "400001",
  "gstin": "27ABCDE1234F1Z5",
  "pan_number": "ABCDE1234F",
  "bank_account_number": "1234567890",
  "bank_name": "Bank Name",
  "bank_branch": "Branch Name",
  "bank_ifsc_code": "ABCD0123456"
}
```

**Field Details:**

| Field | Type | Required | Validation | Notes |
|-------|------|----------|------------|-------|
| `business_name` | string | No | 2-200 characters | Can be updated |
| `business_description` | string | No | - | Can be updated |
| `business_address` | string | No | - | Can be updated |
| `username` | string | No | 3-30 chars, alphanumeric + underscore | Can be updated **once per year** |
| `profile_img` | string | No | Valid URL | Can be updated (use upload endpoint for file upload) |
| `country_code` | string | No | Valid country code | Can be updated |
| `state_province` | string | No | - | Can be updated |
| `city` | string | No | - | Can be updated |
| `postal_code` | string | No | - | Can be updated |
| `gstin` | string | No | Max 15 characters | India-specific, can be updated |
| `pan_number` | string | No | Max 10 characters | India-specific, can be updated |
| `tax_id` | string | No | Max 50 characters | Global, can be updated |
| `vat_number` | string | No | Max 50 characters | Global, can be updated |
| `sales_tax_number` | string | No | Max 50 characters | Global, can be updated |
| `bank_account_number` | string | No | 9-18 characters | Can be updated |
| `bank_name` | string | No | Max 100 characters | Can be updated |
| `bank_branch` | string | No | Max 100 characters | Can be updated |
| `bank_ifsc_code` | string | No | Max 11 characters | India-specific, can be updated |
| `bank_swift_code` | string | No | Max 11 characters | Global, can be updated |
| `bank_routing_number` | string | No | Max 20 characters | Global, can be updated |
| `bank_iban` | string | No | Max 34 characters | Global, can be updated |

**Restricted Fields (Cannot be updated):**
- `business_email` - Cannot be updated directly
- `business_phone` - Cannot be updated directly
- `id`, `user_id`
- `verification_status`, `is_verified`
- `verification_submitted_at`, `verification_completed_at`, `verification_notes`
- `created_at`, `updated_at`

**Username Update Restrictions:**
- Username can only be updated **once per year**
- If `username_updated_at` is `null`, username can be updated (first time)
- If username was updated less than 365 days ago, update will be rejected
- Username must be unique across all merchants
- Username format: 3-30 characters, alphanumeric and underscores only

**Response:**
```json
{
  "message": "Profile updated successfully",
  "profile": {
    "business_name": "My Business",
    "business_email": "business@example.com",
    "business_phone": "+1234567890",
    "username": "newusername_5678",
    "profile_img": "https://example.com/profile.jpg",
    "country_code": "IN",
    "verification_status": "approved"
  }
}
```

**Status Codes:**
- `200 OK`: Profile updated successfully
- `400 Bad Request`: Validation error, restricted field attempted, or username update too soon
- `401 Unauthorized`: Invalid or missing JWT token
- `403 Forbidden`: User is not a merchant
- `404 Not Found`: Merchant profile not found
- `409 Conflict`: Username already taken
- `500 Internal Server Error`: Server error

**Example Request:**
```bash
curl -X PUT https://api.example.com/api/merchants/profile \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "My Business",
    "business_description": "Updated description",
    "username": "newusername_5678"
  }'
```

**Username Update Error Example:**
```json
{
  "error": "Username can only be updated once per year. You can update again in 180 days."
}
```

---

### Upload Merchant Profile Image

**Endpoint:** `POST /api/merchants/profile/image`

**Authentication:** Required (JWT Token, Merchant Role)

**Description:** Uploads or updates the merchant's profile image. The old image is automatically deleted from S3 if it exists.

**Request Format:** `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `profile_image` | file | Yes | Image file (PNG, JPG, JPEG, GIF, WebP) |

**Response:**
```json
{
  "message": "Profile image uploaded successfully",
  "profile_img_url": "https://cdn.example.com/assets/profile-images/123_uuid_filename.jpg"
}
```

**Status Codes:**
- `200 OK`: Image uploaded successfully
- `400 Bad Request`: No file provided or invalid file
- `401 Unauthorized`: Invalid or missing JWT token
- `403 Forbidden`: User is not a merchant
- `404 Not Found`: Merchant profile not found
- `500 Internal Server Error`: Upload failed

**Example Request:**
```bash
curl -X POST https://api.example.com/api/merchants/profile/image \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "profile_image=@/path/to/image.jpg"
```

---

### Check Username Availability

**Endpoint:** `GET /api/merchants/username/check?username={username}`

**Authentication:** Not required (Public endpoint)

**Description:** Checks if a username is available for merchant registration or update.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `username` | string | Yes | Username to check (3-30 chars, alphanumeric + underscore) |

**Response:**
```json
{
  "available": true,
  "username": "mybusiness_1234"
}
```

**Error Response (Invalid Format):**
```json
{
  "available": false,
  "error": "Invalid username format. Username must be 3-30 characters, alphanumeric and underscores only"
}
```

**Status Codes:**
- `200 OK`: Check completed
- `400 Bad Request`: Username parameter missing or invalid format

**Example Request:**
```bash
curl "https://api.example.com/api/merchants/username/check?username=mybusiness_1234"
```

---

## Field Restrictions Summary

### User Profile

**Updatable Fields:**
- ✅ `first_name`
- ✅ `last_name`
- ✅ `date_of_birth` (DD-MM-YYYY format)
- ✅ `gender` (male, female, other, prefer_not_to_say)
- ✅ `profile_img` (via upload endpoint)

**Restricted Fields:**
- ❌ `email` - Use separate email change flow
- ❌ `phone` - Use separate phone verification flow
- ❌ `id`, `password_hash`, `role`, `is_active`
- ❌ `is_email_verified`, `is_phone_verified`
- ❌ `auth_provider`, `provider_user_id`
- ❌ `created_at`, `updated_at`

### Merchant Profile

**Updatable Fields:**
- ✅ `business_name`
- ✅ `business_description`
- ✅ `business_address`
- ✅ `username` (once per year restriction)
- ✅ `profile_img` (via upload endpoint or URL)
- ✅ `country_code`, `state_province`, `city`, `postal_code`
- ✅ Tax fields: `gstin`, `pan_number`, `tax_id`, `vat_number`, `sales_tax_number`
- ✅ Bank fields: `bank_account_number`, `bank_name`, `bank_branch`, `bank_ifsc_code`, `bank_swift_code`, `bank_routing_number`, `bank_iban`

**Restricted Fields:**
- ❌ `business_email` - Cannot be updated directly
- ❌ `business_phone` - Cannot be updated directly
- ❌ `id`, `user_id`
- ❌ `verification_status`, `is_verified`
- ❌ `verification_submitted_at`, `verification_completed_at`, `verification_notes`
- ❌ `created_at`, `updated_at`

**Special Restrictions:**
- ⚠️ `username` - Can only be updated once per year

---

## Error Handling

### Common Error Responses

**400 Bad Request - Validation Error:**
```json
{
  "error": "Validation error",
  "details": {
    "date_of_birth": ["date_of_birth must be in DD-MM-YYYY format"],
    "gender": ["Must be one of: male, female, other, prefer_not_to_say"]
  }
}
```

**400 Bad Request - Restricted Field:**
```json
{
  "error": "Cannot update restricted fields: business_email, business_phone"
}
```

**400 Bad Request - Username Update Too Soon:**
```json
{
  "error": "Username can only be updated once per year. You can update again in 180 days."
}
```

**401 Unauthorized:**
```json
{
  "error": "Invalid or missing authentication token"
}
```

**403 Forbidden:**
```json
{
  "error": "Access denied. Merchant role required."
}
```

**404 Not Found:**
```json
{
  "error": "Merchant profile not found"
}
```

**409 Conflict - Username Taken:**
```json
{
  "error": "Username already taken"
}
```

**500 Internal Server Error:**
```json
{
  "error": "An internal server error occurred"
}
```

---

## Best Practices

### User Profile Updates

1. **Date Format**: Always use `DD-MM-YYYY` format for `date_of_birth`
2. **Gender Values**: Use exact values: `male`, `female`, `other`, `prefer_not_to_say`
3. **Profile Images**: Use the dedicated upload endpoint instead of passing URLs directly
4. **Email/Phone Changes**: Use separate verification flows for email and phone updates

### Merchant Profile Updates

1. **Username**: Check availability before attempting to update
2. **Username Updates**: Plan username changes carefully due to the 1-year restriction
3. **Profile Images**: Use the dedicated upload endpoint for file uploads
4. **Country-Specific Fields**: Ensure required fields are provided based on `country_code`
5. **Business Email/Phone**: These cannot be updated - contact support if changes are needed

### General

1. **Authentication**: Always include JWT token in `Authorization` header
2. **Content-Type**: Use `application/json` for PUT requests, `multipart/form-data` for file uploads
3. **Error Handling**: Check status codes and handle errors appropriately
4. **Validation**: Validate data client-side before sending requests
5. **Rate Limiting**: Be aware of rate limits on endpoints

---

## Integration Examples

### JavaScript/TypeScript Example

```typescript
// Update User Profile
async function updateUserProfile(data: {
  first_name?: string;
  last_name?: string;
  date_of_birth?: string;
  gender?: string;
}) {
  const response = await fetch(`${API_BASE_URL}/api/users/profile`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Update failed');
  }
  
  return await response.json();
}

// Upload User Profile Image
async function uploadUserProfileImage(file: File) {
  const formData = new FormData();
  formData.append('profile_image', file);
  
  const response = await fetch(`${API_BASE_URL}/api/users/profile/image`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Upload failed');
  }
  
  return await response.json();
}

// Update Merchant Profile
async function updateMerchantProfile(data: {
  business_name?: string;
  username?: string;
  // ... other fields
}) {
  const response = await fetch(`${API_BASE_URL}/api/merchants/profile`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Update failed');
  }
  
  return await response.json();
}

// Check Username Availability
async function checkUsernameAvailability(username: string) {
  const response = await fetch(
    `${API_BASE_URL}/api/merchants/username/check?username=${encodeURIComponent(username)}`
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Check failed');
  }
  
  return await response.json();
}
```

---

## Changelog

### Version 1.0.0 (2025-01-05)
- Initial release
- User profile update API with date_of_birth and gender fields
- Merchant profile update API with username field
- Profile image upload endpoints for both user and merchant
- Username availability check endpoint
- Username update restriction (once per year)
- Email and phone update restrictions for both profiles

---

## Support

For issues or questions regarding the Profile Update APIs, please contact the development team or refer to the main API documentation.

