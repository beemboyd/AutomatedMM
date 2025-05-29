from kiteconnect import KiteConnect

# Replace these with your actual credentials.
KITE_API_KEY = "ms2m54xupkjzvbwj"
KITE_API_SECRET = "84a716dpcnupceyrtk3rsuayzqxwems4"

# Initialize the KiteConnect client.
kite = KiteConnect(api_key=KITE_API_KEY)

# Generate and print the login URL.
print("Login URL:", kite.login_url())

# The URL printed above should be opened in a browser.
# After logging in and authorizing your app, you'll be redirected to your registered redirect URL,
# which will contain a request_token as a query parameter.
# Manually extract the request_token from that URL and input it below.
request_token = input("Enter the request token: ").strip()

# Exchange the request token for an access token.
data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
access_token = data["access_token"]
print("Access Token:", access_token)
