
from modules.inventory import get_all_inventory, get_low_stock_items
from modules.batches import get_expiring_batches


def ask_inventory_assistant(question, store_id=None):
    question = question.lower().strip()

    if any(word in question for word in ["low stock", "running low", "reorder"]):
        data = get_low_stock_items(store_id)

        return {
            "success": True,
            "answer": f"Found {len(data)} low-stock products.",
            "data": data
        }

    elif any(word in question for word in ["expiring", "expiry", "expire"]):
        data = get_expiring_batches(30, store_id)

        return {
            "success": True,
            "answer": f"Found {len(data)} batches expiring within 30 days.",
            "data": data
        }

    elif any(word in question for word in ["inventory", "stock", "quantity"]):
        data = get_all_inventory(store_id)

        return {
            "success": True,
            "answer": f"Found {len(data)} inventory records.",
            "data": data
        }

    else:
        return {
            "success": True,
            "answer": "I can help with low stock, expiring batches, and current inventory. Please ask one of these questions.",
            "data": []
        }
