from app import create_app, db

#https://flask-sqlalchemy.readthedocs.io/en/stable/quickstart/

app = create_app()

#removed db.create_all() as using Flask-Migrate now
