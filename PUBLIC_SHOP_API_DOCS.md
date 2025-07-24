# Public Shop API Documentation

## Overview
This document outlines the new public shop APIs created to provide shop-specific data for frontend applications. These APIs are optimized for performance by returning only relevant data for each shop.

## API Endpoints

### 1. Shop Management

#### Get All Shops
- **Endpoint**: `GET /api/public/shops`
- **Description**: Returns all active shops
- **Response**: List of all shops with their basic information
- **Usage**: For displaying shop selection or directory pages

#### Get Shop by ID
- **Endpoint**: `GET /api/public/shops/{shop_id}`
- **Description**: Returns details of a specific shop
- **Parameters**: 
  - `shop_id` (integer, required): ID of the shop
- **Usage**: For shop-specific header information

#### Get Shop by Slug
- **Endpoint**: `GET /api/public/shops/slug/{slug}`
- **Description**: Returns shop details using slug for SEO-friendly URLs
- **Parameters**: 
  - `slug` (string, required): Slug of the shop
- **Usage**: For shop pages with custom URLs

### 2. Shop Products

#### Get Products by Shop
- **Endpoint**: `GET /api/public/shops/{shop_id}/products`
- **Description**: Returns paginated products for a specific shop
- **Parameters**:
  - `shop_id` (integer, required): ID of the shop
  - `page` (integer, optional): Page number (default: 1)
  - `per_page` (integer, optional): Items per page (default: 20, max: 50)
  - `sort_by` (string, optional): Sort field (created_at, product_name, selling_price, special_price)
  - `order` (string, optional): Sort order (asc, desc)
  - `category_id` (integer, optional): Filter by category
  - `brand_id` (integer, optional): Filter by brand
  - `min_price` (float, optional): Minimum price filter
  - `max_price` (float, optional): Maximum price filter
  - `search` (string, optional): Search term
- **Features**:
  - Only returns published and active products
  - Includes product count per page
  - Optimized price filtering considering special offers
  - Full-text search across product name, description, SKU, category, and brand
- **Usage**: Primary endpoint for shop product listings

#### Get Product Details
- **Endpoint**: `GET /api/public/shops/{shop_id}/products/{product_id}`
- **Description**: Returns detailed information for a specific product
- **Parameters**:
  - `shop_id` (integer, required): ID of the shop
  - `product_id` (integer, required): ID of the product
- **Features**:
  - Includes all product media
  - Stock information
  - Related products from same category
- **Usage**: Product detail pages

#### Get Featured Products
- **Endpoint**: `GET /api/public/shops/{shop_id}/products/featured`
- **Description**: Returns latest/featured products for a shop
- **Parameters**:
  - `shop_id` (integer, required): ID of the shop
  - `limit` (integer, optional): Number of products (default: 8, max: 20)
- **Usage**: Homepage featured sections, new arrivals

### 3. Shop Categories

#### Get Categories by Shop
- **Endpoint**: `GET /api/public/shops/{shop_id}/categories`
- **Description**: Returns all active categories for a specific shop
- **Parameters**:
  - `shop_id` (integer, required): ID of the shop
- **Features**:
  - Includes product count for each category
- **Usage**: Category navigation, filter options

#### Get Category Details
- **Endpoint**: `GET /api/public/shops/{shop_id}/categories/{category_id}`
- **Description**: Returns details of a specific category
- **Parameters**:
  - `shop_id` (integer, required): ID of the shop
  - `category_id` (integer, required): ID of the category
- **Usage**: Category-specific pages

### 4. Shop Brands

#### Get Brands by Shop
- **Endpoint**: `GET /api/public/shops/{shop_id}/brands`
- **Description**: Returns all active brands for a specific shop
- **Parameters**:
  - `shop_id` (integer, required): ID of the shop
- **Features**:
  - Includes product count for each brand
- **Usage**: Brand navigation, filter options

#### Get Brand Details
- **Endpoint**: `GET /api/public/shops/{shop_id}/brands/{brand_id}`
- **Description**: Returns details of a specific brand
- **Parameters**:
  - `shop_id` (integer, required): ID of the shop
  - `brand_id` (integer, required): ID of the brand
- **Usage**: Brand-specific pages

## Frontend Integration

### Shop IDs Reference
Based on frontend analysis, the expected shop IDs are:
- `1`: Fashion Store
- `2`: Watch Store  
- `3`: Electronics Mega Store
- `4`: Footwear Store

### Usage Examples

#### 1. Fashion Store Products
```javascript
// Get fashion store products with filters
const response = await fetch('/api/public/shops/1/products?category_id=5&sort_by=selling_price&order=asc&page=1&per_page=20');
const data = await response.json();
```

#### 2. Electronics Store by Category
```javascript
// Get electronics in specific category
const response = await fetch('/api/public/shops/3/products?category_id=2&search=smartphone');
const data = await response.json();
```

#### 3. Watch Store Featured Products
```javascript
// Get featured watches
const response = await fetch('/api/public/shops/2/products/featured?limit=8');
const data = await response.json();
```

## Performance Benefits

1. **Reduced Data Transfer**: Only shop-specific data is returned
2. **Optimized Queries**: Database queries are filtered by shop_id from the start
3. **Efficient Pagination**: Server-side pagination reduces memory usage
4. **Smart Price Filtering**: Considers special offers in price calculations
5. **Indexed Searches**: Leverages database indexes for fast filtering

## API Response Format

All APIs return a consistent response format:

```json
{
  "success": true,
  "shop": {
    "shop_id": 1,
    "name": "Fashion Store",
    "slug": "fashion",
    "description": "Latest fashion trends",
    "is_active": true
  },
  "products": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 5,
    "total_items": 100,
    "has_next": true,
    "has_prev": false
  },
  "filters_applied": {
    "category_id": null,
    "brand_id": null,
    "search": "dress",
    "sort_by": "created_at",
    "order": "desc"
  }
}
```

## Error Handling

- **404**: Shop not found or not active
- **500**: Internal server error
- All errors include descriptive messages

## Scalability Features

- Shop-specific caching can be easily implemented
- Database indexes on shop_id for all related tables
- Consistent pagination across all endpoints
- Configurable limits to prevent abuse
- Extensible for additional shops without code changes

## Migration Guide

### For Frontend Teams:
1. Replace calls to `/api/shop/products` with `/api/public/shops/{shop_id}/products`
2. Update category and brand API calls to shop-specific endpoints
3. Use shop_id parameter based on current shop context
4. Implement pagination using the returned pagination object

### For Backend Teams:
1. Existing superadmin shop management APIs remain unchanged
2. All new APIs are read-only for public access
3. Authentication not required for public APIs
4. Monitoring and rate limiting can be applied per shop

## Security Considerations

- Only published and active products are returned
- Soft-deleted items are automatically excluded
- No sensitive data (cost prices, internal notes) in public APIs
- Shop activation status is verified for all requests
