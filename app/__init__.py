from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask import Blueprint, render_template
import os 
#going to use pymysql
from dotenv import load_dotenv
from flask_migrate import Migrate


#use flask sqlAlchemy for database
#database
db = SQLAlchemy()
load_dotenv() #get the .env file with password
migrate = Migrate() #flask migrate

def create_app():
    app = Flask(__name__)
    
    #get password from environment variable
    password = os.getenv("DB_PASSWORD")
    
    # Configuration
    app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = (f"mysql+pymysql://flask_account:{password}@localhost/biological_records") #mysql
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/data')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok = True)
 
 
	# Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db) #flask migrate
    
	
	# Configure flask-login
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)
	
	#User loader function for Flask-login
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
		
	# blueprints
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)
    
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    """
    from .records import records as records_blueprint
    app.register_blueprint(records_blueprint)
    """
    
    return app
    
