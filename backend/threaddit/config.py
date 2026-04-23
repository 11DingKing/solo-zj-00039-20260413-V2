import os
from dotenv import dotenv_values

_env = dotenv_values()

DATABASE_URI = os.environ.get("DATABASE_URI") or _env.get("DATABASE_URI")
SECRET_KEY = os.environ.get("SECRET_KEY") or _env.get("SECRET_KEY", "dev-secret")
CLOUDINARY_NAME = os.environ.get("CLOUDINARY_NAME") or _env.get("CLOUDINARY_NAME", "")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY") or _env.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET") or _env.get("CLOUDINARY_API_SECRET", "")
