import os
from flask import Flask, render_template
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from app.config import Config
from app.models import db, User, Category, Notification, Message

login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure required directories exist
    upload_dirs = [
        app.config['UPLOAD_FOLDER'],
        os.path.join(app.config['UPLOAD_FOLDER'], 'listings'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'avatars'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'upi_qrs'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'handover_qrs'),
        os.path.join(app.static_folder, 'images'),
        os.path.join(app.root_path, '..', 'instance')
    ]
    for d in upload_dirs:
        os.makedirs(d, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this feature.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Global context processors
    @app.context_processor
    def inject_global_data():
        cats = []
        unread_notifs = 0
        unread_msgs = 0
        try:
            cats = Category.query.order_by(Category.name).all()
            if current_user.is_authenticated:
                unread_notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
                unread_msgs = Message.query.join(Message.conversation).filter(
                    Message.sender_id != current_user.id,
                    Message.is_read == False,
                    db.or_(
                        Message.conversation.has(user1_id=current_user.id),
                        Message.conversation.has(user2_id=current_user.id)
                    )
                ).count()
        except Exception:
            pass
        return {
            'all_categories': cats,
            'unread_notifications_count': unread_notifs,
            'unread_messages_count': unread_msgs,
            'app_name': 'PassItOn – Campus Edition',
            'tagline': "One student's unused item becomes another student's useful item."
        }

    # Error handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.listings import listings_bp
    from app.routes.orders import orders_bp
    from app.routes.chat import chat_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(listings_bp, url_prefix='/listings')
    app.register_blueprint(orders_bp, url_prefix='/orders')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app
