import requests

url = "http://127.0.0.1:5000/api/batches/deduct"

data = {
    "store_id": 1,
    "product_id": 1,
    "quantity": 10
}

response = requests.post(url, json=data)

print("Status Code:", response.status_code)
print("Response:", response.json())