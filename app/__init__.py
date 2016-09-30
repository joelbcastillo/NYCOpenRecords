import redis
from business_calendar import Calendar, MO, TU, WE, TH, FR
from flask import Flask
from flask_kvsession import KVSessionExtension
from flask_login import LoginManager
from flask_bootstrap import Bootstrap
from flask_mail import Mail
from config import config
from business_calendar import Calendar, MO, TU, WE, TH, FR
from flask_sqlalchemy import SQLAlchemy
from simplekv.decorator import PrefixDecorator
from simplekv.memory.redisstore import RedisStore
from config import config


bootstrap = Bootstrap()
db = SQLAlchemy()
login_manager = LoginManager()
store = RedisStore(redis.StrictRedis(db=1))
prefixed_store = PrefixDecorator('session_', store)

mail = Mail()
app = Flask(__name__)

calendar = Calendar(
    workdays=[MO, TU, WE, TH, FR],
    holidays=[
        '2016-01-01',
        '2016-01-18',
        '2016-02-15',
        '2016-05-30',
        '2016-07-4',
        '2016-09-5',
        '2016-10-10',
        '2016-11-08',
        '2016-11-11',
        '2016-11-24',
        '2016-12-26'
    ]
)


def create_app(config_name):
    """
    Set up the Flask Application context.

    :param config_name: Configuration for specific application context.

    :return: Flask application
    """
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    bootstrap.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'
    KVSessionExtension(prefixed_store, app)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix="/auth")

    from app.request import request_blueprint
    app.register_blueprint(request_blueprint, url_prefix="/request")

    from app.request.api import request_api_blueprint
    app.register_blueprint(request_api_blueprint, url_prefix="/request/api/v1.0")

    return app
