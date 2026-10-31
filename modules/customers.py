
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


def login_required():
    return "user_id" in session


@customers_bp.route("/")
def customer_list():
    if not login_required():
        return redirect(url_for("auth.login"))

    connection = get_db_connection()

    if not connection:
        flash("Database connection failed.", "error")
        return render_template("customers.html", customers=[], search="")

    try:
        cursor = connection.cursor(dictionary=True)
        search = request.args.get("search", "").strip()

        cursor.execute("""
            SELECT customer_id, customer_name, phone, email, created_at
            FROM customers
            WHERE customer_name LIKE %s
               OR phone LIKE %s
               OR email LIKE %s
            ORDER BY customer_id DESC
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))

        customers = cursor.fetchall()
        cursor.close()

        return render_template(
            "customers.html",
            customers=customers,
            search=search
        )

    except Exception as error:
        print("Customer list error:", error)
        flash("Unable to load customers.", "error")
        return render_template("customers.html", customers=[], search="")

    finally:
        connection.close()


@customers_bp.route("/add", methods=["POST"])
def add_customer():
    if not login_required():
        return redirect(url_for("auth.login"))

    customer_name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip() or None
    email = request.form.get("email", "").strip() or None

    if not customer_name:
        flash("Customer name is required.", "error")
        return redirect(url_for("customers.customer_list"))

    connection = get_db_connection()

    if not connection:
        flash("Database connection failed.", "error")
        return redirect(url_for("customers.customer_list"))

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO customers (customer_name, phone, email)
            VALUES (%s, %s, %s)
        """, (customer_name, phone, email))

        connection.commit()
        flash("Customer added successfully!", "success")

    except Exception as error:
        connection.rollback()
        print("Add customer error:", error)
        flash("Unable to add customer. Phone may already exist.", "error")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("customers.customer_list"))


@customers_bp.route("/update/<int:customer_id>", methods=["POST"])
def update_customer(customer_id):
    if not login_required():
        return redirect(url_for("auth.login"))

    customer_name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip() or None
    email = request.form.get("email", "").strip() or None

    if not customer_name:
        flash("Customer name is required.", "error")
        return redirect(url_for("customers.customer_list"))

    connection = get_db_connection()

    if not connection:
        flash("Database connection failed.", "error")
        return redirect(url_for("customers.customer_list"))

    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE customers
            SET customer_name = %s, phone = %s, email = %s
            WHERE customer_id = %s
        """, (customer_name, phone, email, customer_id))

        connection.commit()

        if cursor.rowcount:
            flash("Customer updated successfully!", "success")
        else:
            flash("Customer not found or no changes made.", "error")

    except Exception as error:
        connection.rollback()
        print("Update customer error:", error)
        flash("Unable to update customer.", "error")

    finally:
        if cursor:
            cursor.close()
        connection.close()

    return redirect(url_for("customers.customer_list"))


@customers_bp.route("/delete/<int:customer_id>", methods=["POST"])
def delete_customer(customer_id):
    if not login_required():
        return redirect(url_for("auth.login"))

    connection = get_db_connection()

    if not connection:
        flash("Database connection failed.", "error")
        return redirect(url_for("customers.customer_list"))

    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM customers
            WHERE customer_id = %s
        """, (customer_id,))

        connection.commit()

        if cursor.rowcount:
            flash("Customer deleted successfully!", "success")
        else:
            flash("Customer not found.", "error")

    except Exception as error:
        connection.rollback()
        print("Delete customer error:", error)
        flash("Unable to delete customer. This customer may have sales records.", "error")

    finally:
        if cursor:
            cursor.close()
        connection.close()

    return redirect(url_for("customers.customer_list"))
