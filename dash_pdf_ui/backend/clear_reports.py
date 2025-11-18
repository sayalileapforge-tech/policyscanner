import urllib.request
import urllib.error

url = 'http://127.0.0.1:8000/api/clear'
req = urllib.request.Request(url, method='POST')
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(resp.status, resp.read().decode())
except Exception as e:
    print('Request failed:', e)
