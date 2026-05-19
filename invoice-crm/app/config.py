import os
import secrets


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(24))
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance', 'invoicecrm.db')
