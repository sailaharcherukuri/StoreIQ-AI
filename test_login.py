
from db import get_db_connection
from werkzeug.security import check_password_hash

connection = get_db_connection()

if connection:
    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT u.user_id, u.email, u.password_hash,
                   u.is_active, r.role_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE u.email = %s
        """, ("admin@storeiq.com",))

        user = cursor.fetchone()

        if user:
            print("User found:", user["email"])
            print("Role:", user["role_name"])
            print("Active:", user["is_active"])
            print("Hash exists:", bool(user["password_hash"]))
            print("Password matches:",
                  check_password_hash(user["password_hash"], "Admin@123"))
        else:
            print("Admin user not found!")

        cursor.close()

    except Exception as error:
        import traceback
        traceback.print_exc()

    finally:
        connection.close()
else:
    print("Database connection failed!")
