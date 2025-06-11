// static/js/family_map_manager.js

let map = null;

document.addEventListener('DOMContentLoaded', () => {
    const mapContainer = document.getElementById('family-map');
    const mapStatus = document.getElementById('map-status');

    // Check if the necessary HTML element and Mapbox token are available
    if (!mapContainer || typeof MAPBOX_ACCESS_TOKEN === 'undefined' || MAPBOX_ACCESS_TOKEN === '') {
        if (mapStatus) mapStatus.textContent = 'Map configuration is missing or invalid.';
        console.error('Map container (#family-map) or Mapbox Access Token is missing. Map cannot be initialized.');
        return;
    }

    // --- Initialize Mapbox Map ---
    mapboxgl.accessToken = MAPBOX_ACCESS_TOKEN;
    const map = new mapboxgl.Map({
        container: 'family-map', // ID of the map container div
        style: 'mapbox://styles/mapbox/streets-v12', // Mapbox style URL
        center: [-98.5795, 39.8283], // Starting center of the map (e.g., center of the US)
        zoom: 3 // Starting zoom level
    });

    // Add zoom and rotation controls to the map.
    map.addControl(new mapboxgl.NavigationControl());

    let markers = []; // An array to keep track of markers currently on the map

    // --- Function to Fetch Data and Update Map Markers ---
    function updateFamilyMemberMarkers() {
        if (mapStatus) mapStatus.textContent = 'Fetching latest family member locations...';
        console.log("MAP_DEBUG: Fetching family locations from:", FAMILY_LOCATIONS_API_URL);

        fetch(FAMILY_LOCATIONS_API_URL)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server responded with status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // The 'data' variable is the JSON response from your API view.
                // Based on our last check, we expect the data itself to be the array.
                const memberArray = Array.isArray(data) ? data : data.family_members;

                if (!Array.isArray(memberArray)) {
                    console.error("MAP_DEBUG: Received data is not in the expected format (array of members).", data);
                    if (mapStatus) mapStatus.textContent = 'Received unexpected data format from server.';
                    return;
                }

                console.log("MAP_DEBUG: Received location data array:", memberArray);
                processMembers(memberArray);
            })
            .catch(error => {
                console.error('MAP_DEBUG: Error fetching or processing family location data:', error);
                if (mapStatus) mapStatus.textContent = 'Could not load family member locations.';
            });
    }

    // --- Function to Process Member Data and Add/Remove Markers ---
    function processMembers(memberArray) {
        // First, clear any existing markers from the map
        markers.forEach(marker => marker.remove());
        markers = []; // Reset the markers array

        let membersInWarnedArea = 0;

        // Loop through each family member in the data from the API
        memberArray.forEach(member => {
            console.log(`MAP_DEBUG: Processing member: ${member.username}, In Warned Area: ${member.is_in_warned_area}`);

            // The main condition: Only display a marker if the user is in a warned area.
            if (member.is_in_warned_area) {
                console.log(`%c[DEBUGGER] Pausing execution for warned member: ${member.username}.`, 'color: blue; font-weight: bold;');
                console.log(`[DEBUGGER] Go to the 'Sources' tab to step through code, or 'Console' to inspect variables.`);

                // <<< THIS LINE WILL PAUSE THE SCRIPT

                membersInWarnedArea++;

                console.log(`MARKER_DEBUG: Member ${member.username} IS in a warned area. Attempting to create marker.`);

                // Convert coordinates from string (if they are) to number
                const lon = parseFloat(member.longitude);
                const lat = parseFloat(member.latitude);
                console.log(`MARKER_DEBUG: Parsed Coords - Lon: ${lon}, Lat: ${lat}`);

                // Check if coordinates are valid numbers before creating a marker
                if (isNaN(lon) || isNaN(lat)) {
                    console.error(`MARKER_DEBUG: Invalid coordinates for ${member.username}. Cannot create marker.`);
                    return; // 'return' here skips to the next member in the forEach loop
                }

                try {
                    // Create a popup with the member's info
                    const popup = new mapboxgl.Popup({ offset: 25 })
                        .setHTML(`<h6>${member.username}</h6><p>Location reported:<br>${new Date(member.timestamp_iso).toLocaleString()}</p>`);

                    // Create the marker and add it to the map
                    const marker = new mapboxgl.Marker({
                        color: "#FF0000", // Red color for a warning
                        scale: 0.8
                    })
                        .setLngLat([lon, lat])
                        .setPopup(popup) // sets a popup on this marker
                        .addTo(map);

                    console.log(`MARKER_DEBUG: SUCCESS! Marker for ${member.username} added to map.`);
                    markers.push(marker); // Add the new marker to our tracking array
                } catch (e) {
                    console.error("MARKER_DEBUG: An error occurred during Mapbox marker or popup creation:", e);
                }
            }
        });

        // Update the status message based on what was found
        if (membersInWarnedArea > 0) {
            if (mapStatus) mapStatus.textContent = `Displaying location for ${membersInWarnedArea} member(s) in warned areas.`;
        } else {
            if (mapStatus) mapStatus.textContent = 'All family members are currently safe and outside of warned areas.';
        }
    }

    // --- Map Initialization ---
    // This event listener waits for the map's resources (like its style) to be fully loaded.
    map.on('load', () => {
        // --- ADD THIS LOG ---
        console.log("%cMAP IS NOW FULLY LOADED AND READY FOR MARKERS.", "color: green; font-size: 1.2em; font-weight: bold;");

        if (mapStatus) mapStatus.textContent = 'Map loaded successfully. Fetching data...';

        // The existing function call to get family member data will run now
        updateFamilyMemberMarkers(map);

        // The periodic refresh will also be set up now
        setInterval(() => updateFamilyMemberMarkers(map), 120000);
    });

    map.on('error', (e) => {
        console.error("MAP_JS: A Mapbox error occurred:", e.error);
        if (mapStatus) mapStatus.textContent = `Map error: ${e.error.message}`;
    });
});