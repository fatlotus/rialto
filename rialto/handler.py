from beaker.middleware import SessionMiddleware
from rialto.rest import routes, Request

try:
  from rialto import secrets
except ImportError:
  raise Error("Please rename rialto/secrets_default.py to "+
              "rialto/secrets.py and change the HMAC secret "+
              "to finish application setup.")

def application(environ, start_response):
  session = environ['beaker.session']
  request = Request(environ)
  
  for route in routes:
    action = route(environ)
    
    if action is None:
      continue
    else:
      response = action(request)
      if response:
        return response.render(environ, start_response)
  
  start_response('404 Not Found', [('Content-type', 'text/html')])
  return [ '<h1>404 Object Not Found</h1>' ]

application = SessionMiddleware(application, {
  'session.cookie_expires': True,
  'secret': secrets.SESSION_SECRET,
  'auto': True
})