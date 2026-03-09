from flask_login import UserMixin #To make implementing a user class easier, you can inherit from UserMixin, which provides default implementations for all of these properties and methods. (from documentation)
from . import db
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import relationship

#relatiionships are part of SQLAlchemy, allowing you to use python code i.e user.role rather than sql queries to join tables
#https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html 

#self referential table https://docs.sqlalchemy.org/en/21/orm/self_referential.html

#database
class User(db.Model, UserMixin):
    #name
    __tablename__ = 'user'

    #attributes
    user_id = db.Column(db.Integer, primary_key = True) #PK
    firstName = db.Column(db.String(50), nullable = False)
    surName = db.Column(db.String(50), nullable = False)
    password_hash = db.Column(db.String(200), nullable = False)
    email = db.Column(db.String(100), unique = True, nullable = False)
    is_active = db.Column(db.Boolean, default = False, nullable = False) #unsure if account should be auto set to true or false
    account_creation = db.Column(db.DateTime(timezone = True), server_default=func.now(), nullable = False)
    account_expiration = db.Column(db.DateTime(timezone = True), server_default=func.now()) #Null for admins
    role_id = db.Column(db.Integer, db.ForeignKey('LU_role.role_id'), nullable = False) #FK

    #relationships - these are reverse relationships, which are allowed due to back_populates. letting us do user.reports even without an FK,as there is an FK to User in Report
    reports = relationship('Report', back_populates = 'user')
    
    #referenced relationships - these are the relationships due to the FK in the table, are referenced to by the reverse relationships
    role = relationship('Role', back_populates = 'users')    
    
    #Flask-Login assumes PK is id, so tries to access id, but our PK is user_id
    def get_id(self):
        return str(self.user_id)
    
  
class Taxonomy(db.Model):
    #name
    __tablename__ = 'taxonomy'
    
    #attributes
    taxonomy_id = db.Column(db.Integer, primary_key = True) #PK
    scientific_name = db.Column(db.String(100), nullable = False)
    vernacular_name = db.Column(db.String(100))
    gbif_taxonomy_id = db.Column(db.String(100))
    gbif_taxonomy_url = db.Column(db.String(200))
    authority_id = db.Column(db.Integer, db.ForeignKey('LU_authority.authority_id')) #FK
    data_source_id = db.Column(db.Integer, db.ForeignKey('LU_data_source.data_source_id')) #FK
    taxonomy_rank_id = db.Column(db.Integer, db.ForeignKey('LU_taxonomy_rank.taxonomy_rank_id')) #FK
    parent_id = db.Column(db.Integer, db.ForeignKey('taxonomy.taxonomy_id')) #FK
    
    #reverse relationships
    reports = relationship('Report', back_populates = 'taxonomy')
    conservation_links = relationship('TaxonomyConservationStatus', back_populates = 'taxonomy')
    
    #referenced relationships
    authority = relationship('Authority', back_populates = 'taxonomies')
    data_source = relationship('DataSource', back_populates = 'taxonomies')
    taxonomy_rank = relationship('TaxonomyRank', back_populates = 'taxonomies')
    
    #self referencing
    parent = relationship('Taxonomy', remote_side = [taxonomy_id], back_populates = 'children')
    children = relationship('Taxonomy', back_populates = 'parent')
    
    
    
class Report(db.Model):
    #name
    __tablename__ = 'report'

    #attributes
    report_id = db.Column(db.Integer, primary_key = True) #PK
    latitude = db.Column(db.Float, nullable = False)
    longitude = db.Column(db.Float, nullable = False)
    public_latitude = db.Column(db.Float) #only for protected
    public_longitude = db.Column(db.Float) #only for protected
    numbers_of_sighted = db.Column(db.Integer)
    habitat_sighted = db.Column(db.String(200)) #change to LU table
    report_date = db.Column(db.DateTime(timezone = True), server_default=func.now(), nullable = False)
    image_id = db.Column(db.String(1000))
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable = False) #FK
    report_status_id = db.Column(db.Integer, db.ForeignKey('LU_report_status.report_status_id'), nullable = False) #FK
    taxonomy_id = db.Column(db.Integer, db.ForeignKey('taxonomy.taxonomy_id'), nullable = False) #FK

    #referenced relationships
    user = relationship('User', back_populates = 'reports')
    report_status = relationship('ReportStatus', back_populates= 'reports')
    taxonomy = relationship('Taxonomy', back_populates = 'reports')
    
    
class TaxonomyConservationStatus(db.Model):
    #name
    __tablename__ = 'taxonomy_conservation_status'

    #attributes
    taxonomy_id = db.Column(db.Integer, db.ForeignKey('taxonomy.taxonomy_id'), primary_key = True)
    conservation_status_id = db.Column(db.Integer, db.ForeignKey('LU_conservation_status.conservation_status_id'), primary_key = True)

    #referenced relationships
    taxonomy = relationship('Taxonomy', back_populates = 'conservation_links')
    conservation_status = relationship('ConservationStatus', back_populates = 'taxonomy_links')
    

#Lookup tables
class Role(db.Model):
    #name
    __tablename__ = 'LU_role'
    
    #attributes
    role_id = db.Column(db.Integer, primary_key = True)
    role_name = db.Column(db.String(20), unique = True, nullable = False)

    #reverse relationships
    users = relationship('User', back_populates = 'role')


class ReportStatus(db.Model):
    #name
    __tablename__ = 'LU_report_status'

    #attributes
    report_status_id = db.Column(db.Integer, primary_key = True)
    status_name = db.Column(db.String(20), unique = True, nullable = False)

    #reverse relationships
    reports = relationship('Report', back_populates = 'report_status')
    

class DataSource(db.Model):
    #name
    __tablename__ = 'LU_data_source'

    #attributes
    data_source_id = db.Column(db.Integer, primary_key = True)
    data_source_name = db.Column(db.String(100), nullable = False)
    data_source_date = db.Column(db.DateTime(timezone = True), server_default=func.now())

    #reverse relationships
    taxonomies = relationship('Taxonomy', back_populates = 'data_source')
    


class Authority(db.Model):
    #name
    __tablename__ = 'LU_authority'

    #attributes
    authority_id = db.Column(db.Integer, primary_key = True)
    authority_name = db.Column(db.String(100), unique = True, nullable = False)

    #reverse relationships
    taxonomies = relationship('Taxonomy', back_populates = 'authority')
    
    
class TaxonomyRank(db.Model):
    #name
    __tablename__ = 'LU_taxonomy_rank'

    #attributes
    taxonomy_rank_id = db.Column(db.Integer, primary_key = True)
    taxonomy_rank_name = db.Column(db.String(20), unique = True, nullable = False)

    #reverse relationships
    taxonomies = relationship('Taxonomy', back_populates = 'taxonomy_rank')



class ConservationList(db.Model):
    #name
    __tablename__ = 'LU_conservation_list'

    #attributes
    conservation_list_id = db.Column(db.Integer, primary_key = True)
    conservation_list_name = db.Column(db.String(200), nullable = False)
    conservation_list_url = db.Column(db.String(200))
    
    #reverse relationships
    conservation_statuses = relationship('ConservationStatus', back_populates = 'conservation_list')


class ConservationStatus(db.Model):
    #name
    __tablename__ = 'LU_conservation_status'

    #attributes
    conservation_status_id = db.Column(db.Integer, primary_key = True)
    conservation_status = db.Column(db.String(50), nullable = False)
    status_meaning = db.Column(db.Text)
    conservation_list_id = db.Column(db.Integer, db.ForeignKey('LU_conservation_list.conservation_list_id'), nullable = False)

    #reverse relationships
    taxonomy_links = relationship('TaxonomyConservationStatus', back_populates = 'conservation_status')
    
    #referenced relationships
    conservation_list = relationship('ConservationList', back_populates = 'conservation_statuses')
    
#Trust code
class TrustCodes(db.Model):
    #name
    __tablename__ = 'trust_codes'
    
    #attibutes
    trust_code_id = db.Column(db.Integer, primary_key = True)
    hashed_code = db.Column(db.String(200), nullable = False, unique = True)
    generated_time = db.Column(db.DateTime(timezone = True), server_default=func.now(), nullable = False)
    expiration_time = db.Column(db.DateTime(timezone = True), nullable = False)
    length_of_stay = db.Column(db.Integer) #if null then a staff code
    role_id = db.Column(db.Integer, db.ForeignKey('LU_role.role_id'), nullable = False)
    
    role=relationship('Role')
    