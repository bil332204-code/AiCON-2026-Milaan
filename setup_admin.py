"""Configure a private local demo operator without shipping shared credentials."""
from pathlib import Path
from getpass import getpass
import shutil
from dotenv import dotenv_values,set_key
from email_validator import validate_email,EmailNotValidError
root=Path(__file__).parent
path=root/'milaan/backend/.env'
if not path.exists():shutil.copyfile(path.with_name('.env.example'),path)
values=dotenv_values(path)
if values.get('DEMO_SELLER_EMAIL') and values.get('DEMO_SELLER_PASSWORD'):
    print('Existing operator configuration kept.');raise SystemExit(0)
print('Create your local Milaan demo operator. Use these same details in both apps.')
while True:
    try:
        email=validate_email(input('Email: ').strip(),check_deliverability=False).normalized.lower();break
    except EmailNotValidError as e:print(e)
while True:
    password=getpass('Password (10+ characters): ')
    if len(password)<10:print('Use at least 10 characters.');continue
    if getpass('Confirm password: ')!=password:print('Passwords differ.');continue
    break
set_key(str(path),'DEMO_SELLER_EMAIL',email)
set_key(str(path),'DEMO_SELLER_PASSWORD',password)
print('Configured. Run START_DEMO.bat. Keep .env private. New public signups still require email verification.')
