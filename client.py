import urllib.request

url = "https://sample-python-9cm9u.ondigitalocean.app/test"
print(urllib.request.urlopen(url).read().decode())
