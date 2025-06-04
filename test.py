import requests

BASE_URL = "http://127.0.0.1:8000"

# 1. Get token
def get_token(username, password):
    resp = requests.post(f"{BASE_URL}/get_token", json={"username": username, "password": password})
    resp.raise_for_status()
    return resp.json()["access_token"]

# 2. Register filter schema
def register_filter(token, filters, threshold=0.45):
    headers = {"Authorization": f"Bearer {token}"}
    data = {"filters": filters, "threshold": threshold}
    resp = requests.post(f"{BASE_URL}/register_filter", json=data, headers=headers)
    resp.raise_for_status()
    return resp.json()["schema_id"]

# 3. Query filters
def query_text(schema_id, query):
    data = {"schema_id": schema_id, "query": query}
    resp = requests.post(f"{BASE_URL}/query_text", json=data)
    resp.raise_for_status()
    return resp.json()["filters"]

if __name__ == "__main__":
    # Your user credentials
    username = "admin"
    password = "adminpass"

    # Sample filters dictionary (same shape as expected by your API)
    filters = {
        "category": {
            "Salad": "light and healthy dishes usually with vegetables",
            "Bread": "bakery items like loaves and buns",
            "Pizza": "flatbread topped with cheese and toppings",
            "Dessert": "sweet dishes served after meals"
        },
        "diet": {
            "Vegan": "food with no animal products or dairy",
            "Vegetarian": "no meat, but may include dairy",
            "Healthy": "nutritious low-fat and low-sugar options",
            "Keto": "low carb and high fat diet food"
        },
        "price": {
            "<100": "affordable or cheap items under 100",
            "100-200": "moderately priced food",
            "200-300": "slightly premium pricing",
            ">300": "expensive high-end food"
        },
        "sort": {
            "rating_desc": "sorted by best customer ratings",
            "price_asc": "sorted by lowest price",
            "price_desc": "sorted by highest price",
            "popularity": "most ordered or popular dishes"
        }
    }

    # Step 1: Get JWT token
    token = get_token(username, password)
    print("Access token:", token)

    # Step 2: Register filter schema
    schema_id = register_filter(token, filters)
    print("Registered schema_id:", schema_id)

    # Step 3: Query some filters
    test_queries = [
        "healthy vegan salad under 100 sorted by best rating",
        "cheap bread and pizza",
        "dessert with highest rating"
    ]

    for q in test_queries:
        extracted_filters = query_text(schema_id, q)
        print(f"Query: '{q}'\nExtracted filters:", extracted_filters)
        print("------")
