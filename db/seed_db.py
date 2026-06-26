import random
import sqlite3
import os
import hashlib
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "sample_ecommerce.db")

CUSTOMER_NAMES = [
    "Aarav Sharma", "Diya Patel", "Vihaan Reddy", "Ananya Iyer", "Kabir Singh",
    "Saanvi Nair", "Arjun Menon", "Ishaan Gupta", "Myra Verma", "Reyansh Rao",
    "Aadhya Joshi", "Vivaan Kapoor", "Anika Desai", "Shaurya Pillai", "Kiara Bose",
    "Rohan Malhotra", "Priya Saxena", "Advik Bhat", "Sara Khan", "Aryan Chatterjee",
    "Ishita Mehra", "Dhruv Shetty", "Kavya Srinivasan", "Neel Kulkarni", "Tara Mahajan",
    "Yash Tiwari", "Nisha Aggarwal", "Pranav Shinde", "Anushka Choudhury", "Karan Wagh",
    "Maya Narayan", "Ritwik Banerjee", "Swara Dixit", "Aarush Bora", "Lavanya Prasad",
    "Om Gaikwad", "Riya Thomas", "Arnav Biswas", "Sana Mirza", "Jayesh Patwardhan",
    "Tanvi Gokhale", "Harsh More", "Bhavna Shenoy", "Ishan Bajaj", "Meera Kaur",
    "Rishi Thakur", "Pooja Chaudhary", "Ayushman Dutta", "Jhanvi Rawat", "Ahaan Kapadia",
    "Devika Pai", "Samarth Agarwal", "Anvi Lobo", "Dhairya Shah", "Trisha Nambiar",
    "Hritik Arora", "Prerna Sethi", "Shlok Bhatnagar", "Nandini Hegde", "Vedant Soni",
    "Lakshmi Venkatesh", "Tanay Joshi", "Bhavya Parmar", "Jatin Goradia", "Chaitanya Guha",
    "Smriti Rai", "Tejas Kale", "Mrunalini Pawar", "Vivaan Sekhon", "Anshita Naidu",
    "Kushagra Pandit", "Hiral Parikh", "Parthiv Reddy", "Shivani Saxena", "Aaryan Surve",
    "Akshara Jain", "Sahil Mir", "Pihu Agarwal", "Nakul Garg", "Rhea Gill",
    "Anmol Bhatia", "Prisha Rajan", "Lalit Tiwari", "Deepika Nath", "Madhav Luthra",
    "Suhani Sinha", "Arav Cherian", "Tanya Abrol", "Purab Banerjee", "Neha Kishore",
    "Amit Dhar", "Nalini Iyengar", "Raghav Bansal", "Juhi Singh", "Kunal Grover",
    "Sanya Duggal", "Ayaan Chopra", "Grishma Shah", "Siddharth Panchal", "Jasmine Kaur",
    "Mohit Deshmukh", "Sanjana Rajput", "Gaurav Dhawan", "Bhumika Jha", "Nitesh Tiwari",
]

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Ahmedabad", "Chennai", "Kolkata",
    "Pune", "Jaipur", "Lucknow", "Surat", "Nagpur", "Indore", "Thane", "Bhopal",
    "Visakhapatnam", "Vadodara", "Patna", "Ludhiana", "Agra", "Nashik", "Faridabad",
    "Meerut", "Rajkot", "Varanasi", "Srinagar", "Aurangabad", "Dhanbad", "Amritsar",
    "Ranchi", "Gwalior", "Allahabad", "Coimbatore", "Vijayawada", "Jodhpur",
]

PRODUCT_CATALOG = [
    ("Wireless Earbuds Pro", "Electronics", 2999, 1400),
    ("Smart Fitness Band", "Electronics", 1999, 900),
    ("4K Action Camera", "Electronics", 8999, 4500),
    ("Ergonomic Office Chair", "Furniture", 7499, 3800),
    ("Standing Desk", "Furniture", 12999, 6500),
    ("Cotton Bedsheet Set", "Home", 1499, 600),
    ("Non-Stick Cookware Set", "Home", 3499, 1700),
    ("Organic Green Tea (250g)", "Grocery", 399, 150),
    ("Cold Pressed Coconut Oil", "Grocery", 549, 220),
    ("Running Shoes", "Fashion", 3299, 1300),
    ("Denim Jacket", "Fashion", 2599, 1000),
    ("Leather Wallet", "Fashion", 999, 350),
    ("Bluetooth Speaker", "Electronics", 2499, 1100),
    ("Yoga Mat", "Sports", 899, 300),
    ("Adjustable Dumbbell Set", "Sports", 4999, 2400),
    ("Noise Cancellation Headphones", "Electronics", 7999, 3800),
    ("Mechanical Gaming Keyboard", "Electronics", 4499, 2100),
    ("Portable Power Bank 20000mAh", "Electronics", 1599, 700),
    ("Smartphone Tripod Stand", "Electronics", 699, 250),
    ("USB-C Hub 7-in-1", "Electronics", 1299, 550),
    ("3-Seater Fabric Sofa", "Furniture", 24999, 12000),
    ("Queen Size Mattress", "Furniture", 15999, 7500),
    ("Wall Mounted Bookshelf", "Furniture", 4999, 2200),
    ("LED Study Lamp", "Furniture", 1299, 500),
    ("Foldable Storage Ottoman", "Furniture", 2499, 1100),
    ("Premium Bedsheet Set King", "Home", 2299, 900),
    ("Bath Towel Set 6-Piece", "Home", 1299, 500),
    ("Scented Candle Collection", "Home", 799, 300),
    ("Glass Tupperware Set 12pc", "Home", 999, 400),
    ("Decorative Throw Pillow", "Home", 449, 150),
    ("Organic Honey (500g)", "Grocery", 649, 250),
    ("Premium Nuts Trail Mix", "Grocery", 899, 350),
    ("Cold Brew Coffee Bottle", "Grocery", 499, 180),
    ("Protein Bar Variety Pack", "Grocery", 799, 300),
    ("Organic Quinoa (1kg)", "Grocery", 549, 200),
    ("Casual Sneakers", "Fashion", 4499, 1800),
    ("Formal Shirt Slim Fit", "Fashion", 1999, 700),
    ("Women's Handbag", "Fashion", 3499, 1400),
    ("Silk Scarf", "Fashion", 1499, 500),
    ("Athletic Shorts", "Fashion", 999, 350),
    ("Mountain Bike Helmet", "Sports", 2499, 1000),
    ("Resistance Bands Set", "Sports", 699, 250),
    ("Skipping Rope Speed", "Sports", 299, 100),
    ("Insulated Water Bottle", "Sports", 599, 200),
    ("Tennis Racket Pro", "Sports", 3999, 1800),
    ("Board Game Collection", "Toys", 1499, 600),
    ("Educational Building Blocks", "Toys", 2499, 1100),
    ("Remote Control Car", "Toys", 1799, 700),
    ("DIY Craft Kit", "Toys", 899, 350),
    ("Stuffed Teddy Bear 24in", "Toys", 1299, 500),
    ("Kindle E-Reader", "Books", 9999, 5000),
    ("Wireless Mouse", "Electronics", 849, 350),
    ("Laptop Stand Adjustable", "Furniture", 1899, 800),
]

SUPPLIERS = [
    "TechVista Components", "GreenField Organics", "FurniCraft Ltd", "SportEdge Gear",
    "HomeEase Manufacturing", "BookWorld Distributors", "EcoFashion Hub",
    "SmartGadget Inc", "WellnessWave Supplies", "PlayLearn Toys",
    "StyleCraft Apparel", "NutriFresh Foods",
]

WAREHOUSES = [
    "Chennai-WH1", "Mumbai-WH2", "Delhi-WH3", "Bangalore-WH4",
    "Hyderabad-WH5", "Kolkata-WH6", "Pune-WH7",
]

PAYMENT_METHODS = ["Credit Card", "Debit Card", "UPI", "Net Banking", "Cash on Delivery"]

SHIPPING_CARRIERS = ["Delhivery", "Blue Dart", "Ekart", "Amazon Shipping", "DTDC"]

ORDER_STATUSES = ["PLACED", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"]
ORDER_STATUS_WEIGHTS = [10, 15, 20, 50, 5]


def _transaction_id() -> str:
    raw = os.urandom(16).hex() + str(random.randint(1000, 9999))
    return "TXN" + hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


def build_schema(cur: sqlite3.Cursor) -> None:
    cur.executescript("""
        DROP TABLE IF EXISTS shipping;
        DROP TABLE IF EXISTS payments;
        DROP TABLE IF EXISTS reviews;
        DROP TABLE IF EXISTS suppliers;
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS inventory;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            customer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            city          TEXT NOT NULL,
            signup_date   TEXT NOT NULL
        );

        CREATE TABLE products (
            product_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            category      TEXT NOT NULL,
            price         REAL NOT NULL,
            cost          REAL NOT NULL
        );

        CREATE TABLE inventory (
            inventory_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id         INTEGER NOT NULL REFERENCES products(product_id),
            warehouse_location TEXT NOT NULL,
            stock_quantity     INTEGER NOT NULL
        );

        CREATE TABLE orders (
            order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
            order_date    TEXT NOT NULL,
            status        TEXT NOT NULL
        );

        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id      INTEGER NOT NULL REFERENCES orders(order_id),
            product_id    INTEGER NOT NULL REFERENCES products(product_id),
            quantity      INTEGER NOT NULL,
            unit_price    REAL NOT NULL
        );

        CREATE TABLE suppliers (
            supplier_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            contact_email  TEXT NOT NULL,
            phone          TEXT NOT NULL,
            city           TEXT NOT NULL,
            supply_category TEXT NOT NULL
        );

        CREATE TABLE reviews (
            review_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id    INTEGER NOT NULL REFERENCES products(product_id),
            customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
            rating        INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            review_text   TEXT,
            review_date   TEXT NOT NULL
        );

        CREATE TABLE payments (
            payment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id      INTEGER NOT NULL REFERENCES orders(order_id),
            payment_method TEXT NOT NULL,
            amount         REAL NOT NULL,
            payment_date   TEXT NOT NULL,
            transaction_id TEXT NOT NULL UNIQUE
        );

        CREATE TABLE shipping (
            shipping_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id      INTEGER NOT NULL REFERENCES orders(order_id),
            address       TEXT NOT NULL,
            city          TEXT NOT NULL,
            pincode       TEXT NOT NULL,
            shipped_date  TEXT,
            delivered_date TEXT,
            carrier       TEXT NOT NULL
        );
    """)


def seed_data(cur: sqlite3.Cursor) -> None:
    random.seed(42)
    today = datetime.today()
    start_date = today - timedelta(days=730)

    num_customers = len(CUSTOMER_NAMES)
    num_products = len(PRODUCT_CATALOG)
    num_suppliers = len(SUPPLIERS)

    for i, name in enumerate(CUSTOMER_NAMES, start=1):
        email = name.lower().replace(" ", ".") + f".{i:03d}@email.com"
        city = random.choice(CITIES)
        signup_date = (start_date + timedelta(days=random.randint(0, 730))).date().isoformat()
        cur.execute(
            "INSERT INTO customers (name, email, city, signup_date) VALUES (?, ?, ?, ?)",
            (name, email, city, signup_date),
        )

    for name, category, price, cost in PRODUCT_CATALOG:
        cur.execute(
            "INSERT INTO products (name, category, price, cost) VALUES (?, ?, ?, ?)",
            (name, category, price, cost),
        )

    for i, name in enumerate(SUPPLIERS, start=1):
        email = name.lower().replace(" ", ".").replace("&", "and").replace("'", "") + "@supply.com"
        phone = f"+91-{random.randint(70000, 99999)}-{random.randint(10000, 99999)}"
        city = random.choice(CITIES)
        cat = random.choice(["Electronics", "Furniture", "Home", "Grocery", "Fashion", "Sports", "Toys", "Books", "Mixed"])
        cur.execute(
            "INSERT INTO suppliers (name, contact_email, phone, city, supply_category) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, city, cat),
        )

    for pid in range(1, num_products + 1):
        for wh in random.sample(WAREHOUSES, k=random.randint(2, 4)):
            cur.execute(
                "INSERT INTO inventory (product_id, warehouse_location, stock_quantity) VALUES (?, ?, ?)",
                (pid, wh, random.randint(0, 500)),
            )

    order_count = 2000
    order_id_counter = 1
    for _ in range(order_count):
        customer_id = random.randint(1, num_customers)
        days_ago = random.randint(0, 730)
        order_date = (today - timedelta(days=days_ago)).date().isoformat()
        status = random.choices(ORDER_STATUSES, weights=ORDER_STATUS_WEIGHTS)[0]
        cur.execute(
            "INSERT INTO orders (customer_id, order_date, status) VALUES (?, ?, ?)",
            (customer_id, order_date, status),
        )
        order_id = cur.lastrowid

        for _ in range(random.randint(1, 5)):
            product_id = random.randint(1, num_products)
            price = PRODUCT_CATALOG[product_id - 1][2]
            quantity = random.choices([1, 2, 3], weights=[60, 30, 10])[0]
            final_price = round(price * random.choice([1.0, 1.0, 0.9, 0.8, 0.85]), 2)
            cur.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (order_id, product_id, quantity, final_price),
            )

    review_texts = [
        "Great product! Very satisfied with the quality.",
        "Good value for money. Would recommend.",
        "Decent quality but packaging could be better.",
        "Exceeded my expectations! Will buy again.",
        "Not bad for the price. Works as described.",
        "Amazing quality! Fast delivery too.",
        "Average product. Nothing special.",
        "Exactly what I needed. Perfect!",
        "A bit overpriced but good quality.",
        "Love it! Bought as a gift and they loved it.",
        "Great quality for the price point.",
        "Would have given 5 stars but delivery was delayed.",
        "Excellent craftsmanship and material.",
        "Just okay. Not worth the hype.",
        "Perfect! Exactly as described in the listing.",
    ]
    cur.execute("SELECT order_id FROM orders WHERE status = 'DELIVERED' ORDER BY RANDOM() LIMIT 500")
    delivered_orders = [r[0] for r in cur.fetchall()]
    for oid in delivered_orders:
        cur.execute("SELECT product_id FROM order_items WHERE order_id = ? ORDER BY RANDOM() LIMIT 1", (oid,))
        item = cur.fetchone()
        if item:
            pid = item[0]
            cid = random.randint(1, num_customers)
            rating = random.choices([5, 4, 3, 2, 1], weights=[40, 30, 15, 10, 5])[0]
            text = random.choice(review_texts)
            rdate = (today - timedelta(days=random.randint(0, 700))).date().isoformat()
            cur.execute(
                "INSERT INTO reviews (product_id, customer_id, rating, review_text, review_date) VALUES (?, ?, ?, ?, ?)",
                (pid, cid, rating, text, rdate),
            )

    cur.execute("SELECT order_id, order_date FROM orders WHERE status != 'CANCELLED'")
    for row in cur.fetchall():
        oid = row[0]
        odate = row[1]
        method = random.choice(PAYMENT_METHODS)
        cur.execute("SELECT SUM(quantity * unit_price) FROM order_items WHERE order_id = ?", (oid,))
        total = cur.fetchone()[0] or 0
        tid = _transaction_id()
        cur.execute(
            "INSERT INTO payments (order_id, payment_method, amount, payment_date, transaction_id) VALUES (?, ?, ?, ?, ?)",
            (oid, method, round(total, 2), odate, tid),
        )

    addresses = [
        "42 MG Road, {city}, {pincode}",
        "7/2 Ashok Nagar, {city}, {pincode}",
        "Plot 15 Sector 4, {city}, {pincode}",
        "#88 Indiranagar 2nd Stage, {city}, {pincode}",
        "12B Lake View Apartments, {city}, {pincode}",
        "55 Bazaar Street, {city}, {pincode}",
        "201 Sunshine Colony, {city}, {pincode}",
        "9 Commercial Avenue, {city}, {pincode}",
    ]
    cur.execute("SELECT o.order_id, o.order_date, o.status FROM orders o WHERE o.status NOT IN ('CANCELLED', 'PLACED')")
    for row in cur.fetchall():
        oid, odate, status = row
        city = random.choice(CITIES)
        pincode = f"{random.randint(100000, 999999)}"
        addr = random.choice(addresses).format(city=city, pincode=pincode)
        carrier = random.choice(SHIPPING_CARRIERS)
        shipped_date = None
        delivered_date = None
        if status in ("SHIPPED", "DELIVERED"):
            shipped = datetime.fromisoformat(odate) + timedelta(days=random.randint(1, 3))
            shipped_date = shipped.date().isoformat()
        if status == "DELIVERED":
            delivered = datetime.fromisoformat(odate) + timedelta(days=random.randint(4, 10))
            delivered_date = delivered.date().isoformat()
        cur.execute(
            "INSERT INTO shipping (order_id, address, city, pincode, shipped_date, delivered_date, carrier) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (oid, addr, city, pincode, shipped_date, delivered_date, carrier),
        )


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    build_schema(cur)
    seed_data(cur)
    conn.commit()

    counts = {}
    for table in [
        "customers", "products", "inventory", "orders", "order_items",
        "suppliers", "reviews", "payments", "shipping",
    ]:
        counts[table] = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()

    print(f"Database created: {DB_PATH}")
    print("Row counts:")
    for k, v in counts.items():
        print(f"  {k:20s} -> {v:>6d} rows")
    print(f"\n  TOTAL         -> {sum(counts.values()):>6d} rows")


if __name__ == "__main__":
    main()
