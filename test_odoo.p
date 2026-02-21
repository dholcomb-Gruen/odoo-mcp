import requests
url = "https://gruen-systems.com"
db = "v18.gruen-systems.com"
username = "d.holcomb@gruen-systems.com"
password = “!LoveHolly5820
"response = requests.post(f"{url}/web/session/authenticate", json={"jsonrpc": "2.0", "method": "call", "params": {"db": db, "login": username, "password": password}})
result = response.json()
print(result)
