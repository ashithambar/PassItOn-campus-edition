from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Listing, Order, Wishlist, Notification, Review

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    # Overall dashboard overview
    my_active_listings = Listing.query.filter_by(seller_id=current_user.id, status='available').count()
    my_sold_listings = Listing.query.filter_by(seller_id=current_user.id, status='sold').count()
    
    requests_received = Order.query.filter_by(seller_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
    my_purchases = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
    
    wishlist_count = Wishlist.query.filter_by(user_id=current_user.id).count()
    avg_rating = current_user.get_average_rating()
    rating_count = current_user.rating_count
    
    recent_notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()

    return render_template(
        'dashboard/index.html',
        active_listings_count=my_active_listings,
        sold_listings_count=my_sold_listings,
        requests_received=requests_received,
        my_purchases=my_purchases,
        wishlist_count=wishlist_count,
        avg_rating=avg_rating,
        rating_count=rating_count,
        recent_notifs=recent_notifs
    )


@dashboard_bp.route('/my-listings')
@login_required
def my_listings():
    status = request.args.get('status', 'all')
    query = Listing.query.filter_by(seller_id=current_user.id).filter(Listing.status != 'deleted')
    
    if status in ['available', 'reserved', 'sold']:
        query = query.filter_by(status=status)
        
    listings = query.order_by(Listing.created_at.desc()).all()
    return render_template('dashboard/my_listings.html', listings=listings, current_status=status)


@dashboard_bp.route('/requests-received')
@login_required
def requests_received():
    orders = Order.query.filter_by(seller_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('dashboard/requests_received.html', orders=orders)


@dashboard_bp.route('/my-purchases')
@login_required
def my_purchases():
    orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('dashboard/my_purchases.html', orders=orders)


@dashboard_bp.route('/wishlist')
@login_required
def wishlist():
    items = Wishlist.query.filter_by(user_id=current_user.id).order_by(Wishlist.created_at.desc()).all()
    return render_template('dashboard/wishlist.html', items=items)


@dashboard_bp.route('/wishlist/remove/<int:wishlist_id>', methods=['POST'])
@login_required
def remove_from_wishlist(wishlist_id):
    item = db.session.get(Wishlist, wishlist_id)
    if item and item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash("Item removed from your wishlist.", "info")
    return redirect(url_for('dashboard.wishlist'))


@dashboard_bp.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    pagination = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=15, error_out=False)
    
    # Mark visible notifications as read
    for notif in pagination.items:
        notif.is_read = True
    db.session.commit()
    
    return render_template('dashboard/notifications.html', pagination=pagination)


@dashboard_bp.route('/notifications/mark-read/<int:notif_id>')
@login_required
def mark_notification_read(notif_id):
    notif = db.session.get(Notification, notif_id)
    if notif and notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
        if notif.link:
            return redirect(notif.link)
    return redirect(url_for('dashboard.notifications'))


@dashboard_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for('dashboard.notifications'))
