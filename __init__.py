from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask import Blueprint, render_template
import os 
#going to use pymysql

#https://www.digitalocean.com/community/tutorials/how-to-add-authentication-to-your-app-with-flask-login reference

#use flask sqlAlchemy for database
#database
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:yourpassword@localhost/yourdatabase' #mysql
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    #for file uploading
    #app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
	
	# Initialize extensions
    db.init_app(app)
	
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
    
    return app
    
