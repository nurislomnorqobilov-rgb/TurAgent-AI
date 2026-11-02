/**
 * TurAgent AI Cloudflare Workers + D1 backend.
 * Public API mirrors TurAgent AI v5.2 to preserve the existing frontend.
 * Payments are SIMULATION ONLY. No real bank or card processing.
 */
import seed from './seed.json' with { type: 'json' };

const encoder = new TextEncoder();
const LIMIT_BODY = 20_000;
const DAY = 86_400;
const COOKIE = 'ta_session';
// The Cloudflare Workers WebCrypto PBKDF2 implementation rejects >100,000 iterations.
// Use the same value for signup, login verification, admin setup and password reset.
const PASSWORD_PBKDF2_ITERATIONS = 100_000;
const COMMON_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Frame-Options': 'DENY',
  'Cache-Control': 'no-store'
};
class ApiError extends Error {
  constructor(message, status=400){ super(message); this.status=status; }
}
const fail = (condition, message, status=400) => { if(!condition) throw new ApiError(message,status); };
const clean=(value,max=120)=>String(value??'').trim().slice(0,max);
const now=()=>new Date().toISOString();
const stamp=()=>Math.floor(Date.now()/1000);
const validEmail=(v)=>v.length<255&&/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
const random=(bytes=32)=>{const array=crypto.getRandomValues(new Uint8Array(bytes));return b64url(array)};
const b64url=bytes=>btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'');
const b64decode=s=>Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')),x=>x.charCodeAt(0));
async function sha(text){const bytes=await crypto.subtle.digest('SHA-256',encoder.encode(text));return b64url(new Uint8Array(bytes));}
async function passwordHash(password,salt=random(16)) {
  const key=await crypto.subtle.importKey('raw',encoder.encode(password),'PBKDF2',false,['deriveBits']);
  const bits=await crypto.subtle.deriveBits({name:'PBKDF2',hash:'SHA-256',salt:b64decode(salt),iterations:PASSWORD_PBKDF2_ITERATIONS},key,256);
  return {salt,hash:b64url(new Uint8Array(bits))};
}
function timingEq(a,b){const x=encoder.encode(String(a)),y=encoder.encode(String(b));let difference=x.length^y.length;for(let i=0;i<Math.max(x.length,y.length);i++)difference|=(x[i]||0)^(y[i]||0);return difference===0;}
async function verifyPassword(password,salt,hash){if(!salt||!hash)return false;try{return timingEq((await passwordHash(password,salt)).hash,hash)}catch{return false}}
const query=(db,sql,...params)=>db.prepare(sql).bind(...params);
async function one(db,sql,...args){return query(db,sql,...args).first()}
async function all(db,sql,...args){return (await query(db,sql,...args).all()).results||[]}
async function run(db,sql,...args){return query(db,sql,...args).run()}
function reply(body,status=200,headers={}){return new Response(JSON.stringify(body),{status,headers:{...COMMON_HEADERS,'Content-Type':'application/json; charset=utf-8',...headers}})}
function redirect(location,cookies=[]){const h=new Headers({...COMMON_HEADERS,Location:location});for(const item of cookies)h.append('Set-Cookie',item);return new Response(null,{status:302,headers:h})}
function setCookie(name,value,age=600,path='/'){
  return `${name}=${encodeURIComponent(value)}; Path=${path}; HttpOnly; SameSite=Lax; Secure; Max-Age=${age}`;
}
function cookie(request,name){const s=request.headers.get('Cookie')||'';const match=s.match(new RegExp('(?:^|;\\s*)'+name+'=([^;]*)'));try{return match?decodeURIComponent(match[1]):''}catch{return ''}}
async function body(request){
  const length=Number(request.headers.get('content-length'));
  if(length>LIMIT_BODY)throw new ApiError('Request too large',413);
  fail(request.headers.get('content-type')?.toLowerCase().startsWith('application/json'),'JSON required',415);
  const text=await request.text();fail(text.length>0&&text.length<=LIMIT_BODY,'Invalid body size',413);
  try{const result=JSON.parse(text);fail(result&&typeof result==='object'&&!Array.isArray(result),'JSON object required');return result}
  catch(e){if(e instanceof ApiError)throw e;throw new ApiError('Invalid JSON')}
}
function requestOrigin(request){return new URL(request.url).origin}
function verifyOrigin(request,user,csrf){
  const origin=request.headers.get('Origin');if(origin)fail(origin===requestOrigin(request),'Origin rejected',403);
  if(user){fail(csrf&&timingEq(request.headers.get('X-CSRF-Token')||'',csrf),'Invalid CSRF token',403)}
  else fail(request.headers.get('X-Turagent-Request')==='1','Client header required',403);
}
async function actor(db,request){const token=cookie(request,COOKIE);if(!token)return {user:null,csrf:null,token:''};
  const row=await one(db,'SELECT s.csrf,s.expires,u.id,u.name,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?',await sha(token));
  if(!row||row.expires<stamp())return {user:null,csrf:null,token:''};
  return {user:{id:row.id,name:row.name,email:row.email,role:row.role},csrf:row.csrf,token};
}
async function newSession(db,uid){const token=random(),csrf=random(24);await run(db,'INSERT INTO sessions(token_hash,user_id,csrf,expires) VALUES(?,?,?,?)',await sha(token),uid,csrf,stamp()+14*DAY);return {token,csrf}}
async function throttle(db,request,path){
  const ip=(request.headers.get('CF-Connecting-IP')||'local').slice(0,90);
  const limit=/register|login|reset|ai\//.test(path)?12:65;
  const window=stamp()-stamp()%60;
  const key=await sha(ip+'|'+path+'|'+window);
  // Atomic update avoids the in-memory limits that do not work across Worker isolates.
  await run(db,'INSERT INTO rate_limits(key,window_start,hits) VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET hits=hits+1',key,window);
  const r=await one(db,'SELECT hits FROM rate_limits WHERE key=?',key);
  fail(r.hits<=limit,'Too many requests. Please try later.',429);
}
async function tour(db,id,admin=false){const r=await one(db,'SELECT data,active FROM tours WHERE id=?',id);fail(r&&(admin||r.active),'Tour not found',404);return {...JSON.parse(r.data),active:!!r.active}}
async function tours(db,admin=false){return (await all(db,admin?'SELECT data,active FROM tours ORDER BY created_at,id':'SELECT data,active FROM tours WHERE active=1 ORDER BY created_at,id')).map(r=>({...JSON.parse(r.data),active:!!r.active}))}
const bookingOutput=b=>({...b,total:b.total_usd,tripId:b.tour_id,date:b.travel_date,paymentStatus:b.payment_status});
const isAdmin=user=>fail(user?.role==='admin','Admin access required',403);
async function audit(db,user,action,target){await run(db,'INSERT INTO admin_audit(id,admin_id,action,target,at) VALUES(?,?,?,?,?)',crypto.randomUUID(),user.id,action,clean(target,100),now())}
async function sendMail(env,to,subject,text){
  if(!env.RESEND_API_KEY||!env.MAIL_FROM)return false;
  const result=await fetch('https://api.resend.com/emails',{method:'POST',headers:{Authorization:'Bearer '+env.RESEND_API_KEY,'Content-Type':'application/json'},body:JSON.stringify({from:env.MAIL_FROM,to:[to],subject,text}),signal:AbortSignal.timeout(10000)}).catch(()=>null);
  if(!result?.ok){console.warn('Email provider unavailable',result?.status||'network');return false}return true;
}
async function googleStart(request,env){
  fail(env.GOOGLE_CLIENT_ID&&env.GOOGLE_CLIENT_SECRET,'Google sign-in not configured',503);
  const state=random(32);await run(env.DB,'INSERT INTO oauth_states(state_hash,expires) VALUES(?,?)',await sha(state),stamp()+600);
  const callback=requestOrigin(request)+'/auth/google/callback';
  const params=new URLSearchParams({client_id:env.GOOGLE_CLIENT_ID,redirect_uri:callback,response_type:'code',scope:'openid email profile',state,prompt:'select_account'});
  return redirect('https://accounts.google.com/o/oauth2/v2/auth?'+params,[setCookie('ta_oauth_state',state,600,'/auth/google')]);
}
async function googleCallback(request,env){
  const url=new URL(request.url),state=url.searchParams.get('state')||'',code=url.searchParams.get('code')||'';
  fail(state&&code&&timingEq(state,cookie(request,'ta_oauth_state')),'Invalid Google OAuth state',403);
  const stateHash=await sha(state),found=await one(env.DB,'SELECT expires FROM oauth_states WHERE state_hash=?',stateHash);
  fail(found&&found.expires>stamp(),'OAuth login expired',400);
  await run(env.DB,'DELETE FROM oauth_states WHERE state_hash=?',stateHash);
  const callback=requestOrigin(request)+'/auth/google/callback';
  const tokenReq=new URLSearchParams({client_id:env.GOOGLE_CLIENT_ID,client_secret:env.GOOGLE_CLIENT_SECRET,code,grant_type:'authorization_code',redirect_uri:callback});
  let token,profile;
  try{
    const r=await fetch('https://oauth2.googleapis.com/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:tokenReq,signal:AbortSignal.timeout(10000)});
    fail(r.ok,'Google token exchange failed',502);token=await r.json();fail(token.id_token,'No Google ID token',502);
    const p=await fetch('https://oauth2.googleapis.com/tokeninfo?id_token='+encodeURIComponent(token.id_token),{signal:AbortSignal.timeout(10000)});
    fail(p.ok,'Google token validation failed',502);profile=await p.json();
  }catch(e){if(e instanceof ApiError)throw e;throw new ApiError('Google login temporarily unavailable',502)}
  fail(profile.aud===env.GOOGLE_CLIENT_ID&&['accounts.google.com','https://accounts.google.com'].includes(profile.iss)&&String(profile.email_verified)==='true','Google identity invalid',403);
  const googleSub=clean(profile.sub,200),email=clean(profile.email,255).toLowerCase(),name=clean(profile.name||email.split('@')[0],90);
  fail(googleSub&&validEmail(email),'Invalid Google profile',403);
  let user=await one(env.DB,'SELECT id FROM users WHERE google_sub=?',googleSub);
  if(!user){
    user=await one(env.DB,'SELECT id,google_sub FROM users WHERE email=?',email);
    if(user){fail(!user.google_sub||user.google_sub===googleSub,'Email linked to another Google identity',409);await run(env.DB,'UPDATE users SET google_sub=? WHERE id=?',googleSub,user.id)}
    else{user={id:crypto.randomUUID()};await run(env.DB,'INSERT INTO users(id,name,email,google_sub,created_at) VALUES(?,?,?,?,?)',user.id,name,email,googleSub,now())}
  }
  const {token:session}=await newSession(env.DB,user.id);
  return redirect(requestOrigin(request)+'/#/account',[setCookie(COOKIE,session,14*DAY),setCookie('ta_oauth_state','',0,'/auth/google')]);
}
function aiContext(items){return 'You are the official TurAgent AI travel website assistant. Only answer questions about this website, tour packages, services, bookings, account features and navigation. Prices are DEMO example values, and all payments are simulated (no real money). Never invent tour availability or real booking confirmations. Speak the same language as user, Uzbek/Russian/English. Contacts: phone 70 700 70 70; email assalomualaykum@gmail.com; Telegram @uzbekistan. Catalog:\n'+items.slice(0,40).map(x=>`${x.id}: ${x.title?.uz||x.id}, USD ${x.price}, ${x.days} days`).join('\n')}
function candidateModels(env){return [...new Set([clean(env.GEMINI_MODEL,80)||'gemini-3.5-flash-lite','gemini-3.5-flash-lite','gemini-2.5-flash'])]}
function geminiPayload(message,context){return {systemInstruction:{parts:[{text:context}]},contents:[{role:'user',parts:[{text:message}]}],generationConfig:{maxOutputTokens:1024,temperature:0.2}}}
async function googleAI(env,model,payload,stream=false){
  const url=`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:${stream?'streamGenerateContent?alt=sse':'generateContent'}`;
  return fetch(url,{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':env.GEMINI_API_KEY},body:JSON.stringify(payload),signal:AbortSignal.timeout(18000)});
}
async function tryGemini(env,payload,stream){
  let error='AI_PROVIDER_TEMPORARY',code=503;
  for(const model of candidateModels(env)){
    try{
      const response=await googleAI(env,model,payload,stream);
      if(response.ok)return {response,model};
      const status=response.status;console.warn('Gemini response',status,'model',model);
      if(status===429){code=429;error='AI_QUOTA_EXCEEDED';continue}
      if(status===401||status===403)throw new ApiError('AI_KEY_OR_PERMISSION',503);
      if(status===400||status===404){error='AI_MODEL_UNAVAILABLE';continue}
      if(status>=500){error='AI_PROVIDER_TEMPORARY';continue}
      throw new ApiError('AI_REQUEST_FAILED',502);
    }catch(e){if(e instanceof ApiError)throw e;console.warn('Gemini network issue',e.name);error='AI_NETWORK_ERROR'}
  }
  throw new ApiError(error,code);
}
function contentParts(item){return (item.candidates||[]).flatMap(c=>c.content?.parts||[]).map(x=>x.text||'').join('')}
function streamAiResponse(upstream){
  const reader=upstream.body.getReader(),decoder=new TextDecoder();
  const readable=new ReadableStream({async start(controller){
    const send=(data)=>controller.enqueue(encoder.encode('data: '+JSON.stringify(data)+'\n\n'));
    let buf='',got=false;
    try{
      while(true){const {done,value}=await reader.read();if(done)break;buf+=decoder.decode(value,{stream:true}).replace(/\r\n/g,'\n');const packets=buf.split('\n\n');buf=packets.pop()||'';
        for(const packet of packets){for(const line of packet.split('\n')){if(!line.startsWith('data:'))continue;const raw=line.slice(5).trim();if(!raw||raw==='[DONE]')continue;
          try{const delta=contentParts(JSON.parse(raw));if(delta){send({delta});got=true}}catch{}
        }}
      }
      if(!got)send({error:'AI_EMPTY_RESPONSE'});
      send({done:true});
    }catch(e){console.warn('Gemini stream terminated',e.name);send({error:'AI_NETWORK_ERROR'});send({done:true})}
    finally{controller.close();reader.releaseLock()}
  }});
  return new Response(readable,{headers:{...COMMON_HEADERS,'Content-Type':'text/event-stream; charset=utf-8','Cache-Control':'no-cache, no-transform','X-Accel-Buffering':'no'}})
}

async function api(request,env,path){
  const db=env.DB,method=request.method,{user,csrf,token}=await actor(db,request);
  if(method==='GET'){
    if(path==='/api/health')return reply({ok:true,db:'d1',version:'6.0-cloudflare'});
    if(path==='/api/config')return reply({googleEnabled:!!(env.GOOGLE_CLIENT_ID&&env.GOOGLE_CLIENT_SECRET),aiEnabled:!!env.GEMINI_API_KEY,payments:'simulation',currencyRate:Number(env.CURRENCY_RATE)||12800});
    if(path==='/api/catalog')return reply({tours:await tours(db),destinations:seed.destinations});
    if(path==='/api/posts')return reply({posts:(await all(db,'SELECT data FROM posts WHERE active=1')).map(x=>JSON.parse(x.data))});
    if(path==='/api/session'){
      const bookings=user?await all(db,'SELECT * FROM bookings WHERE user_id=? ORDER BY created_at DESC',user.id):[];
      const favorites=user?(await all(db,'SELECT tour_id FROM favorites WHERE user_id=?',user.id)).map(x=>x.tour_id):[];
      return reply({user,csrf,bookings:bookings.map(bookingOutput),favorites});
    }
    if(path==='/api/admin/overview'){
      isAdmin(user);
      const [u,b,i,r,t,p]=await Promise.all([
        one(db,'SELECT COUNT(*) AS n FROM users'),one(db,'SELECT COUNT(*) AS n FROM bookings'),one(db,'SELECT COUNT(*) AS n FROM inquiries'),
        one(db,"SELECT COALESCE(SUM(total_usd),0) AS n FROM bookings WHERE payment_status='demo_paid'"),tours(db,true),all(db,'SELECT data,active FROM posts')
      ]);
      return reply({users:u.n,bookings:b.n,inquiries:i.n,revenueDemo:r.n,tours:t,posts:p.map(x=>({...JSON.parse(x.data),active:!!x.active}))});
    }
    if(path==='/api/admin/bookings'){isAdmin(user);return reply({bookings:(await all(db,'SELECT * FROM bookings ORDER BY created_at DESC LIMIT 300')).map(bookingOutput)})}
    if(path==='/api/admin/inquiries'){isAdmin(user);return reply({inquiries:await all(db,'SELECT * FROM inquiries ORDER BY created_at DESC LIMIT 300')})}
    if(path==='/api/admin/users'){isAdmin(user);return reply({users:await all(db,'SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC LIMIT 300')})}
    throw new ApiError('Not found',404);
  }
  fail(['POST','PATCH','DELETE'].includes(method),'Method not allowed',405);
  verifyOrigin(request,user,csrf);
  const data=method==='DELETE'?{}:await body(request);
  await throttle(db,request,path);
  if(path==='/api/register'){
    const name=clean(data.name,90),email=clean(data.email,255).toLowerCase(),password=String(data.password||'');
    fail(name.length>=2&&validEmail(email)&&password.length>=10&&password.length<=128,'Check name, email and password (10+ characters)');
    const exists=await one(db,'SELECT id FROM users WHERE email=?',email);fail(!exists,'Email already registered',409);
    const {salt,hash}=await passwordHash(password),uid=crypto.randomUUID();
    await run(db,'INSERT INTO users(id,name,email,password_salt,password_hash,created_at) VALUES(?,?,?,?,?,?)',uid,name,email,salt,hash,now());
    const session=await newSession(db,uid);
    return reply({user:{id:uid,name,email,role:'customer'},csrf:session.csrf},201,{'Set-Cookie':setCookie(COOKIE,session.token,14*DAY)});
  }
  if(path==='/api/login'){
    const email=clean(data.email,255).toLowerCase(),password=String(data.password||'');
    const found=await one(db,'SELECT * FROM users WHERE email=?',email);
    fail(found&&await verifyPassword(password,found.password_salt,found.password_hash),'Invalid email or password',401);
    const session=await newSession(db,found.id);
    return reply({user:{id:found.id,name:found.name,email:found.email,role:found.role},csrf:session.csrf},200,{'Set-Cookie':setCookie(COOKIE,session.token,14*DAY)});
  }
  if(path==='/api/logout'){
    if(token)await run(db,'DELETE FROM sessions WHERE token_hash=?',await sha(token));
    return reply({ok:true},200,{'Set-Cookie':setCookie(COOKIE,'',0)});
  }
  if(path==='/api/reset/request'){
    const email=clean(data.email,255).toLowerCase();fail(validEmail(email),'Invalid email');
    const found=await one(db,'SELECT id FROM users WHERE email=?',email);
    const enabled=!!(env.RESEND_API_KEY&&env.MAIL_FROM);
    if(found&&enabled){const resetToken=random();await run(db,'INSERT INTO password_resets(token_hash,user_id,expires) VALUES(?,?,?)',await sha(resetToken),found.id,stamp()+1800);
      await sendMail(env,email,'TurAgent AI — Password reset','Reset your password (valid 30 minutes): '+requestOrigin(request)+'/#/reset?token='+resetToken);
    }
    return reply({ok:true,mailConfigured:enabled});
  }
  if(path==='/api/reset/complete'){
    const resetToken=clean(data.token,300),password=String(data.password||'');fail(password.length>=10&&password.length<=128,'Password must be 10-128 characters');
    const hash=await sha(resetToken),found=await one(db,'SELECT user_id,expires FROM password_resets WHERE token_hash=?',hash);
    fail(found&&found.expires>stamp(),'Invalid or expired reset link');
    const p=await passwordHash(password);
    await db.batch([query(db,'UPDATE users SET password_salt=?,password_hash=? WHERE id=?',p.salt,p.hash,found.user_id),query(db,'DELETE FROM password_resets WHERE user_id=?',found.user_id),query(db,'DELETE FROM sessions WHERE user_id=?',found.user_id)]);
    return reply({ok:true});
  }
  if(path==='/api/profile'){
    fail(user,'Log in to continue',401);const name=clean(data.name,90);fail(name.length>=2,'Invalid name');
    await run(db,'UPDATE users SET name=? WHERE id=?',name,user.id);return reply({ok:true});
  }
  if(path==='/api/favorites'){
    fail(user,'Log in to save favorites',401);const id=clean(data.tourId,100);await tour(db,id);
    const favorite=await one(db,'SELECT user_id FROM favorites WHERE user_id=? AND tour_id=?',user.id,id);
    if(favorite)await run(db,'DELETE FROM favorites WHERE user_id=? AND tour_id=?',user.id,id);
    else await run(db,'INSERT INTO favorites(user_id,tour_id) VALUES(?,?)',user.id,id);
    return reply({favorite:!favorite});
  }
  if(path==='/api/bookings'){
    const selected=await tour(db,clean(data.tourId,100));const date=clean(data.date,16);
    fail(/^\d{4}-\d{2}-\d{2}$/.test(date)&&!Number.isNaN(Date.parse(date))&&date>=now().slice(0,10),'Choose a valid future date');
    const adults=Number(data.adults),children=Number(data.children||0);
    fail(Number.isInteger(adults)&&adults>=1&&adults<=12&&Number.isInteger(children)&&children>=0&&children<=10&&adults+children<=16,'Invalid number of travelers');
    const name=clean(data.name||user?.name,90),email=clean(data.email||user?.email,255).toLowerCase(),phone=clean(data.phone,40),method=clean(data.method,20);
    fail(name.length>=2&&validEmail(email)&&phone.length>=7,'Provide name, email and phone');
    fail(data.agree===true,'Please accept booking conditions');fail(['card','payme','click'].includes(method),'Invalid payment method');
    const total=Number(selected.price)*adults+Math.round(Number(selected.price)*0.65)*children;
    const id=crypto.randomUUID(),ref='TA-'+random(6).slice(0,10).toUpperCase(),guestToken=user?'':random();
    await run(db,'INSERT INTO bookings(id,ref,user_id,tour_id,name,email,phone,travel_date,adults,children,note,total_usd,method,status,payment_status,created_at,guest_payment_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',id,ref,user?.id||null,selected.id,name,email,phone,date,adults,children,clean(data.note,700),total,method,'pending','unpaid',now(),guestToken?await sha(guestToken):null);
    if(env.NOTIFY_EMAIL&&env.RESEND_API_KEY&&env.MAIL_FROM){ /* notification is best-effort; booking never depends on mail */
      await sendMail(env,env.NOTIFY_EMAIL,'TurAgent AI booking '+ref,`New booking ${ref} / ${name} / ${email} / USD ${total}`);
    }
    return reply({ref,id,total,paymentStatus:'unpaid',guestToken},201);
  }
  if(path==='/api/payment/simulate'){
    const ref=clean(data.ref,50),outcome=clean(data.outcome,20),method=clean(data.method||'card',20);
    fail(['success','declined'].includes(outcome),'Invalid simulation result');fail(['card','payme','click'].includes(method),'Invalid payment method');
    const booking=await one(db,'SELECT * FROM bookings WHERE ref=?',ref);fail(booking,'Booking not found',404);
    const guest=!!(!booking.user_id&&data.guestToken&&booking.guest_payment_hash&&timingEq(await sha(String(data.guestToken)),booking.guest_payment_hash));
    fail(guest||user&&(booking.user_id===user.id||user.role==='admin'),'Not your booking',403);
    fail(['unpaid','demo_declined'].includes(booking.payment_status),'Payment simulation already completed',409);
    const status=outcome==='success'?'demo_paid':'demo_declined';
    await run(db,'UPDATE bookings SET payment_status=?,method=? WHERE id=? AND payment_status IN (\'unpaid\',\'demo_declined\')',status,method,booking.id);
    return reply({ok:true,paymentStatus:status,notice:'SIMULATION ONLY. No money was transferred.'});
  }
  if(path==='/api/bookings/cancel'){
    fail(user,'Log in first',401);const booking=await one(db,'SELECT id,status FROM bookings WHERE ref=? AND user_id=?',clean(data.ref,50),user.id);
    fail(booking,'Booking not found',404);fail(booking.status==='pending','Booking can no longer be cancelled',409);
    await run(db,"UPDATE bookings SET status='cancelled' WHERE id=?",booking.id);return reply({ok:true});
  }
  if(path==='/api/inquiries'){
    const kind=clean(data.kind,40),name=clean(data.name,90),email=clean(data.email,255).toLowerCase(),message=clean(data.message,1200),service=clean(data.service,100);
    fail(['contact','service'].includes(kind),'Invalid message type');fail(name.length>=2&&validEmail(email)&&message.length>=8,'Please fill out all fields');
    await run(db,'INSERT INTO inquiries(id,kind,name,email,message,service,created_at) VALUES(?,?,?,?,?,?,?)',crypto.randomUUID(),kind,name,email,message,service,now());
    const sent=env.NOTIFY_EMAIL?await sendMail(env,env.NOTIFY_EMAIL,'TurAgent AI inquiry',`${kind} / ${service}\n${name} (${email})\n${message}`):false;
    return reply({ok:true,emailSent:sent},201);
  }
  if(path==='/api/newsletter'){
    const email=clean(data.email,255).toLowerCase();fail(validEmail(email),'Invalid email');
    await run(db,'INSERT OR IGNORE INTO newsletter(email,created_at) VALUES(?,?)',email,now());return reply({ok:true});
  }
  if(path==='/api/ai/chat'||path==='/api/ai/stream'){
    fail(env.GEMINI_API_KEY,'AI is not configured',503);fail(typeof data.message==='string','Invalid message');const message=clean(data.message,1200);
    fail(message.length>=2,'Message is too short');
    const context=aiContext(await tours(db)),payload=geminiPayload(message,context);
    const stream=path.endsWith('/stream');const {response,model}=await tryGemini(env,payload,stream);
    if(stream)return streamAiResponse(response);
    const result=await response.json();const answer=contentParts(result).trim();fail(answer,'AI_EMPTY_RESPONSE',502);
    return reply({answer:answer.slice(0,3800),model});
  }
  if(path==='/api/admin/bootstrap'){
    fail(env.ADMIN_SETUP_TOKEN,'Admin setup disabled',403);
    fail(timingEq(clean(data.token,512),env.ADMIN_SETUP_TOKEN),'Invalid admin setup token',403);
    fail(!(await one(db,"SELECT id FROM users WHERE role='admin' LIMIT 1")),'Administrator already exists',409);
    const name=clean(data.name,90),email=clean(data.email,255).toLowerCase(),password=String(data.password||'');
    fail(name.length>=2&&validEmail(email)&&password.length>=12,'Name, email, password (12+ characters) required');
    fail(!(await one(db,'SELECT id FROM users WHERE email=?',email)),'Email already registered',409);
    const p=await passwordHash(password),id=crypto.randomUUID();
    await run(db,'INSERT INTO users(id,name,email,password_salt,password_hash,role,created_at) VALUES(?,?,?,?,?,?,?)',id,name,email,p.salt,p.hash,'admin',now());
    return reply({ok:true},201);
  }
  if(path.startsWith('/api/admin/')){
    isAdmin(user);
    if(path==='/api/admin/tours'){
      const id=clean(data.id,80);fail(/^[a-z0-9][a-z0-9-]{1,78}$/.test(id),'Use a URL-friendly tour ID');
      fail(['uz','en','ru'].every(k=>data.title?.[k]&&data.city?.[k]&&data.desc?.[k]),'Provide title/city/description in UZ, EN, RU');
      const price=Number(data.price),days=Number(data.days);fail(Number.isInteger(price)&&price>=1&&price<=1000000&&Number.isInteger(days)&&days>=1&&days<=100,'Invalid price/days');
      fail(seed.destinations.some(d=>d.id===data.destination),'Invalid destination');
      fail(typeof data.image==='string'&&(data.image.startsWith('/assets/')||data.image.startsWith('https://images.unsplash.com/')),'Invalid image URL');
      const payload=Object.fromEntries(['id','title','city','desc','price','days','destination','type','image','rating','reviews','featured','discount','itinerary'].filter(k=>k in data).map(k=>[k,data[k]]));
      Object.assign(payload,{id,price,days,rating:Math.min(5,Math.max(0,Number(payload.rating)||4.7)),reviews:Math.max(0,Number(payload.reviews)||0),featured:!!payload.featured,discount:Math.min(90,Math.max(0,Number(payload.discount)||0))});
      await run(db,'INSERT INTO tours(id,data,active,created_at) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,active=excluded.active',id,JSON.stringify(payload),data.active===false?0:1,now());
      await audit(db,user,'tour.upsert',id);return reply({ok:true});
    }
    if(path==='/api/admin/tours/toggle'){
      const id=clean(data.id,80);await tour(db,id,true);await run(db,'UPDATE tours SET active=? WHERE id=?',data.active?1:0,id);
      await audit(db,user,'tour.toggle',id);return reply({ok:true});
    }
    if(path==='/api/admin/posts'){
      const id=clean(data.id,80);fail(/^[a-z0-9-]{2,80}$/.test(id),'Invalid article ID');
      fail(['title','summary','body'].every(k=>['uz','en','ru'].every(l=>data[k]?.[l])),'Fill article translations');
      const payload=Object.fromEntries(['id','title','summary','body','image','date','read'].map(k=>[k,data[k]]));
      await run(db,'INSERT INTO posts(id,data,active) VALUES(?,?,1) ON CONFLICT(id) DO UPDATE SET data=excluded.data',id,JSON.stringify(payload));
      await audit(db,user,'post.upsert',id);return reply({ok:true});
    }
    if(path==='/api/admin/bookings/status'){
      const id=clean(data.id,80),status=clean(data.status,25);
      fail(['pending','confirmed','cancelled','completed'].includes(status),'Invalid booking status');
      const b=await one(db,'SELECT id FROM bookings WHERE id=?',id);fail(b,'Booking not found',404);
      await run(db,'UPDATE bookings SET status=? WHERE id=?',status,id);
      await audit(db,user,'booking.status',id);return reply({ok:true});
    }
  }
  throw new ApiError('Not found',404);
}

export default {
  async scheduled(_event,env){
    const cutoff=stamp()-2*DAY;
    await env.DB.batch([
      env.DB.prepare('DELETE FROM rate_limits WHERE window_start<?').bind(cutoff),
      env.DB.prepare('DELETE FROM sessions WHERE expires<?').bind(stamp()),
      env.DB.prepare('DELETE FROM oauth_states WHERE expires<?').bind(stamp()),
      env.DB.prepare('DELETE FROM password_resets WHERE expires<?').bind(stamp())
    ]);
  },
  async fetch(request,env){
    const url=new URL(request.url),path=url.pathname;
    try{
      if(path==='/assets/hero-real.mp4'){
        // The real, unmodified video can be placed under public/assets/hero-real.mp4.
        // Otherwise the official Pexels video is used; it requires the user's browser to access Pexels.
        const local=await env.ASSETS.fetch(request);
        if(local.ok && (local.headers.get('Content-Type')||'').toLowerCase().includes('video/')) return local;
        return Response.redirect(env.HERO_VIDEO_URL || 'https://videos.pexels.com/video-files/6554717/6554717-hd_1920_1080_30fps.mp4',302);
      }
      if(path==='/auth/google'&&request.method==='GET')return googleStart(request,env);
      if(path==='/auth/google/callback'&&request.method==='GET')return googleCallback(request,env);
      if(path.startsWith('/api/'))return await api(request,env,path);
      if(request.method!=='GET'&&request.method!=='HEAD')return reply({error:'Method not allowed'},405);
      return env.ASSETS.fetch(request);
    }catch(e){
      if(e instanceof ApiError)return reply({error:e.message},e.status);
      console.error('TurAgent worker error',e.name,clean(e.message,100));return reply({error:'Internal server error'},500);
    }
  }
};
