// EcoPOOL Service Worker
// Version for cache busting
const CACHE_VERSION = 'v1';
const STATIC_CACHE = `ecopool-static-${CACHE_VERSION}`;
const DATA_CACHE = `ecopool-data-${CACHE_VERSION}`;

// Static assets to cache on install
const STATIC_ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/js/offline-db.js',
    '/static/js/sync-manager.js',
    '/static/images/logo.png',
    '/static/images/ecoREACTION.png',
    '/favicon.ico',
    '/manifest.json'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
    console.log('[SW] Installing service worker...');
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                // Skip waiting to activate immediately
                return self.skipWaiting();
            })
            .catch((err) => {
                console.error('[SW] Error caching static assets:', err);
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating service worker...');
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => {
                            // Delete old versioned caches
                            return name.startsWith('ecopool-') &&
                                   name !== STATIC_CACHE &&
                                   name !== DATA_CACHE;
                        })
                        .map((name) => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                // Take control of all clients immediately
                return self.clients.claim();
            })
    );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Skip SSE streams - they cannot be cached
    if (url.pathname === '/api/stream') {
        return;
    }

    // Skip non-GET requests (POST, PUT, DELETE)
    if (event.request.method !== 'GET') {
        return;
    }

    // Handle API requests (network-first with cache fallback)
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkFirstWithCache(event.request, DATA_CACHE));
        return;
    }

    // Handle static assets (cache-first with network fallback)
    if (url.pathname.startsWith('/static/') ||
        url.pathname === '/' ||
        url.pathname === '/favicon.ico' ||
        url.pathname === '/manifest.json') {
        event.respondWith(cacheFirstWithNetwork(event.request, STATIC_CACHE));
        return;
    }

    // For other requests, try network first
    event.respondWith(networkFirstWithCache(event.request, DATA_CACHE));
});

// Cache-first strategy (for static assets)
async function cacheFirstWithNetwork(request, cacheName) {
    try {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            // Return cached version, but update cache in background
            fetchAndCache(request, cacheName);
            return cachedResponse;
        }

        // Not in cache, fetch from network
        return await fetchAndCache(request, cacheName);
    } catch (error) {
        console.error('[SW] Cache-first error:', error);
        // Try to return any cached version
        const cached = await caches.match(request);
        if (cached) return cached;

        // Return offline page for navigation requests
        if (request.mode === 'navigate') {
            return caches.match('/');
        }

        throw error;
    }
}

// Network-first strategy (for API data)
async function networkFirstWithCache(request, cacheName) {
    try {
        const networkResponse = await fetch(request);

        // Cache successful responses
        if (networkResponse.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, networkResponse.clone());
        }

        return networkResponse;
    } catch (error) {
        console.log('[SW] Network failed, trying cache:', request.url);

        // Network failed, try cache
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }

        // No cache available, throw error
        throw error;
    }
}

// Fetch and cache helper
async function fetchAndCache(request, cacheName) {
    const networkResponse = await fetch(request);

    if (networkResponse.ok) {
        const cache = await caches.open(cacheName);
        cache.put(request, networkResponse.clone());
    }

    return networkResponse;
}

// Handle messages from the main app
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }

    if (event.data && event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((name) => caches.delete(name))
                );
            })
        );
    }
});
