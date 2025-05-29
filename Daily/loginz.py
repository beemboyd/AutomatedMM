import configparser
import os
from kiteconnect import KiteConnect

def load_config():
    """Load configuration from config.ini file"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    if not os.path.exists(config_path):
        print(f"Error: config.ini file not found at {config_path}")
        return None
    
    config.read(config_path)
    return config

def get_available_users(config):
    """Extract available user credentials from config"""
    users = []
    for section in config.sections():
        if section.startswith('API_CREDENTIALS_'):
            user_name = section.replace('API_CREDENTIALS_', '')
            api_key = config.get(section, 'api_key', fallback='')
            api_secret = config.get(section, 'api_secret', fallback='')
            
            if api_key and api_secret:  # Only include users with both api_key and api_secret
                users.append({
                    'name': user_name,
                    'section': section,
                    'api_key': api_key,
                    'api_secret': api_secret
                })
    
    return users

def select_user(users):
    """Allow user to select which credentials to use"""
    if not users:
        print("No valid API credentials found in config.ini")
        return None
    
    print("\nAvailable users:")
    for i, user in enumerate(users, 1):
        print(f"{i}. {user['name']}")
    
    while True:
        try:
            choice = int(input(f"\nSelect user (1-{len(users)}): "))
            if 1 <= choice <= len(users):
                return users[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(users)}")
        except ValueError:
            print("Please enter a valid number")

def update_access_token(config, user, access_token):
    """Update the access token in config.ini file"""
    config.set(user['section'], 'access_token', access_token)
    
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    with open(config_path, 'w') as configfile:
        config.write(configfile)
    
    print(f"\nAccess token updated for {user['name']} in config.ini")

def main():
    # Load configuration
    config = load_config()
    if not config:
        return
    
    # Get available users
    users = get_available_users(config)
    if not users:
        return
    
    # Let user select credentials
    selected_user = select_user(users)
    if not selected_user:
        return
    
    print(f"\nSelected user: {selected_user['name']}")
    print(f"API Key: {selected_user['api_key']}")
    
    # Initialize the KiteConnect client
    kite = KiteConnect(api_key=selected_user['api_key'])
    
    # Generate and print the login URL
    print(f"\nLogin URL: {kite.login_url()}")
    
    # The URL printed above should be opened in a browser.
    # After logging in and authorizing your app, you'll be redirected to your registered redirect URL,
    # which will contain a request_token as a query parameter.
    # Manually extract the request_token from that URL and input it below.
    request_token = input("\nEnter the request token: ").strip()
    
    try:
        # Exchange the request token for an access token
        data = kite.generate_session(request_token, api_secret=selected_user['api_secret'])
        access_token = data["access_token"]
        print(f"\nAccess Token: {access_token}")
        
        # Update the config file with the new access token
        update_access_token(config, selected_user, access_token)
        
    except Exception as e:
        print(f"Error generating access token: {e}")

if __name__ == "__main__":
    main()