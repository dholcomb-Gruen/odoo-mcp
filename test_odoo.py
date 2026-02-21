import xmlrpc.client
import ssl

context = ssl._create_unverified_context()
url = 'https://www.gruen-systems.com'
db = 'v18.gruen-systems.com'
username ='d.holcomb@gruen-systems.com'
password = 'marcus6619'

common = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common',context=context)
vid = common.authenticate(db, username, password, {})
print('User ID:', vid)

models = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object', context=context)
partners = models.execute_kw(db, vid, password, 'res.partner', 'search_read', [[]], {'fields': ['name', 'email'], 'limit': 5})
for p in partners:
    print(p['name'], p.get('email', ''))
