-- StoreIQ AI - Shared MySQL schema
-- Requires MySQL 8.0.16+ (enforced CHECK constraints).
-- Run this file on BOTH developers' laptops to create the same database.
-- Application code must update inventory and batches in one SQL transaction.

CREATE DATABASE IF NOT EXISTS storeiq_ai
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE storeiq_ai;

-- Run this schema once on a new/empty database. It intentionally does not drop existing tables or data.

CREATE TABLE stores (
    store_id INT AUTO_INCREMENT PRIMARY KEY,
    store_name VARCHAR(120) NOT NULL,
    address VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE roles (
    role_id INT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(40) NOT NULL UNIQUE,
    description VARCHAR(255)
) ENGINE=InnoDB;

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    role_id INT NOT NULL,
    store_id INT NULL,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_role FOREIGN KEY (role_id)
        REFERENCES roles(role_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_users_store FOREIGN KEY (store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255)
) ENGINE=InnoDB;

CREATE TABLE products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    product_name VARCHAR(150) NOT NULL,
    sku VARCHAR(64) NOT NULL UNIQUE,
    barcode VARCHAR(64) NULL UNIQUE,
    unit VARCHAR(30) NOT NULL DEFAULT 'piece',
    cost_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    selling_price DECIMAL(10,2) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_products_cost CHECK (cost_price >= 0),
    CONSTRAINT chk_products_selling CHECK (selling_price >= 0),
    CONSTRAINT fk_products_category FOREIGN KEY (category_id)
        REFERENCES categories(category_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE inventory (
    inventory_id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity_on_hand INT NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_inventory_store_product UNIQUE (store_id, product_id),
    CONSTRAINT chk_inventory_qty CHECK (quantity_on_hand >= 0),
    CONSTRAINT chk_inventory_reorder CHECK (reorder_level >= 0),
    CONSTRAINT fk_inventory_store FOREIGN KEY (store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_inventory_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE suppliers (
    supplier_id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_name VARCHAR(150) NOT NULL,
    contact_person VARCHAR(120),
    phone VARCHAR(20),
    email VARCHAR(150),
    address VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE purchase_orders (
    purchase_order_id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    supplier_id INT NOT NULL,
    created_by INT NOT NULL,
    order_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expected_delivery_date DATE NULL,
    status ENUM('draft','placed','partially_received','received','cancelled')
        NOT NULL DEFAULT 'draft',
    notes VARCHAR(500),
    CONSTRAINT fk_po_store FOREIGN KEY (store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_po_supplier FOREIGN KEY (supplier_id)
        REFERENCES suppliers(supplier_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_po_user FOREIGN KEY (created_by)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE purchase_order_items (
    po_item_id INT AUTO_INCREMENT PRIMARY KEY,
    purchase_order_id INT NOT NULL,
    product_id INT NOT NULL,
    ordered_qty INT NOT NULL,
    unit_cost DECIMAL(10,2) NOT NULL,
    CONSTRAINT chk_po_item_qty CHECK (ordered_qty > 0),
    CONSTRAINT chk_po_item_cost CHECK (unit_cost >= 0),
    CONSTRAINT uq_po_product UNIQUE (purchase_order_id, product_id),
    CONSTRAINT fk_poi_order FOREIGN KEY (purchase_order_id)
        REFERENCES purchase_orders(purchase_order_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_poi_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE purchase_receipts (
    receipt_id INT AUTO_INCREMENT PRIMARY KEY,
    purchase_order_id INT NOT NULL,
    received_by INT NOT NULL,
    received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('received','partially_received','rejected') NOT NULL DEFAULT 'received',
    notes VARCHAR(500),
    CONSTRAINT fk_receipt_order FOREIGN KEY (purchase_order_id)
        REFERENCES purchase_orders(purchase_order_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_receipt_user FOREIGN KEY (received_by)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE purchase_receipt_items (
    receipt_item_id INT AUTO_INCREMENT PRIMARY KEY,
    receipt_id INT NOT NULL,
    po_item_id INT NOT NULL,
    product_id INT NOT NULL,
    received_qty INT NOT NULL,
    unit_cost DECIMAL(10,2) NOT NULL,
    CONSTRAINT chk_receipt_item_qty CHECK (received_qty > 0),
    CONSTRAINT chk_receipt_item_cost CHECK (unit_cost >= 0),
    CONSTRAINT fk_receipt_item_receipt FOREIGN KEY (receipt_id)
        REFERENCES purchase_receipts(receipt_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_receipt_item_po_item FOREIGN KEY (po_item_id)
        REFERENCES purchase_order_items(po_item_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_receipt_item_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE batches (
    batch_id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    product_id INT NOT NULL,
    receipt_item_id INT NULL,
    batch_code VARCHAR(80) NOT NULL,
    quantity_received INT NOT NULL,
    quantity_remaining INT NOT NULL,
    manufacturing_date DATE NULL,
    expiry_date DATE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_batch_store_code UNIQUE (store_id, batch_code),
    CONSTRAINT chk_batch_received CHECK (quantity_received > 0),
    CONSTRAINT chk_batch_remaining CHECK (
        quantity_remaining >= 0 AND quantity_remaining <= quantity_received
    ),
    CONSTRAINT chk_batch_dates CHECK (
        manufacturing_date IS NULL OR expiry_date IS NULL
        OR expiry_date >= manufacturing_date
    ),
    CONSTRAINT fk_batch_store FOREIGN KEY (store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_batch_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_batch_receipt_item FOREIGN KEY (receipt_item_id)
        REFERENCES purchase_receipt_items(receipt_item_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE stock_alerts (
    alert_id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    product_id INT NOT NULL,
    batch_id INT NULL,
    alert_type ENUM('low_stock','near_expiry','expired','out_of_stock') NOT NULL,
    message VARCHAR(500) NOT NULL,
    status ENUM('open','acknowledged','resolved') NOT NULL DEFAULT 'open',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME NULL,
    CONSTRAINT fk_alert_store FOREIGN KEY (store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_alert_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_alert_batch FOREIGN KEY (batch_id)
        REFERENCES batches(batch_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE demand_forecasts (
    forecast_id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    product_id INT NOT NULL,
    forecast_date DATE NOT NULL,
    predicted_qty DECIMAL(10,2) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_forecast_qty CHECK (predicted_qty >= 0),
    CONSTRAINT fk_forecast_store FOREIGN KEY (store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_forecast_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(120) NOT NULL,
    phone VARCHAR(20) NULL UNIQUE,
    email VARCHAR(150) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE sales (
    sale_id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    customer_id INT NULL,
    cashier_id INT NOT NULL,
    invoice_no VARCHAR(64) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    discount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    tax DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    total_amount DECIMAL(10,2) NOT NULL,
    payment_method ENUM('cash','card','upi','other') NOT NULL DEFAULT 'cash',
    status ENUM('completed','partially_returned','returned','cancelled') NOT NULL DEFAULT 'completed',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_sales_store_invoice UNIQUE (store_id, invoice_no),
    CONSTRAINT chk_sales_amounts CHECK (
        subtotal >= 0 AND discount >= 0 AND tax >= 0 AND total_amount >= 0
    ),
    CONSTRAINT fk_sales_store FOREIGN KEY (store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_sales_customer FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_sales_cashier FOREIGN KEY (cashier_id)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE sale_items (
    sale_item_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    discount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    total_price DECIMAL(10,2) NOT NULL,
    CONSTRAINT chk_sale_item_qty CHECK (quantity > 0),
    CONSTRAINT chk_sale_item_amounts CHECK (
        unit_price >= 0 AND discount >= 0 AND total_price >= 0
    ),
    CONSTRAINT fk_sale_item_sale FOREIGN KEY (sale_id)
        REFERENCES sales(sale_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_sale_item_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE sale_item_batches (
    sale_item_batch_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_item_id INT NOT NULL,
    batch_id INT NOT NULL,
    quantity INT NOT NULL,
    CONSTRAINT uq_sale_item_batch UNIQUE (sale_item_id, batch_id),
    CONSTRAINT chk_sale_batch_qty CHECK (quantity > 0),
    CONSTRAINT fk_sib_sale_item FOREIGN KEY (sale_item_id)
        REFERENCES sale_items(sale_item_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_sib_batch FOREIGN KEY (batch_id)
        REFERENCES batches(batch_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE returns (
    return_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT NOT NULL,
    processed_by INT NOT NULL,
    return_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason VARCHAR(500),
    total_refund DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    status ENUM('completed','pending','rejected') NOT NULL DEFAULT 'completed',
    CONSTRAINT chk_return_refund CHECK (total_refund >= 0),
    CONSTRAINT fk_returns_sale FOREIGN KEY (sale_id)
        REFERENCES sales(sale_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_returns_user FOREIGN KEY (processed_by)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE return_items (
    return_item_id INT AUTO_INCREMENT PRIMARY KEY,
    return_id INT NOT NULL,
    sale_item_id INT NOT NULL,
    quantity INT NOT NULL,
    refund_amount DECIMAL(10,2) NOT NULL,
    CONSTRAINT chk_return_item_qty CHECK (quantity > 0),
    CONSTRAINT chk_return_item_refund CHECK (refund_amount >= 0),
    CONSTRAINT uq_return_sale_item UNIQUE (return_id, sale_item_id),
    CONSTRAINT fk_return_item_return FOREIGN KEY (return_id)
        REFERENCES returns(return_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_return_item_sale_item FOREIGN KEY (sale_item_id)
        REFERENCES sale_items(sale_item_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE return_item_batches (
    return_item_batch_id INT AUTO_INCREMENT PRIMARY KEY,
    return_item_id INT NOT NULL,
    batch_id INT NOT NULL,
    quantity INT NOT NULL,
    CONSTRAINT uq_return_item_batch UNIQUE (return_item_id, batch_id),
    CONSTRAINT chk_return_batch_qty CHECK (quantity > 0),
    CONSTRAINT fk_rib_return_item FOREIGN KEY (return_item_id)
        REFERENCES return_items(return_item_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_rib_batch FOREIGN KEY (batch_id)
        REFERENCES batches(batch_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE stock_transfers (
    transfer_id INT AUTO_INCREMENT PRIMARY KEY,
    from_store_id INT NOT NULL,
    to_store_id INT NOT NULL,
    initiated_by INT NOT NULL,
    status ENUM('requested','approved','dispatched','received','cancelled') NOT NULL DEFAULT 'requested',
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dispatched_at DATETIME NULL,
    received_at DATETIME NULL,
    notes VARCHAR(500),
    CONSTRAINT chk_transfer_different_stores CHECK (from_store_id <> to_store_id),
    CONSTRAINT fk_transfer_from_store FOREIGN KEY (from_store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_transfer_to_store FOREIGN KEY (to_store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_transfer_user FOREIGN KEY (initiated_by)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE stock_transfer_items (
    transfer_item_id INT AUTO_INCREMENT PRIMARY KEY,
    transfer_id INT NOT NULL,
    product_id INT NOT NULL,
    requested_qty INT NOT NULL,
    dispatched_qty INT NOT NULL DEFAULT 0,
    received_qty INT NOT NULL DEFAULT 0,
    CONSTRAINT uq_transfer_product UNIQUE (transfer_id, product_id),
    CONSTRAINT chk_transfer_item_qty CHECK (
        requested_qty > 0 AND dispatched_qty >= 0
        AND received_qty >= 0 AND received_qty <= dispatched_qty
        AND dispatched_qty <= requested_qty
    ),
    CONSTRAINT fk_transfer_item_transfer FOREIGN KEY (transfer_id)
        REFERENCES stock_transfers(transfer_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_transfer_item_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE product_recommendations (
    recommendation_id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    product_id INT NOT NULL,
    recommended_product_id INT NOT NULL,
    score DECIMAL(8,4) NOT NULL DEFAULT 0.0000,
    reason VARCHAR(500),
    generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_recommendation_score CHECK (score >= 0),
    CONSTRAINT chk_recommendation_not_same CHECK (product_id <> recommended_product_id),
    CONSTRAINT fk_recommendation_store FOREIGN KEY (store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_recommendation_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_recommendation_recommended_product FOREIGN KEY (recommended_product_id)
        REFERENCES products(product_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE weekly_reports (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    store_id INT NOT NULL,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    generated_by INT NULL,
    report_content LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_report_dates CHECK (week_end >= week_start),
    CONSTRAINT fk_weekly_report_store FOREIGN KEY (store_id)
        REFERENCES stores(store_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_weekly_report_user FOREIGN KEY (generated_by)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Trigger-level safeguards:
-- 1) A return item must belong to the same sale as its return header.
-- 2) Total returned quantity across all return records cannot exceed sold quantity.
-- 3) A returned batch must have been allocated to that sale item, and cumulative
--    returned quantity from that batch cannot exceed the quantity sold from it.
DELIMITER $$

CREATE TRIGGER trg_return_items_before_insert
BEFORE INSERT ON return_items
FOR EACH ROW
BEGIN
    DECLARE v_return_sale_id INT;
    DECLARE v_item_sale_id INT;
    DECLARE v_sold_qty INT;
    DECLARE v_already_returned INT;

    SELECT sale_id INTO v_return_sale_id
      FROM returns WHERE return_id = NEW.return_id;
    SELECT sale_id, quantity INTO v_item_sale_id, v_sold_qty
      FROM sale_items WHERE sale_item_id = NEW.sale_item_id;

    IF v_return_sale_id <> v_item_sale_id THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'Return item must belong to the sale in its return header';
    END IF;

    SELECT COALESCE(SUM(ri.quantity), 0) INTO v_already_returned
      FROM return_items ri
      JOIN returns r ON r.return_id = ri.return_id
     WHERE ri.sale_item_id = NEW.sale_item_id
       AND r.status <> 'rejected';

    IF v_already_returned + NEW.quantity > v_sold_qty THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'Returned quantity cannot exceed sold quantity';
    END IF;
END$$

CREATE TRIGGER trg_return_items_before_update
BEFORE UPDATE ON return_items
FOR EACH ROW
BEGIN
    DECLARE v_return_sale_id INT;
    DECLARE v_item_sale_id INT;
    DECLARE v_sold_qty INT;
    DECLARE v_already_returned INT;

    SELECT sale_id INTO v_return_sale_id
      FROM returns WHERE return_id = NEW.return_id;
    SELECT sale_id, quantity INTO v_item_sale_id, v_sold_qty
      FROM sale_items WHERE sale_item_id = NEW.sale_item_id;

    IF v_return_sale_id <> v_item_sale_id THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'Return item must belong to the sale in its return header';
    END IF;

    SELECT COALESCE(SUM(ri.quantity), 0) INTO v_already_returned
      FROM return_items ri
      JOIN returns r ON r.return_id = ri.return_id
     WHERE ri.sale_item_id = NEW.sale_item_id
       AND r.status <> 'rejected'
       AND ri.return_item_id <> OLD.return_item_id;

    IF v_already_returned + NEW.quantity > v_sold_qty THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'Returned quantity cannot exceed sold quantity';
    END IF;
END$$

CREATE TRIGGER trg_return_item_batches_before_insert
BEFORE INSERT ON return_item_batches
FOR EACH ROW
BEGIN
    DECLARE v_sale_item_id INT;
    DECLARE v_allocated_qty INT;
    DECLARE v_already_returned_from_batch INT;
    DECLARE v_return_item_qty INT;
    DECLARE v_already_allocated_for_return INT;

    SELECT sale_item_id, quantity
      INTO v_sale_item_id, v_return_item_qty
      FROM return_items WHERE return_item_id = NEW.return_item_id;

    SELECT COALESCE(SUM(sib.quantity), 0)
      INTO v_allocated_qty
      FROM sale_item_batches sib
     WHERE sib.sale_item_id = v_sale_item_id
       AND sib.batch_id = NEW.batch_id;

    IF v_allocated_qty = 0 THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'Returned batch was not allocated to this sale item';
    END IF;

    SELECT COALESCE(SUM(rib.quantity), 0)
      INTO v_already_returned_from_batch
      FROM return_item_batches rib
      JOIN return_items ri ON ri.return_item_id = rib.return_item_id
      JOIN returns r ON r.return_id = ri.return_id
     WHERE ri.sale_item_id = v_sale_item_id
       AND rib.batch_id = NEW.batch_id
       AND r.status <> 'rejected';

    IF v_already_returned_from_batch + NEW.quantity > v_allocated_qty THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'Returned quantity from batch cannot exceed quantity sold from that batch';
    END IF;

    SELECT COALESCE(SUM(rib.quantity), 0)
      INTO v_already_allocated_for_return
      FROM return_item_batches rib
     WHERE rib.return_item_id = NEW.return_item_id;

    IF v_already_allocated_for_return + NEW.quantity > v_return_item_qty THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'Batch quantities cannot exceed the return item quantity';
    END IF;
END$$

DELIMITER ;
