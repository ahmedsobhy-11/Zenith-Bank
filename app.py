from flask import Flask, render_template, request, redirect, session, jsonify
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity
)
from models import db, bcrypt, User, Account, Transaction, VirtualCard, Loan
from config import Config
from functools import wraps
from time import time
from flask_migrate import Migrate
from decimal import Decimal

app = Flask(__name__)
app.config.from_object(Config)

login_attempts = {}

# Extensions
db.init_app(app)
bcrypt.init_app(app)
jwt = JWTManager(app)
migrate = Migrate(app, db)

# =============================
# DATABASE INIT
# =============================

# with app.app_context():
#     db.create_all()

# =============================
# WEB ROUTES
# =============================

@app.route("/")
def home():
    return render_template("index.html")

# -------- Register --------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        # Basic validation
        if not username or not email or not password:
            return render_template("register.html", error="All fields are required")

        if len(password) < 6:
            return render_template("register.html", error="Password must be at least 6 characters")

        if User.query.filter_by(username=username).first():
            return render_template("register.html", error="Username already exists")

        if User.query.filter_by(email=email).first():
            return render_template("register.html", error="Email already registered")

        hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

        new_user = User(
            username=username,
            email=email,
            password=hashed_pw
        )

        db.session.add(new_user)
        db.session.commit()

        account = Account(balance=1000, user_id=new_user.id)
        db.session.add(account)
        db.session.commit()

        return redirect("/login")

    return render_template("register.html")


# -------- Login --------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        ip = request.remote_addr
        current_time = time()

        # امسح المحاولات الأقدم من 60 ثانية
        login_attempts[ip] = [
            t for t in login_attempts.get(ip, [])
            if current_time - t < 60
        ]

        # لو أكتر من 5 محاولات في دقيقة
        if len(login_attempts.get(ip, [])) >= 5:
            return render_template("login.html", error="Too many attempts. Try again in a minute.")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()

        if not user or not bcrypt.check_password_hash(user.password, password):
            login_attempts.setdefault(ip, []).append(current_time)
            return render_template("login.html", error="Invalid username or password")

        # تسجيل دخول ناجح
        session.clear()
        session["user_id"] = user.id
        session.permanent = True

        # امسح المحاولات بعد النجاح
        login_attempts.pop(ip, None)

        return redirect("/dashboard")

    return render_template("login.html")


    return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

# -------- Logout --------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# -------- Dashboard --------

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])
    accounts = Account.query.filter_by(user_id=user.id).all()

    transactions = []
    for acc in accounts:
        transactions.extend(acc.transactions)

    return render_template(
        "dashboard.html",
        user=user,
        accounts=accounts,
        transactions=transactions,
        bank_name=Config.BANK_NAME
    )

# -------- Transfer (Web) --------

@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if "user_id" not in session:
        return redirect("/login")

    user = db.session.get(User, session["user_id"])
    accounts = Account.query.filter_by(user_id=user.id).all()
    virtual_cards = VirtualCard.query.filter_by(user_id=user.id).all()

    if request.method == "POST":
        target_username = request.form.get("target_username", "").strip()
        
        # FIX: Cast to Decimal instead of float to prevent Python TypeErrors
        try:
            amount = Decimal(request.form.get("amount", "0"))
        except:
            amount = Decimal('0')
            
        source = request.form.get("source")  

        target_user = User.query.filter_by(username=target_username).first()
        
        if not target_user:
            return render_template("transfer.html", user=user, accounts=accounts, virtual_cards=virtual_cards, error="Target user not found")

        try:
            source_type, source_id = source.split("_")
            source_id = int(source_id)
            
            if source_type == "account":
                sender_source = db.session.get(Account, source_id)
                sender_source.balance -= amount
                tx_out = Transaction(
                    amount=-amount, 
                    transaction_type="Transfer Out", 
                    description=f"Sent to {target_username}", 
                    account_id=source_id
                )
            elif source_type == "vcard":
                sender_source = db.session.get(VirtualCard, source_id)
                sender_source.balance -= amount
                tx_out = Transaction(
                    amount=-amount, 
                    transaction_type="Transfer Out", 
                    description=f"Sent to {target_username}", 
                    virtual_card_id=source_id
                )
            else:
                raise ValueError("Invalid source")

            target_account = Account.query.filter_by(user_id=target_user.id).first()
            target_account.balance += amount
            
            tx_in = Transaction(
                amount=amount, 
                transaction_type="Transfer In", 
                description=f"Received from {user.username}", 
                account_id=target_account.id
            )

            db.session.add(tx_out)
            db.session.add(tx_in)
            db.session.commit()
            
            return redirect("/history")

        except Exception as e:
            # FIX: Print the exact error to the terminal for easy debugging
            print(f"TRANSFER ERROR: {e}") 
            return render_template("transfer.html", user=user, accounts=accounts, virtual_cards=virtual_cards, error="Transaction failed due to processing error.")

    return render_template(
        "transfer.html", 
        user=user, 
        accounts=accounts, 
        virtual_cards=virtual_cards, 
        bank_name=Config.BANK_NAME
    )


# -------- Loans --------

@app.route("/loan", methods=["GET", "POST"])
def loan():
    if "user_id" not in session:
        return redirect("/login")

    user = db.session.get(User, session["user_id"])
    accounts = Account.query.filter_by(user_id=user.id).all()
    virtual_cards = VirtualCard.query.filter_by(user_id=user.id).all()

    if request.method == "POST":
        # FIX: Cast to Decimal instead of float
        try:
            amount = Decimal(request.form.get("amount", "0"))
        except:
            amount = Decimal('0')
            
        target = request.form.get("target")

        try:
            target_type, target_id = target.split("_")
            target_id = int(target_id)
            
            if target_type == "account":
                dest = db.session.get(Account, target_id)
                dest.balance += amount
                tx = Transaction(
                    amount=amount, 
                    transaction_type="Loan Disbursed", 
                    description="System Loan", 
                    account_id=dest.id
                )
            elif target_type == "vcard":
                dest = db.session.get(VirtualCard, target_id)
                dest.balance += amount
                tx = Transaction(
                    amount=amount, 
                    transaction_type="Loan Disbursed", 
                    description="System Loan", 
                    virtual_card_id=dest.id
                )
            else:
                raise ValueError("Invalid target")

            new_loan = Loan(amount=amount, user_id=user.id)

            db.session.add(tx)
            db.session.add(new_loan)
            db.session.commit()
            
            return redirect("/history")

        except Exception as e:
            # FIX: Print the exact error to the terminal
            print(f"LOAN ERROR: {e}")
            return render_template("loan.html", user=user, accounts=accounts, virtual_cards=virtual_cards, error="Loan processing failed.")

    return render_template(
        "loan.html", 
        user=user, 
        accounts=accounts, 
        virtual_cards=virtual_cards, 
        bank_name=Config.BANK_NAME
    )

# -------- Transaction History --------

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])
    accounts = Account.query.filter_by(user_id=user.id).all()

    # Gather all transactions linked to the user's primary accounts
    transactions = []
    for acc in accounts:
        transactions.extend(acc.transactions)
        
    # Sort transactions chronologically (newest first)
    transactions.sort(key=lambda x: x.created_at, reverse=True)

    return render_template(
        "history.html",
        user=user,
        transactions=transactions,
        bank_name=Config.BANK_NAME
    )

# -------- Admin Panel --------

@app.route("/admin")
def admin():
    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])

    if not user.is_admin:
        return "Unauthorized", 403

    total_users = User.query.count()
    total_transactions = Transaction.query.count()
    total_balance = db.session.query(
        db.func.sum(Account.balance)
    ).scalar()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_transactions=total_transactions,
        total_balance=total_balance
    )

# =============================
# API ROUTES (JWT Protected)
# =============================

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()

    user = User.query.filter_by(
        username=data["username"]
    ).first()

    if not user or not bcrypt.check_password_hash(
        user.password,
        data["password"]
    ):
        return jsonify({"msg": "Invalid credentials"}), 401

    return jsonify({
        "access_token": create_access_token(identity=user.id),
        "refresh_token": create_refresh_token(identity=user.id)
    })

@app.route("/api/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    new_access = create_access_token(identity=identity)
    return jsonify({"access_token": new_access})

# -------- Admin Required Decorator --------

def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user or not user.is_admin:
            return jsonify({"msg": "Admin access required"}), 403

        return fn(*args, **kwargs)

    return wrapper

@app.route("/api/admin/stats")
@admin_required
def admin_stats():
    return jsonify({
        "users": User.query.count(),
        "transactions": Transaction.query.count()
    })

# -------- API Transfer --------

@app.route("/api/transfer", methods=["POST"])
@jwt_required()
def api_transfer():

    user_id = get_jwt_identity()
    data = request.get_json()
    amount = float(data["amount"])

    if amount <= 0:
        return jsonify({"msg": "Invalid amount"}), 400

    if amount > 5000:
        return jsonify({"msg": "Transaction limit exceeded"}), 400

    account = Account.query.filter_by(user_id=user_id).first()

    if account.balance < amount:
        return jsonify({"msg": "Insufficient funds"}), 400

    account.balance -= amount

    tx = Transaction(
        amount=-amount,
        transaction_type="API Transfer",
        description="API Transfer",
        account_id=account.id
    )

    db.session.add(tx)
    db.session.commit()

    return jsonify({"msg": "Transfer successful"}), 200

# =============================
# RUN
# =============================

if __name__ == "__main__":
    app.run(debug=True)