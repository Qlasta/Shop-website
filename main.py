from flask import Flask,render_template, redirect, url_for, flash, request, abort
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_wtf import FlaskForm, RecaptchaField
from wtforms import StringField, PasswordField, SubmitField, BooleanField, FormField, FieldList, IntegerField, DecimalField
from wtforms.validators import DataRequired, Length, Email
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import Table, Column, Integer, ForeignKey
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from functools import wraps
import stripe

stripe.api_key = os.environ["STRIPE_KEY"]
checkout_key = os.environ["CHECKOUT_KEY"]

TEST_DOMAIN = 'http://127.0.0.1:5000'
# App configuration
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///farm.db'
app.config['SECRET_KEY'] = os.environ['APP_KEY']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['RECAPTCHA_PUBLIC_KEY'] = os.environ['REC_PUBLIC']
app.config['RECAPTCHA_PRIVATE_KEY'] = os.environ['REC_PRIVATE']
RECAPTCHA_PARAMETERS = {'hl': 'zh', 'render': 'explicit'}
RECAPTCHA_DATA_ATTRS = {'theme': 'dark'}
db = SQLAlchemy(app)
Bootstrap(app)

login_manager = LoginManager()
login_manager.init_app(app)

# Databases conf

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    order = relationship("Order", back_populates="user")

    def __repr__(self):
        return '<User %r>' % self.email


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(250))
    user = relationship("User", back_populates="order")
    user_id = Column(Integer, ForeignKey("users.id"))
    items = relationship("Cart")
    paid = db.Column(db.Boolean, nullable=False)
    order_sum = db.Column(db.Float())
    finished = db.Column(db.Boolean, nullable=False)



    def __repr__(self):
        return '<Order %r>' % self.id

class Goods(db.Model):
    __tablename__ = "good"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    description = db.Column(db.String(1000))
    picture_link = db.Column(db.String(1000), nullable=False)
    price = db.Column(db.Float(1000), nullable=False)
    units = db.Column(db.String(250), nullable=False)
    in_stock_amount = db.Column(db.Integer, nullable=False)
    available = db.Column(db.Boolean, nullable=False)


    def __repr__(self):
        return '<Goods %r>' % self.name

class Cart(db.Model):
    __tablename__ = "cart"
    order_id = Column(Integer, ForeignKey("orders.id"))
    item_id = Column(Integer, ForeignKey("good.id"))
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    total_sum = db.Column(db.Integer, nullable=False)
    item = relationship("Goods")


    def __repr__(self):
        return '<Item %r>' % self.id


# Forms configuration

class RegitstrationForm(FlaskForm):
    email = StringField(label="El.paštas", validators=[DataRequired(), Length(4,120), Email()])
    password = PasswordField(label="Slaptažodis", validators=[DataRequired(), Length(6,80)])
    # recatcha = RecaptchaField()
    submit = SubmitField(label="Pirmyn!")


class AddToCart(FlaskForm):
    item_id = IntegerField()
    quantity = IntegerField()
    order_id = IntegerField()
    save = SubmitField(label="Į krepšį")

class EditCartItem(FlaskForm):
    id = IntegerField()
    item_id = IntegerField()
    quantity = IntegerField()
    save = SubmitField(label="Keisti kiekį")


class AddToGoods(FlaskForm):
    name = StringField(label="Pavadinimas",validators=[DataRequired(), Length(4,250)])
    description = StringField(label="Aprašymas",validators=[DataRequired(), Length(4,1000)])
    picture_link = StringField(label="Nuotraukos nuoroda",validators=[DataRequired(), Length(4,1000)])
    price = DecimalField(label="Kaina už vnt.",validators=[DataRequired()])
    units = StringField(label="Mato vnt.",validators=[DataRequired()])
    in_stock_amount = IntegerField(label="Kiekis sandėlyje",validators=[DataRequired()])
    available = BooleanField(label="Rodyti parduotuvėje",validators=[DataRequired()])
    save = SubmitField(label="Išsaugoti")

db.create_all()



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def admin_only(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated:
            if current_user.id in (1,2):
                return function(*args, **kwargs)
            else:
                return abort(403)
        else:
            return abort(403)
    return wrapper

# Index - all shop items
@app.route('/', methods=["GET", "POST"])
def index():
    form = AddToCart()
    all_active_orders = Order.query.filter_by(paid=1,finished=0).all()
    orders_q = len(all_active_orders)
    all_items = db.session.query(Goods).all()
    if request.method == "POST":
        print("post")
        if current_user.is_authenticated:
            current_order = Order.query.filter_by(user_id=current_user.id, paid=False).first()
            print(current_order)
            if current_order is None:
                new_order = Order(date=datetime.now(),
                                  user_id=current_user.id, paid=False, finished=False)
                db.session.add(new_order)
                db.session.commit()
                order_id = new_order.id
            else:
                order_id = current_order.id
            print(order_id)
            item_id = form.item_id.data
            item_from_db = Goods.query.get(item_id)
            new_item_cart = Cart(order_id=order_id,
                                 item_id=item_id,
                                 quantity=form.quantity.data,
                                 total_sum=form.quantity.data * item_from_db.price)
            db.session.add(new_item_cart)
            db.session.commit()
            return redirect(url_for('index'))
    if current_user.is_authenticated:
        current_order = Order.query.filter_by(user_id=current_user.id, paid=False).first()
        if current_order:
            cart_items_q = len(Cart.query.filter_by(order_id=current_order.id).all())
        else:
            cart_items_q = 0

        return render_template("index.html", items=all_items,
                               current_user=current_user,
                               form=form,
                               cart_items_q=cart_items_q,
                               orders_q=orders_q)

    return render_template("index.html", items=all_items,
                           form=form)

# Users cart
@app.route('/cart', methods=["GET", "POST"])
def cart():
    if current_user.is_authenticated:
        current_order = Order.query.filter_by(user_id=current_user.id, paid=False).first()
        if current_order is None:
            return render_template("cart.html", logged_in=True, current_user=current_user, cart_empty=True)
        else:
            form = EditCartItem()
            if request.method == "POST":
                current_item_cart = Cart.query.get(form.id.data)
                current_item = Goods.query.get(form.item_id.data)
                current_item_cart.quantity = form.quantity.data
                current_item_cart.total_sum = current_item.price * form.quantity.data
                db.session.commit()
        current_cart = Cart.query.filter_by(order_id=current_order.id).all()
        form = EditCartItem()
        cart_items = {}
        to_pay = 0
        for item_cart in current_cart:
            item = Goods.query.get(item_cart.item_id)
            cart_items[item_cart] = item
            to_pay += item_cart.total_sum
        current_order.order_sum = round(to_pay, 2)
        db.session.commit()
        return render_template("cart.html",logged_in=True, current_user=current_user, current_order=current_order,
                                   cart_items=cart_items, to_pay="{:.2f}".format(round(to_pay,2)), form=form)

    return render_template("cart.html",logged_in=False)

# Delete cart item
@app.route('/cart_delete/<int:item_cart_id>', methods=["GET", "POST"])
def cart_delete(item_cart_id):
    if current_user.is_authenticated:
        current_cart_item = Cart.query.get(item_cart_id)
        db.session.delete(current_cart_item)
        db.session.commit()
        return redirect(url_for('cart'))
    return render_template("cart.html",logged_in=False)

# Pay for order
@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    if current_user.is_authenticated:
        current_order = Order.query.filter_by(user_id=current_user.id, paid=False).first()
        if current_order is None:
            return render_template("cart.html", logged_in=True, current_user=current_user, cart_empty=True)
        else:
            product = stripe.Product.create(name=f"Užsakymas Nr.{current_order.id}")
            product_id = product['id']
            price = stripe.Price.create(product=product_id, unit_amount=int(current_order.order_sum*100), currency="eur")
            price_id = price['id']
            try:
                checkout_session = stripe.checkout.Session.create(
                    line_items=[
                        {
                            # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                            'price': price_id,
                            'quantity': 1,
                        },
                    ],
                    mode='payment',
                    success_url=TEST_DOMAIN+f'/{checkout_key}',
                    cancel_url=TEST_DOMAIN+'/cancel',
                )
            except Exception as e:
                return str(e)

            return redirect(checkout_session.url, code=303)
    else:
        return render_template("cart.html", logged_in=False)

# Payment succeeded
@app.route(f'/{checkout_key}', methods=["GET"])
def mark_paid():
    if current_user.is_authenticated:
        current_order = Order.query.filter_by(user_id=current_user.id, paid=False).first()
        if current_order is None:
            return render_template("cart.html", logged_in=True, current_user=current_user, cart_empty=True)
        current_order.paid = True
        db.session.commit()
        return redirect(url_for('success'))
    return redirect(url_for('cart'))

@app.route('/success', methods=["GET"])
def success():
    if current_user.is_authenticated:
        return render_template("success.html")
    return redirect(url_for('cart'))

# Payment failed
@app.route('/cancel', methods=["GET"])
def cancel():
    if current_user.is_authenticated:
        return render_template("cancel.html")
    return redirect(url_for('cart'))

# Admin windows
    # See all shop items
@admin_only
@app.route('/manager', methods=["GET", "POST"])
def admin_manager():
    all_items = db.session.query(Goods).all()
    return render_template("manager.html",  items=all_items, current_user=current_user)

    # Edit shop item
@admin_only
@app.route('/edit/<int:item_id>', methods=["GET", "POST"])
def edit_goods_item(item_id):
    current_item = Goods.query.get(item_id)
    form = AddToGoods(name=current_item.name,
                      description=current_item.description,
                      picture_link=current_item.picture_link,
                      price=current_item.price,
                      units=current_item.units,
                      in_stock_amount=current_item.in_stock_amount,
                      available=current_item.available
                    )
    if request.method == "POST":
        current_item.name = form.name.data
        current_item.description = form.description.data
        current_item.picture_link = form.picture_link.data
        current_item.price = form.price.data
        current_item.units = form.units.data
        current_item.in_stock_amount = form.in_stock_amount.data
        current_item.available = form.available.data

        db.session.commit()
        return redirect(url_for("admin_manager", current_user=current_user))

    return render_template("admin_form.html", form=form, current_user=current_user)

    # Add new shop item
@admin_only
@app.route('/add', methods=["GET", "POST"])
def add_goods_item():
    form = AddToGoods()
    if request.method == "POST":
        new_item = Goods(name=form.name.data,
                        description=form.description.data,
                        picture_link=form.picture_link.data,
                        price=form.price.data,
                        units=form.units.data,
                        in_stock_amount=form.in_stock_amount.data,
                        available=form.available.data)

        db.session.add(new_item)
        db.session.commit()

        return redirect(url_for("admin_manager", current_user=current_user))
    else:
        return render_template("admin_form.html", form=form, new_item=True, current_user=current_user)

    # See paid orders
@admin_only
@app.route('/orders', methods=["GET", "POST"])
def orders():
    active_orders_info = {}
    all_active_orders = Order.query.filter_by(paid=1,finished=0).all()
    for order in all_active_orders:
        cart_items = Cart.query.filter_by(order_id=order.id).all()
        active_orders_info[order] = cart_items

    return render_template("orders.html", active_orders_info=active_orders_info)

    # Mark order finished
@admin_only
@app.route('/order_finished/<int:order_id>', methods=["GET", "POST"])
def order_finished(order_id):
    current_order = Order.query.get(order_id)
    current_order.finished = True
    db.session.commit()
    return redirect(url_for('orders'))


# Register
@app.route('/register', methods=["GET", "POST"])
def register():
    register = RegitstrationForm()
    if request.method == "POST":
        if User.query.filter_by(email=register.email.data).first():
            flash("You have already registered, please log in.")
        else:
            new_user = User(email=register.email.data, password=generate_password_hash(register.password.data, method='pbkdf2:sha256', salt_length=8))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('index'))

    return render_template("register.html", register=register)

# Log in
@app.route('/login', methods=["GET", "POST"])
def login():
    login = RegitstrationForm()
    if request.method == "POST":
        if User.query.filter_by(email=login.email.data).first():
            current_user = User.query.filter_by(email=login.email.data).first()

            if check_password_hash(current_user.password, login.password.data):
                login_user(current_user)
                return redirect(url_for('index'))
            else:
                flash('Invalid credentials.')
        else:
            flash('User does not exist, please register.')

    return render_template("login.html", login=login)

# Log out
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# Debug mode
if __name__ ==  "__main__" :
    app.run(debug=True)