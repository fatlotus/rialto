from rialto.rest import *
from google.appengine.ext import db
import re
import logging

class Page(db.Model):
  name = db.StringProperty()
  body = db.TextProperty()
  
  def locate(self):
    return '/pages/%s' % (self.key().id())

def empty(x):
  if x is None:
    return True
  return re.sub(r'[ \t\r\n]', '', unicode(x).lower()) == ''

@TemplateResponse.variable('menu')
def generate_menu():
  prefixes = { }
  
  for page in Page.all():
    if not page.name:
      continue
    
    if '|' in page.name:
      section, name = page.name.split('|')
      section = section.lower()
      
      if section not in prefixes:
        prefixes[section] = [ ]
      prefixes[section].append((name, page))
  
  logging.error(prefixes)
  
  result = [ ]
  
  for prefix, pages in sorted(prefixes.items()):
    result.append('<h2>%s</h2><ul>' % escape(prefix))
    for name, entity in sorted(pages):
      result.append('<li><a href="%s">%s</a></li>' % (escape(entity.locate()), escape(name)))
    result.append('</ul>')
  
  return HTML(''.join(result))

@route(r'/create', method = GET)
def create_page_form(request):
  return TemplateResponse('create_page')

@route(r'/create', method = POST)
def create_page(request):
  if empty(request['name']):
    return TemplateResponse('create_page', message = 'Please enter a page title before submitting.')
  
  elif empty(request['body']):
    return TemplateResponse('create_page', message = 'Please enter a page body before submitting.')
  
  page = Page(name = request['name'], body = request['body'])
  page.put()
  
  return RedirectResponse(page)

@route(r'/pages/([^/]+)/edit', method=GET)
@resource(Page)
def edit_page_form(request, page):
  return TemplateResponse('edit_page',
    title = page.name,
    body = page.body,
    page = page
  )

@route(r'/pages/([^/]+)', method=POST)
@resource(Page)
def edit_page(request, page):
  def failure(message):
    return TemplateResponse('edit_page',
      title = page.name,
      body = page.body,
      page = page,
      message = message
    )
  
  if empty(request['name']):
    return failure('Please enter a page name before submitting.')
  elif empty(request['body']):
    return failure('Please enter a body before submitting.')
  else:
    page.name = request['name']
    page.body = request['body']
    page.put()
    
    return RedirectResponse(page)

@route(r'/pages/([^/]+)', method=GET)
@resource(Page)
def view_page(request, page):
  return TemplateResponse('view_page',
    title = page.name,
    body = Markdown(page.body),
    page = page
  )

@route(r'/', method=GET)
def view_home_page(request):
  for page in Page.all():
    if page.name is None:
      continue
    
    if 'WELCOME' in page.name.upper():
      page_id = page.key().id()
      break
  
  return view_page(request, page_id)