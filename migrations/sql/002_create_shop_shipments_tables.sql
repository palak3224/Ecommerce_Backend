-- Migration: Create shop shipments tables
-- Date: 2024-01-01
-- Description: Creates shop_shipments and shop_shipment_items tables for shop order shipping

-- Create shop_shipments table
CREATE TABLE shop_shipments (
    shipment_id INT AUTO_INCREMENT PRIMARY KEY,
    shop_order_id VARCHAR(50) NOT NULL,
    shop_id INT NOT NULL,
    carrier_name VARCHAR(100) NULL,
    tracking_number VARCHAR(100) NULL,
    shipped_date DATETIME NULL,
    estimated_delivery_date DATE NULL,
    actual_delivery_date DATETIME NULL,
    shipment_status ENUM('PENDING_PICKUP', 'PICKUP_GENERATED', 'IN_TRANSIT', 'DELIVERED', 'FAILED', 'CANCELLED') NOT NULL DEFAULT 'PENDING_PICKUP',
    shiprocket_order_id INT NULL,
    shiprocket_shipment_id INT NULL,
    awb_code VARCHAR(50) NULL,
    courier_id INT NULL,
    pickup_generated BOOLEAN NOT NULL DEFAULT FALSE,
    pickup_generated_at DATETIME NULL,
    pickup_address_id INT NULL,
    delivery_address_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_shop_shipments_shop_order_id (shop_order_id),
    INDEX idx_shop_shipments_shop_id (shop_id),
    INDEX idx_shop_shipments_tracking_number (tracking_number),
    INDEX idx_shop_shipments_shiprocket_order_id (shiprocket_order_id),
    INDEX idx_shop_shipments_awb_code (awb_code),
    INDEX idx_shop_shipments_courier_id (courier_id),
    INDEX idx_shop_shipments_pickup_address_id (pickup_address_id),
    INDEX idx_shop_shipments_delivery_address_id (delivery_address_id),
    
    FOREIGN KEY (shop_order_id) REFERENCES shop_orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (shop_id) REFERENCES shops(shop_id) ON DELETE CASCADE,
    FOREIGN KEY (pickup_address_id) REFERENCES user_addresses(address_id) ON DELETE SET NULL,
    FOREIGN KEY (delivery_address_id) REFERENCES user_addresses(address_id) ON DELETE SET NULL
);

-- Create shop_shipment_items table
CREATE TABLE shop_shipment_items (
    shipment_item_id INT AUTO_INCREMENT PRIMARY KEY,
    shipment_id INT NOT NULL,
    shop_order_item_id INT NOT NULL,
    quantity_shipped INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_shop_shipment_items_shipment_id (shipment_id),
    INDEX idx_shop_shipment_items_shop_order_item_id (shop_order_item_id),
    
    FOREIGN KEY (shipment_id) REFERENCES shop_shipments(shipment_id) ON DELETE CASCADE,
    FOREIGN KEY (shop_order_item_id) REFERENCES shop_order_items(order_item_id) ON DELETE CASCADE,
    
    UNIQUE KEY uq_shop_shipment_order_item_inclusion (shipment_id, shop_order_item_id)
);

-- Add comments to document the new tables
COMMENT ON TABLE shop_shipments IS 'Shipment records for shop orders';
COMMENT ON TABLE shop_shipment_items IS 'Individual items within shop shipments';
