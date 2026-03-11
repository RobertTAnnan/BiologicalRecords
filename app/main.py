from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
import secrets
import string
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from . import db
from .models import User, Role, TrustCodes

main = Blueprint('main', __name__)

#helper functions
def generate_trust_code(role_id, length_of_stay, expires_in_min = 15):
    code_pool = string.ascii_uppercase + string.digits
    code = ''.join(secrets.choice(code_pool) for _ in range(5)) #5 digit code
    
    hashed_code = generate_password_hash(code, salt_length = 16)
    
    expiration_time = datetime.now(timezone.utc) + timedelta(minutes = expires_in_min)
     
    new_code = TrustCodes(
        hashed_code = hashed_code,
        expiration_time = expiration_time,
        length_of_stay = length_of_stay,
        role_id = role_id
    )
    
    db.session.add(new_code)
    db.session.commit()
    
    return code       
    

# homepage
@main.route('/')
def home():    
    return render_template('home.html')

# dashboard for logged in users
@main.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role.role_name != 'Admin':
        flash('You do not have permission to access this page.')
        return redirect(url_for('main.home'))

    trust_code = None

    #add code to allow admin to generate a trust code, need visualisation to do this
    
    return render_template('admin_dashboard.html')
    
@main.route('/index')
def index():    
    return render_template('index.html')