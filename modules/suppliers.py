from db import get_connection


def get_all_suppliers():
    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                supplier_id,
                supplier_name,
                contact_person,
                phone,
                email,
                address,
                is_active
            FROM suppliers
            ORDER BY supplier_id
        """)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def add_supplier(
    supplier_name,
    contact_person,
    phone,
    email,
    address
):
    connection = get_connection()

    if connection is None:
        return False

    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO suppliers (
                supplier_name,
                contact_person,
                phone,
                email,
                address
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            supplier_name,
            contact_person,
            phone,
            email,
            address
        ))

        connection.commit()
        return True

    finally:
        cursor.close()
        connection.close()