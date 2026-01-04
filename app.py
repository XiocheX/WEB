import os
import random
import string
from datetime import datetime

from flask import Flask, render_template, request, jsonify, abort
import psycopg2

app = Flask(__name__)

# ====================== CONFIG ======================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set!")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# ====================== ORDER ID GENERATOR ======================
def generate_order_id():
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    date_str = datetime.now().strftime("%d%m%y")
    return f"W-{random_part}-{date_str}"

# ====================== ROUTES ======================
@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, price, currency, description FROM products ORDER BY id")
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', products=products)

@app.route('/create-order', methods=['POST'])
def create_order():
    data = request.json
    product_id = data.get('product_id')
    if not product_id:
        abort(400, "Missing product_id")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, price, currency FROM products WHERE id = %s", (product_id,))
    product = cur.fetchone()
    if not product:
        cur.close()
        conn.close()
        abort(404, "Product not found")

    name, price, currency = product

    order_id = generate_order_id()

    cur.execute("""
        INSERT INTO orders (product_id, quantity, total_amount, user_identifier, order_status, order_id)
        VALUES (%s, 1, %s, %s, 'pending', %s)
        RETURNING id
    """, (product_id, price, order_id, order_id))  # user_identifier = order_id for web
    db_order_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        'order_id': order_id,
        'product_name': name,
        'price': price,
        'currency': currency
    })

@app.route('/order-status/<order_id>')
def order_status(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT order_status, paid_at, product_id 
        FROM orders 
        WHERE order_id = %s
    """, (order_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({'error': 'Order not found'}), 404

    status, paid_at, product_id = row
    return jsonify({
        'status': status,
        'paid': paid_at is not None,
        'product_id': product_id
    })

# For now, delivery submit just logs (later POST to bot)
@app.route('/submit-delivery', methods=['POST'])
def submit_delivery():
    data = request.json
    logger.info(f"Delivery submit from web: {data}")
    # TODO: POST to bot webhook or Telegram API
    return jsonify({'success': True, 'message': 'Delivery request sent'})

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)