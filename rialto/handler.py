def application(environ, start_response):
  start_response('200 Okay', [('Content-type', 'text/plain')])
  return [ 'Hello, world!' ]