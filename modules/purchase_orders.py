
from db import get_connection


def create_purchase_order(
    store_id,
    supplier_id,
    created_by,
    items,
    expected_delivery_date=None,
    notes=None
):
    connection = get_connection()

    if connection is None:
        return False

    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO purchase_orders (
                store_id,
                supplier_id,
                created_by,
                expected_delivery_date,
                notes
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            store_id,
            supplier_id,
            created_by,
            expected_delivery_date,
            notes
        ))

        purchase_order_id = cursor.lastrowid

        for item in items:
            cursor.execute("""
                INSERT INTO purchase_order_items (
                    purchase_order_id,
                    product_id,
                    ordered_qty,
                    unit_cost
                )
                VALUES (%s, %s, %s, %s)
            """, (
                purchase_order_id,
                item["product_id"],
                item["ordered_qty"],
                item["unit_cost"]
            ))

        connection.commit()
        return purchase_order_id

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def get_all_purchase_orders():
    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                po.purchase_order_id,
                po.store_id,
                s.store_name,
                po.supplier_id,
                sp.supplier_name,
                po.created_by,
                po.order_date,
                po.expected_delivery_date,
                po.status,
                po.notes
            FROM purchase_orders po
            JOIN stores s
                ON po.store_id = s.store_id
            JOIN suppliers sp
                ON po.supplier_id = sp.supplier_id
            ORDER BY po.purchase_order_id DESC
        """)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()
