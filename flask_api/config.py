import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://admin:Admin123!@localhost/restauracja"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "4ac3d303fb8e777c82192b7361d76768f03f133497053f5d506e3470f785d30d")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRES_SECONDS = int(os.getenv("JWT_EXPIRES_SECONDS", "3600"))
