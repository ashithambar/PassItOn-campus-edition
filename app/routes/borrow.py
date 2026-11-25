from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.forms import BorrowRequestForm
from app.models import BorrowRequest, Category, Listing, Order, db

borrow_bp = Blueprint('borrow', __name__)

ACTIVE_ORDER_STATUSES = (
    'request_sent', 'accepted', 'payment_pending', 'payment_completed',
    'payment_confirmed', 'handover_pending'
)


@borrow_bp.route('/')
def index():
    query_text = request.args.get('q', '').strip()
    category_slug = request.args.get('category', '').strip()
    condition = request.args.get('condition', '').strip()
    sort_by = request.args.get('sort', 'newest')
    query = Listing.query.filter_by(status='available').filter(
        Listing.listing_type.in_(['borrow_only', 'sell_and_borrow'])
    )

    if query_text:
        query = query.filter(db.or_(
            Listing.title.ilike(f'%{query_text}%'),
            Listing.description.ilike(f'%{query_text}%'),
            Listing.location.ilike(f'%{query_text}%')
        ))

    if condition in {'New', 'Like New', 'Good', 'Used'}:
        query = query.filter(Listing.condition == condition)

    selected_category = None
    if category_slug:
        selected_category = Category.query.filter_by(slug=category_slug).first()
        if selected_category:
            query = query.filter(Listing.category_id == selected_category.id)

    if sort_by == 'price_asc':
        query = query.order_by(Listing.price.asc())
    elif sort_by == 'price_desc':
        query = query.order_by(Listing.price.desc())
    else:
        query = query.order_by(Listing.created_at.desc())

    pagination = query.paginate(page=request.args.get('page', 1, type=int), per_page=12, error_out=False)
    return render_template(
        'borrow/index.html',
        listings=pagination.items,
        pagination=pagination,
        categories=Category.query.order_by(Category.name).all(),
        query_text=query_text,
        current_condition=condition,
        selected_category=selected_category,
        current_sort=sort_by
    )


@borrow_bp.route('/request/<int:listing_id>', methods=['GET', 'POST'])
@login_required
def request_item(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing or listing.status != 'available' or not listing.is_borrowable:
        flash("This item is no longer available for borrowing.", "warning")
        return redirect(url_for('borrow.index'))

    if listing.seller_id == current_user.id:
        flash("You cannot borrow your own listing.", "warning")
        return redirect(url_for('listings.detail', listing_id=listing.id))

    active_sale = Order.query.filter(
        Order.listing_id == listing.id,
        Order.status.in_(ACTIVE_ORDER_STATUSES)
    ).first()
    if active_sale:
        flash("This item has an active purchase request and cannot be borrowed yet.", "warning")
        return redirect(url_for('listings.detail', listing_id=listing.id))

    form = BorrowRequestForm()
    if form.validate_on_submit():
        borrow_request = BorrowRequest(
            listing_id=listing.id,
            borrower_id=current_user.id,
            owner_id=listing.seller_id,
            active_listing_id=listing.id,
            start_date=form.start_date.data,
            expected_return_date=form.expected_return_date.data,
            status='pending'
        )
        listing.status = 'reserved'
        db.session.add(borrow_request)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Another borrowing request was just submitted for this item.", "warning")
            return redirect(url_for('listings.detail', listing_id=listing.id))

        flash("Your borrowing request was sent to the owner.", "success")
        return redirect(url_for('borrow.my_borrowings'))

    return render_template('borrow/request.html', listing=listing, form=form)


@borrow_bp.route('/my')
@login_required
def my_borrowings():
    borrow_requests = BorrowRequest.query.filter_by(
        borrower_id=current_user.id
    ).order_by(BorrowRequest.created_at.desc()).all()
    return render_template('borrow/my_borrowings.html', borrow_requests=borrow_requests)


@borrow_bp.route('/requests')
@login_required
def owner_requests():
    borrow_requests = BorrowRequest.query.filter_by(
        owner_id=current_user.id
    ).order_by(BorrowRequest.created_at.desc()).all()
    return render_template('borrow/owner_requests.html', borrow_requests=borrow_requests)


@borrow_bp.route('/requests/<int:borrow_request_id>')
@login_required
def detail(borrow_request_id):
    borrow_request = db.session.get(BorrowRequest, borrow_request_id)
    if not borrow_request:
        abort(404)
    if current_user.id not in (borrow_request.borrower_id, borrow_request.owner_id) and not current_user.is_admin:
        abort(403)
    return render_template('borrow/detail.html', borrow_request=borrow_request)


@borrow_bp.route('/requests/<int:borrow_request_id>/accept', methods=['POST'])
@login_required
def accept(borrow_request_id):
    borrow_request = db.session.get(BorrowRequest, borrow_request_id)
    if not borrow_request or (borrow_request.owner_id != current_user.id and not current_user.is_admin):
        abort(403)
    if borrow_request.status != 'pending' or borrow_request.listing.status != 'reserved':
        flash("This borrowing request can no longer be accepted.", "warning")
        return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))

    borrow_request.status = 'approved'
    db.session.commit()
    flash("Borrowing request approved. Mark the item borrowed when it is handed over.", "success")
    return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))


@borrow_bp.route('/requests/<int:borrow_request_id>/reject', methods=['POST'])
@login_required
def reject(borrow_request_id):
    borrow_request = db.session.get(BorrowRequest, borrow_request_id)
    if not borrow_request or (borrow_request.owner_id != current_user.id and not current_user.is_admin):
        abort(403)
    if borrow_request.status != 'pending':
        flash("Only pending borrowing requests can be rejected.", "warning")
        return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))

    borrow_request.status = 'rejected'
    borrow_request.active_listing_id = None
    if borrow_request.listing.status == 'reserved':
        borrow_request.listing.status = 'available'
    db.session.commit()
    flash("Borrowing request rejected. The item is available again.", "info")
    return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))


@borrow_bp.route('/requests/<int:borrow_request_id>/mark-borrowed', methods=['POST'])
@login_required
def mark_borrowed(borrow_request_id):
    borrow_request = db.session.get(BorrowRequest, borrow_request_id)
    if not borrow_request or (borrow_request.owner_id != current_user.id and not current_user.is_admin):
        abort(403)
    if borrow_request.status != 'approved' or borrow_request.listing.status != 'reserved':
        flash("Only an approved request can be marked borrowed.", "warning")
        return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))

    borrow_request.status = 'borrowed'
    borrow_request.listing.status = 'borrowed'
    db.session.commit()
    flash("The item is now marked as borrowed.", "success")
    return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))


@borrow_bp.route('/requests/<int:borrow_request_id>/request-return', methods=['POST'])
@login_required
def request_return(borrow_request_id):
    borrow_request = db.session.get(BorrowRequest, borrow_request_id)
    if not borrow_request or borrow_request.borrower_id != current_user.id:
        abort(403)
    if borrow_request.status != 'borrowed':
        flash("Only a borrowed item can be returned.", "warning")
        return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))

    borrow_request.status = 'return_requested'
    borrow_request.return_requested_at = datetime.utcnow()
    db.session.commit()
    flash("Return confirmation requested from the owner.", "success")
    return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))


@borrow_bp.route('/requests/<int:borrow_request_id>/confirm-return', methods=['POST'])
@login_required
def confirm_return(borrow_request_id):
    borrow_request = db.session.get(BorrowRequest, borrow_request_id)
    if not borrow_request or (borrow_request.owner_id != current_user.id and not current_user.is_admin):
        abort(403)
    if borrow_request.status != 'return_requested' or borrow_request.listing.status != 'borrowed':
        flash("There is no return awaiting confirmation.", "warning")
        return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))

    borrow_request.status = 'returned'
    borrow_request.returned_at = datetime.utcnow()
    borrow_request.return_confirmed_at = datetime.utcnow()
    borrow_request.active_listing_id = None
    borrow_request.listing.status = 'available'
    db.session.commit()
    flash("Return confirmed. The listing is available again.", "success")
    return redirect(url_for('borrow.detail', borrow_request_id=borrow_request.id))
