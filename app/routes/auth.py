import secrets
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, Listing, Review, Report
from app.forms import (
    RegistrationForm, LoginForm, ForgotPasswordForm, 
    ResetPasswordForm, ProfileEditForm, ReportForm
)
from app.utils import save_uploaded_file, create_notification

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=form.phone.data.strip(),
            department=form.department.data,
            year_semester=form.year_semester.data,
            college=form.college.data.strip(),
            role='student'
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        create_notification(
            user_id=user.id,
            title="Welcome to PassItOn – Campus Edition!",
            message="Your student marketplace account is active. You can now browse, wishlist, buy, and sell items easily on campus.",
            link=url_for('listings.create')
        )
        
        flash("Registration successful! You can now log in with your campus credentials.", "success")
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        
        if not user or not user.check_password(form.password.data):
            flash("Invalid email or password. Please check your credentials.", "danger")
            return render_template('auth/login.html', form=form)
            
        if user.is_blocked:
            flash("Your account has been suspended by the campus administrator. Please contact support.", "danger")
            return render_template('auth/login.html', form=form)
            
        login_user(user, remember=form.remember.data)
        flash(f"Welcome back, {user.name}!", "success")
        
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('main.index'))
        
    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('main.index'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = ForgotPasswordForm()
    reset_url = None
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            db.session.commit()
            
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            print("\n" + "="*60)
            print(f"[DEMO EMAIL SERVICE] Password Reset Request for {user.email}")
            print(f"Reset Link: {reset_url}")
            print("="*60 + "\n")
            
            flash("A password reset link has been generated! (See below for local demo testing)", "info")
        else:
            flash("If that email address is registered, a password reset link has been generated.", "info")
            
    return render_template('auth/forgot_password.html', form=form, reset_url=reset_url)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    user = User.query.filter_by(reset_token=token).first()
    if not user:
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for('auth.forgot_password'))
        
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.reset_token = None
        db.session.commit()
        flash("Your password has been successfully reset! Please sign in with your new password.", "success")
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', form=form)


@auth_bp.route('/profile')
@login_required
def profile():
    active_listings = Listing.query.filter_by(seller_id=current_user.id, status='available').order_by(Listing.created_at.desc()).all()
    sold_listings = Listing.query.filter_by(seller_id=current_user.id, status='sold').order_by(Listing.created_at.desc()).all()
    reviews = Review.query.filter_by(reviewee_id=current_user.id).order_by(Review.created_at.desc()).all()
    avg_rating = current_user.get_average_rating()
    
    return render_template(
        'auth/profile.html', 
        user=current_user,
        active_listings=active_listings,
        sold_listings=sold_listings,
        reviews=reviews,
        avg_rating=avg_rating,
        is_own_profile=True
    )


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileEditForm(obj=current_user)
    
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.phone = form.phone.data.strip()
        current_user.department = form.department.data
        current_user.year_semester = form.year_semester.data
        current_user.college = form.college.data.strip()
        current_user.upi_id = form.upi_id.data.strip() if form.upi_id.data else None
        
        # Profile Picture Upload
        if form.profile_pic.data:
            avatar_path = save_uploaded_file(form.profile_pic.data, folder_name='avatars')
            if avatar_path:
                current_user.profile_pic = avatar_path
                
        # UPI QR Upload
        if form.upi_qr.data:
            qr_path = save_uploaded_file(form.upi_qr.data, folder_name='upi_qrs')
            if qr_path:
                current_user.upi_qr_image = qr_path
                
        db.session.commit()
        flash("Your profile information has been updated successfully!", "success")
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/edit_profile.html', form=form)


@auth_bp.route('/user/<int:user_id>')
def view_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("Student user not found.", "warning")
        return redirect(url_for('main.index'))
        
    is_own = current_user.is_authenticated and current_user.id == user.id
    if is_own:
        return redirect(url_for('auth.profile'))
        
    active_listings = Listing.query.filter_by(seller_id=user.id, status='available').order_by(Listing.created_at.desc()).all()
    sold_listings = Listing.query.filter_by(seller_id=user.id, status='sold').order_by(Listing.created_at.desc()).all()
    reviews = Review.query.filter_by(reviewee_id=user.id).order_by(Review.created_at.desc()).all()
    avg_rating = user.get_average_rating()
    
    return render_template(
        'auth/profile.html',
        user=user,
        active_listings=active_listings,
        sold_listings=sold_listings,
        reviews=reviews,
        avg_rating=avg_rating,
        is_own_profile=False
    )


@auth_bp.route('/user/<int:user_id>/report', methods=['GET', 'POST'])
@login_required
def report_user(user_id):
    if user_id == current_user.id:
        flash("You cannot report yourself.", "warning")
        return redirect(url_for('auth.profile'))
        
    target_user = db.session.get(User, user_id)
    if not target_user:
        flash("User not found.", "warning")
        return redirect(url_for('main.index'))
        
    form = ReportForm()
    if form.validate_on_submit():
        report = Report(
            reporter_id=current_user.id,
            reported_user_id=target_user.id,
            reason=form.reason.data,
            comment=form.comment.data.strip()
        )
        db.session.add(report)
        db.session.commit()
        flash("Your report has been submitted to campus administrators for review. Thank you for keeping the campus community safe.", "success")
        return redirect(url_for('auth.view_user', user_id=target_user.id))
        
    return render_template('auth/report_user.html', form=form, target_user=target_user)
