from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app import db, login_manager
from models import User, Product, Message

# Blueprint definitions
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
main_bp = Blueprint('main', __name__)
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')
products_bp = Blueprint('products', __name__, url_prefix='/products')
chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

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

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists')
            return redirect(url_for('auth.register'))

        new_user = User(username=username, email=email, user_type=user_type)
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
        product = Product(
            name=request.form.get('name'),
            description=request.form.get('description'),
            price=float(request.form.get('price')),
            quantity=float(request.form.get('quantity')),
            unit=request.form.get('unit'),
            location=request.form.get('location'),
            latitude=float(request.form.get('latitude')),
            longitude=float(request.form.get('longitude')),
            user_id=current_user.id
        )
        db.session.add(product)
        db.session.commit()
        return redirect(url_for('dashboard.index'))
    return render_template('products/create.html')

@products_bp.route('/')
def list():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('products/list.html', products=products)

# Chat routes
@chat_bp.route('/<int:user_id>')
@login_required
def chat(user_id):
    other_user = User.query.get_or_404(user_id)
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp).all()
    return render_template('chat/index.html', other_user=other_user, messages=messages)

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(chat_bp)
