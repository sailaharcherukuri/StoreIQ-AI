from modules.inventory import get_all_inventory, get_low_stock_items

print("\n===== ALL INVENTORY =====")
inventory = get_all_inventory()

for item in inventory:
    print(item)

print("\n===== LOW STOCK ITEMS =====")
low_stock = get_low_stock_items()

for item in low_stock:
    print(item)

print("\nTotal inventory records:", len(inventory))
print("Total low-stock records:", len(low_stock))