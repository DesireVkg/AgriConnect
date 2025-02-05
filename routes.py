import os
import stripe
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from flask_socketio import emit, join_room, leave_room
from app import db, login_manager, socketio
from models import User, Product, Message, Order
from datetime import datetime
from sqlalchemy import and_, or_, desc
from sqlalchemy.orm import aliased

# Configure Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Blueprint definitions
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
main_bp = Blueprint('main', __name__)
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')
products_bp = Blueprint('products', __name__, url_prefix='/products')
chat_bp = Blueprint('chat', __name__, url_prefix='/chat')
orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

# Create upload folder if it doesn't exist
UPLOAD_FOLDER = 'static/uploads/products'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# Auth routes
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        phone = request.form.get('phone')
        address = request.form.get('address')

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists')
            return redirect(url_for('auth.register'))

        new_user = User(
            username=username,
            email=email,
            user_type=user_type,
            phone=phone,
            address=address
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard.index'))
            
        flash('Invalid email or password')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

# Main routes
@main_bp.route('/')
def index():
    products = Product.query.order_by(Product.created_at.desc()).limit(6).all()
    return render_template('index.html', products=products)

# Dashboard routes
@dashboard_bp.route('/')
@login_required
def index():
    if current_user.user_type == 'farmer':
        return render_template('dashboard/farmer.html')
    return render_template('dashboard/merchant.html')

# Product routes
@products_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        # Handle file upload
        if 'product_image' not in request.files:
            flash('No file uploaded')
            return redirect(request.url)

        file = request.files['product_image']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to filename to make it unique
            filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            # Create product with image URL
            product = Product(
                name=request.form.get('name'),
                description=request.form.get('description'),
                price=float(request.form.get('price')),
                quantity=float(request.form.get('quantity')),
                unit=request.form.get('unit'),
                location=request.form.get('location'),
                latitude=float(request.form.get('latitude')),
                longitude=float(request.form.get('longitude')),
                user_id=current_user.id,
                image_url=os.path.join('uploads/products', filename)
            )
            db.session.add(product)
            db.session.commit()
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid file type')
            return redirect(request.url)

    return render_template('products/create.html')

@products_bp.route('/')
def list():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('products/list.html', products=products)

@products_bp.route('/<int:id>')
def detail(id):
    product = Product.query.get_or_404(id)
    # Get similar products (same type, excluding current product)
    similar_products = Product.query.filter(
        Product.id != id,
        Product.status == 'available'
    ).limit(3).all()

    stripe_publishable_key = os.environ.get('STRIPE_PUBLISHABLE_KEY')

    return render_template('products/detail.html', 
                         product=product, 
                         similar_products=similar_products,
                         stripe_publishable_key=stripe_publishable_key)

@products_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    product = Product.query.get_or_404(id)
    if product.user_id != current_user.id:
        flash('Vous n\'êtes pas autorisé à modifier ce produit')
        return redirect(url_for('products.list'))

    if request.method == 'POST':
        # Update product details
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.quantity = float(request.form.get('quantity'))
        product.unit = request.form.get('unit')
        product.location = request.form.get('location')
        product.latitude = float(request.form.get('latitude'))
        product.longitude = float(request.form.get('longitude'))

        # Handle new image if uploaded
        if 'product_image' in request.files:
            file = request.files['product_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)
                product.image_url = os.path.join('uploads/products', filename)

        db.session.commit()
        flash('Produit mis à jour avec succès')
        return redirect(url_for('dashboard.index'))

    return render_template('products/create.html', product=product, edit=True)


# Chat routes
@chat_bp.route('/messages')
@login_required
def messages():
    # Get all messages sent or received by the current user
    messages = Message.query.filter(
        or_(
            Message.sender_id == current_user.id,
            Message.recipient_id == current_user.id
        )
    ).order_by(desc(Message.timestamp)).all()

    # Group messages by conversation
    conversations = {}
    for message in messages:
        other_user_id = message.recipient_id if message.sender_id == current_user.id else message.sender_id
        if other_user_id not in conversations:
            other_user = User.query.get(other_user_id)
            conversations[other_user_id] = {
                'other_user': other_user,
                'last_message': message
            }

    return render_template('chat/messages.html', conversations=conversations.values())

@chat_bp.route('/<int:user_id>')
@login_required
def chat(user_id):
    other_user = User.query.get_or_404(user_id)

    # Mark messages as read
    unread_messages = Message.query.filter(
        Message.sender_id == user_id,
        Message.recipient_id == current_user.id,
        Message.read == False
    ).all()

    for message in unread_messages:
        message.read = True

    if unread_messages:
        db.session.commit()

    messages = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
            and_(Message.sender_id == user_id, Message.recipient_id == current_user.id)
        )
    ).order_by(Message.timestamp).all()

    return render_template('chat/index.html', other_user=other_user, messages=messages)


@socketio.on('join')
def on_join(data):
    if current_user.is_authenticated:
        room = str(data['room'])
        join_room(room)

@socketio.on('send_message')
def handle_message(data):
    if not current_user.is_authenticated:
        return

    message = Message(
        sender_id=current_user.id,
        recipient_id=data['recipient_id'],
        content=data['content']
    )
    db.session.add(message)
    db.session.commit()

    # Emit to both sender and recipient rooms
    sender_room = str(current_user.id)
    recipient_room = str(data['recipient_id'])

    message_data = {
        'sender_id': current_user.id,
        'content': data['content'],
        'timestamp': message.timestamp.isoformat()
    }

    socketio.emit('new_message', message_data, room=sender_room)
    socketio.emit('new_message', message_data, room=recipient_room)

# Order routes
@orders_bp.route('/create/<int:product_id>', methods=['POST'])
@login_required
def create_order(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = float(request.form.get('quantity', 1))

    if quantity > product.quantity:
        flash('Quantité non disponible')
        return redirect(url_for('products.detail', id=product_id))

    total_amount = product.price * quantity

    # Create order
    order = Order(
        buyer_id=current_user.id,
        seller_id=product.user_id,
        product_id=product_id,
        quantity=quantity,
        total_amount=total_amount,
        status='pending'
    )

    db.session.add(order)
    db.session.commit()

    # Create Stripe Payment Intent
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(total_amount * 100),  # Stripe expects amount in cents
            currency='xaf',
            metadata={'order_id': order.id}
        )

        order.payment_intent_id = intent.id
        db.session.commit()

        return jsonify({
            'clientSecret': intent.client_secret,
            'order_id': order.id
        })
    except Exception as e:
        db.session.delete(order)
        db.session.commit()
        return jsonify({'error': str(e)}), 403

@orders_bp.route('/confirm/<int:order_id>', methods=['POST'])
@login_required
def confirm_payment(order_id):
    order = Order.query.get_or_404(order_id)

    if order.buyer_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        intent = stripe.PaymentIntent.retrieve(order.payment_intent_id)

        if intent.status == 'succeeded':
            order.status = 'paid'
            # Decrease product quantity
            order.product.quantity -= order.quantity
            if order.product.quantity <= 0:
                order.product.status = 'sold'

            db.session.commit()

            # Send message to seller
            message = Message(
                sender_id=current_user.id,
                recipient_id=order.seller_id,
                content=f"Nouvelle commande pour {order.product.name} - {order.quantity} {order.product.unit}"
            )
            db.session.add(message)
            db.session.commit()

            flash('Paiement confirmé! Le vendeur a été notifié.')
            return jsonify({'status': 'success'})

    except Exception as e:
        return jsonify({'error': str(e)}), 403

    return jsonify({'status': 'pending'})

@orders_bp.route('/my-orders')
@login_required
def my_orders():
    # Get both bought and sold orders
    bought_orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
    sold_orders = Order.query.filter_by(seller_id=current_user.id).order_by(Order.created_at.desc()).all()

    return render_template('orders/list.html', bought_orders=bought_orders, sold_orders=sold_orders)

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(orders_bp)