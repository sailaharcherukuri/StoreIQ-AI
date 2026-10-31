
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
from decimal import Decimal, ROUND_HALF_UP

returns_bp = Blueprint("returns", __name__, url_prefix="/returns")


def login_required():
    return "user_id" in session


@returns_bp.route("/", methods=["GET"])
def returns_page():
    if not login_required():
        return redirect(url_for("auth.login"))

    invoice_no = request.args.get("invoice_no", "").strip()
    sale = None
    items = []

    if invoice_no:
        connection = get_db_connection()

        if not connection:
            flash("Database connection failed.", "error")
            return render_template(
                "returns.html",
                sale=None,
                items=[],
                invoice_no=invoice_no
            )

        try:
            cursor = connection.cursor(dictionary=True)

            cursor.execute("""
                SELECT
                    s.sale_id,
                    s.invoice_no,
                    s.store_id,
                    s.customer_id,
                    s.cashier_id,
                    s.total_amount,
                    s.status,
                    s.created_at
                FROM sales s
                WHERE s.invoice_no = %s
            """, (invoice_no,))

            sale = cursor.fetchone()

            if sale:
                cursor.execute("""
                    SELECT
                        si.sale_item_id,
                        si.product_id,
                        p.product_name,
                        si.quantity AS purchased_quantity,
                        si.unit_price,
                        si.discount,
                        si.total_price,
                        COALESCE(SUM(ri.quantity), 0) AS returned_quantity
                    FROM sale_items si
                    JOIN products p
                        ON p.product_id = si.product_id
                    LEFT JOIN return_items ri
                        ON ri.sale_item_id = si.sale_item_id
                    LEFT JOIN returns r
                        ON r.return_id = ri.return_id
                        AND r.status = 'completed'
                    WHERE si.sale_id = %s
                    GROUP BY
                        si.sale_item_id,
                        si.product_id,
                        p.product_name,
                        si.quantity,
                        si.unit_price,
                        si.discount,
                        si.total_price
                    ORDER BY si.sale_item_id
                """, (sale["sale_id"],))

                items = cursor.fetchall()

                for item in items:
                    item["remaining_quantity"] = (
                        item["purchased_quantity"] -
                        item["returned_quantity"]
                    )

                    item["refund_per_unit"] = (
                        Decimal(str(item["total_price"])) /
                        Decimal(str(item["purchased_quantity"]))
                    ).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP
                    )

            cursor.close()

        except Exception as error:
            print("Return search error:", error)
            flash("Unable to search invoice.", "error")

        finally:
            connection.close()

    return render_template(
        "returns.html",
        sale=sale,
        items=items,
        invoice_no=invoice_no
    )


@returns_bp.route("/process", methods=["POST"])
def process_return():
    if not login_required():
        return redirect(url_for("auth.login"))

    sale_id = request.form.get("sale_id", type=int)
    reason = request.form.get("reason", "").strip()

    if not sale_id:
        flash("Invalid sale.", "error")
        return redirect(url_for("returns.return_page"))

    connection = get_db_connection()

    if not connection:
        flash("Database connection failed.", "error")
        return redirect(url_for("returns.return_page"))

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM sales
            WHERE sale_id = %s
            FOR UPDATE
        """, (sale_id,))

        sale = cursor.fetchone()

        if not sale:
            raise ValueError("Sale not found.")

        if sale["status"] not in ("completed", "partially_returned"):
            raise ValueError("This sale cannot be returned.")

        return_quantities = {}

        for key, value in request.form.items():
            if key.startswith("quantity_"):
                sale_item_id = int(key.replace("quantity_", ""))
                quantity = int(value or 0)

                if quantity < 0:
                    raise ValueError("Return quantity cannot be negative.")

                if quantity > 0:
                    return_quantities[sale_item_id] = quantity

        if not return_quantities:
            raise ValueError("Select at least one product to return.")

        selected_ids = list(return_quantities.keys())
        placeholders = ",".join(["%s"] * len(selected_ids))

        cursor.execute(f"""
            SELECT
                si.sale_item_id,
                si.product_id,
                si.quantity,
                si.unit_price,
                si.total_price
            FROM sale_items si
            WHERE si.sale_id = %s
            AND si.sale_item_id IN ({placeholders})
            FOR UPDATE
        """, [sale_id] + selected_ids)

        sale_items = cursor.fetchall()

        if len(sale_items) != len(return_quantities):
            raise ValueError("Invalid sale item selected.")

        refund_total = Decimal("0.00")
        return_details = []

        for item in sale_items:
            sale_item_id = item["sale_item_id"]
            requested_quantity = return_quantities[sale_item_id]

            cursor.execute("""
                SELECT COALESCE(SUM(ri.quantity), 0) AS returned_quantity
                FROM return_items ri
                JOIN returns r
                    ON r.return_id = ri.return_id
                WHERE ri.sale_item_id = %s
                AND r.status = 'completed'
            """, (sale_item_id,))

            returned_quantity = cursor.fetchone()["returned_quantity"]

            remaining_quantity = item["quantity"] - returned_quantity

            if requested_quantity > remaining_quantity:
                raise ValueError(
                    f"Cannot return {requested_quantity} units. "
                    f"Only {remaining_quantity} units remain returnable."
                )

            cursor.execute("""
                SELECT batch_id, quantity
                FROM sale_item_batches
                WHERE sale_item_id = %s
                ORDER BY batch_id
                FOR UPDATE
            """, (sale_item_id,))

            batches = cursor.fetchall()

            if not batches:
                raise ValueError(
                    f"No original batch information found for sale item "
                    f"{sale_item_id}. Cannot safely restore stock."
                )

            cursor.execute("""
                SELECT
                    rib.batch_id,
                    COALESCE(SUM(rib.quantity), 0) AS returned_quantity
                FROM return_item_batches rib
                JOIN return_items ri
                    ON ri.return_item_id = rib.return_item_id
                JOIN returns r
                    ON r.return_id = ri.return_id
                WHERE ri.sale_item_id = %s
                AND r.status = 'completed'
                GROUP BY rib.batch_id
            """, (sale_item_id,))

            previously_returned = {
                row["batch_id"]: row["returned_quantity"]
                for row in cursor.fetchall()
            }

            available_batches = []

            for batch in batches:
                available = (
                    batch["quantity"] -
                    previously_returned.get(batch["batch_id"], 0)
                )

                if available > 0:
                    available_batches.append({
                        "batch_id": batch["batch_id"],
                        "available": available
                    })

            if sum(b["available"] for b in available_batches) < requested_quantity:
                raise ValueError(
                    "Insufficient original batch quantity for this return."
                )

            net_unit_price = (
                Decimal(str(item["total_price"])) /
                Decimal(str(item["quantity"]))
            )

            item_refund = (
                net_unit_price * requested_quantity
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            refund_total += item_refund

            return_details.append({
                "sale_item_id": sale_item_id,
                "product_id": item["product_id"],
                "quantity": requested_quantity,
                "refund_amount": item_refund,
                "batches": available_batches
            })

        cursor.execute("""
            INSERT INTO returns (
                sale_id,
                processed_by,
                reason,
                total_refund,
                status
            )
            VALUES (%s, %s, %s, %s, 'completed')
        """, (
            sale_id,
            session["user_id"],
            reason or None,
            refund_total
        ))

        return_id = cursor.lastrowid

        for detail in return_details:
            cursor.execute("""
                INSERT INTO return_items (
                    return_id,
                    sale_item_id,
                    quantity,
                    refund_amount
                )
                VALUES (%s, %s, %s, %s)
            """, (
                return_id,
                detail["sale_item_id"],
                detail["quantity"],
                detail["refund_amount"]
            ))

            return_item_id = cursor.lastrowid
            remaining_to_restore = detail["quantity"]

            for batch in detail["batches"]:
                if remaining_to_restore <= 0:
                    break

                restore_quantity = min(
                    remaining_to_restore,
                    batch["available"]
                )

                cursor.execute("""
                    UPDATE batches
                    SET quantity_remaining =
                        quantity_remaining + %s
                    WHERE batch_id = %s
                """, (
                    restore_quantity,
                    batch["batch_id"]
                ))

                if cursor.rowcount != 1:
                    raise ValueError("Unable to restore original batch.")

                cursor.execute("""
                    INSERT INTO return_item_batches (
                        return_item_id,
                        batch_id,
                        quantity
                    )
                    VALUES (%s, %s, %s)
                """, (
                    return_item_id,
                    batch["batch_id"],
                    restore_quantity
                ))

                remaining_to_restore -= restore_quantity

            if remaining_to_restore > 0:
                raise ValueError("Unable to allocate returned batch quantity.")

            cursor.execute("""
                UPDATE inventory
                SET quantity_on_hand = quantity_on_hand + %s
                WHERE store_id = %s
                AND product_id = %s
            """, (
                detail["quantity"],
                sale["store_id"],
                detail["product_id"]
            ))

            if cursor.rowcount != 1:
                raise ValueError("Inventory record not found for returned product.")

        cursor.execute("""
            SELECT COUNT(*) AS total_items,
                   SUM(si.quantity) AS purchased_quantity
            FROM sale_items si
            WHERE si.sale_id = %s
        """, (sale_id,))

        total_purchased = cursor.fetchone()["purchased_quantity"] or 0

        cursor.execute("""
            SELECT COALESCE(SUM(ri.quantity), 0) AS returned_quantity
            FROM return_items ri
            JOIN returns r
                ON r.return_id = ri.return_id
            JOIN sale_items si
                ON si.sale_item_id = ri.sale_item_id
            WHERE si.sale_id = %s
            AND r.status = 'completed'
        """, (sale_id,))

        total_returned = cursor.fetchone()["returned_quantity"]

        new_status = (
            "returned"
            if total_returned >= total_purchased
            else "partially_returned"
        )

        cursor.execute("""
            UPDATE sales
            SET status = %s
            WHERE sale_id = %s
        """, (new_status, sale_id))

        connection.commit()

        flash(
            f"Return completed successfully! Refund: ₹{refund_total}",
            "success"
        )

        return redirect(url_for(
            "returns.return_page",
            invoice_no=sale["invoice_no"]
        ))

    except Exception as error:
        connection.rollback()
        print("Return processing error:", error)
        flash(str(error), "error")

        return redirect(url_for("returns.return_page"))

    finally:
        if cursor:
            cursor.close()
        connection.close()
