import os
import uuid
import secrets
from functools import wraps
import qrcode
from PIL import Image
from flask import current_app, redirect, url_for, flash, abort
from flask_login import current_user
from werkzeug.utils import secure_filename
from app.models import db, Notification, Listing

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file_storage, folder_name='listings'):
    """
    Saves an uploaded file securely into static/uploads/<folder_name>
    Returns the relative path e.g. 'uploads/listings/filename.jpg'
    """
    if not file_storage or file_storage.filename == '':
        return None
        
    if not allowed_file(file_storage.filename):
        return None

    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    unique_filename = f"{uuid.uuid4().hex[:12]}_{secrets.token_hex(4)}.{extension}"
    
    target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(target_dir, exist_ok=True)
    
    file_path = os.path.join(target_dir, unique_filename)
    
    # Resize and optimize image with Pillow if large
    try:
        image = Image.open(file_storage)
        image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        # Convert RGBA to RGB for saving as JPEG if necessary
        if extension in ['jpg', 'jpeg'] and image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        image.save(file_path, optimize=True, quality=85)
    except Exception:
        # Fallback to direct save
        file_storage.seek(0)
        file_storage.save(file_path)
        
    return f"uploads/{folder_name}/{unique_filename}"


def generate_handover_qr(order_number):
    """
    Generates a secure single-use handover QR code and returns (token, relative_qr_path)
    """
    token = f"HANDOVER-{secrets.token_urlsafe(16)}"
    target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'handover_qrs')
    os.makedirs(target_dir, exist_ok=True)
    
    qr_filename = f"qr_{order_number}_{secrets.token_hex(4)}.png"
    file_path = os.path.join(target_dir, qr_filename)
    
    # Data encoded in QR
    qr_data = token
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#0f766e", back_color="white")  # Campus teal color
    img.save(file_path)
    
    relative_path = f"uploads/handover_qrs/{qr_filename}"
    return token, relative_path


def generate_dynamic_upi_qr(upi_id, payee_name, amount):
    """
    Generates a UPI Payment QR code dynamically
    """
    target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'upi_qrs')
    os.makedirs(target_dir, exist_ok=True)
    
    qr_filename = f"upi_{uuid.uuid4().hex[:10]}.png"
    file_path = os.path.join(target_dir, qr_filename)
    
    # UPI standard deep link URI
    clean_name = payee_name.replace(" ", "%20")
    upi_uri = f"upi://pay?pa={upi_id}&pn={clean_name}&am={amount:.2f}&cu=INR&tn=PassItOn%20Item%20Purchase"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#1e293b", back_color="white")
    img.save(file_path)
    
    return f"uploads/upi_qrs/{qr_filename}"


def calculate_smart_price(category_id, condition, original_price=None, item_age_months=0):
    """
    Rule-based Smart Price Suggestion:
    - Condition depreciation:
        New: 80-90% (avg 85%)
        Like New: 65-80% (avg 72.5%)
        Good: 45-65% (avg 55%)
        Used: 25-45% (avg 35%)
    - Age depreciation:
        Reduces by ~1.5% to 2.5% per month (max 35% extra reduction)
    - Benchmarked against average price of similar listings in the category
    """
    condition_factors = {
        'New': (0.80, 0.90, 0.85),
        'Like New': (0.65, 0.80, 0.725),
        'Good': (0.45, 0.65, 0.55),
        'Used': (0.25, 0.45, 0.35)
    }
    
    low_pct, high_pct, avg_pct = condition_factors.get(condition, (0.40, 0.60, 0.50))
    
    # Age factor: 1.5% drop per month up to 30% maximum age penalty
    age_penalty = min(item_age_months * 0.015, 0.30)
    low_pct = max(0.15, low_pct - age_penalty)
    high_pct = max(0.25, high_pct - age_penalty)
    avg_pct = max(0.20, avg_pct - age_penalty)
    
    # Query database for existing category listings average price
    cat_listings = Listing.query.filter_by(category_id=category_id, status='available').all()
    if not cat_listings:
        cat_listings = Listing.query.filter_by(category_id=category_id).all()
        
    cat_avg = sum(l.price for l in cat_listings) / len(cat_listings) if cat_listings else None
    
    if original_price and original_price > 0:
        base_low = original_price * low_pct
        base_high = original_price * high_pct
        base_sugg = original_price * avg_pct
        
        # If we have category data, slightly pull towards category average for sanity
        if cat_avg and cat_avg > 0:
            sugg_price = (base_sugg * 0.75) + (cat_avg * 0.25)
            min_price = max(10, min(base_low, sugg_price * 0.85))
            max_price = max(min_price + 20, max(base_high, sugg_price * 1.15))
        else:
            min_price = round(base_low)
            max_price = round(base_high)
            sugg_price = round(base_sugg)
            
        explanation = f"Based on '{condition}' condition ({int(avg_pct*100)}% of original ₹{int(original_price)}) and {item_age_months} months age."
    elif cat_avg and cat_avg > 0:
        # No original price provided: estimate from category average & condition factor
        factor = avg_pct / 0.55  # Relative to 'Good'
        sugg_price = round(cat_avg * factor)
        min_price = round(sugg_price * 0.80)
        max_price = round(sugg_price * 1.20)
        explanation = f"Based on campus category average (₹{int(cat_avg)}) adjusted for '{condition}' condition."
    else:
        # Fallback defaults
        min_price = 150
        max_price = 450
        sugg_price = 300
        explanation = "Estimated typical campus item price range."
        
    min_price = max(10, int(round(min_price, -1)))  # Round to nearest 10
    max_price = max(min_price + 20, int(round(max_price, -1)))
    sugg_price = int(round(sugg_price, -1))
    sugg_price = max(min_price, min(max_price, sugg_price))
    
    return {
        'min_price': min_price,
        'max_price': max_price,
        'suggested_price': sugg_price,
        'explanation': explanation
    }


def create_notification(user_id, title, message, link=None, notification_type='general'):
    """Helper to dispatch a system notification to a user"""
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            link=link,
            notification_type=notification_type
        )
        db.session.add(notif)
        db.session.commit()
        return notif
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating notification: {e}")
        return None


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash("Access denied. Admin privileges required.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
