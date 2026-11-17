from flask import Blueprint, render_template, request
from app.models import db, Listing, Category, User

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    categories = Category.query.all()
    
    # Recently added listings
    recent_listings = Listing.query.filter_by(status='available').order_by(Listing.created_at.desc()).limit(8).all()
    
    # Popular items (by views)
    popular_listings = Listing.query.filter_by(status='available').order_by(Listing.views_count.desc()).limit(4).all()
    
    # Featured items
    featured_listings = Listing.query.filter_by(status='available').order_by(Listing.id.desc()).limit(6).all()
    
    # Total counts for stats banner
    total_listings = Listing.query.filter(Listing.status != 'deleted').count()
    total_students = User.query.filter_by(role='student').count()
    total_sold = Listing.query.filter_by(status='sold').count()

    return render_template(
        'index.html',
        categories=categories,
        recent_listings=recent_listings,
        popular_listings=popular_listings,
        featured_listings=featured_listings,
        total_listings=total_listings,
        total_students=total_students,
        total_sold=total_sold
    )

@main_bp.route('/safety')
def safety():
    return render_template('safety.html')

@main_bp.route('/about')
def about():
    return render_template('about.html')
