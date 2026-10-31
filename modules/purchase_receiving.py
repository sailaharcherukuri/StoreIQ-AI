
from db import get_connection


def receive_purchase_order(purchase_order_id, received_by, items, notes=None):
    connection = get_connection()

    if connection is None:
        return False

    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute("""
            SELECT store_id, status
            FROM purchase_orders
            WHERE purchase_order_id = %s
            FOR UPDATE
        """, (purchase_order_id,))

        order = cursor.fetchone()

        if not order or order["status"] in ("draft", "received"):
            raise ValueError("Purchase order not found or cannot be received")

        store_id = order["store_id"]

        cursor.execute("""
            INSERT INTO purchase_receipts
            (purchase_order_id, received_by, status, notes)
            VALUES (%s, %s, 'received', %s)
        """, (purchase_order_id, received_by, notes))

        receipt_id = cursor.lastrowid

        for item in items:
            po_item_id = item["po_item_id"]
            product_id = item["product_id"]
            received_qty = int(item["received_qty"])
            unit_cost = item["unit_cost"]

            if received_qty <= 0:
                raise ValueError("Received quantity must be positive")

            cursor.execute("""
                SELECT ordered_qty, product_id
                FROM purchase_order_items
                WHERE po_item_id = %s
                  AND purchase_order_id = %s
                FOR UPDATE
            """, (po_item_id, purchase_order_id))

            po_item = cursor.fetchone()

            if not po_item or po_item["product_id"] != product_id:
                raise ValueError("Invalid purchase order item")

            cursor.execute("""
                SELECT COALESCE(SUM(pri.received_qty), 0) AS received_total
                FROM purchase_receipt_items pri
                JOIN purchase_receipts pr
                    ON pri.receipt_id = pr.receipt_id
                WHERE pri.po_item_id = %s
                  AND pr.status != 'rejected'
            """, (po_item_id,))

            previous_received = cursor.fetchone()["received_total"]

            remaining = po_item["ordered_qty"] - previous_received

            if received_qty > remaining:
                raise ValueError(
                    f"Received quantity exceeds remaining order quantity for product {product_id}"
                )

            cursor.execute("""
                INSERT INTO purchase_receipt_items
                (receipt_id, po_item_id, product_id, received_qty, unit_cost)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                receipt_id,
                po_item_id,
                product_id,
                received_qty,
                unit_cost
            ))

            receipt_item_id = cursor.lastrowid

            cursor.execute("""
                UPDATE inventory
                SET quantity_on_hand = quantity_on_hand + %s
                WHERE store_id = %s AND product_id = %s
            """, (received_qty, store_id, product_id))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO inventory
                    (store_id, product_id, quantity_on_hand, reorder_level)
                    VALUES (%s, %s, %s, 10)
                """, (store_id, product_id, received_qty))

            cursor.execute("""
                INSERT INTO batches (
                    store_id,
                    product_id,
                    receipt_item_id,
                    batch_code,
                    quantity_received,
                    quantity_remaining,
                    manufacturing_date,
                    expiry_date
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                store_id,
                product_id,
                receipt_item_id,
                item["batch_code"],
                received_qty,
                received_qty,
                item["manufacturing_date"],
                item["expiry_date"]
            ))

        cursor.execute("""
            SELECT
                poi.po_item_id,
                poi.ordered_qty,
                COALESCE(SUM(
                    CASE
                        WHEN pr.status != 'rejected' THEN pri.received_qty
                        ELSE 0
                    END
                ), 0) AS received_qty
            FROM purchase_order_items poi
            LEFT JOIN purchase_receipt_items pri
                ON poi.po_item_id = pri.po_item_id
            LEFT JOIN purchase_receipts pr
                ON pri.receipt_id = pr.receipt_id
            WHERE poi.purchase_order_id = %s
            GROUP BY poi.po_item_id, poi.ordered_qty
        """, (purchase_order_id,))

        order_items = cursor.fetchall()

        all_received = all(
            row["received_qty"] >= row["ordered_qty"]
            for row in order_items
        )

        new_status = "received" if all_received else "partially_received"
        receipt_status = new_status

        cursor.execute("""
            UPDATE purchase_orders
            SET status = %s
            WHERE purchase_order_id = %s
        """, (new_status, purchase_order_id))

        cursor.execute("""
            UPDATE purchase_receipts
            SET status = %s
            WHERE receipt_id = %s
        """, (receipt_status, receipt_id))

        connection.commit()

        return receipt_id

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
