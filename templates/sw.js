// templates/sw.js - PASTE THIS CODE INTO THIS FILE
{% load static %}
// templates/sw.js
const CACHE_NAME = 'weather-app-cache-v1'; // Change version to force update
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

self.addEventListener('push', function(event) {
    console.log('[Service Worker] Push Received.');

    let notificationTitle = 'Weather Alert'; // Default
    let notificationBody = 'New alert received!';  // Default
    let iconPath = "{% static 'images/icons/icon-192x192.png' %}"; // Default
    let badgePath = "{% static 'images/icons/icon-72x72.png' %}";  // Default
    let notificationUrl = '/'; // Default

    if (event.data) {
        const rawDataString = event.data.text();
        console.log(`[Service Worker] Push had this data (text): "${rawDataString}"`);

        const parts = rawDataString.split('|||');
        if (parts.length >= 2) { // Expect at least title and body
            notificationTitle = parts[0] || notificationTitle;
            notificationBody = parts[1] || notificationBody;
            if (parts.length >= 3 && parts[2]) { // Icon path
                iconPath = parts[2];
            }
            if (parts.length >= 4 && parts[3]) { // URL to open
                notificationUrl = parts[3];
            }
        } else {
            // If not enough parts, use the whole string as body
            notificationBody = rawDataString || notificationBody;
        }
    } else {
        console.log('[Service Worker] Push event had no data.');
    }

    const options = {
        body: notificationBody,
        icon: iconPath,
        badge: badgePath, // You can use a default or make it part of the string payload too
        sound: "{% static 'sounds/danger.mp3' %}",
        data: {
            url: notificationUrl
        }
    };

    console.log('[Service Worker] Showing notification with Title:', notificationTitle, 'Options:', options);
    event.waitUntil(self.registration.showNotification(notificationTitle, options));
});

// Notification click listener (keep existing)
self.addEventListener('notificationclick', function(event) {
    // ... your existing notification click handling ...
    console.log('[Service Worker] Notification click Received.');
    event.notification.close();
    const urlToOpen = event.notification.data && event.notification.data.url ? event.notification.data.url : '/';
    event.waitUntil( clients.matchAll({ type: 'window' }).then(windowClients => { for (var i = 0; i < windowClients.length; i++) { var client = windowClients[i]; if (client.url === urlToOpen && 'focus' in client) { return client.focus(); }} if (clients.openWindow) { return clients.openWindow(urlToOpen);}}) );
});
