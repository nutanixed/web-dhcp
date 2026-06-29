from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from ldap3 import Server, Connection, ALL
import subprocess
from functools import wraps
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or 'dhcp-management-fixed-secret-key-123'

# Hardcoded Credentials
AUTH_USERNAME = os.getenv('AUTH_USERNAME')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD')

# LDAP Configuration
LDAP_SERVER = os.getenv('LDAP_SERVER')
LDAP_ADMIN_DN = os.getenv('LDAP_ADMIN_DN')
LDAP_ADMIN_PASSWORD = os.getenv('LDAP_ADMIN_PASSWORD')
LDAP_USER_SEARCH_BASE = os.getenv('LDAP_USER_SEARCH_BASE')
LDAP_USER_ATTRIBUTE = os.getenv('LDAP_USER_ATTRIBUTE')
LOGOUT_REDIRECT_URL = os.getenv('LOGOUT_REDIRECT_URL', '/')

@app.before_request
def auto_login():
    # DISABLE LOGIN: Automatically log in as 'admin' to bypass login screen.
    if 'logged_in' not in session:
        session['logged_in'] = True

def check_ldap_auth(username, password):
    if not username or not password:
        return False
    try:
        server = Server(LDAP_SERVER, get_info=ALL)
        admin_conn = Connection(server, user=LDAP_ADMIN_DN, password=LDAP_ADMIN_PASSWORD, authentication='SIMPLE')
        if not admin_conn.bind():
            return False
        search_filter = f"({LDAP_USER_ATTRIBUTE}={username})"
        admin_conn.search(LDAP_USER_SEARCH_BASE, search_filter, attributes=[])
        if not admin_conn.entries:
            admin_conn.unbind()
            return False
        user_dn = admin_conn.entries[0].entry_dn
        admin_conn.unbind()
        user_conn = Connection(server, user=user_dn, password=password, authentication='SIMPLE')
        if user_conn.bind():
            user_conn.unbind()
            return True
        return False
    except Exception as e:
        print(f"LDAP Error: {e}")
        return False

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

SCRIPT_PATH = '/home/nutanix/web-dhcp/list_dhcp_reservations.sh'

def run_script(action, mac=None, ip=None):
    cmd = [SCRIPT_PATH, action]
    if mac:
        cmd.append(mac)
    if ip:
        cmd.append(ip)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

def get_dhcp_data():
    stdout, stderr, code = run_script('list')
    leases = []
    reservations = []
    
    section = None
    lines = stdout.split('\n')
    for line in lines:
        if not line.strip() or "---" in line or "MAC Address" in line:
            continue
            
        if "Active DHCP Leases" in line:
            section = "leases"
            continue
        elif "Static DHCP Reservations" in line:
            section = "reservations"
            continue
            
        if section == "leases":
            parts = line.split()
            if len(parts) >= 3:
                # MAC, IP, Hostname, ExpiryDate (2 parts), ExpiryTime (1 part)
                # 50:6b:8d:7b:10:c0 10.142.152.198 nutanix 2026-03-26 10:26:40
                mac = parts[0]
                ip = parts[1]
                hostname = parts[2]
                expiry = " ".join(parts[3:]) if len(parts) > 3 else "Unknown"
                leases.append({'mac': mac, 'ip': ip, 'hostname': hostname, 'expiry': expiry})
        elif section == "reservations":
            parts = line.split()
            if len(parts) >= 2:
                reservations.append({'mac': parts[0], 'ip': parts[1]})
                
    return leases, reservations

@app.route('/login', methods=['GET', 'POST'])
def login():
    # DISABLE LOGIN: Redirect to index immediately.
    return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        auth_type = request.form.get('auth_type')
        if auth_type == 'ldap':
            if check_ldap_auth(username, password):
                session['logged_in'] = True
                return redirect(url_for('index'))
            else:
                flash('Invalid LDAP credentials', 'danger')
        else:
            if username == AUTH_USERNAME and password == AUTH_PASSWORD:
                session['logged_in'] = True
                return redirect(url_for('index'))
            else:
                flash('Invalid local credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('email', None)
    session.pop('description', None)
    return redirect(LOGOUT_REDIRECT_URL)

@app.route('/')
@requires_auth
def index():
    leases, reservations = get_dhcp_data()
    return render_template('index.html', leases=leases, reservations=reservations)

@app.route('/api/data')
@requires_auth
def api_get_data():
    leases, reservations = get_dhcp_data()
    return jsonify({'leases': leases, 'reservations': reservations})

@app.route('/add', methods=['POST'])
@requires_auth
def add():
    if request.is_json:
        data = request.get_json()
        mac = data.get('mac')
        ip = data.get('ip')
    else:
        mac = request.form.get('mac')
        ip = request.form.get('ip')
        
    if mac and ip:
        stdout, stderr, code = run_script('add', mac, ip)
        if code == 0:
            msg = f'Successfully added reservation for {mac} with {ip}'
            if request.is_json:
                return jsonify({'status': 'success', 'message': msg})
            flash(msg, 'success')
        else:
            if request.is_json:
                return jsonify({'status': 'error', 'message': stderr}), 500
            flash(f'Error adding reservation: {stderr}', 'danger')
    return redirect(url_for('index'))

@app.route('/update', methods=['POST'])
@requires_auth
def update():
    if request.is_json:
        data = request.get_json()
        mac = data.get('mac')
        ip = data.get('ip')
    else:
        mac = request.form.get('mac')
        ip = request.form.get('ip')
        
    if mac and ip:
        stdout, stderr, code = run_script('update', mac, ip)
        if code == 0:
            msg = f'Successfully updated reservation for {mac} to {ip}'
            if request.is_json:
                return jsonify({'status': 'success', 'message': msg})
            flash(msg, 'success')
        else:
            if request.is_json:
                return jsonify({'status': 'error', 'message': stderr}), 500
            flash(f'Error updating reservation: {stderr}', 'danger')
    return redirect(url_for('index'))

@app.route('/delete/<mac>', methods=['GET', 'DELETE'])
@requires_auth
def delete(mac):
    stdout, stderr, code = run_script('del', mac)
    if code == 0:
        msg = f'Successfully deleted reservation for {mac}'
        if request.method == 'DELETE' or request.args.get('json'):
            return jsonify({'status': 'success', 'message': msg})
        flash(msg, 'success')
    else:
        if request.method == 'DELETE' or request.args.get('json'):
            return jsonify({'status': 'error', 'message': stderr}), 500
        flash(f'Error deleting reservation: {stderr}', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
