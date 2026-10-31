from db import get_connection


def get_all_inventory(store_id=None):
    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:
        query = """
            SELECT
                i.inventory_id,
                i.store_id,
                s.store_name,
                p.product_id,
                p.product_name,
                p.sku,
                i.quantity_on_hand,
                i.reorder_level
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            JOIN stores s ON i.store_id = s.store_id
        """

        if store_id is not None:
            query += " WHERE i.store_id = %s"
            cursor.execute(query, (store_id,))
        else:
            cursor.execute(query)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_low_stock_items(store_id=None):
    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:
        query = """
            SELECT
                p.product_name,
                s.store_name,
                i.quantity_on_hand,
                i.reorder_level
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            JOIN stores s ON i.store_id = s.store_id
            WHERE i.quantity_on_hand <= i.reorder_level
        """

        if store_id is not None:
            query += " AND i.store_id = %s"
            cursor.execute(query, (store_id,))
        else:
            cursor.execute(query)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

def update_stock(inventory_id, new_quantity):
    connection = get_connection()

    if connection is None:
        return False

    cursor = connection.cursor()

    try:
        query = """
            UPDATE inventory
            SET quantity_on_hand = %s
            WHERE inventory_id = %s
        """

        cursor.execute(query, (new_quantity, inventory_id))
        connection.commit()

        return cursor.rowcount > 0

    finally:
        cursor.close()
        connection.close()   

def add_inventory(store_id, product_id, quantity, reorder_level):
    connection = get_connection()

    if connection is None:
        return False

    cursor = connection.cursor()

    try:
        query = """
            INSERT INTO inventory
            (store_id, product_id, quantity_on_hand, reorder_level)
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (store_id, product_id, quantity, reorder_level)
        )

        connection.commit()
        return True

    finally:
        cursor.close()
        connection.close()        