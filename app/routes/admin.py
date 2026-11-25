from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.models import db, User, Listing, Category, Order, Payment, Report
from app.forms import CategoryForm
from app.utils import admin_required

admin_bp = Blueprint('admin', __name__)


def _category_slug(name):
    return name.strip().lower().replace(' ', '-').replace('&', 'and')


def _find_duplicate_category(name, slug, exclude_id=None):
    query = Category.query.filter(
        db.or_(
            db.func.lower(Category.name) == name.lower(),
            db.func.lower(Category.slug) == slug.lower()
        )
    )
    if exclude_id is not None:
        query = query.filter(Category.id != exclude_id)
    return query.first()


@admin_bp.before_request
@login_required
def check_admin():
    if not current_user.is_admin:
        abort(403)


@admin_bp.route('/')
def index():
    total_users = User.query.filter_by(role='student').count()
    total_listings = Listing.query.filter(Listing.status != 'deleted').count()
    active_listings = Listing.query.filter_by(status='available').count()
    sold_listings = Listing.query.filter_by(status='sold').count()
    
    completed_orders = Order.query.filter_by(status='completed').count()
    total_volume = db.session.query(db.func.sum(Payment.amount)).filter(Payment.status.in_(['confirmed', 'submitted'])).scalar() or 0.0
    pending_reports = Report.query.filter_by(status='pending').count()

    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(6).all()
    recent_reports = Report.query.filter_by(status='pending').order_by(Report.created_at.desc()).limit(5).all()

    return render_template(
        'admin/index.html',
        total_users=total_users,
        total_listings=total_listings,
        active_listings=active_listings,
        sold_listings=sold_listings,
        completed_orders=completed_orders,
        total_volume=total_volume,
        pending_reports=pending_reports,
        recent_orders=recent_orders,
        recent_reports=recent_reports
    )


@admin_bp.route('/api/stats')
def api_stats():
    # Category distribution for Chart.js
    categories = Category.query.all()
    cat_labels = []
    cat_counts = []
    for c in categories:
        count = Listing.query.filter_by(category_id=c.id).filter(Listing.status != 'deleted').count()
        cat_labels.append(c.name)
        cat_counts.append(count)
        
    # Listing condition distribution
    condition_counts = {
        'New': Listing.query.filter_by(condition='New').filter(Listing.status != 'deleted').count(),
        'Like New': Listing.query.filter_by(condition='Like New').filter(Listing.status != 'deleted').count(),
        'Good': Listing.query.filter_by(condition='Good').filter(Listing.status != 'deleted').count(),
        'Used': Listing.query.filter_by(condition='Used').filter(Listing.status != 'deleted').count(),
    }
    
    # Order statuses
    order_status_counts = {
        'Completed': Order.query.filter_by(status='completed').count(),
        'Handover Pending': Order.query.filter_by(status='handover_pending').count(),
        'Payment In Progress': Order.query.filter(Order.status.in_(['payment_pending', 'payment_completed'])).count(),
        'Request Sent': Order.query.filter_by(status='request_sent').count(),
        'Cancelled/Rejected': Order.query.filter(Order.status.in_(['cancelled', 'rejected'])).count()
    }

    return jsonify({
        'categories': {
            'labels': cat_labels,
            'counts': cat_counts
        },
        'conditions': {
            'labels': list(condition_counts.keys()),
            'counts': list(condition_counts.values())
        },
        'orders': {
            'labels': list(order_status_counts.keys()),
            'counts': list(order_status_counts.values())
        }
    })


@admin_bp.route('/users')
def users():
    search = request.args.get('q', '').strip()
    query = User.query
    if search:
        query = query.filter(
            db.or_(
                User.name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.department.ilike(f'%{search}%')
            )
        )
    user_list = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=user_list, search=search)


@admin_bp.route('/users/<int:user_id>/toggle-block', methods=['POST'])
def toggle_block_user(user_id):
    target_user = db.session.get(User, user_id)
    if not target_user:
        abort(404)
        
    if target_user.role == 'admin':
        flash("Admin accounts cannot be suspended.", "danger")
        return redirect(url_for('admin.users'))
        
    target_user.is_blocked = not target_user.is_blocked
    db.session.commit()
    
    state_str = "suspended" if target_user.is_blocked else "reactivated"
    flash(f"User {target_user.name} ({target_user.email}) has been {state_str}.", "warning" if target_user.is_blocked else "success")
    return redirect(url_for('admin.users'))


@admin_bp.route('/listings')
def listings():
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all')
    
    query = Listing.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
        
    if search:
        query = query.filter(
            db.or_(
                Listing.title.ilike(f'%{search}%'),
                Listing.description.ilike(f'%{search}%')
            )
        )
        
    all_listings = query.order_by(Listing.created_at.desc()).all()
    return render_template('admin/listings.html', listings=all_listings, search=search, current_status=status_filter)


@admin_bp.route('/listings/<int:listing_id>/delete', methods=['POST'])
def delete_listing(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        abort(404)
        
    if listing.status in {'reserved', 'borrowed'}:
        flash("A reserved or borrowed listing cannot be removed until its transaction is resolved.", "warning")
        return redirect(url_for('admin.listings'))

    listing.status = 'deleted'
    db.session.commit()
    flash(f"Listing '{listing.title}' has been removed by admin moderation.", "info")
    return redirect(url_for('admin.listings'))


@admin_bp.route('/transactions')
def transactions():
    all_orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/transactions.html', orders=all_orders)


@admin_bp.route('/categories', methods=['GET', 'POST'])
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        slug = _category_slug(name)
        if _find_duplicate_category(name, slug):
            flash("A category with this name or URL already exists.", "danger")
        else:
            cat = Category(
                name=name,
                slug=slug,
                icon=form.icon.data.strip(),
                description=form.description.data.strip() if form.description.data else None
            )
            db.session.add(cat)
            db.session.commit()
            flash(f"Category '{cat.name}' created successfully!", "success")
            return redirect(url_for('admin.categories'))
            
    cats = Category.query.order_by(Category.name).all()
    return render_template('admin/categories.html', categories=cats, form=form)


@admin_bp.route('/categories/<int:cat_id>/edit', methods=['GET', 'POST'])
def edit_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if not cat:
        abort(404)
        
    form = CategoryForm(obj=cat)
    if form.validate_on_submit():
        name = form.name.data.strip()
        slug = _category_slug(name)
        if _find_duplicate_category(name, slug, exclude_id=cat.id):
            flash("A category with this name or URL already exists.", "danger")
            return render_template('admin/edit_category.html', form=form, category=cat)

        cat.name = name
        cat.slug = slug
        cat.icon = form.icon.data.strip()
        cat.description = form.description.data.strip() if form.description.data else None
        db.session.commit()
        flash(f"Category '{cat.name}' updated successfully!", "success")
        return redirect(url_for('admin.categories'))
        
    return render_template('admin/edit_category.html', form=form, category=cat)


@admin_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
def delete_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if not cat:
        abort(404)
        
    if cat.listings.count() > 0:
        flash(f"Cannot delete '{cat.name}' because {cat.listings.count()} listings belong to it. Reassign listings first.", "danger")
        return redirect(url_for('admin.categories'))
        
    db.session.delete(cat)
    db.session.commit()
    flash(f"Category '{cat.name}' deleted.", "info")
    return redirect(url_for('admin.categories'))


@admin_bp.route('/reports')
def reports():
    status_filter = request.args.get('status', 'all')
    query = Report.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
        
    all_reports = query.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=all_reports, current_status=status_filter)


@admin_bp.route('/reports/<int:report_id>/resolve', methods=['POST'])
def resolve_report(report_id):
    report = db.session.get(Report, report_id)
    if not report:
        abort(404)
        
    action = request.form.get('action', 'resolve')
    admin_notes = request.form.get('admin_notes', '').strip()
    
    if action == 'resolve':
        report.status = 'resolved'
    elif action == 'dismiss':
        report.status = 'dismissed'
        
    report.admin_notes = admin_notes
    report.resolved_at = datetime.utcnow()
    db.session.commit()
    
    flash(f"Report #{report.id} marked as {report.status}.", "success")
    return redirect(url_for('admin.reports'))
