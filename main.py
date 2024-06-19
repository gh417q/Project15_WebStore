from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, send_from_directory, request
from flask_bootstrap import Bootstrap5
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, login_required, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, mapped_column
from sqlalchemy import Integer, String, Text, Float, Boolean, ForeignKey, null
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegisterForm, AddItemForm
import os

# Import forms from the forms.py


'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

IMAGE_DIR = "static/assets/img"

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
Bootstrap5(app)

login_manager = LoginManager(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///online_store.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class Item(db.Model):
    __tablename__ = "items"
    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(50), unique=True, nullable=False)
    price = mapped_column(Float, nullable=False)
    image = mapped_column(String(50), unique=True, nullable=False)
    in_stock = mapped_column(Integer, nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(250), nullable=False)
    email = mapped_column(String(100), unique=True, nullable=False)
    password = mapped_column(String(100), nullable=False)
    order = relationship("Order", back_populates="customer")  # past orders


class Order(db.Model):
    __tablename__ = "orders"
    id = mapped_column(Integer, primary_key=True)
    customer_id = mapped_column(ForeignKey("users.id"))  # table name, not class
    customer = relationship("User", back_populates="order")
    order_date = mapped_column(String(50), nullable=True)


class OrderItems(db.Model):
    __tablename__ = "order_items"
    id = mapped_column(Integer, primary_key=True)
    order_id = mapped_column(ForeignKey("orders.id"))
    item_id = mapped_column(ForeignKey("items.id"))
    number_ordered = mapped_column(Integer, default=1, nullable=False)


with app.app_context():
    db.create_all()

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.get_id() != "1":
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


# Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if user with this e-mail already exists
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user is not None:
            flash(f"User {form.email.data} already exists, please login.")
            return render_template("login.html", form=LoginForm())
        new_user_password = form.password.data
        hash_pwd = generate_password_hash(new_user_password, method='pbkdf2', salt_length=8)
        new_user = User(name=form.name.data, password=hash_pwd, email=form.email.data)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)  # flask_login method, so it can proceed where "login is required" and be traced
        return redirect(url_for('get_all_items'))  # home
    return render_template("register.html", form=form)


# Retrieve a user from the database based on their email.
@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user is None:
            flash(f"User {form.email.data} doesn't exist, please register or login as different user.")
            return redirect(url_for('login'))
        if not check_password_hash(pwhash=user.password, password=form.password.data):
            flash("Login unsuccessful, please register or try again.")
            return redirect(url_for('login'))
        login_user(user)  # flask_login method, so it can proceed where "login is required" and be traced
        return redirect(url_for('get_all_items'))  # home
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_items'))


# Use a decorator so only an admin user can add a new item to stock
@app.route("/new-item", methods=["GET", "POST"])
@admin_only
def add_new_item_to_stock():
    form = AddItemForm()
    if form.validate_on_submit():
        db.session.add(Item(name=form.name.data, price=form.price.data, image=form.image.data, in_stock=form.amount.data))
        db.session.commit()
        return redirect(url_for("get_all_items"))
    return render_template("add-item.html", form=form, is_edit=False)



# Only an admin user can edit item
@app.route("/edit-item/<int:item_id>", methods=["GET", "POST"])
@admin_only
def edit_item(item_id):
    item = db.get_or_404(Item, item_id)
    edit_form = AddItemForm(
        name=item.name,
        price=item.price,
        image=item.image,
        amount=item.in_stock,
    )
    if edit_form.validate_on_submit():
        item.name = edit_form.name.data
        item.price = edit_form.price.data
        item.image = edit_form.image.data
        item.in_stock = edit_form.amount.data
        db.session.commit()
        return redirect(url_for("get_all_items"))
    return render_template("add-item.html", form=edit_form, is_edit=True)


# Use a decorator so only an admin user can delete item
@app.route("/update_item/<int:item_id>")
@admin_only
def update_item_availability(item_id: int):
    # Mark as unavailable (in_stock = -1), can't just delete, it may be in existing orders / history
    item_to_delete = db.get_or_404(Item, item_id)
    if item_to_delete.in_stock == -1:
        item_to_delete.in_stock = 0
    else:
        item_to_delete.in_stock = -1
    db.session.commit()
    return redirect(url_for('get_all_items'))


@app.route('/')
def get_all_items():
    result = db.session.execute(db.select(Item))
    items = result.scalars().all()
    cart_id = 0
    if current_user.is_authenticated:
        user_cart = db.session.execute(db.select(Order).where(Order.customer_id == current_user.get_id())\
            .where(Order.order_date.is_(null()))).scalar()
        if user_cart is not None:
            cart_id = user_cart.id
    return render_template("index.html", all_items=items, cart_id=cart_id)


# Allow logged-in users to add items to cart
@app.route("/cart/<int:cart_id>", methods=["POST"])
@login_required
def add_to_cart(cart_id: int):
    # print("Adding item")
    item_id = request.values.get("item_id")
    # print(f"Item ID: {item_id}")
    amount = int(request.values.get("amount"))
    item = db.get_or_404(Item, item_id)
    number_in_stock = item.in_stock
    if number_in_stock == 0:
        flash("Sorry, this item is currently not available.")
        return redirect(url_for('get_all_items'))
    if number_in_stock == -1:
        flash("Sorry, this item is no longer available.")
        return redirect(url_for('get_all_items'))
    # user_cart =\
    #     db.session.execute(db.select(Order).where(Order.customer_id == user_id)).where(Order.date.is_(null())).scalar()
    # if user_cart is None:  # first item in new cart
    if cart_id == 0:
        new_cart = Order(customer_id=current_user.get_id())
        db.session.add(new_cart)
        db.session.commit()
        cart_id = new_cart.id
    if amount > number_in_stock:  # this block must work for additional order too (if there is existing order below)
        flash(f"Only {number_in_stock} items available.")
        amount = number_in_stock
    item.in_stock = item.in_stock - amount
    existing_order = db.session.execute(db.select(OrderItems).where(OrderItems.order_id == cart_id)\
        .where(OrderItems.item_id == item_id)).scalar()
    if existing_order is None:  # this item is not in cart
        db.session.add(OrderItems(order_id=cart_id, item_id=item_id, number_ordered=amount))
    else:  # this item already is in this cart
        existing_order.number_ordered += amount
    db.session.commit()
    return redirect(url_for('get_all_items'))


# Allow logged-in user to view the cart
@app.route("/view-cart/<int:cart_id>", methods=["GET", "POST"])
@login_required
def view_cart(cart_id: int):
    # user_cart =\
    #     db.session.execute(db.select(Order).where(Order.customer_id == user_id)).where(Order.date.is_(null())).scalar()
    # if user_cart is None:
    if cart_id == 0:
        flash("Your cart is empty.")
        return redirect(url_for('get_all_items'))
    cart_items = db.session.execute(db.select(OrderItems).where(OrderItems.order_id == cart_id))
    return render_template("view-cart.html", cart=cart_items)


# Allow logged-in user to update the cart
@app.route("/update-cart/<int:cart_id>/int:item_id>/<int:amount>", methods=["GET", "POST"])
@login_required
def update_cart(cart_id: int, item_id: int, amount: int):
    item_to_update = db.session.execute(db.select(OrderItems).where(OrderItems.order_id == cart_id)) \
        .where(OrderItems.item_id == item_id).scalar()
    amount_to_update = amount - item_to_update.number_ordered  # how to update Item.in_stock
    if amount == 0:  # delete the item from cart
        db.session.delete(item_to_update)
    item = db.get_or_404(Item, item_id)
    number_in_stock = item.in_stock
    if amount_to_update > number_in_stock:
        flash(f"Only {number_in_stock} items available.")
        amount_to_update = number_in_stock
    item_to_update.number_ordered = amount
    item.in_stock = item.in_stock - amount_to_update
    db.session.commit()
    return redirect(url_for("view_cart", cart_id=cart_id))


# Allow logged-in user to check out
@app.route("/checkout/<int:cart_id>", methods=["GET", "POST"])
@login_required
def checkout(cart_id):
    order_co_close = db.get_or_404(Order, cart_id)
    order_co_close.order_date = date.today().strftime("%B %d, %Y")
    return redirect(url_for("view_order_history"))


# Allow logged-in user to view orders history
@app.route("/order-history")
@login_required
def view_order_history():
    history = {}
    orders = db.session.execute(db.select(Order).where(Order.customer_id == current_user.get_id())).scalar()
    for order in orders:
        history[order] = db.session.execute(db.select(OrderItems).where(OrderItems.order_id == order.id))\
            .join(Item, Item.id == OrderItems.item_id).scalar()
    return render_template("view-history.html", orders=history)

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route('/item/<filename>')
def send_uploaded_file(filename=''):
    return send_from_directory(IMAGE_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, port=5002)
