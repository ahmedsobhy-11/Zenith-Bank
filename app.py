from flask import Flask, render_template, request, redirect, session, jsonify
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity
)
from models import db, bcrypt, User, Account, Transaction, VirtualCard, Loan, ActivityLog
from config import Config
from functools import wraps
from time import time
from flask_migrate import Migrate
from decimal import Decimal
import random
import os

app = Flask(__name__)
app.config.from_object(Config)

app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

login_attempts = {}

# Extensions
db.init_app(app)
bcrypt.init_app(app)
jwt = JWTManager(app)
migrate = Migrate(app, db)

# =============================
# ADMIN & SECURITY UTILS
# =============================

def web_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        user = db.session.get(User, session["user_id"])
        if not user or not user.is_admin:
            # Intentional verbose error revealing path existence
            return "Forbidden: Insufficient privileges to access the administrative console.", 403
        return f(*args, **kwargs)
    return decorated_function

def log_activity(user_id, action):
    try:
        log = ActivityLog(
            user_id=user_id,
            action=action,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "Unknown")[:250] # Truncated to fit DB
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Failed to write to audit log: {e}")

# CLI Command to provision the initial admin account
@app.cli.command("create-admin")
def create_admin():
    """Run `flask create-admin` to seed the database with an admin from env vars."""
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "SuperSecretAdmin123!")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@zenith.local")
    
    if not User.query.filter_by(username=admin_user).first():
        hashed_pw = bcrypt.generate_password_hash(admin_pass).decode("utf-8")
        admin = User(username=admin_user, email=admin_email, password=hashed_pw, is_admin=True)
        db.session.add(admin)
        db.session.commit()
        print(f"[*] Provisioned administrative account: {admin_user}")
    else:
        print("[!] Administrator account already exists in the registry.")

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

        account = Account(balance=0, user_id=new_user.id)
        db.session.add(account)
        db.session.commit()
        
        log_activity(new_user.id, "Account Registration")

        return redirect("/login")

    return render_template("register.html")


# -------- Login --------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr
        current_time = time()

        # Anti-brute-force mechanism
        login_attempts[ip] = [
            t for t in login_attempts.get(ip, [])
            if current_time - t < 60
        ]

        if len(login_attempts.get(ip, [])) >= 5:
            return render_template("login.html", error="Too many attempts. Try again in a minute.")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()

        if not user or not bcrypt.check_password_hash(user.password, password):
            login_attempts.setdefault(ip, []).append(current_time)
            return render_template("login.html", error="Invalid username or password")

        # Successful authentication
        session.clear()
        session["user_id"] = user.id
        session.permanent = True

        login_attempts.pop(ip, None)
        
        # Log the action (Optional, if you kept the ActivityLog model)
        try:
            log_activity(user.id, "Successful Authentication")
        except:
            pass

        # ENFORCE SEPARATION OF DUTIES: Route admins to the admin panel
        if user.is_admin:
            return redirect("/admin")
            
        return redirect("/dashboard")

    return render_template("login.html")

# -------- Logout --------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# -------- Profile --------

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/login")

    user = db.session.get(User, session["user_id"])
    error = None
    success = None

    if request.method == "POST":
        # Handle Password Change Request
        if "old_password" in request.form:
            old_password = request.form.get("old_password")
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            if new_password != confirm_password:
                error = "New passwords do not match."
            elif not bcrypt.check_password_hash(user.password, old_password):
                error = "Incorrect current password."
            else:
                # Vulnerability Note: No password complexity requirements or CSRF tokens are enforced here.
                hashed_pw = bcrypt.generate_password_hash(new_password).decode("utf-8")
                user.password = hashed_pw
                db.session.commit()
                success = "Password updated successfully."

        # Handle Profile Photo Upload Request (Unrestricted File Upload Vulnerability)
        elif 'photo' in request.files:
            file = request.files['photo']
            if file.filename != '':
                filename = file.filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                try:
                    file.save(filepath)
                    user.profile_photo = filename
                    db.session.commit()
                    success = "Profile photo updated successfully."
                except Exception as e:
                    print(f"UPLOAD ERROR: {e}")
                    error = "File upload failed."

    return render_template(
        "profile.html",
        user=user,
        bank_name=Config.BANK_NAME,
        error=error,
        success=success
    )

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
    if user.is_suspended:
        return "Your account has been suspended by an administrator. Transactions are disabled.", 403
    
    accounts = Account.query.filter_by(user_id=user.id).all()
    virtual_cards = VirtualCard.query.filter_by(user_id=user.id).all()

    if request.method == "POST":
        target_username = request.form.get("target_username", "").strip()
        
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
            
            log_activity(user.id, f"Initiated a transfer of ${amount}")
            
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
    if user.is_suspended:
        return "Your account has been suspended by an administrator. Transactions are disabled.", 403
    
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

# -------- Virtual Cards --------

@app.route("/virtual_cards", methods=["GET", "POST"])
def virtual_cards():
    if "user_id" not in session:
        return redirect("/login")

    user = db.session.get(User, session["user_id"])
    if user.is_suspended:
        return "Your account has been suspended by an administrator. Transactions are disabled.", 403
    
    accounts = Account.query.filter_by(user_id=user.id).all()
    cards = VirtualCard.query.filter_by(user_id=user.id).all()

    if request.method == "POST":
        try:
            amount = Decimal(request.form.get("amount", "0"))
        except:
            amount = Decimal('0')
            
        funding_source_id = request.form.get("funding_source")

        try:
            card_number = "".join([str(random.randint(0, 9)) for _ in range(16)])
            cvv = "".join([str(random.randint(0, 9)) for _ in range(3)])

            funding_account = db.session.get(Account, int(funding_source_id))
            
            funding_account.balance -= amount
            
            # Create the card
            new_card = VirtualCard(
                card_number=card_number,
                cvv=cvv,
                balance=amount,
                user_id=user.id
            )
            
            db.session.add(new_card)
            db.session.flush() # Flush to get the new_card.id before committing
            
            tx_out = Transaction(
                amount=-amount, 
                transaction_type="Card Funding", 
                description=f"Funded VCard {card_number[-4:]}", 
                account_id=funding_account.id
            )
            
            tx_in = Transaction(
                amount=amount, 
                transaction_type="Card Funded", 
                description="Initial Deposit", 
                virtual_card_id=new_card.id
            )

            db.session.add(tx_out)
            db.session.add(tx_in)
            db.session.commit()
            
            log_activity(user.id, "Provisioned a Virtual Credit Card")
            
            return redirect("/virtual_cards")

        except Exception as e:
            print(f"VCARD ERROR: {e}")
            return render_template("virtual_cards.html", user=user, accounts=accounts, cards=cards, error="Card generation failed.")

    return render_template(
        "virtual_cards.html", 
        user=user, 
        accounts=accounts, 
        cards=cards, 
        bank_name=Config.BANK_NAME
    )

# -------- Transaction History --------

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect("/login")

    user = db.session.get(User, session["user_id"])
    accounts = Account.query.filter_by(user_id=user.id).all()
    
    # NEW: Fetch the user's virtual cards
    virtual_cards = VirtualCard.query.filter_by(user_id=user.id).all()

    # Gather all transactions linked to both accounts and virtual cards
    transactions = []
    
    for acc in accounts:
        transactions.extend(acc.transactions)
        
    for card in virtual_cards:
        transactions.extend(card.transactions)
        
    # Sort transactions chronologically (newest first)
    transactions.sort(key=lambda x: x.created_at, reverse=True)

    return render_template(
        "history.html",
        user=user,
        transactions=transactions,
        bank_name=Config.BANK_NAME
    )

# -------- Bill Payments --------

@app.route("/bill_payments", methods=["GET", "POST"])
def bill_payments():
    if "user_id" not in session:
        return redirect("/login")

    user = db.session.get(User, session["user_id"])
    if user.is_suspended:
        return "Your account has been suspended by an administrator. Transactions are disabled.", 403
    
    accounts = Account.query.filter_by(user_id=user.id).all()
    virtual_cards = VirtualCard.query.filter_by(user_id=user.id).all()

    if request.method == "POST":
        service = request.form.get("service")
        service_number = request.form.get("service_number", "").strip()
        funding_source = request.form.get("funding_source")

        # Vulnerability 1: No bounds checking. Paying a negative bill ADDS money to the account!
        try:
            amount = Decimal(request.form.get("amount", "0"))
        except:
            amount = Decimal('0')

        # Vulnerability 2: IDOR. The user can manipulate the funding_source to pay their bill using someone else's account.
        try:
            source_type, source_id = funding_source.split("_")
            source_id = int(source_id)
            
            if source_type == "account":
                sender_source = db.session.get(Account, source_id)
                sender_source.balance -= amount
                tx_out = Transaction(
                    amount=-amount, 
                    transaction_type="Bill Payment", 
                    description=f"{service} Bill - #{service_number}", 
                    account_id=source_id
                )
            elif source_type == "vcard":
                sender_source = db.session.get(VirtualCard, source_id)
                sender_source.balance -= amount
                tx_out = Transaction(
                    amount=-amount, 
                    transaction_type="Bill Payment", 
                    description=f"{service} Bill - #{service_number}", 
                    virtual_card_id=source_id
                )
            else:
                raise ValueError("Invalid source")

            db.session.add(tx_out)
            db.session.commit()
            
            return redirect("/history")

        except Exception as e:
            print(f"BILL PAYMENT ERROR: {e}")
            return render_template("bill_payments.html", user=user, accounts=accounts, virtual_cards=virtual_cards, error="Payment processing failed.")

    return render_template(
        "bill_payments.html", 
        user=user, 
        accounts=accounts, 
        virtual_cards=virtual_cards, 
        bank_name=Config.BANK_NAME
    )

# -------- Admin Panel --------

@app.route("/admin")
@web_admin_required
def admin():
    user = db.session.get(User, session["user_id"])
    
    # Fetch exact, real-time actions directly from the core tables
    recent_users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).limit(10).all()
    recent_transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()
    recent_cards = VirtualCard.query.order_by(VirtualCard.created_at.desc()).limit(10).all()

    return render_template(
        "admin.html",
        user=user,
        recent_users=recent_users,
        recent_transactions=recent_transactions,
        recent_cards=recent_cards,
        bank_name=Config.BANK_NAME
    )
    

# -------- Admin User Directory & Actions --------

@app.route("/admin/users", methods=["GET"])
@web_admin_required
def admin_users():
    admin_user = db.session.get(User, session["user_id"])
    search_query = request.args.get("search", "").strip()
    
    if search_query:
        # Vulnerable to potential DoS if wildcards are heavily abused, but functional for search
        users = User.query.filter(
            (User.username.ilike(f"%{search_query}%")) |
            (User.email.ilike(f"%{search_query}%")) |
            (db.cast(User.created_at, db.String).ilike(f"%{search_query}%"))
        ).filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    else:
        users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()

    return render_template("admin_users.html", user=admin_user, target_users=users, bank_name=Config.BANK_NAME)


@app.route("/admin/user/<int:target_id>", methods=["GET"])
@web_admin_required
def admin_user_details(target_id):
    admin_user = db.session.get(User, session["user_id"])
    target_user = db.session.get(User, target_id)
    
    if not target_user or target_user.is_admin:
        return "User not found or cannot inspect other administrators.", 404

    accounts = Account.query.filter_by(user_id=target_user.id).all()
    virtual_cards = VirtualCard.query.filter_by(user_id=target_user.id).all()
    
    transactions = []
    for acc in accounts:
        transactions.extend(acc.transactions)
    for card in virtual_cards:
        transactions.extend(card.transactions)
    transactions.sort(key=lambda x: x.created_at, reverse=True)

    return render_template(
        "admin_user_details.html", 
        user=admin_user, 
        target=target_user, 
        accounts=accounts,
        virtual_cards=virtual_cards,
        transactions=transactions,
        bank_name=Config.BANK_NAME
    )

@app.route("/admin/user/<int:target_id>/suspend", methods=["POST"])
@web_admin_required
def admin_suspend_user(target_id):
    target_user = db.session.get(User, target_id)
    if target_user and not target_user.is_admin:
        target_user.is_suspended = not target_user.is_suspended # Toggle suspension
        db.session.commit()
    return redirect(f"/admin/user/{target_id}")

@app.route("/admin/user/<int:target_id>/delete", methods=["POST"])
@web_admin_required
def admin_delete_user(target_id):
    target_user = db.session.get(User, target_id)
    if not target_user or target_user.is_admin:
        return "Invalid operation", 400

    # Ensure absolute zero balance across all accounts and virtual cards
    total_balance = sum(acc.balance for acc in target_user.accounts)
    virtual_cards = VirtualCard.query.filter_by(user_id=target_user.id).all()
    total_balance += sum(card.balance for card in virtual_cards)

    if total_balance != Decimal('0.00'):
        # In a real environment, you'd flash a message. We'll return a direct error string.
        return "Cannot delete account: User has an outstanding positive or negative balance.", 400

    db.session.delete(target_user)
    db.session.commit()
    return redirect("/admin/users")

@app.route("/admin/user/<int:target_id>/reset_password", methods=["POST"])
@web_admin_required
def admin_reset_password(target_id):
    target_user = db.session.get(User, target_id)
    if target_user and not target_user.is_admin:
        # Hardcoded reset password for simplicity and vulnerability testing
        hashed_pw = bcrypt.generate_password_hash("ZenithReset123!").decode("utf-8")
        target_user.password = hashed_pw
        db.session.commit()
    return redirect(f"/admin/user/{target_id}")


# -------- Admin Global Ledger --------

@app.route("/admin/transactions", methods=["GET"])
@web_admin_required
def admin_transactions():
    admin_user = db.session.get(User, session["user_id"])
    search_query = request.args.get("search", "").strip()

    # Construct a base query joining Transactions to Accounts, Virtual Cards, and their owning Users
    query = Transaction.query.outerjoin(Account, Transaction.account_id == Account.id) \
                             .outerjoin(VirtualCard, Transaction.virtual_card_id == VirtualCard.id) \
                             .outerjoin(User, db.or_(Account.user_id == User.id, VirtualCard.user_id == User.id))

    if search_query:
        # Filter across all joined tables simultaneously
        query = query.filter(
            (User.username.ilike(f"%{search_query}%")) |
            (User.email.ilike(f"%{search_query}%")) |
            (Transaction.description.ilike(f"%{search_query}%")) |
            (VirtualCard.card_number.ilike(f"%{search_query}%")) |
            (db.cast(Transaction.amount, db.String).ilike(f"%{search_query}%")) |
            (db.cast(Transaction.created_at, db.String).ilike(f"%{search_query}%"))
        )

    # Execute the query and sort newest first
    transactions = query.order_by(Transaction.created_at.desc()).all()

    return render_template(
        "admin_transactions.html", 
        user=admin_user, 
        transactions=transactions, 
        bank_name=Config.BANK_NAME
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