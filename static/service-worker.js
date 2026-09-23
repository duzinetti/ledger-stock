// Nome do cache versionado. Quando a lista de arquivos pré-cacheados
// mudar, troque o número (v1 -> v2) - isso faz o navegador tratar como
// um cache novo e descartar o antigo (ver evento 'activate' abaixo).
const CACHE_NAME = 'ledgerstock-static-v1';

// O que é "estático" de verdade nesse projeto hoje: o CSS está embutido
// em <style> no base.html e o Bootstrap/Google Fonts/Chart.js vêm de
// CDN externo (outra origem) - então só o manifest e os ícones do PWA
// são arquivos locais servidos por /static/ agora mesmo.
const PRECACHE_ASSETS = [
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-maskable-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_ASSETS))
  );
});

self.addEventListener('activate', (event) => {
  // Apaga qualquer cache de uma versão anterior (nome diferente do
  // CACHE_NAME atual) - evita acumular lixo de versões antigas do
  // service worker no navegador de quem já tinha instalado antes.
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
});

self.addEventListener('fetch', (event) => {
  // Cache-first: se o arquivo já está no cache, responde na hora sem
  // ir na rede. Senão, busca normalmente. Só afeta o que foi
  // pré-cacheado acima - páginas de produtos/vendas/etc nunca passam
  // por aqui cacheadas, então sempre mostram dado atual.
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
