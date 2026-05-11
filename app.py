from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
from datetime import datetime
from supabase import create_client

SUPABASE_URL = os.environ.get("https://wykfmuslixwlfkybwqkz.supabase.co")
SUPABASE_KEY = os.environ.get("sb_secret_ZNX9p6n9wRTfpQ98jipYfg_yuD3gaVR")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# ---------------- APP INIT ----------------
app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise Exception("SECRET_KEY must be set in environment variables")

# ---------------- CONFIG ----------------
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"

# ---------------- SUPABASE DATABASE ----------------
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL is not set (Supabase Postgres required)")


def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor,
        connect_timeout=10
    )


# ---------------- HELPERS ----------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------- DATABASE INIT (SUPABASE READY) ----------------
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # PRODUCTS (FIXED FOR SUPABASE)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT,
            images JSONB,
            stock INTEGER DEFAULT 0,
            category TEXT DEFAULT 'amigurumi',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ORDERS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            address TEXT NOT NULL,
            items JSONB NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ADMINS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # DEFAULT ADMIN (SAFE)
    cursor.execute("SELECT COUNT(*) AS count FROM admins")
    admin_count = cursor.fetchone()["count"]

    if admin_count == 0:
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if not admin_password:
            raise Exception("ADMIN_PASSWORD not set in environment variables")

        pwd_hash = generate_password_hash(admin_password)

        cursor.execute("""
            INSERT INTO admins (username, password_hash)
            VALUES (%s, %s)
        """, ("sandy", pwd_hash))

    conn.commit()
    cursor.close()
    conn.close()
# ---------------- MODELS ----------------
class AdminUser(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


# ---------------- USER LOADER ----------------
@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username FROM admins WHERE id = %s",
            (user_id,)
        )

        user = cursor.fetchone()

        if user:
            return AdminUser(user["id"], user["username"])

        return None

    finally:
        cursor.close()
        conn.close()


# ---------------- PRODUCT QUERIES ----------------
def get_products():
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM products
            WHERE stock > 0
            ORDER BY created_at DESC
        """)

        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def get_all_products():
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM products
            ORDER BY created_at DESC
        """)

        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def get_product(product_id):
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM products WHERE id = %s",
            (product_id,)
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        conn.close()


# ---------------- ORDER QUERIES ----------------
def get_order_by_id(order_id):
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM orders WHERE id = %s",
            (order_id,)
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        conn.close()


def get_all_orders():
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM orders
            ORDER BY created_at DESC
        """)

        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


# ---------------- INSERT PRODUCT (SUPABASE SAFE) ----------------
def add_product(name, description, price, image, images, stock, category="amigurumi"):
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO products
            (name, description, price, image, images, stock, category)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            name,
            description,
            float(price),
            image,
            json.dumps(images) if images else None,
            int(stock),
            category
        ))

        conn.commit()

    finally:
        cursor.close()
        conn.close()


# ---------------- UPDATE PRODUCT ----------------
def update_product(product_id, name, description, price, image, stock):
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE products
            SET name=%s,
                description=%s,
                price=%s,
                image=%s,
                stock=%s
            WHERE id=%s
        """, (
            name,
            description,
            float(price),
            image,
            int(stock),
            product_id
        ))

        conn.commit()

    finally:
        cursor.close()
        conn.close()


# ---------------- DELETE PRODUCT ----------------
def delete_product(product_id):
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM products WHERE id=%s",
            (product_id,)
        )

        conn.commit()

    finally:
        cursor.close()
        conn.close()


# ---------------- SAVE ORDER (SUPABASE JSONB SAFE) ----------------
def save_order(name, email, phone, address, items_json, total):
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO orders
            (name, email, phone, address, items, total)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            name,
            email,
            phone,
            address,
            json.dumps(items_json) if isinstance(items_json, list) else items_json,
            float(total)
        ))

        order_id = cursor.fetchone()["id"]

        conn.commit()
        return order_id

    finally:
        cursor.close()
        conn.close()


# ---------------- ORDER STATUS ----------------
def update_order_status(order_id, status):
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE orders
            SET status = %s
            WHERE id = %s
        """, (status, order_id))

        conn.commit()

    finally:
        cursor.close()
        conn.close()
# ---------------- CART FUNCTIONS ----------------
def add_item_to_cart(product_id):
    product = get_product(product_id)

    if not product or product["stock"] <= 0:
        return False

    cart = session.get("cart", [])
    product_id = int(product_id)

    for item in cart:
        if int(item["id"]) == product_id:

            if item["quantity"] < product["stock"]:
                item["quantity"] += 1

            session["cart"] = cart
            session.modified = True
            return True

    cart.append({
        "id": product_id,
        "name": product["name"],
        "price": float(product["price"]),
        "quantity": 1,
        "image": product.get("image")
    })

    session["cart"] = cart
    session.modified = True
    return True


# ---------------- UPDATE CART ----------------
def update_cart_quantity(product_id, quantity):
    cart = session.get("cart", [])
    product_id = int(product_id)

    try:
        quantity = int(quantity)
    except:
        quantity = 0

    updated_cart = []

    for item in cart:
        if int(item["id"]) == product_id:
            item["quantity"] = quantity

        if item["quantity"] > 0:
            updated_cart.append(item)

    session["cart"] = updated_cart
    session.modified = True


# ---------------- TOTAL CALCULATION ----------------
def calculate_cart_total(cart):
    if not cart:
        return 0.0

    return float(
        sum(float(item["price"]) * int(item["quantity"]) for item in cart)
    )


# ---------------- ROUTES ----------------

@app.route("/")
def index():
    products = get_products()
    return render_template("index.html", products=products)


# ---------------- PRODUCT PAGE ----------------
@app.route("/product/<int:product_id>")
def product(product_id):
    product = get_product(product_id)

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("index"))

    product = dict(product)

    # SAFE JSON HANDLING (Supabase JSONB ready)
    product_images = product.get("images")

    if product_images:
        try:
            product["images"] = json.loads(product_images)
        except:
            product["images"] = []
    else:
        product["images"] = []

    return render_template("product.html", product=product)


# ---------------- CART ROUTES ----------------
@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):
    if add_item_to_cart(product_id):
        flash("Added to cart! 🧶", "success")
    else:
        flash("Product not available", "error")

    return redirect(request.referrer or url_for("cart"))


@app.route("/cart")
def cart():
    cart_items = session.get("cart", [])
    total = calculate_cart_total(cart_items)

    return render_template("cart.html", cart=cart_items, total=total)


@app.route("/update_cart/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    quantity = request.form.get("quantity", 0)
    update_cart_quantity(product_id, quantity)

    flash("Cart updated!", "info")
    return redirect(url_for("cart"))


@app.route("/remove_from_cart/<int:product_id>")
def remove_from_cart(product_id):
    cart = session.get("cart", [])
    product_id = int(product_id)

    session["cart"] = [
        item for item in cart
        if int(item["id"]) != product_id
    ]

    session.modified = True

    flash("Item removed", "info")
    return redirect(url_for("cart"))


# ---------------- CHECKOUT ----------------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart_items = session.get("cart", [])

    if not cart_items:
        flash("Your cart is empty", "warning")
        return redirect(url_for("index"))

    total = calculate_cart_total(cart_items)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not all([name, email, address]):
            flash("Please fill all required fields", "error")
            return render_template("checkout.html", cart=cart_items, total=total)

        if phone and not phone.startswith(("09", "+959")):
            flash("Invalid Myanmar phone number", "error")
            return render_template("checkout.html", cart=cart_items, total=total)

        # SAFE JSON FOR SUPABASE JSONB
        items_json = json.dumps(cart_items)

        order_id = save_order(
            name,
            email,
            phone,
            address,
            items_json,
            total
        )

        session.pop("cart", None)

        flash(
            f"🎉 Order placed successfully! Order ID #{order_id}",
            "success"
        )

        return redirect(url_for("track_order", order_id=order_id))

    return render_template("checkout.html", cart=cart_items, total=total)
# ---------------- ADMIN ROUTES ----------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM admins WHERE username = %s",
                (username,)
            )

            admin = cursor.fetchone()

        finally:
            cursor.close()
            conn.close()

        if admin and check_password_hash(admin["password_hash"], password):
            login_user(AdminUser(admin["id"], admin["username"]))
            flash("Welcome back, Sandy! 👋", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password", "error")

    return render_template("admin_login.html")


# ---------------- LOGOUT ----------------
@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    flash("Logged out successfully", "info")
    return redirect(url_for("index"))


# ---------------- DASHBOARD ----------------
@app.route("/admin")
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    orders = get_all_orders()
    products = get_all_products()

    total_revenue = sum(float(o["total"]) for o in orders)

    return render_template(
        "admin_dashboard.html",
        orders=orders,
        products=products,
        total_revenue=total_revenue,
        order_count=len(orders)
    )


# ---------------- PRODUCTS ----------------
@app.route("/admin/products")
@login_required
def admin_products():
    return render_template(
        "admin_products.html",
        products=get_all_products()
    )


# ---------------- ADD PRODUCT (SUPABASE READY STRUCTURE) ----------------
@app.route("/admin/products/add", methods=["GET", "POST"])
@login_required
def admin_add_product():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "0")
        stock = request.form.get("stock", "0")
        category = request.form.get("category", "amigurumi")

        if not all([name, description, price, stock]):
            flash("Please fill all required fields!", "error")
            return render_template("admin_add_product.html")

        # Supabase Storage သို့ Upload တင်ခြင်း
        uploaded_files = request.files.getlist("images")
        image_urls = []

        for file in uploaded_files:
            if file and file.filename:
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S%f')}_{filename}"
                    
                    file_data = file.read()
                    
                    # Supabase Storage သို့ ပို့မယ်
                    supabase.storage.from_("crochet-bucket").upload(
                        path=unique_filename,
                        file=file_data,
                        file_options={"content-type": file.content_type}
                    )
                    
                    # Public URL ယူမယ်
                    res = supabase.storage.from_("crochet-bucket").get_public_url(unique_filename)
                    image_urls.append(res)

        # ပထမဆုံးပုံကို main image အဖြစ်သုံးမယ်
        main_image_url = image_urls[0] if image_urls else None

        # Database ထဲ ထည့်မယ်
        add_product(
            name,
            description,
            price,
            main_image_url, # image column
            image_urls,     # images (JSONB) column
            stock,
            category
        )

        flash(f"✅ {name} added successfully!", "success")
        return redirect(url_for("admin_products"))

    return render_template("admin_add_product.html")

# ---------------- EDIT PRODUCT ----------------
@app.route("/admin/products/<int:product_id>/edit", methods=["POST"])
@login_required
def admin_update_product(product_id):
    product = get_product(product_id)

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("admin_products"))

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price = request.form.get("price", "0")
    stock = request.form.get("stock", "0")

    # ပုံအသစ်တင်ရင် Supabase သို့ ပို့မယ်၊ မတင်ရင် အဟောင်းအတိုင်းထားမယ်
    uploaded_file = request.files.get("image")
    image_url = product["image"]

    if uploaded_file and uploaded_file.filename:
        if allowed_file(uploaded_file.filename):
            filename = secure_filename(uploaded_file.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S%f')}_{filename}"
            
            file_data = uploaded_file.read()
            supabase.storage.from_("crochet-bucket").upload(
                path=unique_filename,
                file=file_data,
                file_options={"content-type": uploaded_file.content_type}
            )
            image_url = supabase.storage.from_("crochet-bucket").get_public_url(unique_filename)

    update_product(product_id, name, description, price, image_url, stock)

    flash(f"✅ {name} updated successfully!", "success")
    return redirect(url_for("admin_products"))

# ---------------- DELETE PRODUCT ----------------
@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
@login_required
def admin_delete_product(product_id):
    product = get_product(product_id)

    if not product:
        return jsonify({"success": False, "message": "Product not found"}), 404

    # delete local image (TEMP system)
    if product.get("image"):
        image_path = os.path.join(
            app.root_path,
            app.config["UPLOAD_FOLDER"],
            product["image"]
        )

        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                app.logger.warning(f"Image delete failed: {e}")

    delete_product(product_id)

    return jsonify({"success": True})


# ---------------- ADMIN ORDERS ----------------
@app.route("/admin/orders")
@login_required
def admin_orders():
    orders = get_all_orders()
    return render_template(
        "admin_orders.html",
        orders=orders,
        single_order=False
    )


@app.route("/admin/orders/<int:order_id>")
@login_required
def admin_order_detail(order_id):
    order = get_order_by_id(order_id)

    if not order:
        flash("Order not found", "danger")
        return redirect(url_for("admin_orders"))

    try:
        order_items = json.loads(order["items"])
    except Exception:
        order_items = []

    return render_template(
        "admin_orders.html",
        order=order,
        order_items=order_items,
        single_order=True
    )


@app.route("/admin/orders/update_status/<int:order_id>", methods=["POST"])
@login_required
def admin_update_order_status(order_id):
    new_status = request.form.get("status")

    valid_status = ["pending", "paid", "processing", "delivered", "cancelled"]

    if new_status not in valid_status:
        flash("Invalid status!", "danger")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    update_order_status(order_id, new_status)

    flash("Order status updated successfully!", "success")
    return redirect(url_for("admin_order_detail", order_id=order_id))


# ---------------- TRACK ORDER SEARCH ----------------
@app.route("/track-order", methods=["GET", "POST"])
def track_order_search():
    if request.method == "POST":
        order_id = request.form.get("order_id")
        email = request.form.get("email")

        try:
            order_id = int(order_id)
        except (ValueError, TypeError):
            flash("Invalid Order ID", "error")
            return render_template("track_order_search.html")

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM orders
                WHERE id = %s AND email = %s
                """,
                (order_id, email)
            )
            order = cursor.fetchone()

        finally:
            cursor.close()
            conn.close()

        if order:
            return redirect(url_for("track_order", order_id=order_id))
        else:
            flash("Order not found. Please check Order ID and Email.", "error")

    return render_template("track_order_search.html")


# ---------------- TRACK ORDER PAGE ----------------
@app.route("/track-order/<int:order_id>")
def track_order(order_id):
    order = get_order_by_id(order_id)

    if not order:
        flash("Order not found", "error")
        return redirect(url_for("index"))

    try:
        order_items = json.loads(order["items"])
    except Exception:
        order_items = []

    return render_template(
        "track_order.html",
        order=order,
        order_items=order_items
    )


# ---------------- MAIN ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=6050)
