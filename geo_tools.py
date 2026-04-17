# ── 1. IMPORTS & CONFIG ─────────────────────────────────────
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
STATICMAP_URL = "https://maps.googleapis.com/maps/api/staticmap"


# ── 2. GEOCODING ────────────────────────────────────────────
def geocode_address(address: str) -> dict:
    """Convert an address or place name into latitude/longitude coordinates."""
    try:
        response = requests.get(GEOCODE_URL, params={"address": address, "key": API_KEY}, timeout=10)
        data = response.json()

        if data.get("status") != "OK" or not data.get("results"):
            return {"error": f"Could not geocode address: {address}"}

        result = data["results"][0]
        location = result["geometry"]["location"]
        return {
            "formatted_address": result["formatted_address"],
            "latitude": location["lat"],
            "longitude": location["lng"],
            "place_types": result.get("types", []),
        }
    except Exception as e:
        return {"error": f"Geocoding failed: {str(e)}"}


# ── 3. SATELLITE IMAGERY ────────────────────────────────────
def get_satellite_image_url(address: str = None, lat: float = None, lng: float = None, zoom: int = 17) -> str:
    """Get a satellite image URL. Zoom: 15=neighborhood, 17=building, 19=close-up."""
    if address and (lat is None or lng is None):
        geocoded = geocode_address(address)
        if "error" in geocoded:
            return geocoded["error"]
        lat, lng = geocoded["latitude"], geocoded["longitude"]

    if lat is None or lng is None:
        return "Error: Provide either address or lat/lng coordinates."

    return f"{STATICMAP_URL}?center={lat},{lng}&zoom={zoom}&size=640x480&maptype=satellite&key={API_KEY}"


# ── 4. LOCATION INTELLIGENCE ────────────────────────────────
def get_location_intelligence(location_query: str) -> str:
    """Get comprehensive location intelligence: satellite imagery at three zoom levels plus context."""
    if not API_KEY:
        return "Error: GOOGLE_MAPS_API_KEY not set in environment."

    geocoded = geocode_address(location_query)
    if "error" in geocoded:
        return geocoded["error"]

    lat = geocoded["latitude"]
    lng = geocoded["longitude"]
    formatted = geocoded["formatted_address"]
    types = ", ".join(geocoded.get("place_types", [])) or "general location"

    wide = get_satellite_image_url(lat=lat, lng=lng, zoom=14)
    building = get_satellite_image_url(lat=lat, lng=lng, zoom=17)
    close = get_satellite_image_url(lat=lat, lng=lng, zoom=19)

    return f"""=== LOCATION INTELLIGENCE ===

📍 **Location:** {formatted}
🌐 **Coordinates:** {lat}, {lng}
🏷️ **Type:** {types}

🛰️ **Satellite imagery at multiple zoom levels:**
- Wide area (neighborhood context): {wide}
- Building level: {building}
- Close-up detail: {close}

🗺️ **Google Maps link:** https://www.google.com/maps/@{lat},{lng},17z/data=!3m1!1e3
"""
