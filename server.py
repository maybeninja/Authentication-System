from Modules import *
import yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

app = Flask(__name__)
db = 'Database/Apps'


base = 'Auth'
token = config['authtoken']

@app.route(f'/{base}')
def index():
    return jsonify({'message': 'Auth Server Running'}) 


@app.route(f'/{base}/create-app', methods=['POST'])
def create_app():
    data = request.json
    app_name = data.get('app_name')
    version = data.get('version')
    link = data.get('link')
    ip_address = request.remote_addr

    auth_header = request.headers.get("Authorization")
    
    if not auth_header or auth_header != f"Bearer {token}":
       

        log(
            "api",
            "Unauthorized - App Creation",
            f"Authorization Token: {auth_header}\nApp Name: {app_name}\nIP Address: {ip_address}",
            color=0xFF0000  
        )

        return jsonify({"error": "Unauthorized"}), 401

    # Validate input
    if not app_name:
        return jsonify({"error": "Missing app_name"}), 400

    # Generate unique IDs
    app_secret = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    app_id = ''.join(random.choices(string.digits, k=8))
    version = str(version)

    app_data = {
        "app_name": app_name,
        "app_secret": app_secret,
        "app_id": app_id,
        "version": version,
        "link": link
    }

    # Ensure app directory exists
    app_dir = os.path.join(db, app_name)
    os.makedirs(app_dir, exist_ok=True)

    # Save app data
    with open(os.path.join(app_dir, "app_info.json"), "w") as f:
        json.dump(app_data, f, indent=4)

    log(
        'api','App Created',
        f'App Name: {app_name}\nIP Address: {ip_address}',
          color=0x32CD32
    )

    return jsonify(app_data), 201


@app.route(f'/{base}/update-version', methods=['POST'])
def update_version():
    data = request.json
    app_name = data.get('app_name')
    version = data.get('version')
    link = data.get('link')
    ip_address = request.remote_addr

    version = str(version)


    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {token}":

        log(
            "api",
            "Unauthorized - Version Update",
            f"Authorization Token: {auth_header}\nApp Name: {app_name}\nIP Address: {ip_address}",
            color=0xFF0000  
        )

        return jsonify({"error": "Unauthorized"}), 401 
    
    if not app_name or not version:
        return jsonify({"error": "Missing app_name or version"}), 400

    app_info_path = os.path.join(db, app_name, "app_info.json")

    if not os.path.exists(app_info_path):
        return jsonify({"error": "App not found"}), 404

    try:
        with open(app_info_path, "r") as f:
            app_data = json.load(f)

        app_data["version"] = version
        app_data["link"] = link

        with open(app_info_path, "w") as f:
            json.dump(app_data, f, indent=4)
        
        log(
        'api','App Update',
        f'Version: {version}\nApp Name: {app_name}\nIP Address: {ip_address}',
          color=0x32CD32
    )

        return jsonify({"message": "Version And Link Updated"}), 200
        


    except json.JSONDecodeError:
        return jsonify({"error": "Corrupted app_info.json"}), 500




@app.route(f'/{base}/gen-license', methods=['POST'])
def gen_license():
    data = request.json
    app_name = data.get('app_name')
    duration = data.get('duration')
    quantity = data.get('quantity')
    ip_address = request.remote_addr

    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {token}":
        log(
            "api",
            "Unauthorized - License Generation",
            f"Authorization Token: {auth_header}\n"
            f"App Name: {app_name}\nIP Address: {ip_address}",
            color=0xFF0000)  
        return jsonify({"error": "Unauthorized"}), 401 

    if not app_name:
        return jsonify({"error": "Missing app_name"}), 400
    if not duration:
        return jsonify({"error": "Missing duration"}), 400
    if not quantity:
        return jsonify({"error": "Missing quantity"}), 400
    if duration not in ['Month', 'Week', 'Lifetime']:
        return jsonify({"error": "Invalid duration"}), 400
    
    try:
        quantity = int(quantity)
    except ValueError:
        return jsonify({"error": "Quantity must be a number"}), 400
    
    app_dir = os.path.join(db, app_name)
    if not os.path.exists(app_dir):
        return jsonify({"error": "App not found"}), 404

    with open(os.path.join(app_dir, "unused_license.txt"), "a") as f:
        for _ in range(quantity):
            license_key = f"{app_name}-{duration[0]}-" + ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            f.write(f"{license_key}\n")

    log(
        'api','License Generated',
        f'License Quantity: {quantity}\nApp Name: {app_name}\nIP Address: {ip_address}',
          color=0x32CD32
    )

    return jsonify({"message": f"{quantity} licenses generated successfully"}), 201

@app.route(f'/{base}/assign-license', methods=['POST'])
def assign_license():
    data = request.json
    app_name = data.get('app_name')
    duration = data.get('duration')
    ip_address = request.remote_addr

    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {token}":
        log(
            "api",
            "Unauthorized - License Assignment",
            f"Authorization Token: {auth_header}\n"
            f"App Name: {app_name}\nIP Address: {ip_address}",
            color=0xFF0000)
        return jsonify({"error": "Unauthorized"}), 401 

    if not app_name:
        return jsonify({"error": "Missing app_name"}), 400
    if not duration:
        return jsonify({"error": "Missing duration"}), 400
    if duration not in ['Month', 'Week', 'Lifetime']:
        return jsonify({"error": "Invalid duration"}), 400

    app_dir = os.path.join(db, app_name)
    unused_file = os.path.join(app_dir, "unused_license.txt")
    active_license_file = os.path.join(app_dir, "active_license.json")

    if not os.path.exists(app_dir):
        return jsonify({"error": "App not found"}), 404
    if not os.path.exists(unused_file):
        return jsonify({"error": "No unused licenses available"}), 404

    # Read available licenses
    with open(unused_file, "r") as f:
        licenses = [line.strip() for line in f.readlines()]

    # Find the first license that matches duration
    license_to_assign = None
    for i, license_key in enumerate(licenses):
        if f"-{duration[0]}-" in license_key:  # Match by first letter of duration
            license_to_assign = license_key.strip()
            del licenses[i]  # Remove it from the list
            break  

    if not license_to_assign:
        return jsonify({"error": f"No licenses available for {duration}"}), 404

    # Update unused licenses file (only remove the assigned license)
    with open(unused_file, "w") as f:
        f.write("\n".join(licenses) + "\n")

    # Calculate expiry date
    current_time = datetime.utcnow()
    if duration == "Month":
        expiry_date = current_time + timedelta(days=30)
    elif duration == "Week":
        expiry_date = current_time + timedelta(days=7)
    else:  # Lifetime
        expiry_date = "Lifetime"

    # Load active licenses, ensure it's a dictionary
    if os.path.exists(active_license_file):
        with open(active_license_file, "r") as f:
            try:
                active_licenses = json.load(f)
                if not isinstance(active_licenses, dict):
                    active_licenses = {}
            except json.JSONDecodeError:
                active_licenses = {}
    else:
        active_licenses = {}

    # Assign the license without removing others
    active_licenses[license_to_assign] = {
        "expiry": expiry_date if expiry_date == "Lifetime" else expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
        "user": None,
        "hwid": None
    }

    # Save back the updated licenses
    with open(active_license_file, "w") as f:
        json.dump(active_licenses, f, indent=4)

    log(
        'api', 'License Assigned',
        f'License Key: {license_to_assign}\nApp Name: {app_name}\nIP Address: {ip_address}',
        color=0x32CD32
    )

    return jsonify({"license": license_to_assign, "expiry": active_licenses[license_to_assign]["expiry"]}), 200

@app.route(f'/{base}/verify-license', methods=['GET'])
def verify_license():
    license_key = request.args.get('license_key')
    app_name = request.args.get('app_name')
    app_secret = request.args.get('app_secret')
    hwid = request.args.get('hwid')
    version = request.args.get('version')
    ip_address = request.remote_addr

    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {token}":
        log(
            "api",
            "Unauthorized - License Verification",
            f"Authorization Token: {auth_header}\n"
            f"App Name: {app_name}\nIP Address: {ip_address}",
            color=0xFF0000)  
        return jsonify({"error": "Unauthorized"}), 401 
    
    if not license_key or not app_name or not app_secret or not version:
        return jsonify({"error": "Missing parameters"}), 400

    app_dir = os.path.join(db, app_name)
    app_info_file = os.path.join(app_dir, "app_info.json")
    active_license_file = os.path.join(app_dir, "active_license.json")

    # Check if app exists
    if not os.path.exists(app_info_file):
        return jsonify({"error": "App not found"}), 404

    # Verify app secret
    with open(app_info_file, "r") as f:
        app_info = json.load(f)
    
    if app_info.get("app_secret") != app_secret:
        return jsonify({"error": "Invalid app secret"}), 401

    # Verify license
    if not os.path.exists(active_license_file):
        return jsonify({"error": "No active licenses for this app"}), 404

    with open(active_license_file, "r") as f:
        try:
            active_licenses = json.load(f)
        except json.JSONDecodeError:
            return jsonify({"error": "Corrupted license data"}), 500

    license_data = active_licenses.get(license_key)

    if not license_data:
        return jsonify({"error": "License not found"}), 404

    # Check expiration
    expiry = license_data["expiry"]
    if expiry != "Lifetime":
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone('UTC'))

        if datetime.now(timezone('UTC')) > expiry_date:
            return jsonify({"error": "License expired"}), 403

    # HWID Handling (Fix)
    if "hwid" not in license_data or not license_data["hwid"]:
        # Assign HWID if not set (null, empty, or missing)
        license_data["hwid"] = hwid  
        with open(active_license_file, "w") as f:
            json.dump(active_licenses, f, indent=4)
    else:
        if license_data["hwid"] != hwid:
            return jsonify({"error": "HWID locked. Different device detected"}), 403

    # Version Check
    if version != app_info.get("version"):
        link = app_info.get('link')
        return jsonify({"error": f"Outdated version. Please Download Latest: {link}"}), 426  # HTTP 426 Upgrade Required
    
    log(
        'api', 'License Authorized',
        f'License Key: {license_key}\nApp Name: {app_name}\nIP Address: {ip_address}',
        color=0x32CD32
    )
    
    return jsonify({
        "message": "License valid",
        "expiry": expiry,
        "hwid": license_data["hwid"]
    }), 200

def ban_license_logic(license_key):
    """Function to ban a license by removing it from active licenses."""
    ip_address = request.remote_addr
    if not license_key:
        return {"error": "License key is required"}, 400

    # Extract app_name dynamically from the license directory
    app_name = None
    for app_folder in os.listdir(db):  # Loop through all apps
        app_dir = os.path.join(db, app_folder)
        active_license_file = os.path.join(app_dir, "active_license.json")

        if os.path.exists(active_license_file):
            try:
                with open(active_license_file, "r") as f:
                    active_licenses = json.load(f)
                if license_key in active_licenses:
                    app_name = app_folder  # Found the app
                    break
            except json.JSONDecodeError:
                return {"error": "Corrupted license data"}, 500

    if not app_name:
        return {"error": "License not found"}, 404

    # Ban the license by deleting it
    del active_licenses[license_key]

    # Save updated data
    with open(active_license_file, "w") as f:
        json.dump(active_licenses, f, indent=4)

    log(
        'api', 'License Banned',
        f'License Key: {license_key}\nApp Name: {app_name}\nIP Address: {ip_address}',
        color=0x32CD32
    )
    
    return {"message": "License banned successfully"}, 200


@app.route(f'/{base}/ban-license', methods=['POST'])
def ban_license_route():
    """Flask route to handle banning a license."""
    ip_address = request.remote_addr

    data = request.json
    if not data or "license_key" not in data:
        return jsonify({"error": "Missing license key"}), 400

    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {token}":
    
        log(
            "api",
            "Unauthorized - License Ban",
            f"Authorization Token: {auth_header}\nIP Address: {ip_address}",
            color=0xFF0000
        )
        
        return jsonify({"error": "Unauthorized"}), 401 
    
    license_key = data["license_key"]

    response, status_code = ban_license_logic(license_key)
    return jsonify(response), status_code





def find_app_from_license(license_key):
    """Find the app directory based on the license key."""
    for app_name in os.listdir(db):
        app_dir = os.path.join(db, app_name)
        active_license_file = os.path.join(app_dir, "active_license.json")

        if os.path.exists(active_license_file):
            try:
                with open(active_license_file, "r") as f:
                    active_licenses = json.load(f) or {}

                if isinstance(active_licenses, dict) and license_key in active_licenses:
                    return app_name , active_license_file # Return app name and license file path

            except (json.JSONDecodeError, TypeError):
                continue  # Skip corrupted files

    return None, None  # License not found


@app.route(f'/{base}/reset-hwid', methods=['POST'])
def reset_hwid():
    """Reset HWID for a given license key (app name is auto-detected)."""
    data = request.json
    if not data or "license_key" not in data or "user" not in data:
        return jsonify({"error": "Missing required parameters"}), 400

    license_key = data["license_key"]
    user = data["user"]
    ip_address = request.remote_addr
    auth_header = request.headers.get("Authorization")

    if not auth_header or auth_header != f"Bearer {token}":
        return jsonify({"error": "Unauthorized"}), 401

    # Auto-detect app name and license file
    app_name, active_license_file = find_app_from_license(license_key)
    if not app_name:
        return jsonify({"error": "License not found"}), 404

    try:
        with open(active_license_file, "r") as f:
            active_licenses = json.load(f)

        license_data = active_licenses.get(license_key, {})

        # Check user ownership
        if not license_data.get("user"):
            license_data["user"] = user  # Assign user if missing
        elif license_data["user"] != user:
            ban_license_logic(license_key, app_name)
            return jsonify({"error": "License sharing detected, banned"}), 401

        # Reset HWID
        license_data["hwid"] = None

        # Save changes
        with open(active_license_file, "w") as f:
            json.dump(active_licenses, f, indent=4)

        return jsonify({"message": "HWID reset successfully"}), 200

    except (json.JSONDecodeError, TypeError):
        return jsonify({"error": "Corrupted license data"}), 500


@app.route(f'/{base}/update-user', methods=['PATCH'])
def update_user():
    """Update the user for a given license key (app name is auto-detected)."""
    data = request.json
    if not data or "license_key" not in data or "user" not in data:
        return jsonify({"error": "Missing required parameters"}), 400

    license_key = data["license_key"]
    user = data["user"]
    ip_address = request.remote_addr
    auth_header = request.headers.get("Authorization")

    if not auth_header or auth_header != f"Bearer {token}":
        return jsonify({"error": "Unauthorized"}), 401

    # Auto-detect app name and license file
    app_name, active_license_file = find_app_from_license(license_key)
    if not app_name:
        return jsonify({"error": "License not found"}), 404

    try:
        with open(active_license_file, "r") as f:
            active_licenses = json.load(f)

        if license_key not in active_licenses:
            return jsonify({"error": "Invalid license key"}), 400

        # Update user
        active_licenses[license_key]["user"] = user

        # Save changes
        with open(active_license_file, "w") as f:
            json.dump(active_licenses, f, indent=4)

        return jsonify({"message": "User updated successfully"}), 200

    except (json.JSONDecodeError, TypeError):
        return jsonify({"error": "Corrupted license data"}), 500



@app.route(f'/{base}/get-license', methods=['POST'])
def get_license():
    try:
        data = request.json
        auth_header = request.headers.get('Authorization')
        ip_address = request.remote_addr

        if not auth_header or auth_header != f"Bearer {token}":
            return jsonify({"error": "Unauthorized"}), 401

        license_key = data.get('license_key')
        if not license_key:
            return jsonify({"error": "Missing license_key"}), 400

        app_name,active_license_file = find_app_from_license(license_key=license_key)
        if not app_name:
            return jsonify({"error": "Invalid license key format"}), 400  # Added check


        if not os.path.exists(active_license_file):
            return jsonify({"error": "Application not found"}), 404

        with open(active_license_file, "r") as f:
            active_licenses = json.load(f)

        license_data = active_licenses.get(license_key)

        if not license_data:
            return jsonify({"error": "License not found"}), 404

        expiry = license_data.get('expiry')
        user = license_data.get('user', 'Unknown')

        if not expiry:
            return jsonify({"error": "Expiry date missing"}), 500

        try:
            if expiry == 'Lifetime':
                expiry_date = 'Never'
            else:
            
               expiry_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone('UTC'))
               if datetime.now(timezone('UTC')) > expiry_date:
                return jsonify({"error": "License expired"}), 403
        except ValueError as e:
            print(f"Expiry Date Parsing Error: {e}, Expiry: {expiry}")
            return jsonify({"error": "Invalid expiry date format"}), 500

        return jsonify({
            "license_key": license_key,
            "app_name": app_name,
            "user": user,
            "expiry_date": expiry,
            "valid": "Yes"
        }), 200

    except Exception as e:
        print(f"Internal Server Error: {e}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500




@app.route(f'/{base}/check', methods=['GET'])
def check():
    auth_header = request.headers.get('Authorization')
    ip_address = request.remote_addr

    if not auth_header or auth_header != f"Bearer {token}":
        log(
            "api",
            "Unauthorized - Check",
            f"Authorization Token: {auth_header}\nIP Address: {ip_address}",
            color=0xFF0000
        )
        return jsonify({"error": "Unauthorized"}), 401

    total_apps = 0
    total_licenses = 0

    try:
        # Iterate through each app directory
        for app_name in os.listdir(db):
            app_dir = os.path.join(db, app_name)
            active_license_file = os.path.join(app_dir, "active_license.json")

            if os.path.isdir(app_dir) and os.path.exists(active_license_file):
                total_apps += 1  # Count this app as active

                with open(active_license_file, "r") as f:
                    try:
                        active_licenses = json.load(f) or {}
                        if isinstance(active_licenses, dict):
                            total_licenses += len(active_licenses)  # Count licenses
                    except json.JSONDecodeError:
                        continue  

    except Exception as e:
        return jsonify({"error": f"Failed to retrieve data: {str(e)}"}), 500

    return jsonify({"total_apps": total_apps, "total_licenses": total_licenses}), 200

    
port = config['port']

app.run(host='0.0.0.0',port=port)
       

         




