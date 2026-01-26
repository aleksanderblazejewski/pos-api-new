import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://admin:Admin123!@localhost/restauracja"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
