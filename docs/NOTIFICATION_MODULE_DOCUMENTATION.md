# Notification Module Documentation

## Table of Contents
1. [Overview](#overview)
2. [Features](#features)
3. [API Endpoints](#api-endpoints)
4. [Frontend Implementation Guide](#frontend-implementation-guide)
5. [Data Models](#data-models)
6. [Best Practices](#best-practices)
7. [Error Handling](#error-handling)
8. [UI/UX Recommendations](#uiux-recommendations)

---

## Overview

The Notification Module is a comprehensive in-app notification system designed for merchants in the AOIN e-commerce platform. It provides real-time notifications for important merchant activities, specifically:

- **Reel Likes**: Merchants receive aggregated notifications when users like their reels
- **Merchant Follows**: Merchants receive individual notifications when users follow them

### Key Characteristics

- **Aggregated Notifications**: Reel likes are aggregated per reel to prevent notification spam (e.g., 5000 likes = 1 notification, not 5000)
- **Automatic Cleanup**: Old read notifications are automatically cleaned up every 6 hours to maintain database performance
- **Real-time Updates**: Notifications are created immediately when events occur
- **Scalable**: Designed to handle high-volume scenarios efficiently

---

## Features

### 1. **Notification Types**

#### REEL_LIKED
- **Trigger**: When a user likes a merchant's reel
- **Aggregation**: Multiple likes on the same reel are aggregated into a single notification
- **Update Behavior**: If a reel already has an unread notification, new likes update the existing notification (increment count)
- **Example**: "Your reel has received 5,000 likes"

#### MERCHANT_FOLLOWED
- **Trigger**: When a user follows a merchant
- **Aggregation**: Each follow creates a separate notification (not aggregated)
- **Example**: "John Doe started following you"

### 2. **Notification Management**

- ✅ **Get All Notifications**: Paginated list with filtering options
- ✅ **Get Unread Count**: Quick count of unread notifications
- ✅ **Mark as Read**: Mark individual notifications as read
- ✅ **Mark All as Read**: Bulk mark all notifications as read
- ✅ **Delete Notification**: Remove individual notifications
- ✅ **Bulk Delete**: Delete multiple notifications at once
- ✅ **Cleanup Old Notifications**: Manual cleanup endpoint (automatic cleanup runs every 6 hours)

### 3. **Smart Aggregation**

- Reel likes are aggregated per reel to prevent notification spam
- Only unread notifications are updated (read notifications create new ones)
- Efficient database queries with proper indexing

### 4. **Automatic Cleanup**

- Background scheduler runs every 6 hours
- Deletes read notifications older than 90 days (configurable)
- Processes in small batches (100 notifications per batch) to avoid heavy database load
- Configurable via environment variables

### 5. **Security & Validation**

- All endpoints require merchant authentication
- Prevents self-follow notifications
- Input validation for all parameters
- Proper error handling and logging

---

## API Endpoints

### Base URL
All notification endpoints are prefixed with `/api/merchants/notifications`

### Authentication
All endpoints require:
- **Header**: `Authorization: Bearer <JWT_TOKEN>`
- **Role**: Merchant role required

---

### 1. Get Notifications

**Endpoint**: `GET /api/merchants/notifications`

**Description**: Retrieve paginated list of notifications for the current merchant.

**Query Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number (min: 1) |
| `per_page` | integer | No | 20 | Items per page (min: 1, max: 100) |
| `unread_only` | boolean | No | false | If true, only return unread notifications |

**Response** (200 OK):
```json
{
  "status": "success",
  "unread_count": 5,
  "data": [
    {
      "id": 1,
      "type": "reel_liked",
      "title": "Your reel is getting popular!",
      "message": "Your reel has received 5000 likes",
      "related_entity_type": "reel",
      "related_entity_id": 123,
      "like_count": 5000,
      "last_liked_by_user_name": "John Doe",
      "is_read": false,
      "read_at": null,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T12:45:00Z"
    },
    {
      "id": 2,
      "type": "merchant_followed",
      "title": "New follower",
      "message": "Jane Smith started following you",
      "related_entity_type": "user",
      "related_entity_id": 456,
      "like_count": null,
      "last_liked_by_user_name": null,
      "is_read": false,
      "read_at": null,
      "created_at": "2024-01-15T09:20:00Z",
      "updated_at": "2024-01-15T09:20:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 15,
    "pages": 1
  }
}
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: User is not a merchant
- `404 Not Found`: Merchant profile not found
- `500 Internal Server Error`: Server error

---

### 2. Get Unread Count

**Endpoint**: `GET /api/merchants/notifications/unread-count`

**Description**: Get the count of unread notifications (useful for badge display).

**Response** (200 OK):
```json
{
  "status": "success",
  "unread_count": 5
}
```

**Use Case**: Display a badge with unread count on the notification icon.

---

### 3. Mark Notification as Read

**Endpoint**: `PUT /api/merchants/notifications/{notification_id}/read`

**Description**: Mark a specific notification as read.

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notification_id` | integer | Yes | Notification ID to mark as read |

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "Notification marked as read"
}
```

**Error Responses**:
- `404 Not Found`: Notification not found or doesn't belong to merchant
- `500 Internal Server Error`: Server error

---

### 4. Mark All as Read

**Endpoint**: `PUT /api/merchants/notifications/mark-all-read`

**Description**: Mark all notifications as read for the current merchant.

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "15 notifications marked as read"
}
```

---

### 5. Delete Notification

**Endpoint**: `DELETE /api/merchants/notifications/{notification_id}`

**Description**: Delete a specific notification.

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notification_id` | integer | Yes | Notification ID to delete |

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "Notification deleted successfully"
}
```

---

### 6. Bulk Delete Notifications

**Endpoint**: `DELETE /api/merchants/notifications/bulk-delete`

**Description**: Delete multiple notifications at once.

**Request Body**:
```json
{
  "notification_ids": [1, 2, 3, 4, 5]
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "5 notification(s) deleted successfully"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid request body or empty array
- `404 Not Found`: Some notifications not found

---

### 7. Cleanup Old Notifications

**Endpoint**: `POST /api/merchants/notifications/cleanup`

**Description**: Manually trigger cleanup of old read notifications (automatic cleanup runs every 6 hours).

**Query Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `days_old` | integer | No | 90 | Delete notifications older than X days (30-365) |
| `batch_size` | integer | No | 100 | Notifications per batch (10-500) |
| `max_batches` | integer | No | 10 | Maximum batches to process (1-50) |

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "150 old notification(s) cleaned up successfully",
  "data": {
    "total_deleted": 150,
    "batches_processed": 2,
    "cutoff_date": "2024-01-15T00:00:00Z"
  }
}
```

---

## Data Models

### Notification Object

```typescript
interface Notification {
  id: number;
  type: 'reel_liked' | 'merchant_followed';
  title: string;
  message: string;
  related_entity_type: 'reel' | 'user' | null;
  related_entity_id: number | null;
  like_count: number | null;  // Only for reel_liked type
  last_liked_by_user_name: string | null;  // Only for reel_liked type
  is_read: boolean;
  read_at: string | null;  // ISO 8601 datetime
  created_at: string;  // ISO 8601 datetime
  updated_at: string;  // ISO 8601 datetime
}
```

### Notification Types

```typescript
type NotificationType = 'reel_liked' | 'merchant_followed';
```

### Pagination Object

```typescript
interface Pagination {
  page: number;
  per_page: number;
  total: number;
  pages: number;
}
```

### API Response Structure

```typescript
interface NotificationListResponse {
  status: 'success' | 'error';
  unread_count: number;
  data: Notification[];
  pagination: Pagination;
}
```

---

## Frontend Implementation Guide

### 1. **Setup and Configuration**

#### API Base URL
```typescript
const API_BASE_URL = 'http://localhost:5000'; // or your backend URL
const NOTIFICATION_ENDPOINT = `${API_BASE_URL}/api/merchants/notifications`;
```

#### Authentication
Ensure you include the JWT token in all requests:
```typescript
const headers = {
  'Authorization': `Bearer ${accessToken}`,
  'Content-Type': 'application/json'
};
```

---

### 2. **State Management**

#### Recommended Approach
Use a state management solution (Redux, Zustand, Context API, etc.) to manage:
- Notifications list
- Unread count
- Loading states
- Error states

#### State Structure
```typescript
interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  isLoading: boolean;
  error: string | null;
  pagination: Pagination;
  filters: {
    page: number;
    per_page: number;
    unread_only: boolean;
  };
}
```

---

### 3. **Fetching Notifications**

#### Initial Load
1. Fetch unread count first (for badge display)
2. Fetch notifications list with pagination
3. Store in state management

#### Implementation Steps:
1. **Create API Service Function**
   - Create a function to fetch notifications with query parameters
   - Handle pagination parameters
   - Include error handling

2. **Polling Strategy** (Optional)
   - Poll unread count every 30-60 seconds
   - Only fetch full list when user opens notification panel
   - Reduces unnecessary API calls

3. **Pagination Handling**
   - Implement "Load More" or infinite scroll
   - Track current page and total pages
   - Disable load more when all pages are loaded

---

### 4. **Displaying Notifications**

#### Notification List UI Components

**Recommended Structure:**
1. **Notification Icon with Badge**
   - Display unread count badge
   - Update badge when notifications are read
   - Click to open notification panel

2. **Notification Panel/Dropdown**
   - List of notifications (newest first)
   - Visual distinction between read/unread
   - Action buttons (mark as read, delete)

3. **Individual Notification Card**
   - Show notification type icon
   - Display title and message
   - Show timestamp (relative time: "2 hours ago")
   - Action buttons (mark as read, delete)
   - Link to related entity (reel/user profile) if applicable

#### Visual Indicators:
- **Unread**: Bold text, colored background, or dot indicator
- **Read**: Normal text, muted background
- **Type Icons**: Different icons for reel_liked vs merchant_followed

---

### 5. **Marking as Read**

#### Implementation Flow:
1. User clicks notification or "Mark as Read" button
2. Optimistically update UI (mark as read immediately)
3. Send API request to mark as read
4. Update unread count
5. Handle errors (revert UI if API fails)

#### Best Practices:
- **Optimistic Updates**: Update UI immediately for better UX
- **Error Handling**: Revert changes if API call fails
- **Batch Operations**: When marking all as read, update all notifications at once

---

### 6. **Deleting Notifications**

#### Implementation Flow:
1. User clicks delete button
2. Show confirmation dialog (optional)
3. Optimistically remove from UI
4. Send API request to delete
5. Update unread count if notification was unread
6. Handle errors (restore notification if API fails)

#### Bulk Delete:
- Allow users to select multiple notifications
- Show "Delete Selected" button
- Use bulk delete endpoint for efficiency

---

### 7. **Real-time Updates** (Optional)

#### Polling Strategy:
- Poll unread count every 30-60 seconds
- When unread count changes, fetch new notifications
- Show "New notifications" indicator

#### WebSocket Integration (Future):
- Connect to WebSocket endpoint
- Receive real-time notification events
- Update UI immediately when new notification arrives

---

### 8. **Navigation and Deep Linking**

#### Related Entity Navigation:
- **Reel Likes**: Navigate to reel detail page (`related_entity_id` = reel_id)
- **Merchant Follows**: Navigate to user profile (`related_entity_id` = user_id)

#### Implementation:
```typescript
// When user clicks notification
if (notification.type === 'reel_liked') {
  navigate(`/reels/${notification.related_entity_id}`);
} else if (notification.type === 'merchant_followed') {
  navigate(`/users/${notification.related_entity_id}`);
}
```

---

### 9. **Error Handling**

#### Common Errors:
- **401 Unauthorized**: Token expired, redirect to login
- **403 Forbidden**: User is not a merchant, show error message
- **404 Not Found**: Notification doesn't exist, remove from UI
- **500 Server Error**: Show error message, allow retry

#### Error Handling Strategy:
1. Display user-friendly error messages
2. Provide retry mechanism
3. Log errors for debugging
4. Handle network errors gracefully

---

### 10. **Performance Optimization**

#### Recommendations:
1. **Lazy Loading**: Load notifications only when panel is opened
2. **Pagination**: Don't load all notifications at once
3. **Caching**: Cache notifications for a short period (5-10 minutes)
4. **Debouncing**: Debounce mark-as-read actions if user is rapidly clicking
5. **Virtual Scrolling**: Use virtual scrolling for long notification lists

---

## Best Practices

### 1. **User Experience**
- ✅ Show unread count badge on notification icon
- ✅ Highlight unread notifications visually
- ✅ Provide "Mark All as Read" option
- ✅ Show relative timestamps ("2 hours ago")
- ✅ Allow bulk operations (delete multiple)
- ✅ Provide loading states during API calls
- ✅ Show empty state when no notifications

### 2. **Performance**
- ✅ Implement pagination (don't load all at once)
- ✅ Poll unread count, not full list
- ✅ Use optimistic updates for better UX
- ✅ Cache notifications for short periods
- ✅ Debounce rapid actions

### 3. **Error Handling**
- ✅ Handle network errors gracefully
- ✅ Show user-friendly error messages
- ✅ Provide retry mechanisms
- ✅ Log errors for debugging

### 4. **Accessibility**
- ✅ Use proper ARIA labels
- ✅ Keyboard navigation support
- ✅ Screen reader friendly
- ✅ High contrast for unread indicators

---

## Error Handling

### Error Response Format

All error responses follow this format:
```json
{
  "error": "Error message here"
}
```

### Common Error Scenarios

#### 1. Authentication Errors
```json
{
  "error": "User not found"
}
```
**Action**: Redirect to login page

#### 2. Authorization Errors
```json
{
  "error": "Merchant profile not found"
}
```
**Action**: Show error message, user may not be a merchant

#### 3. Validation Errors
```json
{
  "error": "notification_ids must be a non-empty array"
}
```
**Action**: Show validation error message

#### 4. Not Found Errors
```json
{
  "error": "Notification not found"
}
```
**Action**: Remove notification from UI, show toast message

#### 5. Server Errors
```json
{
  "error": "Failed to get notifications: <error details>"
}
```
**Action**: Show error message, provide retry button

---

## UI/UX Recommendations

### 1. **Notification Icon**
- Display bell icon with badge showing unread count
- Badge should be prominent but not overwhelming
- Animate badge when count changes
- Position: Top navigation bar (right side)

### 2. **Notification Panel**
- **Position**: Dropdown from notification icon or side panel
- **Size**: Max height with scroll (don't cover entire screen)
- **Layout**: List of notification cards
- **Empty State**: Friendly message when no notifications

### 3. **Notification Card Design**
- **Unread**: Bold title, colored left border, or background highlight
- **Read**: Normal styling, muted colors
- **Icons**: Different icons for each notification type
- **Actions**: Hover to show action buttons (mark as read, delete)
- **Timestamp**: Show relative time ("2 hours ago")

### 4. **Interaction Patterns**
- **Click Notification**: Mark as read + navigate to related entity
- **Hover**: Show action buttons
- **Long Press/Menu**: Show context menu with options
- **Swipe**: Swipe to delete (mobile)

### 5. **Visual Hierarchy**
- Unread notifications at top
- Group by date (Today, Yesterday, This Week, Older)
- Clear visual distinction between read/unread
- Consistent spacing and typography

### 6. **Mobile Considerations**
- Full-screen notification panel on mobile
- Swipe gestures for actions
- Bottom sheet for notification details
- Optimize for one-handed use

### 7. **Loading States**
- Skeleton loaders while fetching
- Shimmer effect for better UX
- Show loading indicator during API calls
- Disable interactions during loading

### 8. **Empty States**
- Friendly message when no notifications
- Illustration or icon
- Clear call-to-action if applicable

---

## Implementation Checklist

### Phase 1: Basic Setup
- [ ] Set up API service functions
- [ ] Create notification state management
- [ ] Implement authentication headers
- [ ] Create notification icon with badge

### Phase 2: Core Features
- [ ] Fetch and display notifications list
- [ ] Implement pagination
- [ ] Mark notifications as read
- [ ] Delete notifications
- [ ] Display unread count

### Phase 3: Enhanced Features
- [ ] Mark all as read
- [ ] Bulk delete
- [ ] Filter by unread only
- [ ] Navigate to related entities
- [ ] Polling for new notifications

### Phase 4: Polish
- [ ] Error handling
- [ ] Loading states
- [ ] Empty states
- [ ] Animations
- [ ] Accessibility
- [ ] Mobile optimization

---

## Testing Recommendations

### 1. **Unit Tests**
- Test API service functions
- Test state management logic
- Test notification filtering/sorting

### 2. **Integration Tests**
- Test API integration
- Test error handling
- Test pagination

### 3. **E2E Tests**
- Test notification flow end-to-end
- Test user interactions
- Test error scenarios

### 4. **Performance Tests**
- Test with large notification lists
- Test pagination performance
- Test polling frequency

---

## Troubleshooting

### Common Issues

#### 1. Notifications not updating
- **Check**: Polling interval
- **Check**: API response handling
- **Check**: State management updates

#### 2. Unread count incorrect
- **Check**: Mark as read API calls
- **Check**: State synchronization
- **Check**: Cache invalidation

#### 3. Performance issues
- **Check**: Pagination implementation
- **Check**: Number of notifications loaded
- **Check**: Polling frequency

#### 4. Authentication errors
- **Check**: Token expiration
- **Check**: Token refresh logic
- **Check**: Header format

---

## Support and Resources

### API Documentation
- Swagger UI: `http://localhost:5000/docs`
- Endpoint: `/api/merchants/notifications`

### Backend Logs
- Check application logs for detailed error messages
- Notification creation is logged in backend

### Configuration
- Cleanup settings: See `config.py`
- Environment variables: See `.env` file

---

## Version History

- **v1.0.0** (Current)
  - Initial implementation
  - Reel likes and merchant follows notifications
  - Aggregated notifications for reel likes
  - Automatic cleanup system
  - Full CRUD operations

---

## Conclusion

This notification module provides a robust, scalable solution for merchant notifications. By following this guide, frontend developers can implement a seamless notification experience that enhances user engagement and provides timely updates on important merchant activities.

For any questions or issues, please refer to the API documentation or contact the backend team.

