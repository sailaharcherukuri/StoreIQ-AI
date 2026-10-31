from db import get_connection


def get_all_batches(store_id=None):
    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:
        query = """
            SELECT
                b.batch_id,
                b.store_id,
                s.store_name,
                b.product_id,
                p.product_name,
                b.batch_code,
                b.quantity_received,
                b.quantity_remaining,
                b.manufacturing_date,
                b.expiry_date
            FROM batches b
            JOIN stores s ON b.store_id = s.store_id
            JOIN products p ON b.product_id = p.product_id
        """

        if store_id is not None:
            query += " WHERE b.store_id = %s"
            cursor.execute(query, (store_id,))
        else:
            cursor.execute(query)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_expiring_batches(days=30, store_id=None):
    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:
        query = """
            SELECT
                b.batch_id,
                p.product_name,
                s.store_name,
                b.batch_code,
                b.quantity_remaining,
                b.expiry_date
            FROM batches b
            JOIN products p ON b.product_id = p.product_id
            JOIN stores s ON b.store_id = s.store_id
            WHERE b.expiry_date IS NOT NULL
              AND b.expiry_date BETWEEN CURDATE()
              AND DATE_ADD(CURDATE(), INTERVAL %s DAY)
              AND b.quantity_remaining > 0
        """

        if store_id is not None:
            query += " AND b.store_id = %s"
            cursor.execute(query, (days, store_id))
        else:
            cursor.execute(query, (days,))

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()
def add_batch(
    store_id,
    product_id,
    batch_code,
    quantity_received,
    manufacturing_date,
    expiry_date
):
    connection = get_connection()

    if connection is None:
        return False

    cursor = connection.cursor()

    try:
        query = """
            INSERT INTO batches (
                store_id,
                product_id,
                batch_code,
                quantity_received,
                quantity_remaining,
                manufacturing_date,
                expiry_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                store_id,
                product_id,
                batch_code,
                quantity_received,
                quantity_received,
                manufacturing_date,
                expiry_date
            )
        )

        connection.commit()
        return True

    finally:
        cursor.close()
        connection.close()     
def deduct_stock_fefo(store_id, product_id, quantity):
    connection = get_connection()

    if connection is None:
        return {
            "success": False,
            "message": "Database connection failed"
        }

    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute("""
            SELECT batch_id, quantity_remaining
            FROM batches
            WHERE store_id = %s
              AND product_id = %s
              AND quantity_remaining > 0
              AND expiry_date >= CURDATE()
            ORDER BY expiry_date ASC, batch_id ASC
            FOR UPDATE
        """, (store_id, product_id))

        batches = cursor.fetchall()

        total_available = sum(
            batch["quantity_remaining"] for batch in batches
        )

        if total_available < quantity:
            connection.rollback()
            return {
                "success": False,
                "message": "Insufficient unexpired batch stock"
            }

        remaining_to_deduct = quantity
        deductions = []

        for batch in batches:
            if remaining_to_deduct == 0:
                break

            available = batch["quantity_remaining"]
            deducted = min(available, remaining_to_deduct)

            cursor.execute("""
                UPDATE batches
                SET quantity_remaining = quantity_remaining - %s
                WHERE batch_id = %s
            """, (deducted, batch["batch_id"]))

            deductions.append({
                "batch_id": batch["batch_id"],
                "quantity_deducted": deducted
            })

            remaining_to_deduct -= deducted

        cursor.execute("""
            UPDATE inventory
            SET quantity_on_hand = quantity_on_hand - %s
            WHERE store_id = %s AND product_id = %s
        """, (quantity, store_id, product_id))

        if cursor.rowcount != 1:
            connection.rollback()
            return {
                "success": False,
                "message": "Inventory record not found"
            }

        connection.commit()

        return {
            "success": True,
            "message": "Stock deducted using FEFO successfully",
            "deductions": deductions
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()