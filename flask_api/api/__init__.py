from flask import Blueprint

api_bp = Blueprint("api", __name__)

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
