const CACHE_NAME = 'hanuai-v1';
const STATIC_ASSETS = [
    '/static/assets/img/HanuAi-logo.webp',
    '/static/Media/Base/HanuAi-logo.webp',
    // We will dynamically add more or let the install event handle them
];

// URLs to NEVER cache for security
const EXCLUDED_URLS = [
    '/admin/',
    '/api/',
    '/logout/',
    '/employee/dashboard/' // Keep the dashboard dynamic for security
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
});

self.addEventListener('activate', (event) => {
    // Clean up old caches
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
            );
        })
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Security Check: Never cache excluded or potentially sensitive URLs
    if (EXCLUDED_URLS.some(path => url.pathname.startsWith(path)) || event.request.method !== 'GET') {
        return;
    }

    // Cache strategy: Stale-While-Revalidate for static assets
    // This allows instant load from cache while updating in the background
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.open(CACHE_NAME).then((cache) => {
                return cache.match(event.request).then((cachedResponse) => {
                    const fetchedResponse = fetch(event.request).then((networkResponse) => {
                        cache.put(event.request, networkResponse.clone());
                        return networkResponse;
                    });
                    return cachedResponse || fetchedResponse;
                });
            })
        );
    }
});
