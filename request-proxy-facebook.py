#!/usr/bin/env python3

# A simple demo of Python requests to reverse proxy
# It's an intermediate between vanilla requests and Selenium
# It let's you interact programatically, but still run JS in
# the browser, without Selenium overhead
#
# This is an example of automating aspects of Facebook
#
# by @singe

from http.server import BaseHTTPRequestHandler, HTTPServer
from bs4 import BeautifulSoup
from requests import Session
import webbrowser
from cgi import parse_header, parse_multipart
from urllib.parse import parse_qs
from socketserver import ThreadingMixIn


class CallBackSrv(BaseHTTPRequestHandler):

  protocol_version = 'HTTP/1.1'
  baseurl = 'https://m.facebook.com'
  user = 'USERNAME'
  pwd = 'PASSWORD'
  session = Session()
  resp = None
  # Open a browser windows to our reverse proxy
  webbrowser.open('http://localhost:1337/')

  def fb_login(self):
    # Login to facebook mobile
    resp = self.session.get(self.baseurl, allow_redirects=True)
    soup = BeautifulSoup(resp.text, 'html5lib')
    try:
      action_url = soup.find('form', id='login_form')['action']
    except TypeError:  # Already loggedin
      return resp
    # Submit all the weird hidden fields too
    form = soup.find('form', id='login_form')
    inputs = form.findAll('input', {'type': ['hidden', 'submit']})
    post_data = {input.get('name'): input.get('value') for input in inputs}
    # Username and password
    post_data['email'] = self.user
    post_data['pass'] = self.pwd
    # Login
    resp = self.session.post(action_url,
                             data=post_data,
                             cookies=self.session.cookies,
                             allow_redirects=True)

    # Skip the one touch login prompt
    soup = BeautifulSoup(resp.text, 'html5lib')
    notnow = soup.find('span', text='Not Now')
    url = self.baseurl + notnow.parent['href']
    resp = self.session.get(url, allow_redirects=True)

    return resp

  def do_GET(self):
    # If it's the first request go with the freshly logged on page
    # Otherwise proxy the request
    if self.resp is None:
      resp = self.fb_login()
    else:
      resp = self.session.get(self.baseurl + self.path, allow_redirects=True)

    self.send_response(resp.status_code)
    # Sending other headers breaks stuff
    # The content length needs to be done manually
    self.send_header('Content-Length', len(resp.content))
    self.end_headers()
    self.wfile.write(resp.content)
    self.resp = resp

  def parse_POST(self):
    ctype, pdict = parse_header(self.headers['content-type'])
    if ctype == 'multipart/form-data':
      postvars = parse_multipart(self.rfile, pdict)
    elif ctype == 'application/x-www-form-urlencoded':
      length = int(self.headers['content-length'])
      postvars = parse_qs(self.rfile.read(length),
                          keep_blank_values=1)
    else:
      postvars = {}
    return postvars

  def do_POST(self):
    postvars = self.parse_POST()
    if self.resp is None:
      resp = self.fb_login()
    else:
      resp = self.session.post(self.baseurl + self.path,
                               data=postvars,
                               allow_redirects=True)
    self.send_response(resp.status_code)
    self.send_header('Content-Length', len(resp.content))
    self.end_headers()
    self.wfile.write(resp.content)
    self.resp = resp


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
  """ Make our HTTP server multi-threaded """


httpd = ThreadedHTTPServer(('', 1337), CallBackSrv)
httpd.serve_forever()