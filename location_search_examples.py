#!/usr/bin/env python
"""
Location-Based Property Search - Example Implementation & Testing Guide

This script demonstrates practical usage of the Haversine/Dijkstra location search
feature in Rental Connect.
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rentalConnect.settings')
django.setup()

from listings.models import Property, Booking
from listings.utils import nearest_properties, haversine
from users.models import CustomUser
from datetime import timedelta
from django.utils import timezone


def setup_test_properties():
    """Create sample properties across Kathmandu with different coordinates."""
    
    # Clean up existing test data
    Property.objects.filter(title__startswith="TEST_").delete()
    
    # Get or create a test landlord
    landlord, _ = CustomUser.objects.get_or_create(
        username='test_landlord',
        defaults={
            'email': 'landlord@test.com',
            'is_landlord': True,
            'is_active': True,
        }
    )
    landlord.set_password('testpass123')
    landlord.save()
    
    # Sample properties in Kathmandu area
    properties_data = [
        {
            'title': 'TEST_Downtown Studio',
            'latitude': 27.7172,
            'longitude': 85.3240,
            'rent': 15000,
            'bedrooms': 1,
        },
        {
            'title': 'TEST_Thamel 2BR',
            'latitude': 27.7260,
            'longitude': 85.2883,
            'rent': 25000,
            'bedrooms': 2,
        },
        {
            'title': 'TEST_Boudha Apartment',
            'latitude': 27.7217,
            'longitude': 85.3647,
            'rent': 30000,
            'bedrooms': 3,
        },
        {
            'title': 'TEST_Patan Residence',
            'latitude': 27.6744,
            'longitude': 85.3236,
            'rent': 20000,
            'bedrooms': 2,
        },
        {
            'title': 'TEST_Bhaktapur House',
            'latitude': 27.6702,
            'longitude': 85.4303,
            'rent': 18000,
            'bedrooms': 2,
        },
    ]
    
    created = []
    for data in properties_data:
        prop = Property.objects.create(
            landlord=landlord,
            title=data['title'],
            description=f"Test property: {data['title']}",
            city='Kathmandu',
            rent=data['rent'],
            bedrooms=data['bedrooms'],
            bathrooms=1,
            address='Test Address',
            latitude=data['latitude'],
            longitude=data['longitude'],
            is_verified=True,
        )
        created.append(prop)
        print(f"✓ Created: {prop.title} ({prop.latitude}, {prop.longitude})")
    
    return created


def example_1_direct_distance():
    """Example 1: Calculate distance between two points."""
    print("\n" + "="*70)
    print("Example 1: Direct Distance Calculation")
    print("="*70)
    
    kathmandu_center = (27.7172, 85.3240)
    thamel = (27.7260, 85.2883)
    boudha = (27.7217, 85.3647)
    
    dist_thamel = haversine(kathmandu_center, thamel)
    dist_boudha = haversine(kathmandu_center, boudha)
    
    print(f"\nFrom Kathmandu center ({kathmandu_center[0]}, {kathmandu_center[1]}):")
    print(f"  → Thamel:  {dist_thamel:.2f} km")
    print(f"  → Boudha:  {dist_boudha:.2f} km")


def example_2_nearest_in_memory():
    """Example 2: Find nearest properties using in-memory algorithm."""
    print("\n" + "="*70)
    print("Example 2: Find Nearest Properties (In-Memory)")
    print("="*70)
    
    # Tenant's location (e.g., their workplace)
    tenant_location = (27.7172, 85.3240)  # Downtown Kathmandu
    
    # Get all verified properties with coordinates
    properties = Property.objects.filter(
        is_verified=True,
        title__startswith='TEST_',
        latitude__isnull=False,
        longitude__isnull=False,
    )
    
    if not properties.exists():
        print("⚠ No test properties found. Run setup_test_properties() first.")
        return
    
    # Build coordinate dictionary
    coords = {
        p.id: (p.latitude, p.longitude)
        for p in properties
    }
    
    # Find k nearest properties
    k = 3
    nearest_ids = nearest_properties(tenant_location, coords, k=k)
    
    print(f"\nTenant location: ({tenant_location[0]}, {tenant_location[1]})")
    print(f"\nTop {k} nearest properties:")
    print("-" * 70)
    
    for rank, prop_id in enumerate(nearest_ids, 1):
        prop = Property.objects.get(id=prop_id)
        distance = haversine(tenant_location, (prop.latitude, prop.longitude))
        print(f"{rank}. {prop.title}")
        print(f"   Distance: {distance:.2f} km")
        print(f"   Rent: Rs. {prop.rent}/month ({prop.bedrooms} BR)")
        print()


def example_3_filtered_search():
    """Example 3: Filter by location AND other criteria."""
    print("\n" + "="*70)
    print("Example 3: Filtered Location Search")
    print("="*70)
    
    rental_budget = 25000  # Max Rs. 25,000
    min_bedrooms = 2
    tenant_location = (27.7172, 85.3240)
    
    # First filter by non-location criteria
    filtered = Property.objects.filter(
        is_verified=True,
        title__startswith='TEST_',
        rent__lte=rental_budget,
        bedrooms__gte=min_bedrooms,
        latitude__isnull=False,
        longitude__isnull=False,
    )
    
    if not filtered.exists():
        print("⚠ No properties match filter criteria.")
        return
    
    # Then apply location ranking
    coords = {
        p.id: (p.latitude, p.longitude)
        for p in filtered
    }
    
    nearest_ids = nearest_properties(tenant_location, coords, k=filtered.count())
    
    print(f"\nSearch criteria:")
    print(f"  • Budget: Rs. {rental_budget}/month (max)")
    print(f"  • Bedrooms: {min_bedrooms}+ BR required")
    print(f"  • Location: ({tenant_location[0]}, {tenant_location[1]})")
    print(f"\nMatching properties (sorted by distance):")
    print("-" * 70)
    
    for rank, prop_id in enumerate(nearest_ids, 1):
        prop = Property.objects.get(id=prop_id)
        distance = haversine(tenant_location, (prop.latitude, prop.longitude))
        print(f"{rank}. {prop.title}")
        print(f"   Rent: Rs. {prop.rent} | Bedrooms: {prop.bedrooms} | Distance: {distance:.2f} km")


def example_4_django_view_integration():
    """Example 4: How the view integrates location search."""
    print("\n" + "="*70)
    print("Example 4: Django View Integration")
    print("="*70)
    
    print("""
This is how the property_list view handles location-based search:

    def property_list(request):
        # ... existing filters (query, city, max_rent, sort) ...
        
        lat = request.GET.get('lat')
        lng = request.GET.get('lng')
        distance_ordered = False
        
        if lat and lng:
            try:
                lat_f, lng_f = float(lat), float(lng)
                coords = {
                    p.id: (p.latitude, p.longitude)
                    for p in properties
                    if p.latitude and p.longitude
                }
                
                ordered_ids = nearest_properties(
                    (lat_f, lng_f), coords, k=properties.count()
                )
                
                # Use Django Case/When to preserve order
                from django.db.models import Case, When
                preserved = Case(
                    *[When(pk=pid, then=pos) 
                      for pos, pid in enumerate(ordered_ids)]
                )
                properties = (
                    properties
                    .filter(id__in=ordered_ids)
                    .order_by(preserved)
                )
                distance_ordered = True
            except ValueError:
                pass
        
        # Skip sort if already ordered by distance
        if not distance_ordered:
            if sort == 'rent_low':
                properties = properties.order_by('rent', '-created_at')
            # ... other sorts

    # URL examples:
    GET /properties/?lat=27.7172&lng=85.3240
    GET /properties/?lat=27.7172&lng=85.3240&max_rent=25000&bedrooms=2
""")


def example_5_performance():
    """Example 5: Performance characteristics."""
    print("\n" + "="*70) 
    print("Example 5: Performance Analysis")
    print("="*70)
    
    import time
    
    # Get all test properties
    properties = Property.objects.filter(
        title__startswith='TEST_',
        latitude__isnull=False,
    )
    
    count = properties.count()
    coords = {p.id: (p.latitude, p.longitude) for p in properties}
    start_location = (27.7172, 85.3240)
    
    # Measure time
    start = time.time()
    result = nearest_properties(start_location, coords, k=count)
    elapsed = time.time() - start
    
    print(f"\nPerformance metrics:")
    print(f"  • Properties analyzed: {count}")
    print(f"  • Time taken: {elapsed*1000:.2f} ms")
    print(f"  • Per-property: {elapsed/count*1000:.2f} ms")
    print(f"\nComplexity: O(n²) where n = number of properties")
    print(f"Suitable for: up to ~1,000 properties per query")
    print(f"\nFor larger datasets, consider:")
    print(f"  • PostGIS geographic database")
    print(f"  • Elasticsearch geo_distance queries")
    print(f"  • Redis sorted sets with geohash")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("RENTAL CONNECT - LOCATION-BASED SEARCH EXAMPLES")
    print("="*70)
    
    # Setup test data
    print("\nSetting up test properties...")
    setup_test_properties()
    
    # Run examples
    example_1_direct_distance()
    example_2_nearest_in_memory()
    example_3_filtered_search()
    example_4_django_view_integration()
    example_5_performance()
    
    print("\n" + "="*70)
    print("EXAMPLES COMPLETE")
    print("="*70)
    print("\nNext steps:")
    print("  1. Add geocoding to auto-populate coordinates from addresses")
    print("  2. Integrate with maps library (Leaflet.js)")
    print("  3. Add geospatial queries for larger-scale deployments")
    print("  4. Create saved searches feature for tenants")


if __name__ == '__main__':
    main()
