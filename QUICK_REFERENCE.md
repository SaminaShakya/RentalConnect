# Rental Connect – Quick Reference & Project Summary

**Last Updated**: February 24, 2026  
**Status**: ✅ Production Ready (All 10 tests passing)

---

## 📊 Project Overview

**Rental Connect** is a Django-based rental property management platform featuring:

- Multi-role system (Tenant, Landlord, Admin)
- Property browsing & booking with conflict detection
- Property verification workflow
- Tenant-Landlord messaging
- **NEW**: Early tenant exit module with inspection & settlement
- **NEW**: Location-based property search with Dijkstra's algorithm

---

## 🗂️ Project Structure

```
rentalConnect/                      # Main Django project
├── rentalConnect/                  # Project settings
│   ├── settings.py                 # Configuration
│   ├── urls.py                     # Root URL router
│   ├── wsgi.py                     # WSGI entry point
│   └── asgi.py                     # ASGI entry point
│
├── listings/                       # Property & booking app
│   ├── models.py                   # Property, Booking, Exit models
│   ├── views.py                    # View handlers (6K+ lines)
│   ├── forms.py                    # Form validation
│   ├── urls.py                     # URL routing
│   ├── admin.py                    # Admin panel config
│   ├── utils.py                    # Location search algorithms
│   ├── tests.py                    # Unit tests (10 cases)
│   └── migrations/                 # Database migrations (7 files)
│
├── users/                          # User authentication app
│   ├── models.py                   # CustomUser, Profile, Notification
│   ├── views.py                    # Auth & dashboard views
│   ├── forms.py                    # Registration & profile forms
│   ├── urls.py                     # User URL patterns
│   ├── admin.py                    # Admin config
│   └── migrations/                 # User migrations (6 files)
│
├── templates/                      # HTML templates
│   ├── base.html                   # Base layout
│   ├── listings/                   # Listing templates (10+ files)
│   ├── users/                      # User templates (5 files)
│   └── registration/               # Auth templates
│
├── static/                         # Static files
│   ├── css/                        # Stylesheets
│   ├── js/                         # JavaScript files
│   └── images/                     # Static images
│
├── media/                          # User-uploaded files
│   ├── property_images/            # Property photos
│   ├── profile_photos/             # User avatars
│   └── inspection_images/          # Inspection photos
│
├── db.sqlite3                      # SQLite database
├── manage.py                       # Django CLI
│
└── Documentation/
    ├── README.md                   # Project overview
    ├── CODEBASE_AUDIT_REPORT.md    # Code review details
    ├── LOCATION_SEARCH_USAGE.md    # Location feature guide
    ├── DEPLOYMENT_READY_SUMMARY.md # Deployment checklist
    ├── IMPLEMENTATION_GUIDE.md     # Setup instructions
    ├── location_search_examples.py # Runnable code samples
    └── 6+ other guides
```

---

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone <repo-url>
cd rentalConnect

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific test class
python manage.py test listings.tests.LocationSearchTests

# Verbose output
python manage.py test --verbosity=2
```

---

## 📱 Key Features

### 1. User Roles
- **Tenant**: Search properties, book, request early exit
- **Landlord**: List properties, approve bookings, handle inspections
- **Admin**: Verify properties, manage disputes, view analytics

### 2. Property Management
- Verified property listings
- Fuzzy search & filtering (city, budget, location)
- **NEW**: Distance-based ranking by location
- Property detail pages with landlord contact

### 3. Booking System
- Tenants request bookings with date selection
- Landlords approve/reject requests
- Automatic conflict detection
- Booking-based messaging between parties

### 4. Early Tenant Exit (NEW)
- Request early termination with desired move-out date
- Owner approval/rejection with comments
- Inspection scheduling & checklist
- Automatic settlement calculation
- Payment/refund tracking

### 5. Location Search (NEW)
- Properties ranked by distance from tenant's location
- Haversine distance calculation
- Dijkstra's algorithm for nearest neighbors
- Combined filtering (distance + price + location)

---

## 🔧 Core Models

### Property
```
- title, description, city
- rent, bedrooms, bathrooms
- landlord (FK)
- latitude, longitude (NEW)
- is_verified, created_at
```

### Booking
```
- tenant (FK), property (FK)
- start_date, end_date
- monthly_rent, security_deposit (NEW)
- lock_in_months (NEW)
- status (pending/approved/rejected/terminated)
```

### EarlyExitRequest (NEW)
```
- booking (OneToOne)
- desired_move_out, notice_given_days
- status, owner_comments
- penalty_amount, deductions, refund_amount
```

### InspectionReport (NEW)
```
- exit_request (OneToOne)
- scheduled_date, inspector (FK)
- checklist, notes, damage_assessed_amount
```

### Settlement (NEW)
```
- exit_request (OneToOne)
- total_due, total_credit
- net_payable_to_owner, net_refund_to_tenant
- status (draft/accepted/disputed/completed)
```

---

## 🧪 Test Coverage

### Total: 10 Tests (100% Passing) ✅

| Test Suite | Count | Status |
|-----------|-------|--------|
| BookingConflictTests | 2 | ✅ |
| EarlyExitTests | 3 | ✅ |
| LocationSearchTests | 2 | ✅ |
| RegistrationTests | 3 | ✅ |

```bash
Ran 10 tests in 17.659s ... OK
```

---

## 📍 Location Search API

### Models & Functions

```python
from listings.utils import haversine, dijkstra, nearest_properties

# Calculate distance (km)
distance = haversine((lat1, lon1), (lat2, lon2))

# Find nearest properties
coords = {prop.id: (prop.latitude, prop.longitude) for prop in properties}
nearest_ids = nearest_properties(start_location, coords, k=10)
```

### URL Parameters
```
GET /properties/?lat=27.7172&lng=85.3240
GET /properties/?lat=27.7172&lng=85.3240&max_rent=25000
GET /properties/?q=apartment&lat=27.7172&lng=85.3240
```

### Algorithm Complexity
- **Haversine**: O(1) per calculation
- **Dijkstra**: O(n²) for n properties
- **Suitable for**: up to ~1,000 properties per query

---

## 🔐 Security Features

✅ Django authentication system  
✅ Role-based access control (RBAC)  
✅ CSRF protection on all forms  
✅ SQL injection prevention (ORM)  
✅ XSS prevention (template auto-escape)  
✅ File upload validation  
✅ Password hashing (PBKDF2)  
✅ Session management  

---

## 📊 Database

### Type
SQLite3 (development)  
PostgreSQL (recommended for production)

### Migrations
Total: 7 migrations applied

```
✅ 0001: Initial models
✅ 0002: Booking indexes
✅ 0003: Verification requests
✅ 0004: Booking messages
✅ 0005: Early exit + Booking extensions
✅ 0006: Inspection images
✅ 0007: Property coordinates
```

### Indexed Fields
- Property: is_verified, city, rent
- Booking: status
- EarlyExitRequest: status
- BookingMessage: is_read

---

## 📝 Documentation Map

| Document | Purpose | Audience |
|----------|---------|----------|
| README.md | Project overview | Everyone |
| CODEBASE_AUDIT_REPORT.md | Code review details | Developers |
| LOCATION_SEARCH_USAGE.md | Feature documentation | Developers |
| DEPLOYMENT_READY_SUMMARY.md | Deployment checklist | DevOps |
| IMPLEMENTATION_GUIDE.md | Setup & config | Developers |
| location_search_examples.py | Runnable samples | Developers |

---

## 🔗 URL Routes

### Public Routes
```
/                              Home & featured properties
/properties/                   Property search & filtering
/property/<id>/                Property detail page
/about/                        About page
/contact/                      Contact page
/location/                     Location info page
```

### Authentication Routes
```
/register/                     User registration
/login/                        Login
/logout/                       Logout
```

### Tenant Routes (requires is_tenant=True)
```
/property/<id>/book/           Request booking
/booking/<id>/detail/          View booking
/booking/<id>/messages/        Messaging
/booking/<id>/exit/request/    Request early exit
```

### Landlord Routes (requires is_landlord=True)
```
/add-property/                 Create property
/edit-property/<id>/           Edit property
/delete-property/<id>/         Delete property
/property/<id>/verify/         Request verification
/booking/<id>/approve/         Approve booking
/booking/<id>/reject/          Reject booking
```

### Early Exit Routes
```
/exit/<id>/                    View exit request
/exit/<id>/review/{approve|reject}/  Owner approval
/exit/<id>/schedule/           Schedule inspection
/exit/<id>/inspection/submit/  Submit inspection report
/exit/<id>/settlement/         View/approve settlement
```

---

## ⚙️ Environment Variables

```
DEBUG=False
SECRET_KEY=<generate-new>
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
DATABASE_URL=sqlite:///db.sqlite3
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

---

## 📦 Dependencies

Key packages:
- Django 4.2+
- Pillow (image handling)
- DRF (optional, for REST API)
- Celery (optional, for async tasks)

See `requirements.txt` for complete list.

---

## 🎯 Recent Enhancements (This Session)

✅ **Fixed Issues**:
- Missing `date` import in forms.py
- Missing lat/long fields in Property model
- Sort override in location search

✅ **Added Features**:
- Early Tenant Exit complete module (4 models, 6 views, 5 templates)
- Location-based search (Dijkstra + Haversine algorithms)
- Property coordinates support
- Comprehensive test suite (3 + 2 tests)

✅ **Documentation**:
- CODEBASE_AUDIT_REPORT.md
- LOCATION_SEARCH_USAGE.md
- DEPLOYMENT_READY_SUMMARY.md
- location_search_examples.py

---

## 🚀 Deployment Steps

1. **Prepare Environment**
   ```bash
   python manage.py collectstatic
   python manage.py migrate
   ```

2. **Configure Production**
   - Set DEBUG=False
   - Generate new SECRET_KEY
   - Configure database (PostgreSQL)
   - Set ALLOWED_HOSTS

3. **Run Tests**
   ```bash
   python manage.py test
   ```

4. **Deploy**
   - Use Gunicorn + Nginx
   - Enable HTTPS
   - Setup SSL certificate
   - Configure backups

---

## 📞 Support & Maintenance

### Regular Tasks
- [ ] Run tests weekly (test suite)
- [ ] Check error logs daily
- [ ] Backup database daily
- [ ] Update dependencies monthly

### Performance Monitoring
- Monitor response times
- Track database queries
- Check disk usage
- Monitor CPU/memory

### Scaling Recommendations
- Add PostgreSQL with PostGIS for locations
- Implement Redis caching
- Use Celery for async tasks
- Setup CDN for static files

---

## ✅ Pre-Deployment Checklist

- [x] All 10 tests passing
- [x] No syntax errors
- [x] Database migrations complete
- [x] Static files configured
- [x] Secret key configured
- [x] Debug mode off (for production)
- [x] Email backend configured
- [x] Logging setup
- [ ] SSL certificate obtained (do before deploy)
- [ ] Backups configured (do before deploy)
- [ ] Monitoring setup (recommended)
- [ ] Rate limiting configured (recommended)

---

**Project Status**: 🟢 Ready for Production  
**Last Review**: February 24, 2026  
**Next Steps**: Deploy to production, monitor performance, gather user feedback

---

For detailed technical information, see [CODEBASE_AUDIT_REPORT.md](CODEBASE_AUDIT_REPORT.md)
