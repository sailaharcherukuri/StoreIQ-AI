
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_db_connection
from decimal import Decimal
import uuid
import traceback

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


@billing_bp.route("/", methods=["GET", "POST"])
def billing_page():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    connection = get_db_connection()

    if not connection:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT store_id FROM users WHERE user_id = %s AND is_active = 1",
            (session["user_id"],)
        )
        user = cursor.fetchone()

        if not user or not user["store_id"]:
            raise ValueError("Your account does not have an active store assigned.")

        store_id = user["store_id"]

        if request.method == "POST":

            payment_method = request.form.get("payment_method", "cash")
            customer_id = request.form.get("customer_id") or None
            cart_data = request.form.get("cart", "")

            if payment_method not in ("cash", "card", "upi", "other"):
                raise ValueError("Invalid payment method.")

            quantities = {}

            for entry in cart_data.split(","):
                if not entry.strip():
                    continue

                parts = entry.split(":")
                if len(parts) != 2:
                    raise ValueError("Invalid cart information.")

                product_id = int(parts[0])
                quantity = int(parts[1])

                if product_id <= 0 or quantity <= 0:
                    raise ValueError("Invalid product or quantity.")

                quantities[product_id] = (
                    quantities.get(product_id, 0) + quantity
                )

            if not quantities:
                raise ValueError("Your cart is empty.")

            connection.start_transaction()

            if customer_id:
                customer_id = int(customer_id)
                cursor.execute(
                    "SELECT customer_id FROM customers WHERE customer_id = %s",
                    (customer_id,)
                )
                if not cursor.fetchone():
                    raise ValueError("Selected customer does not exist.")

            subtotal = Decimal("0.00")
            sale_details = []

            # Lock and validate products and inventory.
            for product_id, quantity in sorted(quantities.items()):

                cursor.execute("""
                    SELECT
                        p.product_id,
                        p.product_name,
                        p.selling_price,
                        i.quantity_on_hand
                    FROM products p
                    JOIN inventory i
                        ON i.product_id = p.product_id
                    WHERE p.product_id = %s
                      AND i.store_id = %s
                      AND p.is_active = 1
                    FOR UPDATE
                """, (product_id, store_id))

                product = cursor.fetchone()

                if not product:
                    raise ValueError(
                        f"Product ID {product_id} is unavailable."
                    )

                if product["quantity_on_hand"] < quantity:
                    raise ValueError(
                        f"Insufficient inventory for {product['product_name']}."
                    )

                # Lock available, unexpired batches in FIFO order.
                cursor.execute("""
                    SELECT batch_id, quantity_remaining
                    FROM batches
                    WHERE store_id = %s
                      AND product_id = %s
                      AND quantity_remaining > 0
                      AND (expiry_date IS NULL OR expiry_date >= CURDATE())
                    ORDER BY created_at ASC, batch_id ASC
                    FOR UPDATE
                """, (store_id, product_id))

                batches = cursor.fetchall()

                available_batch_stock = sum(
                    batch["quantity_remaining"] for batch in batches
                )

                if available_batch_stock < quantity:
                    raise ValueError(
                        f"Insufficient valid batch stock for "
                        f"{product['product_name']}."
                    )

                unit_price = Decimal(str(product["selling_price"]))
                line_total = unit_price * quantity

                subtotal += line_total

                sale_details.append({
                    "product_id": product_id,
                    "name": product["product_name"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": line_total,
                    "batches": batches
                })

            discount = Decimal("0.00")
            tax = Decimal("0.00")
            total_amount = subtotal - discount + tax

            invoice_no = "INV-" + uuid.uuid4().hex[:12].upper()

            # Create sale.
            cursor.execute("""
                INSERT INTO sales (
                    store_id, customer_id, cashier_id, invoice_no,
                    subtotal, discount, tax, total_amount,
                    payment_method, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed')
            """, (
                store_id,
                customer_id,
                session["user_id"],
                invoice_no,
                subtotal,
                discount,
                tax,
                total_amount,
                payment_method
            ))

            sale_id = cursor.lastrowid

            # Create sale items and allocate batches.
            for item in sale_details:

                cursor.execute("""
                    INSERT INTO sale_items (
                        sale_id, product_id, quantity,
                        unit_price, discount, total_price
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    sale_id,
                    item["product_id"],
                    item["quantity"],
                    item["unit_price"],
                    Decimal("0.00"),
                    item["total_price"]
                ))

                sale_item_id = cursor.lastrowid
                remaining = item["quantity"]

                for batch in item["batches"]:
                    if remaining <= 0:
                        break

                    allocated = min(
                        remaining,
                        batch["quantity_remaining"]
                    )

                    cursor.execute("""
                        UPDATE batches
                        SET quantity_remaining = quantity_remaining - %s
                        WHERE batch_id = %s
                          AND quantity_remaining >= %s
                    """, (
                        allocated,
                        batch["batch_id"],
                        allocated
                    ))

                    if cursor.rowcount != 1:
                        raise ValueError(
                            "Batch stock changed. Please retry checkout."
                        )

                    cursor.execute("""
                        INSERT INTO sale_item_batches (
                            sale_item_id, batch_id, quantity
                        )
                        VALUES (%s, %s, %s)
                    """, (
                        sale_item_id,
                        batch["batch_id"],
                        allocated
                    ))

                    remaining -= allocated

                if remaining != 0:
                    raise ValueError("Could not allocate all product batches.")

                # Update store inventory.
                cursor.execute("""
                    UPDATE inventory
                    SET quantity_on_hand = quantity_on_hand - %s
                    WHERE store_id = %s
                      AND product_id = %s
                      AND quantity_on_hand >= %s
                """, (
                    item["quantity"],
                    store_id,
                    item["product_id"],
                    item["quantity"]
                ))

                if cursor.rowcount != 1:
                    raise ValueError("Inventory update failed.")

            connection.commit()

            return render_template(
                "billing.html",
                products=[],
                customers=[],
                invoice={
                    "invoice_no": invoice_no,
                    "items": sale_details,
                    "subtotal": subtotal,
                    "total": total_amount,
                    "payment_method": payment_method
                }
            )

        # Display available products.
        cursor.execute("""
            SELECT
                p.product_id,
                p.product_name,
                p.sku,
                p.selling_price,
                i.quantity_on_hand
            FROM products p
            JOIN inventory i
                ON i.product_id = p.product_id
            WHERE i.store_id = %s
              AND p.is_active = 1
              AND i.quantity_on_hand > 0
            ORDER BY p.product_name
        """, (store_id,))

        products = cursor.fetchall()

        cursor.execute("""
            SELECT customer_id, customer_name
            FROM customers
            ORDER BY customer_name
        """)

        customers = cursor.fetchall()

        return render_template(
            "billing.html",
            products=products,
            customers=customers,
            invoice=None
        )

    except Exception as error:
        connection.rollback()
        traceback.print_exc()

        flash(str(error), "error")

    finally:
        if cursor:
            cursor.close()
        connection.close()

    return redirect(url_for("billing.billing_page"))
