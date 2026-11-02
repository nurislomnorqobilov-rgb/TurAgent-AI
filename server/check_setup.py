"""Safe Gemini configuration diagnostic. Never prints API key or secrets."""
from __future__ import annotations
import json, os, sys, urllib.request, urllib.error, urllib.parse
os.environ.setdefault('TURAGENT_LOCAL_SQLITE','1')
import app

def check():
 print('TurAgent AI - safe configuration check')
 print('Environment file:', 'found' if (app.ROOT/'.env').is_file() else 'not found')
 print('Database mode:', 'Local SQLite' if app.SQLITE else 'PostgreSQL (requires server)')
 print('Gemini key:', 'configured' if app.GEMINI_API_KEY else 'not configured')
 print('Preferred model:',app.GEMINI_MODEL)
 print('Google OAuth:', 'configured' if app.GOOGLE_ID and app.GOOGLE_SECRET else 'not configured')
 print('SMTP:', 'configured' if app.SMTP_HOST else 'not configured')
 if not app.GEMINI_API_KEY:
  print('Gemini key absent. Set GEMINI_API_KEY in project .env.')
  return
 try:
  req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=100',headers={'x-goog-api-key':app.GEMINI_API_KEY})
  with urllib.request.urlopen(req,timeout=14) as r:data=json.load(r)
  capable=[x['name'].removeprefix('models/') for x in data.get('models',[]) if 'generateContent' in x.get('supportedGenerationMethods',[])]
  print('Gemini API access: OK')
  print('Preferred model available:', 'YES' if app.GEMINI_MODEL in capable else 'not listed')
  print('Sample available models:',', '.join(capable[:7]) or '(not listed)')
  print('Note: list-models success does not guarantee unused generateContent quota.')
  chosen=app.GEMINI_MODEL if app.GEMINI_MODEL in capable else next((m for m in app.GEMINI_FALLBACKS if m in capable),None)
  if chosen:
   print('Checking a real short AI response with:',chosen)
   req2=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+urllib.parse.quote(chosen)+':generateContent',data=json.dumps({'contents':[{'parts':[{'text':'Respond with exactly: OK'}]}],'generationConfig':{'maxOutputTokens':20}}).encode(),headers={'Content-Type':'application/json','x-goog-api-key':app.GEMINI_API_KEY},method='POST')
   try:
    with urllib.request.urlopen(req2,timeout=25) as response:data2=json.load(response)
    answer=''.join(p.get('text','') for c in data2.get('candidates',[]) for p in c.get('content',{}).get('parts',[]) if isinstance(p,dict))
    print('GenerateContent test:', 'SUCCESS' if answer.strip() else 'EMPTY_RESPONSE')
   except urllib.error.HTTPError as e:
    print('GenerateContent HTTP status:',e.code)
    if e.code==429:print('CAUSE: Google quota exhausted; check AI Studio Usage / Limits. Model fallback will not bypass a key-wide quota.')
    elif e.code in (401,403):print('CAUSE: key, authorization restriction, regional policy or API permission. Check Google AI Studio key type/restrictions.')
    elif e.code==404:print('CAUSE: model not enabled for this key. Pick a listed text generation model.')
    else:print('CAUSE: Google rejected the generation request. Check project and model access.')
   except (urllib.error.URLError, TimeoutError, OSError) as e:
    print('GenerateContent network/TLS failure:',type(e).__name__,'reason:',type(getattr(e,'reason',None)).__name__)
    print('CAUSE: network, DNS, proxy, firewall or TLS connectivity. The website code alone cannot resolve internet restrictions.')
  else: print('No text generation model found in the model list for this key.')
 except urllib.error.HTTPError as e:
  print('Gemini API HTTP status:',e.code)
  if e.code in (401,403):print('Check API key validity, permissions, region and project settings.')
  elif e.code==429:print('Quota/rate limit reached. Retry after quota resets.')
  else:print('Check internet connection and Gemini API availability.')
 except Exception as e:
  print('Gemini check failed:',type(e).__name__,'(network or TLS problem)')
if __name__=='__main__':
 try:check()
 except Exception as e:print('Configuration error:',type(e).__name__)
