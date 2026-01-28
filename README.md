# Rental Connect

A Django-based rental property management system connecting tenants and landlords.

## Features

- **Role-based authentication** (Tenants and Landlords)
- **Property listings** with image uploads
- **Booking system** with conflict detection
- **Admin verification** for properties
- **Email notifications**
- **Responsive design**

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd rentalConnect
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run server**
   ```bash
   python manage.py runserver
   ```

## Environment Variables

See `.env.example` for required environment variables.

## Deployment

For production deployment:

1. Set `DEBUG=False`
2. Configure `ALLOWED_HOSTS`
3. Set up proper email backend
4. Use a production WSGI server (gunicorn)
5. Set up static file serving (nginx/apache)

## Security Notes

- SECRET_KEY is loaded from environment variables
- DEBUG is disabled in production
- CSRF protection enabled
- Input validation on all forms
- SQL injection prevention via Django ORM