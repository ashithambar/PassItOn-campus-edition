import math
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.models import db, Listing, ListingImage, Category, User, Wishlist, Report
from app.forms import ListingForm, ReportForm
from app.utils import save_uploaded_file, calculate_smart_price

listings_bp = Blueprint('listings', __name__)

@listings_bp.route('/')
def index():
    # Filter and Search parameters
    query_text = request.args.get('q', '').strip()
    category_slug = request.args.get('category', '').strip()
    condition = request.args.get('condition', '').strip()
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    department = request.args.get('department', '').strip()
    location = request.args.get('location', '').strip()
    sort_by = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)
    
    # Base query: non-deleted items
    query = Listing.query.filter(Listing.status != 'deleted')
    
    # Only show available unless specified
    status_filter = request.args.get('status', 'available')
    if status_filter == 'available':
        query = query.filter(Listing.status == 'available')
    elif status_filter == 'all':
        query = query.filter(Listing.status.in_(['available', 'reserved', 'sold']))

    # Search keyword
    if query_text:
        query = query.filter(
            db.or_(
                Listing.title.ilike(f'%{query_text}%'),
                Listing.description.ilike(f'%{query_text}%'),
                Listing.location.ilike(f'%{query_text}%')
            )
        )
        
    # Category filter
    selected_category = None
    if category_slug:
        selected_category = Category.query.filter_by(slug=category_slug).first()
        if selected_category:
            query = query.filter(Listing.category_id == selected_category.id)
            
    # Condition filter
    if condition and condition in ['New', 'Like New', 'Good', 'Used']:
        query = query.filter(Listing.condition == condition)
        
    # Price range filter
    if min_price is not None:
        query = query.filter(Listing.price >= min_price)
    if max_price is not None:
        query = query.filter(Listing.price <= max_price)
        
    # Location keyword filter
    if location:
        query = query.filter(Listing.location.ilike(f'%{location}%'))
        
    # Department filter (requires join on User)
    if department:
        query = query.join(User, Listing.seller_id == User.id).filter(User.department == department)
        
    # Sorting
    if sort_by == 'price_asc':
        query = query.order_by(Listing.price.asc())
    elif sort_by == 'price_desc':
        query = query.order_by(Listing.price.desc())
    elif sort_by == 'popular':
        query = query.order_by(Listing.views_count.desc())
    else:  # newest
        query = query.order_by(Listing.created_at.desc())
        
    # Pagination (12 items per page)
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    listings = pagination.items
    
    categories = Category.query.order_by(Category.name).all()
    departments = [d[0] for d in [
        ('Computer Science & Engg', ''),
        ('Electronics & Communication', ''),
        ('Mechanical Engineering', ''),
        ('Civil Engineering', ''),
        ('Electrical & Electronics', ''),
        ('Information Technology', ''),
        ('Biotechnology & Chemical', ''),
        ('Architecture & Design', ''),
        ('Business & Management (MBA/BBA)', '')
    ]]

    # User's wishlist set for active heart icons
    user_wishlist_ids = set()
    if current_user.is_authenticated:
        user_wishlist_ids = {w.listing_id for w in current_user.wishlist_items.all()}

    return render_template(
        'listings/list.html',
        listings=listings,
        pagination=pagination,
        categories=categories,
        departments=departments,
        selected_category=selected_category,
        query_text=query_text,
        current_condition=condition,
        current_sort=sort_by,
        min_price=min_price,
        max_price=max_price,
        current_location=location,
        current_department=department,
        user_wishlist_ids=user_wishlist_ids
    )


@listings_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form = ListingForm()
    # Populate categories
    categories = Category.query.order_by(Category.name).all()
    form.category_id.choices = [(c.id, c.name) for c in categories]
    
    if request.method == 'GET' and not form.contact_info.data:
        form.contact_info.data = current_user.phone
        
    if form.validate_on_submit():
        listing = Listing(
            seller_id=current_user.id,
            category_id=form.category_id.data,
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            condition=form.condition.data,
            price=float(form.price.data),
            original_price=float(form.original_price.data) if form.original_price.data else None,
            item_age_months=int(form.item_age_months.data) if form.item_age_months.data else 0,
            location=form.location.data.strip(),
            contact_info=form.contact_info.data.strip() if form.contact_info.data else current_user.phone,
            extra_details=form.extra_details.data.strip() if form.extra_details.data else None,
            status='available'
        )
        db.session.add(listing)
        db.session.flush()  # to obtain listing.id
        
        # Process image uploads
        uploaded_files = request.files.getlist('images')
        has_primary = False
        for file in uploaded_files:
            if file and file.filename != '':
                rel_path = save_uploaded_file(file, folder_name='listings')
                if rel_path:
                    img = ListingImage(
                        listing_id=listing.id,
                        image_path=rel_path,
                        is_primary=not has_primary
                    )
                    has_primary = True
                    db.session.add(img)
                    
        db.session.commit()
        flash(f"'{listing.title}' has been successfully listed for campus buyers!", "success")
        return redirect(url_for('listings.detail', listing_id=listing.id))
        
    return render_template('listings/create.html', form=form, categories=categories)


@listings_bp.route('/api/smart-price')
def api_smart_price():
    raw_category_id = request.args.get('category_id', '')
    try:
        category_id = int(raw_category_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'Select a valid category before requesting a price suggestion.'}), 400

    if category_id <= 0 or not Category.query.filter_by(id=category_id).first():
        return jsonify({'error': 'The selected category does not exist.'}), 400

    condition = request.args.get('condition', 'Good')
    if condition not in {'New', 'Like New', 'Good', 'Used'}:
        return jsonify({'error': 'Select a valid item condition.'}), 400

    raw_original_price = request.args.get('original_price')
    if raw_original_price in (None, ''):
        original_price = None
    else:
        try:
            original_price = float(raw_original_price)
        except ValueError:
            return jsonify({'error': 'Original price must be a valid number.'}), 400
        if not math.isfinite(original_price) or original_price < 0:
            return jsonify({'error': 'Original price must be zero or greater.'}), 400

    raw_item_age = request.args.get('item_age_months', '0')
    try:
        item_age = int(raw_item_age)
    except (TypeError, ValueError):
        return jsonify({'error': 'Item age must be a whole number of months.'}), 400
    if item_age < 0:
        return jsonify({'error': 'Item age cannot be negative.'}), 400

    suggestion = calculate_smart_price(
        category_id=category_id,
        condition=condition,
        original_price=original_price,
        item_age_months=item_age
    )
    return jsonify(suggestion)


@listings_bp.route('/<int:listing_id>')
def detail(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing or listing.status == 'deleted':
        flash("Listing not found or has been removed.", "warning")
        return redirect(url_for('listings.index'))
        
    # Increment view counter
    listing.views_count += 1
    db.session.commit()
    
    # Check if in current user's wishlist
    is_in_wishlist = False
    if current_user.is_authenticated:
        is_in_wishlist = Wishlist.query.filter_by(user_id=current_user.id, listing_id=listing.id).first() is not None
        
    # Similar items from same category
    similar_items = Listing.query.filter(
        Listing.category_id == listing.category_id,
        Listing.id != listing.id,
        Listing.status == 'available'
    ).limit(4).all()

    return render_template(
        'listings/detail.html',
        listing=listing,
        is_in_wishlist=is_in_wishlist,
        similar_items=similar_items
    )


@listings_bp.route('/<int:listing_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing or listing.status == 'deleted':
        abort(404)
        
    # Only seller or admin can edit
    if listing.seller_id != current_user.id and not current_user.is_admin:
        flash("You are not authorized to edit this listing.", "danger")
        return redirect(url_for('listings.detail', listing_id=listing.id))
        
    form = ListingForm(obj=listing)
    categories = Category.query.order_by(Category.name).all()
    form.category_id.choices = [(c.id, c.name) for c in categories]
    
    if form.validate_on_submit():
        listing.title = form.title.data.strip()
        listing.category_id = form.category_id.data
        listing.description = form.description.data.strip()
        listing.condition = form.condition.data
        listing.price = float(form.price.data)
        listing.original_price = float(form.original_price.data) if form.original_price.data else None
        listing.item_age_months = int(form.item_age_months.data) if form.item_age_months.data else 0
        listing.location = form.location.data.strip()
        listing.contact_info = form.contact_info.data.strip() if form.contact_info.data else current_user.phone
        listing.extra_details = form.extra_details.data.strip() if form.extra_details.data else None
        
        # New images
        uploaded_files = request.files.getlist('images')
        for file in uploaded_files:
            if file and file.filename != '':
                rel_path = save_uploaded_file(file, folder_name='listings')
                if rel_path:
                    img = ListingImage(listing_id=listing.id, image_path=rel_path, is_primary=False)
                    db.session.add(img)
                    
        db.session.commit()
        flash("Listing updated successfully!", "success")
        return redirect(url_for('listings.detail', listing_id=listing.id))
        
    return render_template('listings/edit.html', form=form, listing=listing, categories=categories)


@listings_bp.route('/<int:listing_id>/delete', methods=['POST'])
@login_required
def delete(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        abort(404)
        
    if listing.seller_id != current_user.id and not current_user.is_admin:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('main.index'))
        
    listing.status = 'deleted'
    db.session.commit()
    flash(f"Listing '{listing.title}' has been deleted.", "info")
    return redirect(url_for('dashboard.my_listings'))


@listings_bp.route('/<int:listing_id>/mark-sold', methods=['POST'])
@login_required
def mark_sold(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing or (listing.seller_id != current_user.id and not current_user.is_admin):
        abort(403)
        
    listing.status = 'sold'
    db.session.commit()
    flash("Item marked as Sold.", "success")
    return redirect(url_for('listings.detail', listing_id=listing.id))


@listings_bp.route('/<int:listing_id>/toggle-wishlist', methods=['POST'])
@login_required
def toggle_wishlist(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        return jsonify({'success': False, 'message': 'Listing not found'}), 404
        
    existing = Wishlist.query.filter_by(user_id=current_user.id, listing_id=listing.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        saved = False
        message = f"Removed '{listing.title}' from your wishlist."
    else:
        wishlist_item = Wishlist(user_id=current_user.id, listing_id=listing.id)
        db.session.add(wishlist_item)
        db.session.commit()
        saved = True
        message = f"Added '{listing.title}' to your wishlist!"
        
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'saved': saved, 'message': message})
        
    flash(message, "info")
    return redirect(request.referrer or url_for('listings.detail', listing_id=listing.id))


@listings_bp.route('/<int:listing_id>/report', methods=['GET', 'POST'])
@login_required
def report(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        abort(404)
        
    if listing.seller_id == current_user.id:
        flash("You cannot report your own listing.", "warning")
        return redirect(url_for('listings.detail', listing_id=listing.id))
        
    form = ReportForm()
    if form.validate_on_submit():
        report_entry = Report(
            reporter_id=current_user.id,
            reported_listing_id=listing.id,
            reason=form.reason.data,
            comment=form.comment.data.strip()
        )
        db.session.add(report_entry)
        db.session.commit()
        flash("Thank you. Your report regarding this listing has been submitted to campus moderators.", "success")
        return redirect(url_for('listings.detail', listing_id=listing.id))
        
    return render_template('listings/report.html', form=form, listing=listing)
