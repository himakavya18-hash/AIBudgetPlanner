from flask import Flask
from flask_login import LoginManager
from app.config import Config
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Register Blueprints
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.dashboard.routes import dashboard_bp
    from app.blueprints.transactions.routes import transactions_bp
    from app.blueprints.goals.routes import goals_bp
    from app.blueprints.ai.routes import ai_bp
    from app.blueprints.reports.routes import reports_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp, url_prefix='/transactions')
    app.register_blueprint(goals_bp, url_prefix='/goals')
    app.register_blueprint(ai_bp, url_prefix='/ai')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    # Create tables if they do not exist
    with app.app_context():
        db.create_all()
        
    return app
