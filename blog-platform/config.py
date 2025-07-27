import os

basedir = os.path.abspath(os.path.dirname(__file__))
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'f7678dbdd37b221239e3f5250521c73198ff7a43bddb0d94'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'instance', 'blog.db')
    SQLALCHEMY_TRACK_MODIFICATION = False