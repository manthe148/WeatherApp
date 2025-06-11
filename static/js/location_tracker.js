// /srv/radar_site_prod/static/js/location_tracker.js

document.addEventListener('DOMContentLoaded', () => {
    const locationToggle = document.getElementById('location-sharing-toggle');
    const locationStatusLabel = document.getElementById('location-sharing-status');
    const locationErrorDiv = document.getElementById('location-sharing-error');

    // If the toggle switch UI isn't on this page, don't run any of the code.
    if (!locationToggle || !locationStatusLabel || !locationErrorDiv) {
        return;
    }
    
    console.log("LOCATION_TRACKER: UI elements found. Initializing script.");

    let watchId = null; // This will hold the ID of our location watcher

    // Helper function to get CSRF token from cookies for POST requests
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Function to send coordinates to the Django backend API endpoint
    function sendLocationToServer(position) {
        const coords = position.coords;
        const lat = coords.latitude;
        const lon = coords.longitude;

        console.log(`LOCATION_TRACKER: Sending location to server - Lat: ${lat.toFixed(4)}, Lon: ${lon.toFixed(4)}`);
        locationErrorDiv.textContent = ''; // Clear previous errors

        // UPDATE_LOCATION_URL must be defined globally in a <script> tag in the HTML template
        fetch(UPDATE_LOCATION_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ lat: lat, lon: lon })
        })
        .then(response => {
            if (!response.ok) {
                console.error('LOCATION_TRACKER: Server error updating location:', response.statusText);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                console.log('LOCATION_TRACKER: Location successfully updated on server.');
            } else {
                console.error('LOCATION_TRACKER: Server responded with error:', data.message);
            }
        })
        .catch(error => {
            console.error('LOCATION_TRACKER: Failed to send location to server:', error);
        });
    }

    // Function to handle errors from the Geolocation API
    function handleLocationError(error) {
        let message = "Location sharing failed. ";
        switch (error.code) {
            case error.PERMISSION_DENIED:
                message += "You denied the request for Geolocation.";
                break;
            case error.POSITION_UNAVAILABLE:
                message += "Location information is unavailable.";
                break;
            case error.TIMEOUT:
                message += "The request to get user location timed out.";
                break;
            default:
                message += "An unknown error occurred.";
                break;
        }
        console.error("LOCATION_TRACKER:", message, error);
        locationErrorDiv.textContent = message;
        stopWatchingLocation(); // Stop trying if there's an error
    }

    // Function to START watching the user's position
    function startWatchingLocation() {
        if (!navigator.geolocation) {
            locationErrorDiv.textContent = 'Geolocation is not supported by your browser.';
            return;
        }
        if (watchId) { 
            console.log("LOCATION_TRACKER: watchPosition is already active.");
            return;
        }

        console.log("LOCATION_TRACKER: Starting location watch...");
        locationStatusLabel.textContent = "Location Sharing is ON";
        locationToggle.checked = true;
        localStorage.setItem('locationSharingEnabled', 'true');

        const options = { enableHighAccuracy: false, timeout: 30000, maximumAge: 600000 };
        watchId = navigator.geolocation.watchPosition(sendLocationToServer, handleLocationError, options);
    }

    function stopWatchingLocation() {
        if (watchId) {
            navigator.geolocation.clearWatch(watchId);
            watchId = null;
            console.log("LOCATION_TRACKER: Stopped watching location.");
        }
        locationStatusLabel.textContent = "Location Sharing is OFF";
        locationToggle.checked = false;
        // We don't set localStorage to false here, because the server will tell us when to turn off.
    }

    // --- NEW: Function to check with the server if tracking should be active ---
    function checkServerAndToggleTracking() {
        console.log("LOCATION_TRACKER: Asking server if location tracking should be active...");

        // Only proceed if user has enabled sharing via the toggle
        if (localStorage.getItem('locationSharingEnabled') !== 'true') {
            console.log("LOCATION_TRACKER: Tracking is disabled by user preference. Halting check.");
            stopWatchingLocation(); // Ensure it's stopped
            return;
        }

        fetch(SHOULD_TRACK_URL) // Call the new API endpoint
            .then(response => response.json())
            .then(data => {
                console.log("LOCATION_TRACKER: Server response for should_track:", data.should_track);
                if (data.should_track) {
                    // Server says yes, start or continue tracking
                    startWatchingLocation();
                } else {
                    // Server says no, stop tracking
                    stopWatchingLocation();
                    // We don't change localStorage here. The user's master preference is still 'on',
                    // but the system is pausing tracking until it's needed again.
                    locationStatusLabel.textContent = "Location Sharing is enabled, but paused (no nearby threats).";
                }
            })
            .catch(error => {
                console.error("LOCATION_TRACKER: Error checking with server:", error);
                // In case of error, stop tracking to be safe
                stopWatchingLocation();
            });
    }

    // Event listener for the user's main toggle switch
    locationToggle.addEventListener('change', () => {
        if (locationToggle.checked) {
            // User wants to turn sharing ON
            console.log("LOCATION_TRACKER: User enabled sharing. Saving preference and starting initial check.");
            localStorage.setItem('locationSharingEnabled', 'true');
            checkServerAndToggleTracking(); // Immediately check if we should start
        } else {
            // User wants to turn sharing OFF
            console.log("LOCATION_TRACKER: User disabled sharing. Saving preference and stopping.");
            localStorage.setItem('locationSharingEnabled', 'false');
            stopWatchingLocation();
        }
    });

    // On page load, check the saved preference and then check the server
    if (localStorage.getItem('locationSharingEnabled') === 'true') {
        console.log("LOCATION_TRACKER: Found saved preference to share location. Checking server...");
        locationToggle.checked = true; // Set the toggle to the correct state
        checkServerAndToggleTracking();
        // Also, check with the server periodically (e.g., every 5 minutes)
        setInterval(checkServerAndToggleTracking, 300000); // 300000ms = 5 minutes
    }



    // Add click listener to the toggle switch
    locationToggle.addEventListener('change', () => {
        console.log("LOCATION_TRACKER: Toggle switch clicked.");
        if (locationToggle.checked) {
            startWatchingLocation();
        } else {
            stopWatchingLocation();
        }
    });

    // On page load, check localStorage to see if tracking should be re-enabled
    try {
        const savedPreference = localStorage.getItem('locationSharingEnabled');
        console.log(`LOCATION_TRACKER: On page load, found savedPreference = '${savedPreference}'`);
        if (savedPreference === 'true') {
            console.log("LOCATION_TRACKER: Resuming location sharing based on saved preference.");
            // Set the toggle to checked. The user may still be prompted for permission by the browser.
            startWatchingLocation();
        } else {
            // Ensure UI is in the 'off' state
            locationToggle.checked = false;
            locationStatusLabel.textContent = "Location Sharing is OFF";
        }
    } catch (e) {
        console.error("LOCATION_TRACKER: Error reading from localStorage on page load:", e);
    }
});
