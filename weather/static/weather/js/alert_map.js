// weather/static/weather/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    console.log("Main.js: DOMContentLoaded - Initializing map and layers for Alerts page.");

    // Data expected from inline script in weather.html (passed via window.mapInitData)
    if (typeof window.mapInitData === 'undefined') {
        console.error("Main.js: window.mapInitData is not defined. Check inline script in HTML template.");
        const mapDiv = document.getElementById('map'); // Assuming map div ID is 'map'
        if (mapDiv) mapDiv.innerHTML = "<p style='text-align:center;color:red;'>Map initial data missing. Please check console.</p>";
        return;
    }

    const mapInitialLat = window.mapInitData.lat;
    const mapInitialLon = window.mapInitData.lon;
    const mapInitialLocationName = window.mapInitData.locationName;
    const rawNwsAlertFeatures = window.mapInitData.alerts;

    if (typeof mapInitialLat === 'undefined' || typeof mapInitialLon === 'undefined') {
        console.error("Main.js: Map center coordinates are undefined in window.mapInitData.");
        const mapDiv = document.getElementById('map');
        if (mapDiv) mapDiv.innerHTML = "<p style='text-align:center;color:red;'>Map center coordinates missing. Please check console.</p>";
        return;
    }

    const mapElement = document.getElementById('map'); // Your map div in weather.html
    if (!mapElement) {
        console.error("Main.js: Map element with ID 'map' not found in DOM.");
        return;
    }

    if (typeof L === 'undefined') { 
        console.error("Main.js: Leaflet library (L) is not loaded!");
        if (mapElement) mapElement.innerHTML = "<p style='text-align:center;color:red;'>Mapping library (Leaflet) not loaded. Please check console.</p>";
        return; 
    }

    // --- Initialize Leaflet Map ---
    console.log(`Main.js: Initializing Leaflet map at [${mapInitialLat}, ${mapInitialLon}]`);
    const map = L.map('map').setView([mapInitialLat, mapInitialLon], 7); // Adjust zoom as needed

    // --- Add Base Map Layer (OpenStreetMap) ---
    const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    console.log("Main.js: OpenStreetMap base layer added.");

    // --- Add a Marker for the Initial Location ---
    if (mapInitialLocationName) {
        L.marker([mapInitialLat, mapInitialLon]).addTo(map)
            .bindPopup(mapInitialLocationName)
            .openPopup();
    } else {
        L.marker([mapInitialLat, mapInitialLon]).addTo(map);
    }

    // --- RainViewer Radar Layer ---
    let rainviewerRadarLayer = null; 

    function addRainViewerLayer(timestampData) {
        if (rainviewerRadarLayer && map.hasLayer(rainviewerRadarLayer)) {
            map.removeLayer(rainviewerRadarLayer); 
        }
        
        const mostRecentPastFrame = timestampData.radar.past[timestampData.radar.past.length - 1];
        if (!mostRecentPastFrame || !mostRecentPastFrame.path) {
            console.error("Main.js: No valid past radar frames or path available from RainViewer.");
            return;
        }

        const rvTileSize = 256;    // Using 256px tiles as you found it worked
        const rvColorScheme = 4;   // Default RainViewer color scheme (can be changed)
        const rvSmooth = 1;        // 0 for false (sharper)
        const rvSnowFilter = 1;    // 1 to show snow

        const radarTileUrl = `https://tilecache.rainviewer.com${mostRecentPastFrame.path}/${rvTileSize}/{z}/{x}/{y}/${rvColorScheme}/${rvSmooth}_${rvSnowFilter}.png`;
        
        console.log("Main.js: Constructed RainViewer Tile URL:", radarTileUrl); 

        rainviewerRadarLayer = L.tileLayer(radarTileUrl, {
            attribution: '<a href="https://www.rainviewer.com/" target="_blank">RainViewer.com</a>',
            opacity: 0.7,
            tileSize: rvTileSize, 
            minZoom: 0,          
            maxZoom: 12         
        });
        // Add to map and potentially to layer control later
        rainviewerRadarLayer.addTo(map); 
        console.log("Main.js: RainViewer radar layer added to map for timestamp:", mostRecentPastFrame.time);
        
        // Update layer control if it exists
        if (window.alertPageLayerControl && rainviewerRadarLayer) {
            window.alertPageLayerControl.addOverlay(rainviewerRadarLayer, "RainViewer Radar");
        }
    }

    fetch('https://api.rainviewer.com/public/weather-maps.json')
        .then(response => {
            if (!response.ok) {
                throw new Error(`RainViewer API request failed: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Main.js: RainViewer API response received:", data);
            if (data && data.radar && data.radar.past && data.radar.past.length > 0) {
                addRainViewerLayer(data);
            } else {
                console.error("Main.js: No radar data available from RainViewer API response.");
            }
        })
        .catch(error => {
            console.error("Main.js: Error fetching or processing RainViewer data:", error);
        });

    // --- NWS Alert Polygon Overlays ---
    console.log("Main.js: Checking for NWS Alert GeoJSON data:", rawNwsAlertFeatures);
    const alertPolygons = {
        warnings: L.layerGroup(),
        watches: L.layerGroup(),
        advisories: L.layerGroup()
    };

    if (typeof rawNwsAlertFeatures !== 'undefined' && rawNwsAlertFeatures.length > 0) {
        console.log("Main.js: Processing NWS Alert Features for map display.");

        function getAlertStyle(alertProperties) {
            let style = { color: "grey", weight: 1, opacity: 0.75, fillOpacity: 0.25, fillColor: "grey" };
            const eventType = alertProperties.event ? alertProperties.event.toLowerCase() : "";
            const severity = alertProperties.severity ? alertProperties.severity.toLowerCase() : "";

            if (eventType.includes("warning")) {
                style.color = "red"; style.fillColor = "#ff0000"; style.weight = 2; style.fillOpacity = 0.3;
            } else if (eventType.includes("watch")) {
                style.color = "orange"; style.fillColor = "#ffa500"; style.fillOpacity = 0.25;
            } else if (eventType.includes("advisory")) {
                style.color = "blue"; style.fillColor = "#0000ff"; style.fillOpacity = 0.2;
            } else if (eventType.includes("statement") || eventType.includes("outlook")) {
                style.color = "#505050"; style.fillColor = "#505050"; style.fillOpacity = 0.15;
            }

            if (severity === "extreme") { style.weight = 3; style.dashArray = '5, 5';}
            else if (severity === "severe") { style.weight = 2.5; }
            
            return style;
        }

        rawNwsAlertFeatures.forEach(alertFeature => {
            if (alertFeature && alertFeature.properties && alertFeature.geometry) { // Check feature itself too
                const alertLayer = L.geoJSON(alertFeature, { // Pass the whole GeoJSON Feature
                    style: function(feature) {
                        return getAlertStyle(feature.properties);
                    }
                }).bindPopup(`<strong>${alertFeature.properties.event}</strong><hr><small>${alertFeature.properties.headline}</small>`);

                const eventType = alertFeature.properties.event ? alertFeature.properties.event.toLowerCase() : "";
                if (eventType.includes("warning")) {
                    alertPolygons.warnings.addLayer(alertLayer);
                } else if (eventType.includes("watch")) {
                    alertPolygons.watches.addLayer(alertLayer);
                } else { 
                    alertPolygons.advisories.addLayer(alertLayer);
                }
            }
        });
        
        // Optionally add some layers to map by default
        // alertPolygons.warnings.addTo(map);

        console.log("Main.js: NWS Alert polygon layers processed.");
    } else {
        console.log("Main.js: No NWS Alert GeoJSON data provided or array is empty.");
    }

    // --- Layer Control ---
    const baseLayersForControl = { "OpenStreetMap": osmLayer };
    const overlaysForControl = {};

    if (rainviewerRadarLayer) { // Add radar if it was successfully created
        overlaysForControl["RainViewer Radar"] = rainviewerRadarLayer;
    }
    overlaysForControl["NWS Warnings"] = alertPolygons.warnings;
    overlaysForControl["NWS Watches"] = alertPolygons.watches;
    overlaysForControl["NWS Advisories/Stmts"] = alertPolygons.advisories;

    if (window.alertPageLayerControl && map.hasControl(window.alertPageLayerControl)) {
        map.removeControl(window.alertPageLayerControl);
    }
    window.alertPageLayerControl = L.control.layers(baseLayersForControl, overlaysForControl, {
        collapsed: false 
    }).addTo(map);
    console.log("Main.js: Layer control added/updated.");

}); // End DOMContentLoaded listener
