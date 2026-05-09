from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os
from datetime import datetime


app = Flask(__name__)
app.secret_key = os.environ.get(
    'SECRET_KEY',
    'sandy-crochet-2026-super-secret-key-change-production!'
)

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"


# ---------------- FILE UPLOAD HELPERS ----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------- DATABASE ----------------
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db():
    conn = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )
    return conn


def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price REAL NOT NULL,
                image TEXT,
                images TEXT,
                stock INTEGER DEFAULT 0,
                category TEXT DEFAULT 'amigurumi',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                address TEXT NOT NULL,
                items TEXT NOT NULL,
                total REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Admins table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default admin if not exists
        cursor.execute("SELECT COUNT(*) AS count FROM admins")
        admin_count = cursor.fetchone()["count"]

        if admin_count == 0:
            pwd_hash = generate_password_hash('crochet123')
            cursor.execute(
                """
                INSERT INTO admins (username, password_hash)
                VALUES (%s, %s)
                """,
                ('sandy', pwd_hash)
            )

        db.commit()
        cursor.close()
        db.close()
# ---------------- MODELS ----------------
class AdminUser(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, username FROM admins WHERE id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user:
        return AdminUser(user['id'], user['username'])
    return None


def get_products():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM products WHERE stock > 0 ORDER BY created_at DESC"
    )
    products = cursor.fetchall()

    cursor.close()
    conn.close()
    return products


def get_all_products():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM products ORDER BY created_at DESC"
    )
    products = cursor.fetchall()

    cursor.close()
    conn.close()
    return products


def get_order_by_id(order_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM orders WHERE id = %s",
        (order_id,)
    )
    order = cursor.fetchone()

    cursor.close()
    conn.close()
    return order


def get_product(product_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM products WHERE id = %s",
        (product_id,)
    )
    product = cursor.fetchone()

    cursor.close()
    conn.close()
    return product


def add_product(name, description, price, image, images, stock, category='amigurumi'):
    conn = get_db()
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
        json.dumps(images),
        stock,
        category
    ))

    conn.commit()
    cursor.close()
    conn.close()


def update_product(product_id, name, description, price, image, stock):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE products
        SET name=%s, description=%s, price=%s, image=%s, stock=%s
        WHERE id=%s
    """, (
        name,
        description,
        float(price),
        image,
        stock,
        product_id
    ))

    conn.commit()
    cursor.close()
    conn.close()


def delete_product(product_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM products WHERE id=%s",
        (product_id,)
    )

    conn.commit()
    cursor.close()
    conn.close()


def save_order(name, email, phone, address, items_json, total):
    conn = get_db()
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
        items_json,
        float(total)
    ))

    order_id = cursor.fetchone()["id"]

    conn.commit()
    cursor.close()
    conn.close()
    return order_id


def get_all_orders():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM orders ORDER BY created_at DESC"
    )
    orders = cursor.fetchall()

    cursor.close()
    conn.close()
    return orders


def update_order_status(order_id, status):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE orders SET status = %s WHERE id = %s",
        (status, order_id)
    )

    conn.commit()
    cursor.close()
    conn.close()
# ---------------- CART FUNCTIONS ----------------
def add_item_to_cart(product_id):
    product = get_product(product_id)

    if not product or product['stock'] <= 0:
        return False

    cart = session.get("cart", [])

    for item in cart:
        if item["id"] == product_id:
            if item["quantity"] < product['stock']:
                item["quantity"] += 1
            session["cart"] = cart
            return True

    cart.append({
        "id": product_id,
        "name": product['name'],
        "price": float(product['price']),
        "quantity": 1,
        "image": product['image']
    })

    session["cart"] = cart
    return True


def update_cart_quantity(product_id, quantity):
    cart = session.get("cart", [])

    for item in cart:
        if item["id"] == product_id:
            item["quantity"] = int(quantity)
            break

    session["cart"] = [
        item for item in cart
        if item["quantity"] > 0
    ]


def calculate_cart_total(cart):
    if not cart:
        return 0.0

    return float(
        sum(float(item["price"]) * item["quantity"] for item in cart)
    )
# ---------------- ROUTES ----------------
@app.route("/")
def index():
    products = get_products()
    return render_template("index.html", products=products)


@app.route("/product/<int:product_id>")
def product(product_id):
    product = get_product(product_id)

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("index"))

    product = dict(product)

    product_images = product.get("images")

    if product_images:
        try:
            product["images"] = json.loads(product_images)
        except:
            product["images"] = product_images.split(",")
    else:
        product["images"] = []

    return render_template("product.html", product=product)


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
    quantity = int(request.form.get("quantity", 0))
    update_cart_quantity(product_id, quantity)

    flash("Cart updated!", "info")
    return redirect(url_for("cart"))


@app.route("/remove_from_cart/<int:product_id>")
def remove_from_cart(product_id):
    cart = session.get("cart", [])

    session["cart"] = [
        item for item in cart
        if item["id"] != product_id
    ]

    flash("Item removed", "info")
    return redirect(url_for("cart"))


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
            flash("Please enter valid Myanmar phone number (09xxxxxxxxx)", "error")
            return render_template("checkout.html", cart=cart_items, total=total)

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
            f"🎉 Order placed successfully! Your Order ID is #{order_id}",
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
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM admins WHERE username = %s",
            (username,)
        )
        admin = cursor.fetchone()

        cursor.close()
        conn.close()

        if admin and check_password_hash(admin['password_hash'], password):
            login_user(AdminUser(admin['id'], admin['username']))
            flash("Welcome back, Sandy! 👋", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password", "error")

    return render_template("admin_login.html")


@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    flash("Logged out successfully", "info")
    return redirect(url_for("index"))


@app.route("/admin")
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    orders = get_all_orders()
    products = get_all_products()

    total_revenue = sum(float(order['total']) for order in orders)

    return render_template(
        "admin_dashboard.html",
        orders=orders,
        products=products,
        total_revenue=total_revenue,
        order_count=len(orders)
    )


@app.route("/admin/products")
@login_required
def admin_products():
    products = get_all_products()
    return render_template("admin_products.html", products=products)


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

        try:
            price = float(price)
            stock = int(stock)
        except ValueError:
            flash("Price and stock must be valid numbers!", "error")
            return render_template("admin_add_product.html")

        uploaded_files = request.files.getlist('images')
        image_filenames = []

        for file in uploaded_files:
            if file.filename != '':
                if allowed_file(file.filename):
                    os.makedirs(
                        os.path.join(app.root_path, app.config['UPLOAD_FOLDER']),
                        exist_ok=True
                    )

                    filename = secure_filename(file.filename)
                    unique_filename = f"sandy_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}_{filename}"

                    file.save(
                        os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], unique_filename)
                    )

                    image_filenames.append(unique_filename)
                else:
                    flash("Only JPG, PNG, GIF, WebP files allowed!", "error")
                    return render_template("admin_add_product.html")

        main_image = image_filenames[0] if image_filenames else None

        add_product(name, description, price, main_image, image_filenames, stock, category)

        flash(f"✅ {name} added successfully!", "success")
        return redirect(url_for("admin_products"))

    return render_template("admin_add_product.html")


@app.route('/admin/products/<int:product_id>/edit')
@login_required
def admin_edit_product(product_id):
    product = get_product(product_id)

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("admin_products"))

    return render_template('admin_edit_product.html', product=product)


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
    category = request.form.get("category", "amigurumi")

    if not all([name, description, price, stock]):
        flash("Please fill all required fields!", "error")
        return render_template('admin_edit_product.html', product=product)

    try:
        price = float(price)
        stock = int(stock)
    except ValueError:
        flash("Price and stock must be valid numbers!", "error")
        return render_template('admin_edit_product.html', product=product)

    uploaded_file = request.files.get('image')
    image_filename = product['image']

    if uploaded_file and uploaded_file.filename != '':
        if allowed_file(uploaded_file.filename):
            if product['image']:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], product['image'])
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except:
                        pass

            os.makedirs(
                os.path.join(app.root_path, app.config['UPLOAD_FOLDER']),
                exist_ok=True
            )

            filename = secure_filename(uploaded_file.filename)
            unique_filename = f"sandy_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}_{filename}"

            uploaded_file.save(
                os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], unique_filename)
            )

            image_filename = unique_filename
        else:
            flash("Only JPG, PNG, GIF, WebP files allowed!", "error")
            return render_template('admin_edit_product.html', product=product)

    update_product(product_id, name, description, price, image_filename, stock)

    flash(f"✅ {name} updated successfully!", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
@login_required
def admin_delete_product(product_id):
    product = get_product(product_id)

    if not product:
        return jsonify({"success": False, "message": "Product not found"}), 404

    if product['image']:
        image_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], product['image'])

        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                app.logger.warning(f"Image delete failed: {e}")

    delete_product(product_id)

    return jsonify({"success": True})


@app.route("/admin/orders")
@login_required
def admin_orders():
    orders = get_all_orders()
    return render_template("admin_orders.html", orders=orders, single_order=False)


@app.route("/admin/orders/<int:order_id>")
@login_required
def admin_order_detail(order_id):
    order = get_order_by_id(order_id)

    if not order:
        flash("Order not found", "danger")
        return redirect(url_for("admin_orders"))

    order_items = json.loads(order["items"])

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

    if new_status not in ["pending", "paid", "processing", "delivered", "cancelled"]:
        flash("Invalid status!", "danger")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    update_order_status(order_id, new_status)

    flash("Order status updated successfully!", "success")
    return redirect(url_for("admin_order_detail", order_id=order_id))


@app.route("/track-order", methods=["GET", "POST"])
def track_order_search():
    if request.method == "POST":
        order_id = request.form.get("order_id")
        email = request.form.get("email")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM orders WHERE id = %s AND email = %s",
            (order_id, email)
        )

        order = cursor.fetchone()

        cursor.close()
        conn.close()

        if order:
            return redirect(url_for("track_order", order_id=order_id))
        else:
            flash("Order not found. Please check Order ID and Email.", "error")

    return render_template("track_order_search.html")


@app.route("/track-order/<int:order_id>")
def track_order(order_id):
    order = get_order_by_id(order_id)

    if not order:
        flash("Order not found", "error")
        return redirect(url_for("index"))

    order_items = json.loads(order["items"])

    return render_template(
        "track_order.html",
        order=order,
        order_items=order_items
    )


if __name__ == "__main__":
    init_db()

    # ❌ REMOVED: SQLite PRAGMA (Postgres doesn't support it)

    app.run(debug=True, host='0.0.0.0', port=6050)