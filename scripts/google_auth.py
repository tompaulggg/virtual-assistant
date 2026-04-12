from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    "scripts/credentials.json",
    ["https://www.googleapis.com/auth/calendar.readonly"],
)
creds = flow.run_local_server(port=8099, open_browser=True)

print()
print("Fertig! Kopiere diese 3 Zeilen:")
print()
print(f"GOOGLE_CLIENT_ID={creds.client_id}")
print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
