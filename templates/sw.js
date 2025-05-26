// templates/sw.js -
{% load static %}
// templates/sw.js
const CACHE_NAME = 'weather-app-cache-v2.1'; // Change version to force update
const urlsToCache = [
    '/', // Cache the homepage
    "{% url 'pages:about' %}", // Cache the about page URL (Django will render this)
    "{% url 'weather:weather_page' %}", // Cache the main weather page URL
    "{% static 'css/style.css' %}",
    "{% static 'js/main.js' %}", // Your main site JS
    // Add other essential static assets: logo, key icons (NOT user-uploaded media)
    "{% static 'images/icons/Icon_192.jpg' %}", // Example icon
    "{% static 'images/icons/Icon_512.jpg' %}", // Example icon
    // CDN assets (optional, they have their own caching but can be added)
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
    // Add a placeholder offline page
    "{% url 'offline_page' %}" // We'll create this URL and template next
];

console.log('[Service Worker] Loading...');

self.addEventListener('install', event => {
    console.log('[Service Worker] Install event - Caching App Shell');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[Service Worker] Opened cache, adding App Shell to cache');
                return cache.addAll(urlsToCache);
            })
            .then(() => self.skipWaiting()) // Activate new SW immediately
            .catch(error => {
                console.error('[Service Worker] Failed to cache App Shell:', error);
            })
    );
});

self.addEventListener('activate', event => {
    console.log('[Service Worker] Activate event');
    // Remove old caches
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.filter(cacheName => {
                    // Delete caches that are not our current one (useful for versioning)
                    return cacheName.startsWith('weather-app-cache-') && cacheName !== CACHE_NAME;
                }).map(cacheName => {
                    console.log('[Service Worker] Deleting old cache:', cacheName);
                    return caches.delete(cacheName);
                })
            );
        }).then(() => self.clients.claim()) // Take control immediately
    );
});

self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') {
        // For non-GET requests, just fetch from network without caching
        // Or handle as per your app's needs (e.g., for API POSTs if you want SW to intercept)
        return;
    }

    // Strategy: Network first, then cache fallback, especially for HTML/navigation requests.
    // For other static assets (CSS, JS, images in urlsToCache), cache-first is often okay.

    // Check if it's a navigation request or an HTML request
    if (event.request.mode === 'navigate' ||
        (event.request.headers.get('Accept') && event.request.headers.get('Accept').includes('text/html'))) {

        // Network-First for HTML pages
        event.respondWith(
            fetch(event.request)
                .then(networkResponse => {
                    // If the fetch is successful, clone it and cache it
                    if (networkResponse && networkResponse.ok) {
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then(cache => {
                            cache.put(event.request, responseToCache);
                            // console.log('[Service Worker] Cached network response for:', event.request.url);
                        });
                    }
                    return networkResponse;
                })
                .catch(error => {
                    // Network failed, try to serve from cache
                    console.log('[Service Worker] Network fetch failed, trying cache for:', event.request.url, error);
                    return caches.match(event.request)
                        .then(cachedResponse => {
                            // Return cached response or the offline page if not in cache
                            return cachedResponse || caches.match("{% url 'offline_page' %}");
                        });
                })
        );
    } else {
        // Cache-First strategy for other static assets (JS, CSS, images etc.)
        // that were pre-cached in the 'install' event.
        event.respondWith(
            caches.match(event.request)
                .then(cachedResponse => {
                    if (cachedResponse) {
                        // console.log('[Service Worker] Serving from cache:', event.request.url);
                        return cachedResponse;
                    }
                    // If not in cache, fetch from network (and optionally cache it)
                    // console.log('[Service Worker] Not in cache, fetching from network:', event.request.url);
                    return fetch(event.request).then(networkResponse => {
                        // Optional: Cache newly fetched static assets dynamically if needed
                        // const responseToCache = networkResponse.clone();
                        // caches.open(CACHE_NAME).then(cache => {
                        //     cache.put(event.request, responseToCache);
                        // });
                        return networkResponse;
                    }).catch(error => {
                        // For static assets, if network fails and not in cache,
                        // it will result in a browser error for that asset.
                        // No specific offline page for individual assets here.
                        console.error('[Service Worker] Static asset fetch failed (not in cache, network error):', event.request.url, error);
                    });
                })
        );
    }
});
// Push event listener (keep existing)

self.addEventListener('push', function (event) {
    console.log('[Service Worker] Push Received.');

    let pushData = {
        head: 'Weather Alert', // Default title
        body: 'New alert received!', // Default body
        icon: "{% static 'images/icons/Icon_192.jpg' %}", // Default icon (ensure this path is correct)
        badge: "{% static 'images/icons/Icon_72.jpg' %}",  // Default badge (ensure this path is correct)
        sound: null, // Default to no sound, will be overridden by payload if present
        url: "{% url 'pages:home' %}" // Default URL to open on click
    };

    if (event.data) {
        try {
            const payloadFromServer = event.data.json(); // Parse the JSON payload from server
            console.log('[Service Worker] Push data JSON:', payloadFromServer);

            // Override defaults with data from the payload if present
            if (payloadFromServer.head) pushData.head = payloadFromServer.head;
            if (payloadFromServer.body) pushData.body = payloadFromServer.body;
            if (payloadFromServer.icon) pushData.icon = payloadFromServer.icon;
            if (payloadFromServer.badge) pushData.badge = payloadFromServer.badge; // If you send a badge URL
            if (payloadFromServer.sound) pushData.sound = payloadFromServer.sound; // Use sound from payload
            if (payloadFromServer.url) pushData.url = payloadFromServer.url;

        } catch (e) {
            console.error('[Service Worker] Error parsing push data as JSON:', e);
            // Fallback for non-JSON data, though your server sends JSON
            const plainTextData = event.data.text();
            if (plainTextData) pushData.body = plainTextData;
        }
    } else {
        console.log('[Service Worker] Push event had no data.');
    }

    const notificationTitle = pushData.head;
    const notificationOptions = {
        body: pushData.body,
        icon: pushData.icon,
        badge: pushData.badge, // For Android
        sound: pushData.sound, // <<< Using the sound URL from your payload
        vibrate: [200, 100, 200, 100, 200], // Optional: add a vibration pattern
        data: { // Data to pass to notification click event
            url: pushData.url
        }
        // You can add other options like:
        // tag: 'weather-alert', // Coalesces notifications with the same tag
        // renotify: true,       // If true, will play sound/vibrate even if tag matches
    };

    console.log('[Service Worker] Final Notification Options:', notificationOptions); // For debugging
    event.waitUntil(
        self.registration.showNotification(notificationTitle, notificationOptions)
    );


    console.log('[Service Worker] Showing notification with Title:', notificationTitle, 'Options:', notificationOptions);
    event.waitUntil(
        self.registration.showNotification(notificationTitle, notificationOptions)
    );
});

// Your notificationclick listener can remain largely the same:
self.addEventListener('notificationclick', function (event) {
    console.log('[Service Worker] Notification click Received.');
    event.notification.close();

    const urlToOpen = event.notification.data && event.notification.data.url ? event.notification.data.url : '/'; // Uses the URL from the data payload

    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then(windowClients => {
            // ... (logic to focus existing tab or open new window to urlToOpen) ...
            const existingClient = windowClients.find(client => {
                return client.url === new URL(urlToOpen, self.location.origin).href && 'focus' in client;
            });

            if (existingClient) {
                return existingClient.focus();
            } else if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});
