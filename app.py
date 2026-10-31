
from flask import Flask, jsonify, request

from modules.inventory import (
    get_all_inventory,
    get_low_stock_items,
    update_stock,
    add_inventory
)

from modules.batches import (
    get_all_batches,
    get_expiring_batches,
    add_batch,
    deduct_stock_fefo
)

from modules.suppliers import (
    get_all_suppliers,
    add_supplier
)

from modules.purchase_orders import (
    create_purchase_order,
    get_all_purchase_orders
)

from modules.purchase_receiving import (
    receive_purchase_order
)

from modules.forecasting import (
    generate_forecasts,
    get_all_forecasts
)

from modules.assistant import (
    ask_inventory_assistant
)


app = Flask(__name__)


# =====================================
# HOME
# =====================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "StoreIQ AI Inventory API is running",
        "status": "success"
    })


# =====================================
# INVENTORY MANAGEMENT
# =====================================

@app.route("/api/inventory", methods=["GET"])
def inventory():
    store_id = request.args.get("store_id", type=int)
    return jsonify(get_all_inventory(store_id))


@app.route("/api/inventory/low-stock", methods=["GET"])
def low_stock():
    store_id = request.args.get("store_id", type=int)
    return jsonify(get_low_stock_items(store_id))


@app.route("/api/inventory/update", methods=["PUT"])
def inventory_update():
    data = request.get_json()

    if not data or "inventory_id" not in data or "new_quantity" not in data:
        return jsonify({
            "success": False,
            "message": "inventory_id and new_quantity are required"
        }), 400

    success = update_stock(
        data["inventory_id"],
        data["new_quantity"]
    )

    return jsonify({
        "success": success,
        "message": "Stock updated successfully" if success
        else "Inventory record not found"
    })


@app.route("/api/inventory/add", methods=["POST"])
def inventory_add():
    data = request.get_json()

    required = [
        "store_id",
        "product_id",
        "quantity",
        "reorder_level"
    ]

    if not data or any(key not in data for key in required):
        return jsonify({
            "success": False,
            "message": "Missing required fields"
        }), 400

    success = add_inventory(
        data["store_id"],
        data["product_id"],
        data["quantity"],
        data["reorder_level"]
    )

    return jsonify({
        "success": success,
        "message": "Inventory added successfully" if success
        else "Could not add inventory"
    })


# =====================================
# BATCH MANAGEMENT
# =====================================

@app.route("/api/batches", methods=["GET"])
def batches():
    store_id = request.args.get("store_id", type=int)
    return jsonify(get_all_batches(store_id))


@app.route("/api/batches/expiring", methods=["GET"])
def expiring_batches():
    days = request.args.get("days", default=30, type=int)
    store_id = request.args.get("store_id", type=int)

    return jsonify(get_expiring_batches(days, store_id))


@app.route("/api/batches/add", methods=["POST"])
def batch_add():
    data = request.get_json()

    required = [
        "store_id",
        "product_id",
        "batch_code",
        "quantity_received",
        "manufacturing_date",
        "expiry_date"
    ]

    if not data or any(key not in data for key in required):
        return jsonify({
            "success": False,
            "message": "Missing required fields"
        }), 400

    success = add_batch(
        data["store_id"],
        data["product_id"],
        data["batch_code"],
        data["quantity_received"],
        data["manufacturing_date"],
        data["expiry_date"]
    )

    return jsonify({
        "success": success,
        "message": "Batch added successfully" if success
        else "Could not add batch"
    })


@app.route("/api/batches/deduct", methods=["POST"])
def batch_deduct():
    data = request.get_json()

    required = ["store_id", "product_id", "quantity"]

    if not data or any(key not in data for key in required):
        return jsonify({
            "success": False,
            "message": "Missing required fields"
        }), 400

    success = deduct_stock_fefo(
        data["store_id"],
        data["product_id"],
        data["quantity"]
    )

    return jsonify({
        "success": success,
        "message": "Stock deducted using FEFO successfully"
        if success else "Insufficient stock or deduction failed"
    })


# =====================================
# SUPPLIER MANAGEMENT
# =====================================

@app.route("/api/suppliers", methods=["GET"])
def suppliers():
    return jsonify(get_all_suppliers())


@app.route("/api/suppliers/add", methods=["POST"])
def supplier_add():
    data = request.get_json()

    if not data or not data.get("supplier_name"):
        return jsonify({
            "success": False,
            "message": "supplier_name is required"
        }), 400

    success = add_supplier(
        data["supplier_name"],
        data.get("contact_person"),
        data.get("phone"),
        data.get("email"),
        data.get("address")
    )

    return jsonify({
        "success": success,
        "message": "Supplier added successfully" if success
        else "Could not add supplier"
    })


# =====================================
# PURCHASE ORDER MANAGEMENT
# =====================================

@app.route("/api/purchase-orders", methods=["GET"])
def purchase_orders():
    return jsonify(get_all_purchase_orders())


@app.route("/api/purchase-orders/add", methods=["POST"])
def purchase_order_add():
    data = request.get_json()

    required = [
        "store_id",
        "supplier_id",
        "created_by",
        "items"
    ]

    if not data or any(key not in data for key in required):
        return jsonify({
            "success": False,
            "message": "Missing required fields"
        }), 400

    if not isinstance(data["items"], list) or not data["items"]:
        return jsonify({
            "success": False,
            "message": "At least one purchase order item is required"
        }), 400

    try:
        order_id = create_purchase_order(
            data["store_id"],
            data["supplier_id"],
            data["created_by"],
            data["items"],
            data.get("expected_delivery_date"),
            data.get("notes")
        )

        if not order_id:
            return jsonify({
                "success": False,
                "message": "Database connection failed"
            }), 500

        return jsonify({
            "success": True,
            "message": "Purchase order created successfully",
            "purchase_order_id": order_id
        }), 201

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400


# =====================================
# PURCHASE RECEIVING
# =====================================

@app.route("/api/purchase-receipts/add", methods=["POST"])
def add_purchase_receipt():
    data = request.get_json()

    required = [
        "purchase_order_id",
        "received_by",
        "items"
    ]

    if not data or any(key not in data for key in required):
        return jsonify({
            "success": False,
            "message": "Missing required fields"
        }), 400

    if not isinstance(data["items"], list) or not data["items"]:
        return jsonify({
            "success": False,
            "message": "At least one receipt item is required"
        }), 400

    try:
        receipt_id = receive_purchase_order(
            data["purchase_order_id"],
            data["received_by"],
            data["items"],
            data.get("notes")
        )

        if not receipt_id:
            return jsonify({
                "success": False,
                "message": "Database connection failed"
            }), 500

        return jsonify({
            "success": True,
            "message": "Purchase stock received successfully",
            "receipt_id": receipt_id
        }), 201

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400


# =====================================
# AI DEMAND FORECASTING
# =====================================

@app.route("/api/forecast/generate", methods=["POST"])
def forecast_generate():
    data = request.get_json(silent=True) or {}

    try:
        store_id = data.get("store_id")

        if store_id is not None:
            store_id = int(store_id)

        forecasts = generate_forecasts(
            store_id=store_id,
            forecast_days=7
        )

        return jsonify({
            "success": True,
            "message": "Demand forecasting completed",
            "total_forecasts": len(forecasts),
            "forecasts": forecasts
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400


@app.route("/api/forecasts", methods=["GET"])
def forecasts():
    store_id = request.args.get("store_id", type=int)
    return jsonify(get_all_forecasts(store_id))


# =====================================
# AI INVENTORY ASSISTANT
# =====================================

@app.route("/api/assistant/ask", methods=["POST"])
def inventory_assistant():
    data = request.get_json()

    if not data or not data.get("question"):
        return jsonify({
            "success": False,
            "message": "Please provide a question"
        }), 400

    try:
        store_id = data.get("store_id")

        if store_id is not None:
            store_id = int(store_id)

        result = ask_inventory_assistant(
            data["question"],
            store_id
        )

        return jsonify(result)

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400


# =====================================
# RUN APPLICATION
# =====================================

if __name__ == "__main__":
    app.run(debug=True)
