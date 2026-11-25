from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from wtforms.fields import DateField
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField, 
    TextAreaField, SelectField, FloatField, IntegerField, RadioField
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, ValidationError, 
    Optional, NumberRange, Regexp
)
from app.models import User

DEPARTMENT_CHOICES = [
    ('Computer Science & Engg', 'Computer Science & Engg'),
    ('Electronics & Communication', 'Electronics & Communication'),
    ('Mechanical Engineering', 'Mechanical Engineering'),
    ('Civil Engineering', 'Civil Engineering'),
    ('Electrical & Electronics', 'Electrical & Electronics'),
    ('Information Technology', 'Information Technology'),
    ('Biotechnology & Chemical', 'Biotechnology & Chemical'),
    ('Architecture & Design', 'Architecture & Design'),
    ('Business & Management (MBA/BBA)', 'Business & Management (MBA/BBA)'),
    ('Basic Sciences (Math/Physics/Chem)', 'Basic Sciences (Math/Physics/Chem)'),
    ('Arts & Humanities', 'Arts & Humanities'),
    ('Other Department', 'Other Department')
]

YEAR_CHOICES = [
    ('1st Year / 1st-2nd Sem', '1st Year / 1st-2nd Sem'),
    ('2nd Year / 3rd-4th Sem', '2nd Year / 3rd-4th Sem'),
    ('3rd Year / 5th-6th Sem', '3rd Year / 5th-6th Sem'),
    ('4th Year / 7th-8th Sem', '4th Year / 7th-8th Sem'),
    ('Post-Graduate (M.Tech/MBA/M.Sc)', 'Post-Graduate (M.Tech/MBA/M.Sc)'),
    ('PhD / Research Scholar', 'PhD / Research Scholar')
]

class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('College/Personal Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=6, message="Password must be at least 6 characters long")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message="Passwords must match")
    ])
    phone = StringField('Phone / WhatsApp Number', validators=[
        DataRequired(),
        Regexp(r'^[0-9+\-\s]{10,15}$', message="Enter a valid 10-15 digit phone number")
    ])
    department = SelectField('Department', choices=DEPARTMENT_CHOICES, validators=[DataRequired()])
    year_semester = SelectField('Year / Semester', choices=YEAR_CHOICES, validators=[DataRequired()])
    college = StringField('College / Campus Name', validators=[DataRequired(), Length(max=150)], default="Apex Institute of Technology")
    submit = SubmitField('Create Campus Account')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.strip().lower()).first()
        if user:
            raise ValidationError('An account with this email address already exists.')


class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Registered Email Address', validators=[DataRequired(), Email()])
    submit = SubmitField('Generate Reset Link')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(), 
        Length(min=6, message="Password must be at least 6 characters")
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(), 
        EqualTo('password', message="Passwords must match")
    ])
    submit = SubmitField('Reset Password')


class ProfileEditForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Phone Number', validators=[DataRequired()])
    department = SelectField('Department', choices=DEPARTMENT_CHOICES, validators=[DataRequired()])
    year_semester = SelectField('Year / Semester', choices=YEAR_CHOICES, validators=[DataRequired()])
    college = StringField('College Name', validators=[DataRequired(), Length(max=150)])
    upi_id = StringField('Your UPI ID (e.g. username@okhdfcbank)', validators=[Optional(), Length(max=100)])
    profile_pic = FileField('Change Profile Picture', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'webp'], 'Images only!')
    ])
    upi_qr = FileField('Upload Your Personal UPI QR Image (Optional)', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'webp'], 'Images only!')
    ])
    submit = SubmitField('Save Profile Changes')


class ListingForm(FlaskForm):
    title = StringField('Item Title', validators=[
        DataRequired(), 
        Length(min=3, max=150, message="Title must be between 3 and 150 characters")
    ])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    listing_type = SelectField('Available For', choices=[
        ('sell_only', 'Sell Only'),
        ('borrow_only', 'Borrow Only'),
        ('sell_and_borrow', 'Sell and Borrow')
    ], default='sell_only', validators=[DataRequired()])
    description = TextAreaField('Detailed Description', validators=[
        DataRequired(), 
        Length(min=10, message="Please write a clear description (at least 10 chars)")
    ])
    condition = SelectField('Item Condition', choices=[
        ('New', 'Brand New / Sealed Box'),
        ('Like New', 'Like New (Used a few times, no scratches)'),
        ('Good', 'Good (Working properly, normal minor wear)'),
        ('Used', 'Fair / Well Used (Fully functional)')
    ], validators=[DataRequired()])
    price = FloatField('Your Selling Price (₹)', validators=[
        Optional(),
        NumberRange(min=0, message="Price cannot be negative")
    ])
    original_price = FloatField('Original / MRP Price (₹) [Optional]', validators=[
        Optional(), 
        NumberRange(min=1, message="Original price must be positive")
    ])
    item_age_months = IntegerField('Item Age (in months)', default=0, validators=[
        Optional(), 
        NumberRange(min=0, message="Age cannot be negative")
    ])
    location = StringField('Campus Handover Location', validators=[
        DataRequired(), 
        Length(max=120)
    ], default="Campus Central Library / Cafeteria")
    contact_info = StringField('Contact / WhatsApp (Optional)', validators=[
        Optional(), 
        Length(max=120)
    ])
    extra_details = TextAreaField('Additional Specs / Notes (Optional)')
    images = MultipleFileField('Item Photos (Up to 5 images)', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'webp', 'gif'], 'Only image files allowed!')
    ])
    submit = SubmitField('Publish Listing')

    def validate_price(self, field):
        if self.listing_type.data in {'sell_only', 'sell_and_borrow'} and (field.data is None or field.data < 1):
            raise ValidationError("Enter a selling price of at least ₹1 for listings available to purchase.")


class BorrowRequestForm(FlaskForm):
    start_date = DateField('Requested Borrowing Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    expected_return_date = DateField('Expected Return Date', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Send Borrow Request')

    def validate_start_date(self, field):
        if field.data and field.data < date.today():
            raise ValidationError("The borrowing start date cannot be in the past.")

    def validate_expected_return_date(self, field):
        if field.data and self.start_date.data and field.data <= self.start_date.data:
            raise ValidationError("The expected return date must be after the borrowing start date.")


class OrderRequestForm(FlaskForm):
    payment_method = RadioField('Payment Method', choices=[
        ('upi', 'UPI / GPay Demo QR Code (Fast & Digital)'),
        ('cash', 'Cash on Campus Handover')
    ], default='upi', validators=[DataRequired()])
    notes = TextAreaField('Handover Note for Seller (e.g., "Available to meet today at 4 PM near Block 3")', validators=[
        Optional(), 
        Length(max=300)
    ])
    submit = SubmitField('Send Purchase Request')


class PaymentProofForm(FlaskForm):
    transaction_reference = StringField('UPI Reference / UTR Number / Transaction ID', validators=[
        DataRequired(),
        Length(min=6, max=60, message="Enter a valid transaction reference/UTR")
    ])
    proof_image = FileField('Payment Screenshot (Optional)', validators=[
        Optional(),
        FileAllowed(['jpg', 'png', 'jpeg', 'webp'], 'Images only!')
    ])
    submit = SubmitField('I Have Completed Payment')


class HandoverVerifyForm(FlaskForm):
    token = StringField('Enter Handover Security Code', validators=[
        DataRequired(),
        Length(min=8, max=64, message="Invalid token format")
    ])
    submit = SubmitField('Verify & Complete Handover')


class ReviewForm(FlaskForm):
    rating = RadioField('Rating', choices=[
        ('5', '★★★★★ (5 Stars - Outstanding)'),
        ('4', '★★★★☆ (4 Stars - Very Good)'),
        ('3', '★★★☆☆ (3 Stars - Satisfactory)'),
        ('2', '★★☆☆☆ (2 Stars - Mediocre)'),
        ('1', '★☆☆☆☆ (1 Star - Poor)')
    ], default='5', validators=[DataRequired()])
    comment = TextAreaField('Write a Review (Describe your experience)', validators=[
        DataRequired(), 
        Length(min=5, max=500, message="Review must be between 5 and 500 characters")
    ])
    submit = SubmitField('Submit Rating & Review')


class ReportForm(FlaskForm):
    reason = SelectField('Reason for Report', choices=[
        ('fake', 'Fake Listing / Item Does Not Exist'),
        ('wrong_info', 'Misleading / Inaccurate Information'),
        ('scam', 'Suspicious Activity / Potential Scam'),
        ('inappropriate', 'Inappropriate, Offensive, or Prohibited Content'),
        ('other', 'Other Violation of Campus Guidelines')
    ], validators=[DataRequired()])
    comment = TextAreaField('Details / Explanation', validators=[
        DataRequired(), 
        Length(min=10, max=500, message="Please describe the issue (10-500 characters)")
    ])
    submit = SubmitField('Submit Report to Admin')


class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    icon = StringField('Bootstrap Icon Class (e.g. bi-book, bi-laptop, bi-calculator)', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional(), Length(max=250)])
    submit = SubmitField('Save Category')
