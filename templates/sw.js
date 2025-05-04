// templates/sw.js - PASTE THIS CODE INTO THIS FILE

console.log('[Service Worker] Loading...');

self.addEventListener('push', function(event) {
    console.log('[Service Worker] Push Received.');
    // Log data for now, later show notification
    let pushData = 'No payload';
    if (event.data) {
        // Attempt to parse JSON, fallback to text
        try {
            const dataJson = event.data.json();
            // Customize how you extract title/body from JSON payload
            pushData = dataJson.body || JSON.stringify(dataJson); // Example
            console.log('[Service Worker] Push data (JSON parsed):', dataJson);
        } catch(e) {
            pushData = event.data.text(); // Fallback if not JSON
             console.log(`[Service Worker] Push had this data (plain text): "${pushData}"`);
        }
    } else {
        console.log('[Service Worker] Push event had no data.');
        pushData = 'Default alert message.'; // Provide a default body if none sent
    }


    const title = 'Weather Alert'; // You could customize title too
    const options = {
        body: pushData, // Use payload text/data as body
        // You'll need icon files in your static directory later
        // e.g., /static/images/icons/icon-192x192.png
        // icon: '/static/images/your_app_icon.png',
        // badge: '/static/images/your_app_badge.png'
    };

    // Show notification
    console.log('[Service Worker] Showing notification...');
    const notificationPromise = self.registration.showNotification(title, options);
    event.waitUntil(notificationPromise);
});

self.addEventListener('notificationclick', function(event) {
    console.log('[Service Worker] Notification click Received.');
    event.notification.close();
    // Optional: Add logic to focus or open a window/URL when clicked
    // Example: Open the weather page
    // event.waitUntil(clients.openWindow('/weather/'));
});

// Basic install/activate logs (optional but helpful for debugging SW lifecycle)
self.addEventListener('install', event => {
  console.log('[Service Worker] Install event');
  // Optional: allows the new service worker to activate immediately
  // self.skipWaiting();
});

self.addEventListener('activate', event => {
    console.log('[Service Worker] Activate event');
    // Optional: ensures the new service worker takes control immediately
    // event.waitUntil(clients.claim());
});
