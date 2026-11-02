import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import os from 'node:os';
import {execFileSync} from 'node:child_process';
import app from '../src/index.js';
const base=path.dirname(fileURLToPath(import.meta.url)), root=path.resolve(base,'..');
const dbpath=path.join(fs.mkdtempSync(path.join(os.tmpdir(),'turagent-d1-')),'test.sqlite3');
const python=process.platform==='win32'?'python':'python3';
function statement(sql,args=[]){let raw;try{raw=execFileSync(python,[path.join(base,'d1_bridge.py'),dbpath,JSON.stringify({sql,args})],{encoding:'utf8',timeout:15000});}catch(e){console.log('DB ERROR',e.stdout?.slice(0,1500),e.stderr?.slice(0,1500),sql);throw e}const result=JSON.parse(raw);if(result.error)throw Error(result.error);return result}
function db(){
  return {
    prepare(sql){return {bind(...args){return {
      async all(){return {results:statement(sql,args).rows}},
      async first(){return statement(sql,args).rows[0]||null},
      async run(){return {success:true,...statement(sql,args)}}
    }}}},
    async batch(queries){for(const q of queries)await q.run()}
  }
}
const dbObj=db();
for(const file of ['0001_initial.sql','0002_seed.sql']){
  // sqlite executescript is more reliable for multi-statement migrations.
  execFileSync(python,['-c',`import sqlite3,sys; db=sqlite3.connect(sys.argv[1]);db.executescript(open(sys.argv[2],encoding='utf-8').read());db.close()`,dbpath,path.join(root,'migrations',file)]);
}
const env={DB:dbObj,ASSETS:{fetch:async()=>new Response('ok')},CURRENCY_RATE:'12800',GEMINI_MODEL:'gemini-3.5-flash-lite'};
let cookies='',csrf='';
async function send(url,data,method='POST',headers={}){
 const body=method==='GET'?undefined:JSON.stringify(data||{});
 const req=new Request('https://example.workers.dev'+url,{method,headers:{...(body?{'Content-Type':'application/json','X-Turagent-Request':'1'}:{}),...(cookies?{Cookie:cookies}:{}),...(csrf?{'X-CSRF-Token':csrf}:{}),...headers},body});
 const r=await app.fetch(req,env);const set=r.headers.get('set-cookie');if(set)cookies=set.split(';')[0];const json=await r.json().catch(()=>({}));return {status:r.status,json,response:r};
}
test('Public catalog, configuration and default media fallback',async()=>{
 const catalog=await send('/api/catalog',null,'GET');assert.equal(catalog.status,200);assert.equal(catalog.json.tours.length,9);
 const posts=await send('/api/posts',null,'GET');assert.equal(posts.json.posts.length,4);
 const health=await send('/api/health',null,'GET');assert.equal(health.json.db,'d1');
 const ai=await send('/api/ai/chat',{message:'Salom'});assert.equal(ai.status,503);
});
test('Registration, secured profile, favorites, bookings, demo payment and logout',async()=>{
 const registered=await send('/api/register',{name:'Sample User',email:'sample@example.net',password:'a-strong-example-password'});
 assert.equal(registered.status,201,JSON.stringify(registered.json));csrf=registered.json.csrf;assert.ok(csrf);assert.ok(cookies.startsWith('ta_session='));
 const session=await send('/api/session',null,'GET');assert.equal(session.json.user.email,'sample@example.net');
 const bad=await send('/api/favorites',{tourId:'dubai'},'POST',{'X-CSRF-Token':'bad'});assert.equal(bad.status,403);
 const fav=await send('/api/favorites',{tourId:'dubai'});assert.equal(fav.status,200);assert.equal(fav.json.favorite,true);
 const date=new Date(Date.now()+DAY*1000).toISOString().slice(0,10);
 const booked=await send('/api/bookings',{tourId:'dubai',date,adults:2,children:0,name:'Sample User',email:'sample@example.net',phone:'+998901234567',method:'click',agree:true});assert.equal(booked.status,201,JSON.stringify(booked.json));
 assert.equal(booked.json.total,1700);
 const paid=await send('/api/payment/simulate',{ref:booked.json.ref,outcome:'success',method:'click'});assert.equal(paid.json.paymentStatus,'demo_paid');
 const double=await send('/api/payment/simulate',{ref:booked.json.ref,outcome:'success',method:'click'});assert.equal(double.status,409);
 const after=await send('/api/session',null,'GET');assert.equal(after.json.bookings[0].paymentStatus,'demo_paid');
 const cancel=await send('/api/bookings/cancel',{ref:booked.json.ref});assert.equal(cancel.status,200);
 const out=await send('/api/logout',{});assert.equal(out.status,200);csrf='';
 const empty=await send('/api/session',null,'GET');assert.equal(empty.json.user,null);
});
const DAY=86400;
test('Guest checkout, token isolation and contact/newsletter',async()=>{
 const date=new Date(Date.now()+DAY*1000).toISOString().slice(0,10);
 const booking=await send('/api/bookings',{tourId:'dubai',date,adults:1,children:0,name:'Guest Traveler',email:'guest@example.net',phone:'998991234567',method:'card',agree:true});assert.equal(booking.status,201);
 assert.ok(booking.json.guestToken);
 const denied=await send('/api/payment/simulate',{ref:booking.json.ref,method:'card',outcome:'success',guestToken:'bad'});assert.equal(denied.status,403);
 const paid=await send('/api/payment/simulate',{ref:booking.json.ref,method:'card',outcome:'declined',guestToken:booking.json.guestToken});assert.equal(paid.json.paymentStatus,'demo_declined');
 const contact=await send('/api/inquiries',{kind:'contact',name:'Test User',email:'test@example.net',message:'Hello tour agency. Please contact me!'});assert.equal(contact.status,201);
 const newsletter=await send('/api/newsletter',{email:'test@example.net'});assert.equal(newsletter.status,200);
});
test('Admin bootstrap and safe tour editing',async()=>{
 env.ADMIN_SETUP_TOKEN='setup-token-do-not-share';
 const setup=await send('/api/admin/bootstrap',{token:env.ADMIN_SETUP_TOKEN,name:'Administrator',email:'admin@example.net',password:'very-strong-admin-password'});
 assert.equal(setup.status,201,JSON.stringify(setup.json));
 const repeat=await send('/api/admin/bootstrap',{token:env.ADMIN_SETUP_TOKEN,name:'Administrator',email:'admin2@example.net',password:'very-strong-admin-password'});assert.equal(repeat.status,409);
 const logged=await send('/api/login',{email:'admin@example.net',password:'very-strong-admin-password'});assert.equal(logged.status,200,JSON.stringify(logged.json));csrf=logged.json.csrf;
 const overview=await send('/api/admin/overview',null,'GET');assert.equal(overview.status,200);assert.ok(overview.json.tours.length>=9);
 const source=overview.json.tours.find(x=>x.id==='dubai');
 const save=await send('/api/admin/tours',{...source,price:999});assert.equal(save.status,200);
 const catalog=await send('/api/catalog',null,'GET');assert.equal(catalog.json.tours.find(x=>x.id==='dubai').price,999);
 const toggle=await send('/api/admin/tours/toggle',{id:'dubai',active:false});assert.equal(toggle.status,200);
 const inactive=await send('/api/catalog',null,'GET');assert.ok(!inactive.json.tours.some(x=>x.id==='dubai'));
 await send('/api/logout',{});csrf='';
});
test('AI streaming response produces usable SSE deltas with mocked provider',async()=>{
 env.GEMINI_API_KEY='FAKE_TEST_ONLY';
 const original=globalThis.fetch;
 globalThis.fetch=async(url)=>{
  assert.match(url.toString(),/streamGenerateContent/);
  return new Response('data: '+JSON.stringify({candidates:[{content:{parts:[{text:'Assalomu '}]}}]})+'\n\n'+'data: '+JSON.stringify({candidates:[{content:{parts:[{text:'alaykum!'}]}}]})+'\n\n',{status:200,headers:{'Content-Type':'text/event-stream'}})
 };
 try{
  const req=new Request('https://example.workers.dev/api/ai/stream',{method:'POST',headers:{'Content-Type':'application/json','X-Turagent-Request':'1'},body:JSON.stringify({message:'TurAgent AI nima?'})});
  const resp=await app.fetch(req,env);assert.equal(resp.status,200);const txt=await resp.text();assert.match(txt,/Assalomu/);assert.match(txt,/alaykum!/);assert.match(txt,/"done":true/);
 }finally{globalThis.fetch=original}
});
