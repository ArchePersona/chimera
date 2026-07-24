from app.templating import env
from app.routes.web import render
from fastapi import Request
import re

scope = {'type': 'http', 'headers': []}
request = Request(scope)
result = render('studio/dashboard.html', request=request, current_route='/')
content = result.body.decode('utf-8')
links = re.findall(r'href="([^"]*)"', content)
for link in links:
    print(link)