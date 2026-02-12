const CACHE_NAME = 'portfolio-v1';
const STATIC_URLS = ['/'];

self.addEventListener('install', e => {
    e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(STATIC_URLS)));
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(caches.keys().then(keys =>
        Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ));
    self.clients.claim();
});

self.addEventListener('fetch', e => {
    if (e.request.url.includes('/api/')) return;
    e.respondWith(
        fetch(e.request).then(r => {
            const clone = r.clone();
            caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
            return r;
        }).catch(() => caches.match(e.request))
    );
});
