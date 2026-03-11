from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User, Role, TrustCodes
from . import db
from flask_login import current_user, login_user, login_required, logout_user
from sqlalchemy import func
from datetime import datetime, timedelta, timezone

auth = Blueprint('auth', __name__)

#Log into account
@auth.route('/login', methods=['GET', 'POST'])
def login():
    #is already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    #user submits login details
    if request.method == 'POST':
        email = request.form.get('login-email')
        password = request.form.get('login-password')
        remember = True if request.form.get('remember-user') else False #remember me
        
        user = User.query.filter_by(email=email).first() #.first() needed to give a user instance not a query
        
        #invalid
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid login details')
            return redirect(url_for('auth.login'))
            
        #check account activity status
        if not user.is_active:
            flash('Account is inactive')
            return redirect(url_for('auth.login'))
            
        login_user(user, remember=remember)
        return redirect(url_for('main.home'))
        
    #GET method, show login form
    return render_template('login.html')
    
    
#Create account
@auth.route('/register', methods=['GET', 'POST'])
def register():
    #already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))   
       
    #not logged in
    if request.method == 'POST':
        email = request.form.get('register-email')
        firstName = request.form.get('register-firstname')
        surName = request.form.get('register-surname')
        password = request.form.get('register-password')
        
        confirm_password = request.form.get('register-confirm-password')
        
        #must not have null values
        if email == None or firstName == None or surName == None or password == None:
            flash('email, first name, surname and password are required to be filled')
            return redirect(url_for('auth.register'))
        
        #check if email is already in use
        user_check_email = User.query.filter_by(email=email).first() #.first() needed to give a user instance not a query
        
        if user_check_email:
            flash('Email address already exists')
            return redirect(url_for('auth.register'))
        
        #Password checkers
        #Security, make a longer password
        if len(password) < 8:
            flash('Password must be at least 8 characters long')
            return render_template('register.html')
        
        #Extra security rules, must contain at least 1 upper, lower, number and special character
        if any(i.islower() for i in password) == False:
            flash('Password must have at least one lowercase letter.')
            return render_template('register.html')

        if any(i.isupper() for i in password) == False:
            flash('Password must have at least one uppercase letter.')
            return render_template('register.html')

        if any(i.isdigit() for i in password) == False:
            flash('Password must have at least one number.')
            return render_template('register.html')

        #special characters are not alpha numeric, check for containing a non alpha numeric character
        if any(not i.isalnum() for i in password) == False:
            flash('Password must have at least one special character.')
            return render_template('register.html')
            
        #confirm password
        if confirm_password != password:
            flash('Passwords must match')
            return render_template('register.html')
        
            
        #Trust code
        trust_code_input = request.form.get('trust_code')
        
        active_trust_codes = TrustCodes.query.filter(TrustCodes.expiration_time > func.now()).all() #get all active trust codes

        valid_code = None #the valid code
        
        #checks input against hashed trust code
        for code in active_trust_codes:
            if check_password_hash(code.hashed_code, trust_code_input): 
                is_valid_code = True #found a valid code
                valid_code = code
                break
        
        if not valid_code:
            flash('Please use an active trust code')
            return render_template('register.html')
        
        account_creation = datetime.now(timezone.utc)
        
        #length of stay
        if valid_code.length_of_stay is None: #Staff account
            account_expiration = None
        else: #Student account
            account_expiration = account_creation + timedelta(days = valid_code.length_of_stay)

            
        #new user constructor
        new_user = User(
            email = email, 
            firstName = firstName,
            surName = surName,
            password_hash = generate_password_hash(password, salt_length=16), #adding salt for additional hashing protection
            is_active = True,
            account_creation = account_creation,
            account_expiration = account_expiration,
            role_id = valid_code.role_id,
        )
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('auth.login'))
    
    #Get method, show registeration form
    return render_template('register.html')
     
#Logout     
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home')) 
    
#Add code for generating trust code - i.e a page for an admin dashboard with user details?
