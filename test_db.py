from db import get_connection

connection = get_connection()

if connection and connection.is_connected():
    print("SUCCESS: MySQL connected!")
    print("Database:", connection.database)
    connection.close()
else:
    print("FAILED: Could not connect to MySQL.")