
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_db_connection
from datetime import date
import traceback

stock_transfers_bp = Blueprint(
    "stock_transfers",
    __name__,
    url_prefix="/stock-transfers"
)


def get_current_store(cursor):
    cursor.execute(
        """
        SELECT store_id
        FROM users
        WHERE user_id = %s AND is_active = 1
        """,
        (session["user_id"],)
    )
    user = cursor.fetchone()

    if not user or not user["store_id"]:
        raise ValueError("Your account does not have an active store assigned.")

    return user["store_id"]


@stock_transfers_bp.route("/", methods=["GET", "POST"])
def transfer_list():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    if not connection:
        flash("Database connection failed.", "error")
        return redirect(url_for("dashboard"))

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)
        current_store = get_current_store(cursor)

        if request.method == "POST":
            destination_store = int(request.form.get("to_store_id", 0))
            notes = request.form.get("notes", "").strip() or None

            product_ids = request.form.getlist("product_id[]")
            quantities = request.form.getlist("quantity[]")

            if destination_store == current_store:
                raise ValueError("Source and destination stores must be different.")

            cursor.execute(
                "SELECT store_id FROM stores WHERE store_id = %s AND is_active = 1",
                (destination_store,)
            )
            if not cursor.fetchone():
                raise ValueError("Select a valid destination store.")

            requested_items = {}

            for product_id, quantity in zip(product_ids, quantities):
                if not product_id or not quantity:
                    continue

                product_id = int(product_id)
                quantity = int(quantity)

                if product_id <= 0 or quantity <= 0:
                    raise ValueError("Select valid products and quantities.")

                requested_items[product_id] = (
                    requested_items.get(product_id, 0) + quantity
                )

            if not requested_items:
                raise ValueError("Add at least one product to the transfer.")

            connection.start_transaction()

            cursor.execute(
                """
                INSERT INTO stock_transfers
                    (from_store_id, to_store_id, initiated_by, status, notes)
                VALUES (%s, %s, %s, 'requested', %s)
                """,
                (current_store, destination_store, session["user_id"], notes)
            )

            transfer_id = cursor.lastrowid

            for product_id, quantity in requested_items.items():
                cursor.execute(
                    """
                    SELECT product_id
                    FROM products
                    WHERE product_id = %s AND is_active = 1
                    """,
                    (product_id,)
                )

                if not cursor.fetchone():
                    raise ValueError("One of the selected products is unavailable.")

                cursor.execute(
                    """
                    INSERT INTO stock_transfer_items
                        (transfer_id, product_id, requested_qty)
                    VALUES (%s, %s, %s)
                    """,
                    (transfer_id, product_id, quantity)
                )

            connection.commit()
            flash(f"Transfer request #{transfer_id} created successfully.", "success")
            return redirect(url_for("stock_transfers.transfer_list"))

        cursor.execute(
            """
            SELECT t.transfer_id, t.status, t.requested_at,
                   t.dispatched_at, t.received_at, t.notes,
                   source.store_name AS from_store,
                   destination.store_name AS to_store,
                   u.full_name AS initiated_by,
                   COUNT(ti.transfer_item_id) AS item_count
            FROM stock_transfers t
            JOIN stores source ON source.store_id = t.from_store_id
            JOIN stores destination ON destination.store_id = t.to_store_id
            JOIN users u ON u.user_id = t.initiated_by
            LEFT JOIN stock_transfer_items ti ON ti.transfer_id = t.transfer_id
            WHERE t.from_store_id = %s OR t.to_store_id = %s
            GROUP BY t.transfer_id
            ORDER BY t.transfer_id DESC
            """,
            (current_store, current_store)
        )
        transfers = cursor.fetchall()

        cursor.execute(
            """
            SELECT store_id, store_name
            FROM stores
            WHERE is_active = 1 AND store_id != %s
            ORDER BY store_name
            """,
            (current_store,)
        )
        stores = cursor.fetchall()

        cursor.execute(
            """
            SELECT product_id, product_name, sku
            FROM products
            WHERE is_active = 1
            ORDER BY product_name
            """
        )
        products = cursor.fetchall()

        return render_template(
            "stock_transfers.html",
            transfers=transfers,
            stores=stores,
            products=products,
            current_store=current_store
        )

    except Exception as error:
        if connection:
            connection.rollback()
        traceback.print_exc()
        flash(str(error), "error")
        return redirect(url_for("stock_transfers.transfer_list"))

    finally:
        if cursor:
            cursor.close()
        connection.close()


@stock_transfers_bp.route("/dispatch/<int:transfer_id>", methods=["POST"])
def dispatch_transfer(transfer_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    if not connection:
        flash("Database connection failed.", "error")
        return redirect(url_for("stock_transfers.transfer_list"))

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)
        current_store = get_current_store(cursor)
        connection.start_transaction()

        cursor.execute(
            """
            SELECT *
            FROM stock_transfers
            WHERE transfer_id = %s
            FOR UPDATE
            """,
            (transfer_id,)
        )
        transfer = cursor.fetchone()

        if not transfer:
            raise ValueError("Transfer request not found.")

        if transfer["from_store_id"] != current_store:
            raise ValueError("Only the source store can dispatch this transfer.")

        if transfer["status"] != "requested":
            raise ValueError("Only requested transfers can be dispatched.")

        cursor.execute(
            """
            SELECT transfer_item_id, product_id, requested_qty
            FROM stock_transfer_items
            WHERE transfer_id = %s
            """,
            (transfer_id,)
        )
        items = cursor.fetchall()

        if not items:
            raise ValueError("This transfer has no products.")

        for item in items:
            product_id = item["product_id"]
            quantity = item["requested_qty"]

            cursor.execute(
                """
                SELECT quantity_on_hand
                FROM inventory
                WHERE store_id = %s AND product_id = %s
                FOR UPDATE
                """,
                (current_store, product_id)
            )
            inventory = cursor.fetchone()

            if not inventory or inventory["quantity_on_hand"] < quantity:
                raise ValueError(
                    f"Insufficient inventory for product ID {product_id}."
                )

            cursor.execute(
                """
                SELECT batch_id, batch_code, quantity_remaining,
                       manufacturing_date, expiry_date
                FROM batches
                WHERE store_id = %s
                  AND product_id = %s
                  AND quantity_remaining > 0
                  AND (expiry_date IS NULL OR expiry_date >= %s)
                ORDER BY
                    CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END,
                    expiry_date ASC,
                    created_at ASC,
                    batch_id ASC
                FOR UPDATE
                """,
                (current_store, product_id, date.today())
            )
            batches = cursor.fetchall()

            available = sum(batch["quantity_remaining"] for batch in batches)

            if available < quantity:
                raise ValueError(
                    f"Insufficient unexpired batch stock for product ID {product_id}."
                )

            remaining = quantity

            for batch in batches:
                if remaining <= 0:
                    break

                moved_qty = min(remaining, batch["quantity_remaining"])

                cursor.execute(
                    """
                    UPDATE batches
                    SET quantity_remaining = quantity_remaining - %s
                    WHERE batch_id = %s AND quantity_remaining >= %s
                    """,
                    (moved_qty, batch["batch_id"], moved_qty)
                )

                if cursor.rowcount != 1:
                    raise ValueError("Batch stock changed. Please try again.")

                destination_batch_code = (
                    f"TRF-{transfer_id}-{batch['batch_id']}"
                )

                cursor.execute(
                    """
                    INSERT INTO batches
                        (store_id, product_id, receipt_item_id, batch_code,
                         quantity_received, quantity_remaining,
                         manufacturing_date, expiry_date)
                    VALUES (%s, %s, NULL, %s, %s, %s, %s, %s)
                    """,
                    (
                        transfer["to_store_id"],
                        product_id,
                        destination_batch_code,
                        moved_qty,
                        moved_qty,
                        batch["manufacturing_date"],
                        batch["expiry_date"]
                    )
                )

                remaining -= moved_qty

            cursor.execute(
                """
                UPDATE inventory
                SET quantity_on_hand = quantity_on_hand - %s
                WHERE store_id = %s AND product_id = %s
                  AND quantity_on_hand >= %s
                """,
                (quantity, current_store, product_id, quantity)
            )

            if cursor.rowcount != 1:
                raise ValueError("Inventory changed. Please try again.")

            cursor.execute(
                """
                INSERT INTO inventory
                    (store_id, product_id, quantity_on_hand, reorder_level)
                VALUES (%s, %s, %s, 0)
                ON DUPLICATE KEY UPDATE
                    quantity_on_hand = quantity_on_hand + %s
                """,
                (
                    transfer["to_store_id"],
                    product_id,
                    quantity,
                    quantity
                )
            )

            cursor.execute(
                """
                UPDATE stock_transfer_items
                SET dispatched_qty = %s
                WHERE transfer_item_id = %s
                """,
                (quantity, item["transfer_item_id"])
            )

        cursor.execute(
            """
            UPDATE stock_transfers
            SET status = 'dispatched', dispatched_at = CURRENT_TIMESTAMP
            WHERE transfer_id = %s
            """,
            (transfer_id,)
        )

        connection.commit()
        flash(f"Transfer #{transfer_id} dispatched successfully.", "success")

    except Exception as error:
        connection.rollback()
        traceback.print_exc()
        flash(str(error), "error")

    finally:
        if cursor:
            cursor.close()
        connection.close()

    return redirect(url_for("stock_transfers.transfer_list"))


@stock_transfers_bp.route("/receive/<int:transfer_id>", methods=["POST"])
def receive_transfer(transfer_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    if not connection:
        flash("Database connection failed.", "error")
        return redirect(url_for("stock_transfers.transfer_list"))

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)
        current_store = get_current_store(cursor)
        connection.start_transaction()

        cursor.execute(
            """
            SELECT *
            FROM stock_transfers
            WHERE transfer_id = %s
            FOR UPDATE
            """,
            (transfer_id,)
        )
        transfer = cursor.fetchone()

        if not transfer:
            raise ValueError("Transfer request not found.")

        if transfer["to_store_id"] != current_store:
            raise ValueError("Only the destination store can confirm receipt.")

        if transfer["status"] != "dispatched":
            raise ValueError("Only dispatched transfers can be received.")

        cursor.execute(
            """
            UPDATE stock_transfer_items
            SET received_qty = dispatched_qty
            WHERE transfer_id = %s
            """,
            (transfer_id,)
        )

        cursor.execute(
            """
            UPDATE stock_transfers
            SET status = 'received', received_at = CURRENT_TIMESTAMP
            WHERE transfer_id = %s
            """,
            (transfer_id,)
        )

        connection.commit()
        flash(f"Transfer #{transfer_id} marked as received.", "success")

    except Exception as error:
        connection.rollback()
        traceback.print_exc()
        flash(str(error), "error")

    finally:
        if cursor:
            cursor.close()
        connection.close()

    return redirect(url_for("stock_transfers.transfer_list"))


@stock_transfers_bp.route("/cancel/<int:transfer_id>", methods=["POST"])
def cancel_transfer(transfer_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    connection = get_db_connection()
    if not connection:
        flash("Database connection failed.", "error")
        return redirect(url_for("stock_transfers.transfer_list"))

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)
        current_store = get_current_store(cursor)
        connection.start_transaction()

        cursor.execute(
            """
            SELECT *
            FROM stock_transfers
            WHERE transfer_id = %s
            FOR UPDATE
            """,
            (transfer_id,)
        )
        transfer = cursor.fetchone()

        if not transfer:
            raise ValueError("Transfer request not found.")

        if transfer["from_store_id"] != current_store:
            raise ValueError("Only the source store can cancel this request.")

        if transfer["status"] != "requested":
            raise ValueError("Only requested transfers can be cancelled.")

        cursor.execute(
            """
            UPDATE stock_transfers
            SET status = 'cancelled'
            WHERE transfer_id = %s
            """,
            (transfer_id,)
        )

        connection.commit()
        flash(f"Transfer #{transfer_id} cancelled.", "success")

    except Exception as error:
        connection.rollback()
        traceback.print_exc()
        flash(str(error), "error")

    finally:
        if cursor:
            cursor.close()
        connection.close()

    return redirect(url_for("stock_transfers.transfer_list"))
