from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    year_semester = db.Column(db.String(50), nullable=False)
    college = db.Column(db.String(150), nullable=False)
    profile_pic = db.Column(db.String(255), default='default_avatar.png')
    
    # UPI Details
    upi_id = db.Column(db.String(100), nullable=True)
    upi_qr_image = db.Column(db.String(255), nullable=True)
    
    role = db.Column(db.String(20), default='student')  # 'student' or 'admin'
    is_blocked = db.Column(db.Boolean, default=False)
    reset_token = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    listings = db.relationship('Listing', back_populates='seller', lazy='dynamic', cascade='all, delete-orphan')
    orders_bought = db.relationship('Order', foreign_keys='Order.buyer_id', back_populates='buyer', lazy='dynamic')
    orders_sold = db.relationship('Order', foreign_keys='Order.seller_id', back_populates='seller', lazy='dynamic')
    wishlist_items = db.relationship('Wishlist', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    reviews_written = db.relationship('Review', foreign_keys='Review.reviewer_id', back_populates='reviewer', lazy='dynamic')
    reviews_received = db.relationship('Review', foreign_keys='Review.reviewee_id', back_populates='reviewee', lazy='dynamic')
    reports_submitted = db.relationship('Report', foreign_keys='Report.reporter_id', back_populates='reporter', lazy='dynamic')
    
    @property
    def is_active(self):
        # Blocked users cannot log in
        return not self.is_blocked

    @property
    def is_admin(self):
        return self.role == 'admin'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_average_rating(self):
        reviews = self.reviews_received.all()
        if not reviews:
            return 0.0
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def rating_count(self):
        return self.reviews_received.count()

    def __repr__(self):
        return f"<User {self.name} ({self.email})>"


class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    icon = db.Column(db.String(50), default='bi-tag')
    description = db.Column(db.Text, nullable=True)
    
    listings = db.relationship('Listing', back_populates='category', lazy='dynamic')

    def __repr__(self):
        return f"<Category {self.name}>"


class Listing(db.Model):
    __tablename__ = 'listings'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    condition = db.Column(db.String(20), nullable=False)  # 'New', 'Like New', 'Good', 'Used'
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=True)
    item_age_months = db.Column(db.Integer, default=0)
    location = db.Column(db.String(120), nullable=False)
    contact_info = db.Column(db.String(120), nullable=True)
    extra_details = db.Column(db.Text, nullable=True)
    
    # Status: 'available', 'reserved', 'sold', 'deleted'
    status = db.Column(db.String(20), default='available', index=True)
    views_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    seller = db.relationship('User', back_populates='listings')
    category = db.relationship('Category', back_populates='listings')
    images = db.relationship('ListingImage', back_populates='listing', cascade='all, delete-orphan', lazy='joined')
    orders = db.relationship('Order', back_populates='listing', lazy='dynamic')
    wishlist_entries = db.relationship('Wishlist', back_populates='listing', cascade='all, delete-orphan', lazy='dynamic')
    reports = db.relationship('Report', back_populates='reported_listing', lazy='dynamic')

    @property
    def primary_image(self):
        for img in self.images:
            if img.is_primary:
                return img.image_path
        if self.images:
            return self.images[0].image_path
        return 'default_item.png'

    @property
    def discount_percent(self):
        if self.original_price and self.original_price > self.price:
            return int(round(((self.original_price - self.price) / self.original_price) * 100))
        return 0

    def __repr__(self):
        return f"<Listing {self.title} - ₹{self.price}>"


class ListingImage(db.Model):
    __tablename__ = 'listing_images'
    
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id', ondelete='CASCADE'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    
    listing = db.relationship('Listing', back_populates='images')


class Wishlist(db.Model):
    __tablename__ = 'wishlists'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='wishlist_items')
    listing = db.relationship('Listing', back_populates='wishlist_entries')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'listing_id', name='uq_user_listing_wishlist'),
    )


class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    payment_method = db.Column(db.String(20), nullable=False)  # 'upi', 'cash'
    # Flow statuses:
    # 'request_sent' -> 'accepted' -> 'payment_pending' -> 'payment_completed' -> 'payment_confirmed' -> 'handover_pending' -> 'completed'
    # also: 'rejected', 'cancelled'
    status = db.Column(db.String(30), default='request_sent', index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    listing = db.relationship('Listing', back_populates='orders')
    buyer = db.relationship('User', foreign_keys=[buyer_id], back_populates='orders_bought')
    seller = db.relationship('User', foreign_keys=[seller_id], back_populates='orders_sold')
    payment = db.relationship('Payment', back_populates='order', uselist=False, cascade='all, delete-orphan')
    handover = db.relationship('HandoverRecord', back_populates='order', uselist=False, cascade='all, delete-orphan')
    reviews = db.relationship('Review', back_populates='order', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Order {self.order_number} ({self.status})>"


class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), unique=True, nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    transaction_reference = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'submitted', 'confirmed', 'failed'
    proof_image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    
    order = db.relationship('Order', back_populates='payment')


class HandoverRecord(db.Model):
    __tablename__ = 'handover_records'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), unique=True, nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    qr_image_path = db.Column(db.String(255), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    order = db.relationship('Order', back_populates='handover')


class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id', ondelete='SET NULL'), nullable=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    listing = db.relationship('Listing')
    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])
    messages = db.relationship('Message', back_populates='conversation', cascade='all, delete-orphan', order_by='Message.created_at')

    def other_user(self, current_user_id):
        return self.user2 if self.user1_id == current_user_id else self.user1

    def unread_count_for(self, current_user_id):
        return sum(1 for m in self.messages if not m.is_read and m.sender_id != current_user_id)


class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    conversation = db.relationship('Conversation', back_populates='messages')
    sender = db.relationship('User')


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    notification_type = db.Column(db.String(50), default='general')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', back_populates='notifications')


class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5
    comment = db.Column(db.Text, nullable=True)
    role = db.Column(db.String(20), nullable=False)  # 'buyer_to_seller', 'seller_to_buyer'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    order = db.relationship('Order', back_populates='reviews')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], back_populates='reviews_written')
    reviewee = db.relationship('User', foreign_keys=[reviewee_id], back_populates='reviews_received')


class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reported_listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=True)
    reason = db.Column(db.String(50), nullable=False)  # 'fake', 'wrong_info', 'scam', 'inappropriate', 'other'
    comment = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'resolved', 'dismissed'
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    reporter = db.relationship('User', foreign_keys=[reporter_id], back_populates='reports_submitted')
    reported_user = db.relationship('User', foreign_keys=[reported_user_id])
    reported_listing = db.relationship('Listing', back_populates='reports')
