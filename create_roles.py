from app import create_app, db
from app.models import Role

def create_roles():
    app = create_app()

    with app.app_context():
        role_names = ["Public", "Student", "Staff", "Admin"]

        for role_name in role_names:
            existing = Role.query.filter_by(role_name = role_name).first()

            if existing is None:
                db.session.add(Role(role_name = role_name))

        db.session.commit()
        print("Roles created")

if __name__ == "__main__":
    create_roles()