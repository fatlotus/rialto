from rialto.rest import *
from google.appengine.ext import db
import re
import logging

IMAGE_TYPES = ['image/png', 'image/jpg', 'image/jpeg', 'image/gif']

class Page(db.Model):
  name = db.StringProperty()
  body = db.TextProperty()
  
  def locate(self):
    return '/pages/%s' % (self.key().id())

class Photo(db.Model):
  data = db.BlobProperty()
  content_type = db.StringProperty()
  
  def locate(self):
    return '/pages/%s/photos/%s' % (self.key().parent().id(), self.key().id())

def empty(x):
  if x is None:
    return True
  return re.sub(r'[ \t\r\n]', '', unicode(x).lower()) == ''

@TemplateResponse.variable('menu')
def generate_menu():
  prefixes = { }
  
  for page in Page.all():
    name = page.name
    
    if not name:
      continue
    
    if '|' not in name:
      section = "Crown House "
      title = name
    else:
      section, title = name.split('|')
    section = section.lower()
    
    if section not in prefixes:
      prefixes[section] = [ ]
    prefixes[section].append((title, page))
  
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
    return TemplateResponse('create_page',
      message = 'Please enter a page title before submitting.')
  
  elif empty(request['body']):
    return TemplateResponse('create_page',
      message = 'Please enter a page body before submitting.')
  
  page = Page(name = request['name'], body = request['body'])
  page.put()
  
  return RedirectResponse(page)

@route(r'/pages/([0-9]+)/edit', method=GET)
@resource(Page)
def edit_page_form(request, page):
  return TemplateResponse('edit_page',
    title = page.name,
    body = page.body,
    page = page
  )

@route(r'/pages/([0-9]+)/photos', method=POST)
@resource(Page)
def add_photo(request, page):
  upload = request['upload']
  
  if upload.type not in IMAGE_TYPES:
    markup = ''
    message = 'Please only attach images.'
  
  else:
    photo = Photo(
      parent = page,
      data = upload.file.read(),
      content_type = upload.type
    )
    
    try:
      photo.put()
      
      if request['type'] == 'html':
        markup = '\n<img src="' + photo.locate() + '"/>\n'
      else:
        markup = '\n![Description of Image](' + photo.locate() + ')\n'
      
      message = 'Successfully attached image.'
    except:
      markup = ''
      message = 'Unable to attach image; perhaps you should try a smaller one.'
  
  return JSONResponse({
    'message': message,
    'markup': markup
  })

@route(r'/pages/([0-9]+)/photos/([0-9]+)', method=GET)
@resource(Page)
@resource(Photo)
def get_photo(request, page, photo):
  return RawResponse(photo.data, content_type=photo.content_type)

@route(r'/pages/([0-9]+)', method=POST)
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
  else:
    page.name = request['name']
    page.body = request['body'] or ""
    
    for image in Photo.all().ancestor(page):
      url = image.locate()
      
      matcher = '%s([^0-9]|$)' % re.escape(url)
      
      if not re.search(matcher, page.body):
        image.delete()
    
    page.put()
    
    return RedirectResponse(page)

@route(r'/pages/([0-9]+)', method=GET)
@resource(Page)
def view_page(request, page):
  return TemplateResponse('view_page',
    title = page.name,
    body = Markdown(page.body),
    page = page
  )

@route(r'/', method=GET)
def view_home_page(request):
  home_page_id = None
  arbitrary_id = ''
  
  for page in Page.all():
    arbitrary_id = page.key().id()
    
    if page.name is None:
      continue
    
    if 'HOME' in page.name.upper():
      home_page_id = page.key().id()
      break
  
  return view_page(request, home_page_id or arbitrary_id)