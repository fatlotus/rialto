from google.appengine.api import memcache
from functools import wraps
import cgi
import logging
import re
import markdown
import json
import urlparse

__all__ = ['route', 'POST', 'GET', 'RedirectResponse', 'HTML', 'TemplateResponse',
           'resource', 'Markdown', 'escape', 'JSONResponse', 'RawResponse',
           'cache', 'invalidate' ]

routes = [ ] # Singleton!

POST = 'POST' # Let's prevent typing errors.
GET = 'GET' 

class Request(object):
  def __init__(self, environ):
    self.environ = environ
    self.params = cgi.FieldStorage(environ['wsgi.input'])
    self.session = self.environ['beaker.session']
  
  def __getitem__(self, name):
    value = self.params.getfirst(name)
    if value is None:
      return None
    elif self.params[name].file is not None:
      return self.params[name]
    elif type(value) is str:
      try:
        return value.decode('utf-8')
      except UnicodeDecodeError:
        return value
    else:
      return value

class HTML(object):
  def __init__(self, code):
    self.code = code

class Markdown(HTML):
  def __init__(self, code):
    HTML.__init__(self, markdown.markdown(code, ['tables']))

class Response(object):
  def render(self, environ, start_response):
    raise NotImplemented

class TemplateResponse(Response):
  globals = { }
  
  def __init__(self, template, **variables):
    self.template = template
    self.variables = variables
  
  @classmethod
  def variable(klass, name):
    def inner(function):
      klass.globals[name] = function
      return function
    return inner
  
  def render(self, environ, start_response):
    with open('theme/%s.html' % self.template) as fp:
      html = fp.read()
    
    def inner(match):
      name = match.group(1)
      value = self.variables.get(name, None)
      
      if value is None:
        
        @cache(name)
        def retrieve_value():
          return self.__class__.globals.get(name, lambda:None)()
        
        value = retrieve_value()
        
        if value is None:
          return ""
      
      if isinstance(value, HTML):
        return value.code
      else:
        if hasattr(value, 'locate'):
          value = value.locate()
        
        return escape(value)
    
    result = re.sub(r'\{\{([^}]+)\}\}', inner, html)
    
    if self.template != 'index':
      return TemplateResponse('index', content = HTML(result)).render(environ, start_response)
    else:
      start_response('200 Okay', [ ('Content-type', 'text/html')])
      return [ result.encode('utf-8') ]
  
class RedirectResponse(Response):
  def __init__(self, target):
    if hasattr(target, 'locate'):
      self.target = target.locate()
    else:
      self.target = target
  
  def render(self, environ, start_response):
    start_response('302 Found', [('Location', self.target)])
    return [ ]

class JSONResponse(Response):
  def __init__(self, value):
    self.value = value
  
  def render(self, environ, start_response):
    callbacks = urlparse.parse_qs(environ['QUERY_STRING']).get('callback', [ ])
    
    if len(callbacks) == 1:
      prefix = '<script type="text/javascript">%s(' % callbacks[0]
      suffix = ")</script>"
    else:
      prefix = suffix = ""
    
    start_response('200 Okay', [('Content-type', 'text/html')])
    return [ prefix, json.dumps(self.value), suffix ]

class RawResponse(Response):
  def __init__(self, data, content_type = 'application/octet-stream'):
    self.data = data
    self.content_type = content_type
  
  def render(self, environ, start_response):
    start_response('200 Okay', [('Content-type', self.content_type.encode('utf-8'))])
    return [ self.data ]
  
def escape(value):
  value = unicode(value)
  return re.sub(r'[^a-zA-Z0-9]', lambda x: '&#x%02x;' % ord(x.group(0)), value)

def cache(key):
  def wrap(function):
    def inner(*vargs):
      data = memcache.get('cache:%s' % (key % vargs))
      
      if data:
        return data
      
      result = function()
      memcache.set('cache:%s' % (key % vargs), result)
      return result
    
    return inner
  return wrap

def invalidate(key, *vargs):
  memcache.delete('cache:%s' % (key % vargs))

def resource(klass):
  def wrap(function):
    def inner(request, *vargs, **dargs):
      parent = None
      
      for (index, value) in enumerate(vargs):
        if type(value) not in (str, unicode, int, long):
          parent = value
          continue
        
        try:
          identifier = int(value)
        except ValueError:
          return None
        
        instance = klass.get_by_id(identifier, parent = parent)
        
        if instance is None:
          return None
        
        shuffle = vargs[0:index] + ( instance, ) + vargs[index + 1:]
        
        return function(request, *shuffle, **dargs)
      return None
    return inner
  return wrap

def route(url, method = None, methods = [ ]):
  def inner(function):
    if method:
      match_methods = methods[:] + [method]
    else:
      match_methods = methods[:]
    
    if match_methods == [ ]:
      match_methods = [ 'ANY' ]
    
    compiled = re.compile("^%s$" % url)
    
    def matcher(environ):
      match = compiled.match(environ['PATH_INFO'])
      
      if match is None:
        return None
      if environ['REQUEST_METHOD'] not in match_methods and 'ANY' not in match_methods:
        return None
      
      def result(request):
        return function(request, *match.groups())
      
      return result
    
    routes.append(matcher)
    return function
  return inner