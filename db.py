
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        return connection

    except mysql.connector.Error as error:
        print("Database connection error:", error)
        return None


if __name__ == "__main__":
    connection = get_db_connection()

    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        result = cursor.fetchone()

        print("MySQL Connected Successfully!")
        print("Database:", result[0])

        cursor.close()
        connection.close()
    else:
        print("MySQL Connection Failed!")
