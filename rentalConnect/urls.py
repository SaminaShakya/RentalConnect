from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Root: send users to the home page
    path('', RedirectView.as_view(pattern_name='home', permanent=False)),

    path('admin/', admin.site.urls),

    # AUTH (ONLY ONE SYSTEM)
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html'
    ), name='login'),

    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # APPS
    path('listings/', include('listings.urls')),
    path('users/', include('users.urls')),
]

# SERVE MEDIA FILES IN DEVELOPMENT AND PRODUCTION
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# SERVE STATIC FILES IN DEVELOPMENT
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])