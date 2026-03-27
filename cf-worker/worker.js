export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
      }});
    }
    const url = new URL(request.url);
    const q   = url.searchParams.get('q') || '';
    if (!q) return json({ error: 'Missing q' }, 400);
    try {
      const creds = btoa(`${env.EBAY_APP_ID}:${env.EBAY_CERT_ID}`);
      const tok = await fetch('https://api.ebay.com/identity/v1/oauth2/token', {
        method: 'POST',
        headers: { 'Authorization': `Basic ${creds}`, 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope',
      }).then(r => r.json());
      if (!tok.access_token) return json({ error: 'Token failed', detail: tok }, 500);
      const data = await fetch(
        `https://api.ebay.com/buy/browse/v1/item_summary/search?q=${encodeURIComponent(q)}&limit=20`,
        { headers: { 'Authorization': `Bearer ${tok.access_token}`, 'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US' }}
      ).then(r => r.json());
      const items = (data.itemSummaries || []).map(i => ({
        title: i.title, price: parseFloat(i.price?.value || 0), url: i.itemWebUrl,
        type: i.buyingOptions?.includes('AUCTION') ? 'AUCTION' : 'BIN',
        best_offer: i.buyingOptions?.includes('BEST_OFFER') || false,
      }));
      return json({ items });
    } catch(e) { return json({ error: e.message }, 500); }
  }
};
function json(d, s=200) {
  return new Response(JSON.stringify(d), { status: s,
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }});
}
