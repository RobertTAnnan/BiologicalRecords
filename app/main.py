from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
import secrets
import string
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from . import db
from .models import User, Role, TrustCodes, ConservationEntry, ConservationStatus
import os
from .records import import_csv, import_jncc_csv, import_sbl_csv
from sqlalchemy.orm import joinedload



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

#----------------------------Routes--------------------------------------------------------------------------------------------------------------------

# homepage
@main.route('/')
def home():    
    return render_template('home.html')

#admin dashboard with admin only functionality, vibe coded, revisit this when we have an actual dashboard front end
@main.route('/admin_dashboard')
@login_required
def admin_dashboard():

    if current_user.role.role_name != "Admin":
        flash("You do not have permission")
        return redirect(url_for("main.home"))

    users = (
        User.query
        .options(joinedload(User.role))
        .order_by(User.user_id.desc())
        .limit(50)
        .all()
    )

    roles = Role.query.order_by(Role.role_name.asc()).all()

    codes = (
        TrustCodes.query
        .options(joinedload(TrustCodes.role))
        .order_by(TrustCodes.generated_time.desc())
        .limit(50)
        .all()
    )

    statuses = (
        ConservationStatus.query
        .options(joinedload(ConservationStatus.conservation_list))
        .order_by(ConservationStatus.conservation_status.asc())
        .limit(100)
        .all()
    )

    unmatched = (
        ConservationEntry.query
        .options(
            joinedload(ConservationEntry.conservation_status),
            joinedload(ConservationEntry.conservation_list)
        )
        .filter(ConservationEntry.taxonomy_id.is_(None))
        .order_by(ConservationEntry.imported_at.desc())
        .limit(100)
        .all()
    )

    user_count = User.query.count()
    code_count = TrustCodes.query.count()
    status_count = ConservationStatus.query.count()
    unmatched_count = ConservationEntry.query.filter(
        ConservationEntry.taxonomy_id.is_(None)
    ).count()

    return render_template(
        'admin_dashboard.html',
        users=users,
        roles=roles,
        codes=codes,
        statuses=statuses,
        unmatched=unmatched,
        user_count=user_count,
        code_count=code_count,
        status_count=status_count,
        unmatched_count=unmatched_count
    )
    
#import taxonomy from csv
@main.route('/admin/import_taxonomy', methods=['POST'])
@login_required
def admin_import_taxonomy():

    if current_user.role.role_name != "Admin":
        flash("You do not have permission")
        return redirect(url_for("main.home"))

    file = request.files.get('taxonomy_csv')

    if not file:
        flash("No file selected")
        return redirect(url_for('main.admin_dashboard'))

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        import_csv(filepath)
        flash("Taxonomy imported")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {e}")

    return redirect(url_for('main.admin_dashboard'))
   

#import sbl conservation list   
@main.route('/admin/import_sbl', methods=['POST'])
@login_required
def admin_import_sbl():

    if current_user.role.role_name != "Admin":
        flash("You do not have permission")
        return redirect(url_for("main.home"))

    file = request.files.get('sbl_csv')

    if not file:
        flash("No file selected")
        return redirect(url_for('main.admin_dashboard'))

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        import_sbl_csv(filepath)
        flash("SBL conservation list imported")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {e}")

    return redirect(url_for('main.admin_dashboard'))
    
  
#import jncc global and uk red lists  
@main.route('/admin/import_jncc', methods=['POST'])
@login_required
def admin_import_jncc():

    if current_user.role.role_name != "Admin":
        flash("You do not have permission")
        return redirect(url_for("main.home"))

    file = request.files.get('jncc_csv')

    if not file:
        flash("No file selected")
        return redirect(url_for('main.admin_dashboard'))

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        import_jncc_csv(filepath)
        flash("JNCC UK and Global red list imported")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {e}")

    return redirect(url_for('main.admin_dashboard'))
    
@main.route('/admin/generate_code', methods=['POST'])
@login_required
def admin_generate_code():

    if current_user.role.role_name != "Admin":
        flash("You do not have permission")
        return redirect(url_for("main.home"))

    role_id = int(request.form.get("role_id"))
    length = request.form.get("length_of_stay", type=int)

    code = generate_trust_code(
        role_id = role_id,
        length_of_stay = length
    )

    flash(f"New code: {code}")

    return redirect(url_for('main.admin_dashboard'))
    

@main.route('/admin/toggle_status/<int:status_id>', methods=['POST'])
@login_required
def admin_toggle_status(status_id):

    if current_user.role.role_name != "Admin":
        flash("You do not have permission")
        return redirect(url_for("main.home"))

    status = ConservationStatus.query.get(status_id)

    if status:
        status.is_sensitive = not status.is_sensitive
        db.session.commit()

    return redirect(url_for('main.admin_dashboard'))
    
    
    
    
#activate/deactivate users?
@main.route('/admin/toggle_user/<int:user_id>', methods=['POST'])
@login_required
def admin_toggle_user(user_id):

    if current_user.role.role_name != "Admin":
        flash("You do not have permission")
        return redirect(url_for("main.home"))

    user = User.query.get(user_id)

    if user:
        user.is_active = not user.is_active
        db.session.commit()

    return redirect(url_for('main.admin_dashboard'))
    
@main.route('/index')
def index():    
    return render_template('index.html')