from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import validates
from sqlalchemy.types import Numeric

db = SQLAlchemy()
bcrypt = Bcrypt()


# =========================
# USER MODEL
# =========================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        index=True
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )

    is_admin = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    accounts = db.relationship(
        "Account",
        backref="owner",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<User {self.username}>"


# =========================
# ACCOUNT MODEL
# =========================

class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)

    balance = db.Column(
        Numeric(12, 2),   # ✅ Safe for money
        default=0.00,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    transactions = db.relationship(
        "Transaction",
        backref="account",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Account {self.id} - Balance {self.balance}>"


# =========================
# TRANSACTION MODEL
# =========================

class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)

    amount = db.Column(
        Numeric(12, 2),
        nullable=False
    )

    # Added to distinguish between Transfers, Loans, and Virtual Card uses
    transaction_type = db.Column(
        db.String(50),
        default="General",
        nullable=False
    )

    description = db.Column(
        db.String(200),
        nullable=False
    )

    account_id = db.Column(
        db.Integer,
        db.ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True  # Made nullable so virtual cards can act independently
    )

    # Preparation for the Virtual Card feature
    virtual_card_id = db.Column(
        db.Integer,
        nullable=True  
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return f"<Transaction {self.amount} ({self.transaction_type})>"
    
    
# =========================
# VIRTUAL CARD MODEL
# =========================

class VirtualCard(db.Model):
    __tablename__ = "virtual_cards"

    id = db.Column(db.Integer, primary_key=True)

    card_number = db.Column(
        db.String(16),
        unique=True,
        nullable=False
    )

    cvv = db.Column(
        db.String(3),
        nullable=False
    )

    balance = db.Column(
        Numeric(12, 2),
        default=0.00,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return f"<VirtualCard {self.card_number} - Balance {self.balance}>"
    
    
# =========================
# LOAN MODEL
# =========================

class Loan(db.Model):
    __tablename__ = "loans"

    id = db.Column(db.Integer, primary_key=True)

    amount = db.Column(
        Numeric(12, 2),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return f"<Loan {self.amount} - User {self.user_id}>"