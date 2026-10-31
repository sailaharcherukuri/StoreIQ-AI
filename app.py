from flask import Flask, render_template, redirect, url_for, session
from modules.auth import auth_bp
from modules.customers import customers_bp
from modules.returns import returns_bp
from modules.billing import billing_bp
from db import get_db_connection
from modules.stock_transfers import stock_transfers_bp
from modules.inventory_api import inventory_api_bp

app = Flask(__name__)

app.secret_key = "storeiq_ai_secret_key"

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(customers_bp)
app.register_blueprint(returns_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(stock_transfers_bp)
app.register_blueprint(inventory_api_bp, url_prefix="/api")

@app.route("/")
def home():
    return redirect(url_for("auth.login"))


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    connection = get_db_connection()

    stats = {
        "total_sales": 0,
        "total_customers": 0,
        "total_products": 0,
        "low_stock": 0
    }

    if connection:
        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)

            cursor.execute("""
                SELECT COALESCE(SUM(total_amount), 0) AS total_sales
                FROM sales
                WHERE status = 'completed'
            """)
            stats["total_sales"] = cursor.fetchone()["total_sales"]

            cursor.execute("SELECT COUNT(*) AS total FROM customers")
            stats["total_customers"] = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM products
                WHERE is_active = 1
            """)
            stats["total_products"] = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM inventory i
                JOIN products p ON p.product_id = i.product_id
                WHERE i.quantity_on_hand <= i.reorder_level
                  AND p.is_active = 1
            """)
            stats["low_stock"] = cursor.fetchone()["total"]

        except Exception as error:
            print("Dashboard statistics error:", error)

        finally:
            if cursor:
                cursor.close()
            connection.close()

    return render_template("dashboard.html", stats=stats)


@app.route("/health")
def health():
    return "StoreIQ-AI is running successfully!"

if __name__ == "__main__":
    app.run(debug=True)