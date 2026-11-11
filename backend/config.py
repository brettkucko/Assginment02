import os
from urllib.parse import quote_plus

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_HOST = os.environ.get("DB_HOST", "cluster.aqxqsoh.mongodb.net")
DB_NAME = os.environ.get("DB_NAME", "MobileApp")

MONGODB_URI = (
    f"mongodb+srv://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/"
)