from flask import Blueprint

auth = Blueprint('Auth', __name__)

from . import views