import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, createClient, fetchJSON, mediaUrl, normalizeBase } from '../src/api.mjs';
import { filterStays, fold, mapUrl, minimumPrice } from '../src/model.mjs';

const id = n => n.toString(16).padStart(24, '0');
const poi = (n, name = 'Stay ' + n) => ({ id: id(n), name, address: 'Đà Lạt', images: [], menu_items: [] });
const json = (data, etag) => new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json', ...(etag ? { etag } : {}) } });
const page = (items, cursor, more = false, removed = [], mode = 'full') => ({ items, sync_cursor: cursor, has_more: more, removed_poi_ids: removed, mode, as_of: '2026-10-22T00:00:00Z' });

test('API base and media reject injected URLs, credentials and path traversal', () => {
  assert.equal(normalizeBase(' https://example.com/api/ '), 'https://example.com/api');
  assert.equal(normalizeBase('/api/'), '/api');
  for (const value of ['javascript:alert(1)','//evil.test','https://u:p@example.com','/api?q=1','/api\\evil']) assert.throws(() => normalizeBase(value));
  assert.equal(mediaUrl('/media/' + id(1), '/api'), '/api/media/' + id(1));
  for (const value of ['javascript:alert(1)','https://other.test/a.jpg','/media/../secret','/media/' + id(1) + '?token=secret']) assert.equal(mediaUrl(value), null);
});

test('full sync follows every signed page and never returns only the first page', async () => {
  let count = 0;
  const client = createClient('https://api.example', async (url, options) => {
    const q = new URL(url).searchParams;
    assert.equal(q.get('language'),'vi'); assert.equal(q.get('limit'),'100'); assert.equal(options.credentials, 'omit');
    assert.equal(q.get('cursor'), count ? 'page-' + count : null);
    const start = count++ * 100;
    return json(page(Array.from({ length: count === 3 ? 51 : 100 }, (_, n) => poi(start + n + 1)), count < 3 ? 'page-' + count : 'checkpoint', count < 3));
  });
  assert.equal((await client.loadAll('vi')).items.length, 251); assert.equal(count,3);
});

test('delta applies edits and tombstones, and stable ETag 304 preserves the merged dataset', async () => {
  let count = 0;
  const client = createClient('https://api.example', async (url, options) => {
    count++;
    if (count === 1) return json(page([poi(1),poi(2)],'c1'),'full-tag');
    if (count === 2) { assert.equal(new URL(url).searchParams.get('cursor'),'c1'); return json(page([poi(2,'Updated')],'c2',false,[id(1)],'delta'),'changed-tag'); }
    if (count === 3) return json(page([],'c2',false,[],'delta'),'stable-tag');
    assert.equal(options.headers['If-None-Match'],'stable-tag');
    return new Response(null, { status:304, headers:{etag:'stable-tag'} });
  });
  await client.loadAll();
  assert.deepEqual((await client.loadAll()).items.map(row => row.name),['Updated']);
  await client.loadAll(); const result = await client.loadAll();
  assert.equal(result.unchanged,true); assert.deepEqual(result.items.map(row => row.id),[id(2)]);
});

test('failed delta continuation does not corrupt the previous checkpoint or cache', async () => {
  let count=0;
  const client = createClient('https://api.example',async url => {
    count++;
    if(count===1) return json(page([poi(1)],'c1'));
    if(count===2) return json(page([poi(2)],'p2',true,[],'delta'));
    if(count===3) return new Response('',{status:503});
    assert.equal(new URL(url).searchParams.get('cursor'),'c1');
    return json(page([],'c1',false,[],'delta'));
  });
  await client.loadAll(); await assert.rejects(client.loadAll(),error=>error.status===503);
  assert.deepEqual((await client.loadAll()).items.map(row=>row.id),[id(1)]);
});

test('dataset reset gets one full sync and removes obsolete cached properties', async () => {
  let count=0;
  const client=createClient('https://api.example',async url=>{
    count++;
    if(count===1) return json(page([poi(1)],'old'));
    if(count===2) return new Response('',{status:409});
    assert.equal(new URL(url).searchParams.has('cursor'),false);
    return json(page([poi(2)],'new'));
  });
  await client.loadAll(); assert.deepEqual((await client.loadAll()).items.map(row=>row.id),[id(2)]);
});

test('bad cursor retry is bounded to one fresh attempt',async()=>{
  let calls=0;
  const client=createClient('/api',async()=>{ calls++; return new Response('',{status:400}); });
  await assert.rejects(client.loadAll()); assert.equal(calls,2);
});

test('translation caches are independent and preserve language parameters',async()=>{
  const calls=[];
  const client=createClient('https://api.example',async url=>{const q=new URL(url).searchParams;calls.push(q);return json(page([poi(1,q.get('language'))],q.get('language')+'-c'));});
  assert.equal((await client.loadAll('vi')).items[0].name,'vi');
  assert.equal((await client.loadAll('en')).items[0].name,'en');
  await client.loadAll('vi'); assert.equal(calls[2].get('cursor'),'vi-c');
});

test('HTML catch-all pages cannot be mistaken for a connected API',async()=>{
  await assert.rejects(fetchJSON('/api/poi/load-all',{fetcher:async()=>new Response('<html>index</html>',{headers:{'content-type':'text/html'}})}),error=>error.status===502);
});

test('request timeout aborts a hanging upstream',async()=>{
  await assert.rejects(fetchJSON('/api/health',{timeout:5,fetcher:(_url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(signal.reason)))}),error=>error.name==='TimeoutError');
});

test('abort propagates without retrying or returning stale fallback data',async()=>{
  const controller=new AbortController(); let calls=0;
  const client=createClient('/api',async (_url,{signal})=>{calls++;controller.abort(); if(signal.aborted) throw new DOMException('Aborted','AbortError');});
  await assert.rejects(client.loadAll('vi',{signal:controller.signal}),error=>error.name==='AbortError'); assert.equal(calls,1);
});

test('nearby uses the actual API coordinate, meter radius and language contract',async()=>{
  const client=createClient('https://api.example',async(url,options)=>{
    const u=new URL(url); assert.equal(u.pathname,'/poi/nearby'); assert.equal(u.searchParams.get('latitude'),'0'); assert.equal(u.searchParams.get('longitude'),'106.7'); assert.equal(u.searchParams.get('radius_m'),'10000'); assert.equal(u.searchParams.get('language'),'ja'); assert.equal(options.credentials,'omit'); return json({items:[poi(1)]});
  });
  assert.equal((await client.nearby(0,106.7,10000,'ja')).items.length,1);
});

test('unknown detail IDs and invalid response schemas fail explicitly',async()=>{
  const client=createClient('/api',async()=>json({items:[{id:'fake'}],removed_poi_ids:[],sync_cursor:'c',has_more:false}));
  await assert.rejects(client.detail('not-an-id','vi'),error=>error.status===404);
  await assert.rejects(client.loadAll(),error=>error.status===502);
});

test('search matches Vietnamese without accents and prices use available VND rooms only',()=>{
  const rows=[{...poi(1,'Nhà Của Mây'),category:'homestay',menu_items:[{kind:'room_type',price:'450000.00',currency:'VND',is_available:true},{kind:'service',price:'10000',currency:'VND'},{kind:'room_type',price:'1',currency:'USD'},{kind:'room_type',price:'100',currency:'VND',is_available:false}]},{...poi(2),category:'hotel'}];
  assert.equal(fold('Đà Lạt'),'da lat'); assert.equal(minimumPrice(rows[0]),450000);assert.equal(minimumPrice(rows[1]),null);
  assert.deepEqual(filterStays(rows,{search:'nha cua may'}).map(row=>row.id),[id(1)]);
  assert.deepEqual(filterStays(rows,{budget:'low'}).map(row=>row.id),[id(1)]);
  assert.deepEqual(filterStays(rows,{savedOnly:true,favorites:[id(2)]}).map(row=>row.id),[id(2)]);
  assert.deepEqual(filterStays(rows,{sort:'price-down'}).map(row=>row.id),[id(1),id(2)]);
});

test('map links use valid coordinate destinations',()=>{
  assert.equal(mapUrl({latitude:NaN,longitude:10}),null);assert.equal(mapUrl({latitude:91,longitude:10}),null);
  assert.equal(mapUrl({latitude:10,longitude:106},true),'https://www.google.com/maps/dir/?api=1&destination=10,106');
});
