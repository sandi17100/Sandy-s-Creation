import sqlite3
from werkzeug.security import generate_password_hash
import json

DB_NAME = "ecommerce.db"


# ---------------- INIT DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # PRODUCTS TABLE (FIXED)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            image TEXT,
            images TEXT,
            stock INTEGER DEFAULT 0
        )
    ''')

    # ADMINS TABLE
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # ORDERS TABLE
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            address TEXT NOT NULL,
            items TEXT NOT NULL,
            total REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ---------------- SAMPLE PRODUCTS ----------------
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:

        sample_products = [
            (
                "iPhone 15 Pro",
                "Latest iPhone with A17 Pro chip",
                999.99,
                "iphone.jpg",
                json.dumps(["iphone1.jpg", "iphone2.jpg"]),
                50
            ),
            (
                "MacBook Air M2",
                "13-inch MacBook Air",
                1199.99,
                "macbook.jpg",
                json.dumps(["mac1.jpg", "mac2.jpg"]),
                30
            )
        ]

        cursor.executemany('''
            INSERT INTO products (name, description, price, image, images, stock)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_products)

    # ---------------- DEFAULT ADMIN ----------------
    cursor.execute("SELECT COUNT(*) FROM admins")
    if cursor.fetchone()[0] == 0:
        hashed = generate_password_hash("admin123")
        cursor.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            ("admin", hashed)
        )

    conn.commit()
    conn.close()


# ---------------- GET PRODUCTS ----------------
def get_products():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


# ---------------- GET SINGLE PRODUCT (FIXED IMAGES) ----------------
def get_product(product_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id=?", (product_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    product = list(row)

    # FIX: images column safe parsing
    try:
        product[5] = json.loads(product[5]) if product[5] else []
    except:
        product[5] = []

    return product


# ---------------- ADD PRODUCT (MULTI IMAGE FIXED) ----------------
def add_product(name, description, price, image, images, stock):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO products (name, description, price, image, images, stock)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        name,
        description,
        float(price),
        image,
        json.dumps(images),
        stock
    ))

    conn.commit()
    conn.close()


# ---------------- UPDATE PRODUCT (FIXED + IMAGES SUPPORT) ----------------
def update_product(product_id, name, description, price, image, images, stock):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE products
        SET name=?, description=?, price=?, image=?, images=?, stock=?
        WHERE id=?
    ''', (
        name,
        description,
        float(price),
        image,
        json.dumps(images),
        stock,
        product_id
    ))

    conn.commit()
    conn.close()


# ---------------- DELETE PRODUCT ----------------
def delete_product(product_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()


# ---------------- ORDERS ----------------
def save_order(name, email, address, phone, cart_json, total):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO orders (name, email, phone, address, items, total)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, email, phone, address, cart_json, float(total)))

    conn.commit()
    conn.close()


def get_all_orders():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
    orders = cursor.fetchall()
    conn.close()
    return orders