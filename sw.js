// Offline support: the app shell and recipe data are cached on install.
// Same-origin requests are network-first, so a new push shows up on the next visit,
// with the cached copy used when there is no connection (in the kitchen).
const V = "recipes-v3";
const SHELL = ["./", "index.html", "manifest.webmanifest", "logo.png", "favicon.png", "icon-192.png", "icon-512.png", "data/recipes.json"];
self.addEventListener("install", e => { e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const u = new URL(e.request.url);
  if (u.origin !== location.origin) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) { const c = r.clone(); caches.open(V).then(x => x.put(e.request, c)); }
    return r;
  }).catch(() => caches.match(e.request, { ignoreSearch: true }).then(r => r || caches.match("index.html"))));
});
