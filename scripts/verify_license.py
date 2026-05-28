import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.license import verify_license

print(verify_license('certs/license_TestUser.json','certs/license_public.pem'))
