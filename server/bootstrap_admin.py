"""Run locally or `docker compose exec web python server/bootstrap_admin.py`.
One-time administrator creation using ADMIN_SETUP_TOKEN from environment.
"""
import getpass, json, os, sys, urllib.request, urllib.error
from app import rows, passmake, utcnow, emailok, clean, require, ADMIN_SETUP_TOKEN, init_db
import secrets, uuid

def main():
    init_db()
    if not ADMIN_SETUP_TOKEN or ADMIN_SETUP_TOKEN.startswith('REPLACE_'):
        sys.exit('Configure a strong ADMIN_SETUP_TOKEN in .env first.')
    if rows("SELECT id FROM users WHERE role='admin' LIMIT 1",one=True):
        sys.exit('An admin already exists. This command does not create a second admin.')
    name=input('Administrator name: ').strip()
    email=input('Administrator email: ').strip().lower()
    password=getpass.getpass('Administrator password (12+ characters): ')
    if len(name)<2 or not emailok(email) or len(password)<12:sys.exit('Invalid name, email or password')
    if rows('SELECT id FROM users WHERE email=?',(email,),one=True):sys.exit('Email already exists. Use a different one.')
    if input('Type CREATE to confirm: ')!='CREATE':sys.exit('Cancelled')
    salt,ph=passmake(password)
    rows('INSERT INTO users(id,name,email,password_salt,password_hash,role,created_at) VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,name,email,salt,ph,'admin',utcnow()))
    print('Administrator created. Log in from the normal website, then open /#/admin.')
if __name__=='__main__':main()
