// weather/static/weather/js/weather_models.js
document.addEventListener('DOMContentLoaded', function () {
    console.log("Weather Models JS loaded.");

    const mapElement = document.getElementById('model-map');

    // These global JS variables are expected to be defined in an inline script 
    // in the weather_models.html template before this script runs.
    if (mapElement && typeof modelMapLat !== 'undefined' && typeof modelMapLon !== 'undefined') {
        console.log("Initializing Weather Models map at:", modelMapLat, modelMapLon);

        const map = L.map('model-map').setView([modelMapLat, modelMapLon], 5); // Zoom level adjusted for CONUS view

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        // Check if the image exists and data is available
        if (typeof imageExists !== 'undefined' && imageExists && 
            typeof modelImageUrl !== 'undefined' && modelImageUrl &&
            typeof modelImageBounds !== 'undefined' && modelImageBounds) {

            console.log("Attempting to add image overlay:", modelImageUrl, modelImageBounds);

            try {
                // L.imageOverlay expects bounds as [[lat_min, lon_min], [lat_max, lon_max]]
                // or L.latLngBounds(L.latLng(south, west), L.latLng(north, east))
                const bounds = L.latLngBounds(
                    [modelImageBounds[0][0], modelImageBounds[0][0]], // South-West corner
                    [modelImageBounds[0][0], modelImageBounds[0][0]]  // North-East corner
                );

                L.imageOverlay(modelImageUrl, bounds, {
                    opacity: 0.7, // Adjust as needed
                    attribution: "GFS 2m Temperature &copy; NOAA/NCEP"
                }).addTo(map);
                console.log("Model image overlay added.");
            } catch (e) {
                console.error("Error adding image overlay:", e);
                mapElement.innerHTML = '<p style="text-align:center;color:red;">Error displaying model image. Bounds might be incorrect.</p>';
            }
        } else {
            console.log("Model image URL or bounds not available, or image does not exist.");
            // Message is already in HTML if image_exists is false
        }

        L.marker([modelMapLat, modelMapLon]).addTo(map)
            .bindPopup(`Map centered near ${document.title.replace("Weather Models - ", "") || 'selected location'}`);

    } else {
        if (!mapElement) console.error("Model map container (#model-map) not found.");
        // Log missing coordinate variables
        if (typeof modelMapLat === 'undefined') console.error("modelMapLat not defined.");
        if (typeof modelMapLon === 'undefined') console.error("modelMapLon not defined.");
    }
});
