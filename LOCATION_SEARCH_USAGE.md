# Example Usage: Location-Based Rental Search

This document demonstrates how to use the new **location-based search** feature in Rental Connect.

## Features

- **Haversine Distance Algorithm**: Computes great-circle distances between coordinates.
- **Dijkstra's Algorithm**: Finds nearest properties in graph-based ordering.
- **Property Filtering**: Search by location, city, rent, and other criteria.
- **Ranked Results**: Properties sorted by distance from tenant's location.

---

## Backend Usage

### 1. Finding Nearest Properties in Code

```python
from listings.utils import nearest_properties, haversine
from listings.models import Property

# Tenant's location: Kathmandu city center
tenant_location = (27.7172, 85.3240)

# Get all verified properties with coordinates
properties = Property.objects.filter(
    is_verified=True,
    latitude__isnull=False,
    longitude__isnull=False
)

# Build coordinate mapping
coords = {p.id: (p.latitude, p.longitude) for p in properties}

# Get 10 nearest properties
nearest_ids = nearest_properties(tenant_location, coords, k=10)

# Retrieve actual property objects
closest_properties = Property.objects.filter(id__in=nearest_ids).order_by('id')
for prop in closest_properties:
    dist = haversine(tenant_location, (prop.latitude, prop.longitude))
    print(f"{prop.title}: {dist:.2f} km away")
```

**Output:**
```
Studio Downtown: 0.45 km away
Mountain View 2BR: 2.31 km away
Lakeside Apartment: 5.67 km away
...
```

### 2. Distance Calculation Example

```python
from listings.utils import haversine

# Distance between Kathmandu center and nearby areas
kathmandu = (27.7172, 85.3240)
thamel = (27.7260, 85.2883)
boudha = (27.7217, 85.3647)

print(f"Thamel: {haversine(kathmandu, thamel):.2f} km")  # ~3.2 km
print(f"Boudha: {haversine(kathmandu, boudha):.2f} km")  # ~4.1 km
```

---

## Frontend Usage

### URLs & Query Parameters

#### Search with location parameters:

```
/properties/?lat=27.7172&lng=85.3240
```

#### Combined filters (location + rent + city):

```
/properties/?q=apartment&lat=27.7172&lng=85.3240&max_rent=25000&sort=newest
```

#### Parameters:

| Parameter | Type | Example |
|-----------|------|---------|
| `lat` | float | `27.7172` |
| `lng` | float | `85.3240` |
| `q` | string | `apartment` |
| `city` | string | `Kathmandu` |
| `max_rent` | number | `25000` |
| `sort` | string | `newest`, `rent_low`, `rent_high` |

When `lat` and `lng` are provided, all properties are **automatically ordered by distance**.

---

## Testing

Run the test suite to verify location-based search:

```bash
python manage.py test listings.tests.LocationSearchTests --verbosity=2
```

Expected output:
```
Found 2 test(s).
test_nearest_properties_util ... ok
test_property_list_nearby_order ... ok
Ran 2 tests OK
```

---

## Data Model: Property Coordinates

The `Property` model includes new fields:

```python
class Property(models.Model):
    # ... existing fields ...
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
```

You can populate coordinates:

1. **Via Django Admin**: Edit a property and enter latitude/longitude manually.
2. **Via Geocoding Service**: Integrate Google Maps or OpenStreetMap API to auto-populate.
3. **Bulk Import**: CSV with address→coords mapping.

Example property data:

```python
Property.objects.create(
    title="Modern 2BR Downtown",
    latitude=27.7172,
    longitude=85.3240,
    rent=25000,
    # ... other fields ...
)
```

---

## Algorithm Details

### Haversine Distance

Calculates great-circle distance in kilometers between two lat/lon points:

```
a = sin²(Δφ/2) + cos φ1 ⋅ cos φ2 ⋅ sin²(Δλ/2)
c = 2 ⋅ atan2( √a, √(1−a) )
d = R ⋅ c
```

- **R** = Earth's radius (6,371 km)
- **φ** = latitude, **λ** = longitude
- Distance in kilometers

### Dijkstra's Shortest Path

For a complete graph with symmetric edge weights (distance), our implementation:

1. Initializes all distances to infinity
2. Computes direct distance from start to each node
3. Iteratively selects the nearest unvisited node
4. Relaxes edges (updates distances via current node)
5. Returns sorted list of node IDs by distance

**Time Complexity**: O(n²) for n properties  
**Practical for**: up to ~1000 properties per query

For larger datasets (10k+ properties), consider:
- PostGIS extension (PostgreSQL geospatial queries)
- Elasticsearch with geo_distance plugin
- Redis sorted sets for pre-computed zones

---

## Real-World Example: Apartment Hunting

### Scenario:
A tenant in Kathmandu searching for a 2BR apartment within 5 km radius, max Rs. 30,000/month.

### API Request:
```
GET /properties/?lat=27.7172&lng=85.3240&bedrooms=2&max_rent=30000
```

### Backend Processing:
1. Filter: bedrooms=2, rent ≤ 30000, is_verified=True
2. Extract coordinates of matching properties
3. Run Dijkstra from tenant's location
4. Return properties sorted by distance

### Frontend Display:
- Property cards sorted nearest to farthest
- Distance badge on each card: "2.3 km away"
- Map integration (optional): show all results on map with distance circles

---

## Production Recommendations

1. **Add Database Index**: Speed up coordinate lookups
   ```python
   class Meta:
       indexes = [
           models.Index(fields=['latitude', 'longitude', 'is_verified']),
       ]
   ```

2. **Cache Results**: Store frequently-searched locations
   ```python
   from django.views.decorators.cache import cache_page
   @cache_page(60 * 5)  # 5 minutes
   def property_list(request):
   ```

3. **Integrate Geocoding**: Auto-populate coords from address
   ```python
   from geopy.geocoders import Nominatim
   geolocator = Nominatim(user_agent="rentalconnect")
   loc = geolocator.geocode(address)
   property.latitude = loc.latitude
   property.longitude = loc.longitude
   ```

4. **Map Visualization**: Use Leaflet.js or Google Maps
   ```html
   <div id="map" style="height: 400px;"></div>
   <script>
       var map = L.map('map').setView([27.7172, 85.3240], 13);
       L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
       // Add markers for each property
   </script>
   ```

5. **Rate Limiting**: Prevent abuse of distance calculations
   ```python
   from django.core.cache import cache
   from django.http import HttpResponse
   
   def check_rate_limit(request):
       key = f"location_search_{request.user.id}"
       count = cache.get(key, 0)
       if count >= 10:  # Max 10 searches per hour
           return HttpResponse("Rate limit exceeded", status=429)
       cache.set(key, count + 1, 3600)
   ```

---

## Integration with Existing Features

- **Booking System**: Show distance to tenant's home/workplace
- **Property Verification**: Verify coordinates during property listing
- **Notifications**: "New property near you" alerts
- **Search History**: Save favorite search locations
- **Price Analysis**: "Average rent in this radius: Rs. 24,500"

---

**The location-based search feature is now fully integrated and production-ready!**
