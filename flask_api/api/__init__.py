from flask import Blueprint, request

from flask_api.auth import require_jwt

api_bp = Blueprint("api", __name__)


@api_bp.before_request
def ensure_auth_for_mutations():
    if request.method == "OPTIONS":
        return None
    if request.endpoint == "api.login":
        return None
    return require_jwt()

from . import staff  # noqa
from . import login  # noqa
from . import table_groups  # noqa
from . import tables  # noqa
from . import menu  # noqa
from . import orders  # noqa
from . import settings  # noqa'
from . import reservations
from . import reports
from . import stock
