import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-12345')
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mistral API Configuration
    MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY', '')
    MISTRAL_MODEL = os.environ.get('MISTRAL_MODEL', 'mistral-small-latest')
    
    # Categories of expenses
    EXPENSE_CATEGORIES = [
        'Food',
        'Rent',
        'Utilities',
        'Shopping',
        'Transportation',
        'Entertainment',
        'Healthcare',
        'Education',
        'Travel',
        'Others'
    ]

    # Income sources
    INCOME_SOURCES = [
        'Salary',
        'Freelancing',
        'Investments',
        'Business',
        'Gifts',
        'Others'
    ]
