# Google OAuth & Remote Server Patterns

## OAuth Desktop App from Remote Server

**Problem**: Desktop OAuth clients use `redirect_uri: http://localhost:PORT`. When running on a remote server, the browser on the user's machine redirects to THEIR localhost, not the server. Standard `run_local_server()` fails.

**Solution: Manual Code Exchange**

```python
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)

# Step 1: Generate auth URL (save it, give to user)
auth_url, state = flow.authorization_url(
    access_type="offline",       # get refresh_token
    prompt="consent",            # force consent screen
    include_granted_scopes="true",
)

# Step 2: User opens auth_url, authorizes, gets error on localhost
#         They copy ?code=XXXX&state=YYYY from browser address bar

# Step 3: Exchange code for token (run on server)
flow.fetch_token(code=user_provided_code)
creds = flow.credentials

# Step 4: Save tokens
token_data = {
    "token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
    "client_id": creds.client_id,
    "client_secret": creds.client_secret,
    "scopes": creds.scopes,
}
```

**Critical details:**
- `code_challenge` is embedded in the auth_url — generate a NEW url each attempt (single-use)
- `flow` object cannot be pickled — generate auth_url and exchange in the SAME python session
- If token exchange must happen in a separate session, save `client_id`, `client_secret`, `token_uri` separately and reconstruct flow

## write_file / execute_code Heredoc Pitfall

**Problem**: `write_file` heredoc and `execute_code` with `textwrap.dedent` / triple-quoted strings **truncate or corrupt** strings containing colons in paths (`https://`), single quotes inside single-quoted strings, and `os.path.join()` calls.

**Solution**: For Python scripts with dynamic paths, use `execute_code` to write the file via Python string operations:

```python
lines = [
    'import os',
    'CREDS = os.path.expanduser("~/.hermes/credentials/google_oauth.json")',
]
with open("/path/to/output.py", "w") as f:
    f.write("\n".join(lines) + "\n")
```

Or use `base + "/filename"` concatenation instead of `os.path.join(base, "filename")` when embedding paths as literals.

## ngrok for Public Tunnels

```bash
curl -sL https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -o /tmp/ngrok.tgz
tar xzf /tmp/ngrok.tgz -C /tmp
/tmp/ngrok config add-authtoken YOUR_TOKEN
/tmp/ngrok http 8090

# Get public URL
curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "import sys,json; [print(t['public_url']) for t in json.load(sys.stdin)['tunnels']]"
```

Free tier = random subdomains. For OAuth Desktop apps, ngrok can't replace localhost redirect_uri — useful for web servers, not OAuth Desktop flows.

## Google Cloud Console Setup for OAuth

1. [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → Credentials → OAuth client ID → Desktop application
2. Download JSON → `~/.hermes/credentials/google_oauth.json`
3. APIs & Services → Library: enable YouTube Data API v3, Google Drive API, etc.
4. OAuth consent screen: add your email as test user

Common scopes:
```
https://www.googleapis.com/auth/youtube.readonly
https://www.googleapis.com/auth/youtube.upload
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/cloud-platform
```
