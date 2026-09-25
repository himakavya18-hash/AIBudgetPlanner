from flask import Blueprint

goals_bp = Blueprint('goals', __name__)

from . import routes
