from functools import wraps
import cgi
import logging
import re
import markdown

__all__ = ['route', 'POST', 'GET', 'RedirectResponse', 'HTML', 'TemplateResponse',
           'resource', 'Markdown', 'escape']

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
    elif type(value) is str:
      return value.decode('utf-8')
    else:
      return value

class HTML(object):
  def __init__(self, code):
    self.code = code

class Markdown(HTML):
  def __init__(self, code):
    HTML.__init__(self, markdown.markdown(code))

class Response(object):
  def render(self, environ, start_response):
    raise NotImplemented

class TemplateResponse(object):
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
        value = self.__class__.globals.get(name, lambda:None)()
        
        if value is None:
          return ""
        
        logging.error(value.code)
      
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
      return [ result.encode('utf-8') ]
  
class RedirectResponse(object):
  def __init__(self, target):
    if hasattr(target, 'locate'):
      self.target = target.locate()
    else:
      self.target = target
  
  def render(self, environ, start_response):
    start_response('302 Found', [('Location', self.target)])
    return [ ]

def escape(value):
  value = unicode(value)
  return re.sub(r'[^a-zA-Z0-9]', lambda x: '&#x%02x;' % ord(x.group(0)), value)

def resource(klass):
  def wrap(function):
    def inner(request, identifier, *vargs, **dargs):
      try:
        identifier = int(identifier)
      except ValueError:
        return None
      
      instance = klass.get_by_id(identifier)
      
      if instance is None:
        return None
      
      return function(request, instance, *vargs, **dargs)
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