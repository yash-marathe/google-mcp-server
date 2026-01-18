# Google MCP Server - Complete Setup Guide

A comprehensive guide to setting up and using the Google Workspace MCP Server.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Google Cloud Console Setup](#google-cloud-console-setup)
- [Environment Configuration](#environment-configuration)
- [Running the Server](#running-the-server)
- [Usage Examples](#usage-examples)
- [API Scopes and Permissions](#api-scopes-and-permissions)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

---

## Overview

This MCP server provides **27+ tools** for interacting with Google Workspace applications:

- **Google Docs** (7 tools): Create, read, update, format, and delete documents
- **Google Sheets** (12 tools): Manage spreadsheets, manipulate data, format cells
- **Google Drive** (8+ tools): File management, sharing, searching, and organization

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.8+** installed on your system
- A **Google Account** with access to Google Workspace
- Basic familiarity with the command line
- (Optional) **Modal account** for cloud deployment

### Check Python Version

```bash
python --version
# or
python3 --version
```

If Python is not installed, download it from [python.org](https://www.python.org/downloads/).

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yash-marathe/google-mcp-server.git
cd google-mcp-server
```

### Step 2: Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

First, create a `requirements.txt` file:

```bash
cat > requirements.txt << EOF
# MCP Framework
mcp>=0.9.0

# Google API Client Libraries
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
google-auth-httplib2>=0.1.1
google-api-python-client>=2.100.0

# Optional: For Modal deployment
modal>=0.63.0
EOF
```

Then install the dependencies:

```bash
pip install -r requirements.txt
```

### Step 4: Verify Installation

```bash
python -c "import mcp; from googleapiclient import discovery; print('Installation successful!')"
```

---

## Google Cloud Console Setup

This section guides you through obtaining the `credentials.json` file required for OAuth2 authentication.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Enter a project name (e.g., "MCP Google Server")
4. Click **Create**
5. Wait for the project to be created and select it

### Step 2: Enable Required APIs

1. In the Google Cloud Console, go to **APIs & Services** → **Library**
2. Search for and enable these APIs (one at a time):
   - **Google Docs API**
   - **Google Sheets API**
   - **Google Drive API**

For each API:
- Click on the API name
- Click **Enable**
- Wait for it to activate

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** user type (unless you have a Google Workspace account)
3. Click **Create**
4. Fill in the required fields:
   - **App name**: `Google MCP Server`
   - **User support email**: Your email
   - **Developer contact email**: Your email
5. Click **Save and Continue**
6. On **Scopes** page, click **Add or Remove Scopes**
7. Add these scopes:
   - `https://www.googleapis.com/auth/documents`
   - `https://www.googleapis.com/auth/spreadsheets`
   - `https://www.googleapis.com/auth/drive`
8. Click **Update** → **Save and Continue**
9. On **Test users** page, click **Add Users**
10. Add your Google account email
11. Click **Save and Continue** → **Back to Dashboard**

### Step 4: Create OAuth2 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Choose **Application type**: **Desktop app**
4. Enter a name: `MCP Server Client`
5. Click **Create**
6. A dialog appears with your credentials
7. Click **Download JSON**
8. Rename the downloaded file to `credentials.json`
9. Move `credentials.json` to your project root directory

Your project directory should now look like:
```
google-mcp-server/
├── credentials.json          ← Your OAuth2 credentials
├── google_mcp_server_complete.py
├── README.md
├── SETUP.md
└── requirements.txt
```

---

## Environment Configuration

### OAuth2 Authentication Flow

The first time you run the server, it will:

1. Open a browser window for authentication
2. Ask you to sign in with your Google account
3. Request permission to access your Google Workspace data
4. Save an authentication token to `token.json`

After the first authentication, the server will use `token.json` for future sessions.

### File Permissions

Ensure the server can read/write:

```bash
# On macOS/Linux
chmod 600 credentials.json
chmod 600 token.json  # After first run
```

---

## Running the Server

### Local Development

#### Method 1: Direct Execution

```bash
python google_mcp_server_complete.py
```

#### Method 2: Using MCP Inspector (Recommended for Testing)

The MCP Inspector provides a web UI for testing your server:

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Run the inspector
mcp-inspector python google_mcp_server_complete.py
```

This will open a web interface where you can test all tools interactively.

### Production Deployment with Modal

Modal allows you to deploy the server to the cloud.

#### Step 1: Install Modal

```bash
pip install modal
```

#### Step 2: Set Up Modal

```bash
# Authenticate with Modal
modal setup

# Create a Modal secret for your credentials
modal secret create google-credentials \
  GOOGLE_CREDENTIALS="$(cat credentials.json)" \
  GOOGLE_TOKEN="$(cat token.json)"
```

#### Step 3: Deploy

Add this deployment code to a new file `deploy_modal.py`:

```python
import modal

stub = modal.Stub("google-mcp-server")

@stub.function(
    image=modal.Image.debian_slim()
        .pip_install([
            "mcp>=0.9.0",
            "google-auth>=2.23.0",
            "google-auth-oauthlib>=1.1.0",
            "google-auth-httplib2>=0.1.1",
            "google-api-python-client>=2.100.0",
        ]),
    secrets=[modal.Secret.from_name("google-credentials")]
)
def run_server():
    import os
    import json
    from google_mcp_server_complete import GoogleMCPServer
    
    # Write credentials from secret
    with open("credentials.json", "w") as f:
        f.write(os.environ["GOOGLE_CREDENTIALS"])
    
    with open("token.json", "w") as f:
        f.write(os.environ["GOOGLE_TOKEN"])
    
    # Run server
    server = GoogleMCPServer()
    server.run()

@stub.local_entrypoint()
def main():
    run_server.remote()
```

Deploy:

```bash
modal deploy deploy_modal.py
```

---

## Usage Examples

### Connecting to the Server

Once the server is running, AI assistants (like Claude) can connect to it via the MCP protocol. Configure your AI client with:

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "python",
      "args": ["/path/to/google_mcp_server_complete.py"],
      "env": {}
    }
  }
}
```

### Google Docs Examples

#### Example 1: Create a New Document

```json
{
  "tool": "create_document",
  "arguments": {
    "title": "My First MCP Document"
  }
}
```

**Response:**
```json
{
  "document_id": "1abc...xyz",
  "title": "My First MCP Document",
  "url": "https://docs.google.com/document/d/1abc...xyz/edit"
}
```

#### Example 2: Add Content to a Document

```json
{
  "tool": "append_to_document",
  "arguments": {
    "document_id": "1abc...xyz",
    "content": "This is my first paragraph.\n\nThis is the second paragraph with more content."
  }
}
```

#### Example 3: Format Text (Make it Bold)

```json
{
  "tool": "format_document_text",
  "arguments": {
    "document_id": "1abc...xyz",
    "start_index": 1,
    "end_index": 27,
    "bold": true,
    "font_size": 14
  }
}
```

#### Example 4: Read Document Content

```json
{
  "tool": "get_document_content",
  "arguments": {
    "document_id": "1abc...xyz"
  }
}
```

**Response:**
```json
{
  "title": "My First MCP Document",
  "document_id": "1abc...xyz",
  "content": "This is my first paragraph.\n\nThis is the second paragraph...",
  "revision_id": "ALm..."
}
```

#### Example 5: Update Document Content

```json
{
  "tool": "update_document_content",
  "arguments": {
    "document_id": "1abc...xyz",
    "content": "Updated introduction text here.",
    "start_index": 1
  }
}
```

#### Example 6: Delete Content Range

```json
{
  "tool": "delete_document_content",
  "arguments": {
    "document_id": "1abc...xyz",
    "start_index": 50,
    "end_index": 100
  }
}
```

#### Example 7: Delete a Document

```json
{
  "tool": "delete_document",
  "arguments": {
    "document_id": "1abc...xyz"
  }
}
```

---

### Google Sheets Examples

#### Example 1: Create a New Spreadsheet

```json
{
  "tool": "create_spreadsheet",
  "arguments": {
    "title": "Sales Data 2024"
  }
}
```

**Response:**
```json
{
  "spreadsheet_id": "1def...uvw",
  "title": "Sales Data 2024",
  "url": "https://docs.google.com/spreadsheets/d/1def...uvw/edit"
}
```

#### Example 2: Add Data to Spreadsheet

```json
{
  "tool": "update_sheet_data",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "range_name": "Sheet1!A1:C3",
    "values": [
      ["Name", "Quantity", "Price"],
      ["Widget A", "10", "29.99"],
      ["Widget B", "5", "49.99"]
    ]
  }
}
```

#### Example 3: Append Rows to Sheet

```json
{
  "tool": "append_sheet_data",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "range_name": "Sheet1!A:C",
    "values": [
      ["Widget C", "15", "39.99"],
      ["Widget D", "8", "59.99"]
    ]
  }
}
```

#### Example 4: Read Sheet Data

```json
{
  "tool": "get_sheet_data",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "range_name": "Sheet1!A1:C10"
  }
}
```

**Response:**
```json
{
  "spreadsheet_id": "1def...uvw",
  "range": "Sheet1!A1:C5",
  "values": [
    ["Name", "Quantity", "Price"],
    ["Widget A", "10", "29.99"],
    ["Widget B", "5", "49.99"],
    ["Widget C", "15", "39.99"],
    ["Widget D", "8", "59.99"]
  ],
  "row_count": 5
}
```

#### Example 5: Clear a Range

```json
{
  "tool": "clear_sheet_range",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "range_name": "Sheet1!D1:F10"
  }
}
```

#### Example 6: Add New Rows

```json
{
  "tool": "add_sheet_rows",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "sheet_id": 0,
    "start_index": 5,
    "count": 3
  }
}
```

#### Example 7: Add New Columns

```json
{
  "tool": "add_sheet_columns",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "sheet_id": 0,
    "start_index": 3,
    "count": 2
  }
}
```

#### Example 8: Delete Rows

```json
{
  "tool": "delete_sheet_rows",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "sheet_id": 0,
    "start_index": 10,
    "end_index": 15
  }
}
```

#### Example 9: Delete Columns

```json
{
  "tool": "delete_sheet_columns",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "sheet_id": 0,
    "start_index": 5,
    "end_index": 7
  }
}
```

#### Example 10: Format Cells (Background Color)

```json
{
  "tool": "format_sheet_cells",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "sheet_id": 0,
    "start_row": 0,
    "end_row": 1,
    "start_col": 0,
    "end_col": 3,
    "background_color": {
      "red": 0.2,
      "green": 0.6,
      "blue": 0.9,
      "alpha": 1.0
    },
    "bold": true
  }
}
```

#### Example 11: Format with Text Color

```json
{
  "tool": "format_sheet_cells",
  "arguments": {
    "spreadsheet_id": "1def...uvw",
    "sheet_id": 0,
    "start_row": 1,
    "end_row": 5,
    "start_col": 2,
    "end_col": 3,
    "text_color": {
      "red": 1.0,
      "green": 0.0,
      "blue": 0.0,
      "alpha": 1.0
    }
  }
}
```

---

### Google Drive Examples

#### Example 1: List Files in Drive

```json
{
  "tool": "list_drive_files",
  "arguments": {
    "page_size": 10,
    "order_by": "modifiedTime desc"
  }
}
```

**Response:**
```json
{
  "file_count": 10,
  "files": [
    {
      "id": "1xyz...abc",
      "name": "Important Document.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "created_time": "2024-01-15T10:30:00Z",
      "modified_time": "2024-01-16T14:22:00Z",
      "size": "52480"
    }
  ],
  "next_page_token": "abc123..."
}
```

#### Example 2: Search for Files

```json
{
  "tool": "search_drive_files",
  "arguments": {
    "search_term": "report",
    "file_type": "application/vnd.google-apps.document"
  }
}
```

#### Example 3: Upload a File

```json
{
  "tool": "upload_file_to_drive",
  "arguments": {
    "file_path": "/path/to/local/file.pdf",
    "name": "Uploaded Report.pdf",
    "mime_type": "application/pdf"
  }
}
```

#### Example 4: Create a Folder

```json
{
  "tool": "create_drive_folder",
  "arguments": {
    "name": "Project Documents",
    "parent_folder_id": "1parent...id"
  }
}
```

**Response:**
```json
{
  "folder_id": "1folder...xyz",
  "name": "Project Documents",
  "url": "https://drive.google.com/drive/folders/1folder...xyz",
  "status": "created"
}
```

#### Example 5: Share a File

```json
{
  "tool": "share_drive_file",
  "arguments": {
    "file_id": "1xyz...abc",
    "email": "colleague@example.com",
    "role": "writer",
    "send_notification": true
  }
}
```

**Roles:**
- `reader` - Can view only
- `commenter` - Can view and comment
- `writer` - Can view and edit

#### Example 6: Copy a File

```json
{
  "tool": "copy_drive_file",
  "arguments": {
    "file_id": "1xyz...abc",
    "new_name": "Copy of Important Document",
    "folder_id": "1folder...xyz"
  }
}
```

#### Example 7: Move a File

```json
{
  "tool": "move_drive_file",
  "arguments": {
    "file_id": "1xyz...abc",
    "new_folder_id": "1newfolder...def",
    "old_folder_id": "1oldfolder...ghi"
  }
}
```

#### Example 8: Delete a File

```json
{
  "tool": "delete_drive_file",
  "arguments": {
    "file_id": "1xyz...abc"
  }
}
```

---

## API Scopes and Permissions

### Understanding OAuth2 Scopes

The server requests three scopes from Google:

#### 1. Google Docs API Scope
```
https://www.googleapis.com/auth/documents
```

**Permissions:**
- Create new documents
- Read document content
- Modify document content
- Delete documents
- Format text and apply styles

**Use cases:**
- AI-assisted document writing
- Automated report generation
- Document formatting and editing

#### 2. Google Sheets API Scope
```
https://www.googleapis.com/auth/spreadsheets
```

**Permissions:**
- Create new spreadsheets
- Read spreadsheet data
- Update cells and ranges
- Add/delete rows and columns
- Format cells and apply styles

**Use cases:**
- Data analysis and manipulation
- Automated data entry
- Report generation from structured data

#### 3. Google Drive API Scope
```
https://www.googleapis.com/auth/drive
```

**Permissions:**
- List files and folders
- Upload and download files
- Create folders
- Move and copy files
- Share files with specific users
- Delete files

**Use cases:**
- File organization and management
- Automated file backups
- Collaborative file sharing

### Security Best Practices

1. **Store credentials securely:**
   - Never commit `credentials.json` or `token.json` to version control
   - Add them to `.gitignore`
   - Use environment variables in production

2. **Limit scope access:**
   - Only request scopes you need
   - Review permissions regularly

3. **Rotate credentials:**
   - Regenerate credentials if compromised
   - Delete old credentials from Google Cloud Console

4. **Monitor usage:**
   - Check Google Cloud Console for API usage
   - Set up alerts for unusual activity

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: `FileNotFoundError: credentials.json not found`

**Solution:**
- Ensure `credentials.json` is in the project root directory
- Re-download from Google Cloud Console if missing
- Check file permissions

```bash
ls -la credentials.json
# Should show the file exists
```

#### Issue 2: `ImportError: No module named 'mcp'`

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

#### Issue 3: Browser doesn't open for OAuth

**Solution:**
- Copy the URL from terminal and open it manually
- Check firewall settings
- Use a different browser
- Try running on a different network

#### Issue 4: `Invalid grant` or `Token expired`

**Solution:**
```bash
# Delete the token and re-authenticate
rm token.json
python google_mcp_server_complete.py
```

#### Issue 5: `API has not been enabled`

**Solution:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Navigate to **APIs & Services** → **Library**
4. Enable the required API (Docs, Sheets, or Drive)

#### Issue 6: `Insufficient permissions` error

**Solution:**
- Check OAuth consent screen has correct scopes
- Re-authorize with `rm token.json` and run server again
- Verify test users are added in OAuth consent screen

#### Issue 7: Rate limiting errors

**Solution:**
- Google APIs have quota limits
- Check quotas in Google Cloud Console under **APIs & Services** → **Quotas**
- Request quota increases if needed
- Implement exponential backoff in your application

#### Issue 8: Server won't start

**Solution:**
```bash
# Check Python version (must be 3.8+)
python --version

# Verify all imports work
python -c "
import mcp
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
print('All imports successful')
"

# Check for conflicting processes
lsof -i :port_number  # If using a specific port
```

### Debugging Tips

#### Enable Verbose Logging

Add to the top of `google_mcp_server_complete.py`:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

#### Test Individual Components

Create a test script `test_connection.py`:

```python
import asyncio
from google_mcp_server_complete import GoogleAPIClient, GoogleDocsTools

async def test():
    # Initialize client
    client = GoogleAPIClient()
    client.authenticate()
    
    # Test Docs API
    docs = GoogleDocsTools(client)
    result = await docs.create_document("Test Document")
    print(f"Created document: {result}")
    
    # Clean up
    await docs.delete_document(result['document_id'])
    print("Test successful!")

if __name__ == "__main__":
    asyncio.run(test())
```

Run it:
```bash
python test_connection.py
```

### Getting Help

If you encounter issues not covered here:

1. **Check Google Cloud Console:**
   - Review API quotas and usage
   - Check for service outages

2. **Review logs:**
   - Look for error messages in terminal output
   - Check Google Cloud Console logs

3. **Community resources:**
   - [Google Workspace API Documentation](https://developers.google.com/workspace)
   - [MCP Protocol Documentation](https://modelcontextprotocol.io)
   - Stack Overflow with tags: `google-api`, `python`, `oauth2`

4. **File an issue:**
   - [GitHub Issues](https://github.com/yash-marathe/google-mcp-server/issues)
   - Include error messages and steps to reproduce

---

## Advanced Configuration

### Custom Credential Paths

Modify the initialization in `google_mcp_server_complete.py`:

```python
api_client = GoogleAPIClient(
    credentials_path="/custom/path/credentials.json",
    token_path="/custom/path/token.json"
)
```

### Environment Variables

Create a `.env` file:

```env
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
GOOGLE_TOKEN_PATH=/path/to/token.json
LOG_LEVEL=INFO
```

Load in your script:

```python
import os
from dotenv import load_dotenv

load_dotenv()

api_client = GoogleAPIClient(
    credentials_path=os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json'),
    token_path=os.getenv('GOOGLE_TOKEN_PATH', 'token.json')
)
```

### Using Service Accounts (Advanced)

For server-to-server communication without user interaction:

1. Create a service account in Google Cloud Console
2. Download the service account key JSON
3. Modify authentication code:

```python
from google.oauth2 import service_account

SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

creds = service_account.Credentials.from_service_account_file(
    'service-account-key.json',
    scopes=SCOPES
)
```

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY google_mcp_server_complete.py .
COPY credentials.json .
COPY token.json .

CMD ["python", "google_mcp_server_complete.py"]
```

Build and run:

```bash
docker build -t google-mcp-server .
docker run -v $(pwd)/token.json:/app/token.json google-mcp-server
```

### Configuring MCP in Claude Desktop

Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "python",
      "args": [
        "/absolute/path/to/google-mcp-server/google_mcp_server_complete.py"
      ],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/credentials.json"
      }
    }
  }
}
```

Restart Claude Desktop to apply changes.

---

## Performance Optimization

### Caching API Responses

Implement caching for frequently accessed data:

```python
from functools import lru_cache
import time

@lru_cache(maxsize=100)
def cached_get_document(document_id, ttl_hash):
    # ttl_hash changes every minute, invalidating cache
    return docs_tools.get_document_content(document_id)

# Use with:
ttl = int(time.time() / 60)  # Changes every minute
result = cached_get_document("doc_id", ttl)
```

### Batch Operations

Process multiple operations efficiently:

```python
# Instead of multiple individual updates
# Use batch update for sheets
requests = [
    {
        'updateCells': {
            'range': {...},
            'rows': [...]
        }
    },
    {
        'updateCells': {
            'range': {...},
            'rows': [...]
        }
    }
]

sheets_service.spreadsheets().batchUpdate(
    spreadsheetId=spreadsheet_id,
    body={'requests': requests}
).execute()
```

---

## Next Steps

Now that your server is set up:

1. **Explore the tools** - Try each of the 27+ tools with the examples above
2. **Integrate with AI** - Connect Claude or another AI assistant
3. **Build workflows** - Chain multiple tools together for complex tasks
4. **Extend functionality** - Add custom tools for your specific needs
5. **Deploy to production** - Use Modal or Docker for production deployment

---

## Additional Resources

- [Google Workspace API Documentation](https://developers.google.com/workspace)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io)
- [Google API Python Client](https://github.com/googleapis/google-api-python-client)
- [OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)

---

**Happy building with Google MCP Server! 🚀**

For questions, issues, or contributions, visit the [GitHub repository](https://github.com/yash-marathe/google-mcp-server).
