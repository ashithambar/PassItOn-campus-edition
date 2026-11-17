import secrets
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app.models import db, Order, Payment, HandoverRecord, Listing, User, Review, Wishlist
from app.forms import OrderRequestForm, PaymentProofForm, HandoverVerifyForm, ReviewForm
from app.utils import (
    generate_handover_qr, generate_dynamic_upi_qr, 
    create_notification, save_uploaded_file
)

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/request/<int:listing_id>', methods=['GET', 'POST'])
@login_required
def request_item(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing or listing.status != 'available':
        flash("This item is no longer available for purchase.", "warning")
        return redirect(url_for('listings.index'))
        
    if listing.seller_id == current_user.id:
        flash("You cannot buy or request your own listing.", "warning")
        return redirect(url_for('listings.detail', listing_id=listing.id))
        
    # Check if user already has an active pending request for this listing
    existing_order = Order.query.filter_by(
        listing_id=listing.id,
        buyer_id=current_user.id
    ).filter(Order.status.in_(['request_sent', 'accepted', 'payment_pending', 'payment_completed', 'handover_pending'])).first()
    
    if existing_order:
        flash("You already have an active request/order for this item.", "info")
        return redirect(url_for('orders.detail', order_id=existing_order.id))
        
    form = OrderRequestForm()
    if form.validate_on_submit():
        order_num = f"ORD-{secrets.token_hex(4).upper()}"
        
        order = Order(
            order_number=order_num,
            listing_id=listing.id,
            buyer_id=current_user.id,
            seller_id=listing.seller_id,
            payment_method=form.payment_method.data,
            notes=form.notes.data.strip() if form.notes.data else None,
            status='request_sent'
        )
        db.session.add(order)
        db.session.flush()
        
        # Create initial payment record
        payment = Payment(
            order_id=order.id,
            buyer_id=current_user.id,
            seller_id=listing.seller_id,
            amount=listing.price,
            payment_method=form.payment_method.data,
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()
        
        # Notify seller
        create_notification(
            user_id=listing.seller_id,
            title="New Purchase Request!",
            message=f"{current_user.name} sent a request to buy '{listing.title}' for ₹{int(listing.price)}.",
            link=url_for('orders.detail', order_id=order.id),
            notification_type='order_request'
        )
        
        flash("Your request has been submitted to the seller! You will be notified once they accept.", "success")
        return redirect(url_for('orders.detail', order_id=order.id))
        
    return render_template('orders/request.html', form=form, listing=listing)


@orders_bp.route('/<int:order_id>')
@login_required
def detail(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
        
    # Security check: only buyer, seller, or admin can view
    if current_user.id not in (order.buyer_id, order.seller_id) and not current_user.is_admin:
        abort(403)
        
    payment_form = PaymentProofForm()
    verify_form = HandoverVerifyForm()
    
    # Generate UPI QR image path if payment method is UPI and seller hasn't provided a manual image
    dynamic_upi_qr = None
    if order.payment_method == 'upi' and order.seller.upi_id:
        if not order.seller.upi_qr_image:
            dynamic_upi_qr = generate_dynamic_upi_qr(
                upi_id=order.seller.upi_id,
                payee_name=order.seller.name,
                amount=order.payment.amount if order.payment else order.listing.price
            )
            
    # Check if current user has already submitted a review
    existing_review = Review.query.filter_by(order_id=order.id, reviewer_id=current_user.id).first()

    return render_template(
        'orders/detail.html',
        order=order,
        payment_form=payment_form,
        verify_form=verify_form,
        dynamic_upi_qr=dynamic_upi_qr,
        existing_review=existing_review
    )


@orders_bp.route('/<int:order_id>/accept', methods=['POST'])
@login_required
def accept_request(order_id):
    order = db.session.get(Order, order_id)
    if not order or (order.seller_id != current_user.id and not current_user.is_admin):
        abort(403)
        
    if order.status != 'request_sent':
        flash("Order cannot be accepted in its current state.", "warning")
        return redirect(url_for('orders.detail', order_id=order.id))
        
    # Reserve listing
    order.listing.status = 'reserved'
    
    if order.payment_method == 'upi':
        order.status = 'payment_pending'
    else:
        # Cash on handover skips online payment
        order.status = 'handover_pending'
        # Generate handover QR for cash order
        if not order.handover:
            token, qr_path = generate_handover_qr(order.order_number)
            handover = HandoverRecord(
                order_id=order.id,
                token=token,
                qr_image_path=qr_path
            )
            db.session.add(handover)
            
    db.session.commit()
    
    create_notification(
        user_id=order.buyer_id,
        title="Purchase Request Accepted!",
        message=f"Seller {current_user.name} accepted your request for '{order.listing.title}'.",
        link=url_for('orders.detail', order_id=order.id),
        notification_type='order_accepted'
    )
    
    flash("You accepted the request! The item is now reserved.", "success")
    return redirect(url_for('orders.detail', order_id=order.id))


@orders_bp.route('/<int:order_id>/reject', methods=['POST'])
@login_required
def reject_request(order_id):
    order = db.session.get(Order, order_id)
    if not order or (order.seller_id != current_user.id and not current_user.is_admin):
        abort(403)
        
    order.status = 'rejected'
    if order.listing.status == 'reserved':
        order.listing.status = 'available'
        
    db.session.commit()
    
    create_notification(
        user_id=order.buyer_id,
        title="Purchase Request Declined",
        message=f"Seller declined your request for '{order.listing.title}'.",
        link=url_for('listings.detail', listing_id=order.listing.id),
        notification_type='order_rejected'
    )
    
    flash("Purchase request rejected.", "info")
    return redirect(url_for('orders.detail', order_id=order.id))


@orders_bp.route('/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = db.session.get(Order, order_id)
    if not order or (order.buyer_id != current_user.id and not current_user.is_admin):
        abort(403)
        
    if order.status in ['completed', 'payment_confirmed']:
        flash("Order cannot be cancelled at this stage.", "danger")
        return redirect(url_for('orders.detail', order_id=order.id))
        
    order.status = 'cancelled'
    if order.listing.status == 'reserved':
        order.listing.status = 'available'
        
    db.session.commit()
    
    create_notification(
        user_id=order.seller_id,
        title="Order Request Cancelled",
        message=f"Buyer {current_user.name} cancelled their request for '{order.listing.title}'.",
        link=url_for('listings.detail', listing_id=order.listing.id),
        notification_type='order_cancelled'
    )
    
    flash("Order cancelled successfully.", "info")
    return redirect(url_for('dashboard.my_purchases'))


@orders_bp.route('/<int:order_id>/submit-payment', methods=['POST'])
@login_required
def submit_payment(order_id):
    order = db.session.get(Order, order_id)
    if not order or order.buyer_id != current_user.id:
        abort(403)
        
    form = PaymentProofForm()
    if form.validate_on_submit():
        ref_id = form.transaction_reference.data.strip()
        
        proof_path = None
        if form.proof_image.data:
            proof_path = save_uploaded_file(form.proof_image.data, folder_name='upi_qrs')
            
        if not order.payment:
            order.payment = Payment(
                order_id=order.id,
                buyer_id=order.buyer_id,
                seller_id=order.seller_id,
                amount=order.listing.price,
                payment_method='upi'
            )
            
        order.payment.transaction_reference = ref_id
        if proof_path:
            order.payment.proof_image = proof_path
        order.payment.status = 'submitted'
        order.status = 'payment_completed'
        
        db.session.commit()
        
        create_notification(
            user_id=order.seller_id,
            title="Payment Marked by Buyer!",
            message=f"{current_user.name} submitted payment ref: {ref_id} for '{order.listing.title}'. Please verify.",
            link=url_for('orders.detail', order_id=order.id),
            notification_type='payment_submitted'
        )
        
        flash("Payment marked as completed! Seller will verify and confirm.", "success")
    else:
        flash("Please enter a valid transaction reference / UTR number.", "danger")
        
    return redirect(url_for('orders.detail', order_id=order.id))


@orders_bp.route('/<int:order_id>/confirm-payment', methods=['POST'])
@login_required
def confirm_payment(order_id):
    order = db.session.get(Order, order_id)
    if not order or (order.seller_id != current_user.id and not current_user.is_admin):
        abort(403)
        
    if order.payment:
        order.payment.status = 'confirmed'
        order.payment.confirmed_at = datetime.utcnow()
        
    order.status = 'handover_pending'
    
    # Generate Handover QR for buyer
    if not order.handover:
        token, qr_path = generate_handover_qr(order.order_number)
        handover = HandoverRecord(
            order_id=order.id,
            token=token,
            qr_image_path=qr_path
        )
        db.session.add(handover)
        
    db.session.commit()
    
    create_notification(
        user_id=order.buyer_id,
        title="Payment Confirmed by Seller!",
        message=f"Seller {current_user.name} confirmed your payment! Your Handover QR code is ready.",
        link=url_for('orders.detail', order_id=order.id),
        notification_type='payment_confirmed'
    )
    
    flash("Payment confirmed! Handover QR code has been generated for the buyer.", "success")
    return redirect(url_for('orders.detail', order_id=order.id))


@orders_bp.route('/<int:order_id>/reject-payment', methods=['POST'])
@login_required
def reject_payment(order_id):
    order = db.session.get(Order, order_id)
    if not order or (order.seller_id != current_user.id and not current_user.is_admin):
        abort(403)
        
    if order.payment:
        order.payment.status = 'failed'
    order.status = 'payment_pending'
    db.session.commit()
    
    create_notification(
        user_id=order.buyer_id,
        title="Payment Not Received Notice",
        message=f"Seller {current_user.name} could not verify your payment reference. Please check and re-submit.",
        link=url_for('orders.detail', order_id=order.id),
        notification_type='payment_rejected'
    )
    
    flash("Payment marked as not received. Buyer has been notified.", "warning")
    return redirect(url_for('orders.detail', order_id=order.id))


@orders_bp.route('/<int:order_id>/verify-handover', methods=['GET', 'POST'])
@login_required
def verify_handover(order_id):
    order = db.session.get(Order, order_id)
    if not order or (order.seller_id != current_user.id and not current_user.is_admin):
        abort(403)
        
    if order.status != 'handover_pending':
        flash("Order is not currently pending handover.", "warning")
        return redirect(url_for('orders.detail', order_id=order.id))
        
    form = HandoverVerifyForm()
    
    if form.validate_on_submit():
        input_token = form.token.data.strip()
        handover = order.handover
        
        if not handover:
            flash("No handover record found for this order.", "danger")
            return redirect(url_for('orders.detail', order_id=order.id))
            
        if handover.is_used:
            flash("This handover code has already been verified.", "warning")
            return redirect(url_for('orders.detail', order_id=order.id))
            
        if handover.token == input_token:
            # Mark handover completed
            handover.is_used = True
            handover.verified_at = datetime.utcnow()
            handover.verified_by_id = current_user.id
            
            order.status = 'completed'
            order.listing.status = 'sold'
            
            # Notify Wishlist holders that the item has been sold
            wishlist_users = Wishlist.query.filter_by(listing_id=order.listing.id).all()
            for w in wishlist_users:
                if w.user_id != order.buyer_id:
                    create_notification(
                        user_id=w.user_id,
                        title="Wishlist Item Sold",
                        message=f"'{order.listing.title}' on your wishlist has just been sold.",
                        link=url_for('listings.detail', listing_id=order.listing.id),
                        notification_type='wishlist_sold'
                    )
                    
            db.session.commit()
            
            # Notify buyer
            create_notification(
                user_id=order.buyer_id,
                title="Handover Complete!",
                message=f"Seller {current_user.name} successfully scanned your QR! Order is completed. Please rate your experience.",
                link=url_for('orders.review', order_id=order.id),
                notification_type='order_completed'
            )
            
            flash("Handover Verified Successfully! The item has been marked as Sold.", "success")
            return redirect(url_for('orders.review', order_id=order.id))
        else:
            flash("Invalid security code. Please ensure the buyer shows their current order QR code.", "danger")
            
    return render_template('orders/scan_qr.html', order=order, form=form)


@orders_bp.route('/<int:order_id>/review', methods=['GET', 'POST'])
@login_required
def review(order_id):
    order = db.session.get(Order, order_id)
    if not order or order.status != 'completed':
        flash("Reviews can only be submitted after the order is completed.", "warning")
        return redirect(url_for('dashboard.my_purchases'))
        
    if current_user.id not in (order.buyer_id, order.seller_id):
        abort(403)
        
    # Check if already reviewed
    existing = Review.query.filter_by(order_id=order.id, reviewer_id=current_user.id).first()
    if existing:
        flash("You have already submitted a review for this transaction.", "info")
        return redirect(url_for('orders.detail', order_id=order.id))
        
    form = ReviewForm()
    is_buyer = (current_user.id == order.buyer_id)
    reviewee = order.seller if is_buyer else order.buyer
    role = 'buyer_to_seller' if is_buyer else 'seller_to_buyer'
    
    if form.validate_on_submit():
        review_entry = Review(
            order_id=order.id,
            reviewer_id=current_user.id,
            reviewee_id=reviewee.id,
            rating=int(form.rating.data),
            comment=form.comment.data.strip(),
            role=role
        )
        db.session.add(review_entry)
        db.session.commit()
        
        create_notification(
            user_id=reviewee.id,
            title="New Rating & Review!",
            message=f"{current_user.name} gave you a {form.rating.data}-star rating for order {order.order_number}.",
            link=url_for('auth.profile'),
            notification_type='new_review'
        )
        
        flash("Thank you for your rating and feedback!", "success")
        return redirect(url_for('orders.detail', order_id=order.id))
        
    return render_template('orders/review.html', form=form, order=order, reviewee=reviewee, is_buyer=is_buyer)
