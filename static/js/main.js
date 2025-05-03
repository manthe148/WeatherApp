// static/js/main.js
// Remove or keep the previous console log
// console.log("Hello from main.js!");

// Wait for the HTML DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {

    // Check if the map container element exists on the current page
    const mapElement = document.getElementById('map');
    if (mapElement) {

        // --- Initialize Leaflet Map ---
        // Use the latitude and longitude passed from the Django template
        // These variables (mapCenterLat, mapCenterLon) are created in the inline
        // <script> block within weather/templates/weather/weather.html
        const map = L.map('map').setView([mapCenterLat, mapCenterLon], 8); // Center on location, zoom level 8

        // --- Add Base Map Layer (OpenStreetMap) ---
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        // --- Add NWS/IEM Radar Tile Layer ---
        // This URL points to a commonly used composite radar layer from IEM.
        // Timestamps can sometimes be added to the URL for animation (more complex).
        const radarUrl = 'https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png';
        L.tileLayer(radarUrl, {
            attribution: 'Radar data &copy; Iowa Environmental Mesonet',
            opacity: 0.7 // Make radar slightly transparent
        }).addTo(map);

         // --- Add a Marker for the Location ---
         L.marker([mapCenterLat, mapCenterLon]).addTo(map)
            .bindPopup(`Approx. location: ${mapCenterLat.toFixed(4)}, ${mapCenterLon.toFixed(4)}`)
            // .openPopup(); // Uncomment to open popup by default
    }

}); // End DOMContentLoaded listener
