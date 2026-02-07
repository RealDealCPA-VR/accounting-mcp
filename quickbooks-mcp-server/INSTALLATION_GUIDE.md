# QuickBooks MCP Server - Installation & Setup Guide

## 📦 What You're Getting

A complete custom MCP server that connects to QuickBooks Online with these capabilities:

### ✅ Phase 1: Data Entry Automation (READY)
- PDF transaction extraction
- CSV import with intelligent mapping
- AI-powered account matching
- Batch import with validation
- Duplicate detection

### ✅ Phase 2: Bank Reconciliation (READY)
- Auto-match transactions
- Reconciliation reports
- Discrepancy flagging

### ✅ Phase 3: Tax Reporting (READY)
- Tax mapping reports for UltraTax
- Excel export generation
- Custom financial reports

### 🚧 Phase 4: QuickBooks Desktop (Framework Ready)
- QBD file reader (needs implementation)
- Migration tools (needs implementation)

---

## 🚀 Installation Steps

### Step 1: Prerequisites

**On your Windows 11 machine:**

1. **Install Python 3.10 or higher**
   - Download from: https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"
   - Verify: Open Command Prompt and run `python --version`

2. **Install Git (optional, for updates)**
   - Download from: https://git-scm.com/download/win

### Step 2: Download the MCP Server

1. Copy the entire `quickbooks-mcp-server` folder to your Windows machine
   - Recommended location: `C:\Users\YourName\quickbooks-mcp-server`

2. Open Command Prompt and navigate to the folder:
   ```cmd
   cd C:\Users\YourName\quickbooks-mcp-server
   ```

### Step 3: Install Dependencies

Run this command to install all required Python packages:

```cmd
pip install -e .
```

This will install:
- MCP SDK
- QuickBooks API libraries
- PDF parsing tools
- Excel generation tools
- AI matching libraries

### Step 4: Configure Your Credentials

1. **Copy the example environment file:**
   ```cmd
   copy .env.example .env
   ```

2. **Edit the `.env` file** with your QuickBooks credentials:
   
   Open `.env` in Notepad and fill in:

   ```env
   # From your screenshot:
   QBO_CLIENT_ID=your_client_id_from_intuit
   QBO_CLIENT_SECRET=your_client_secret_from_intuit
   QBO_REDIRECT_URI=https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl
   QBO_ENVIRONMENT=production

   # Your company IDs (from screenshot):
   QBO_COMPANY_IDS=9341455432557951,327838186,1020164455,1041511280,1161420580

   # Set your default company (Adult & Child Counseling):
   QBO_DEFAULT_COMPANY_ID=327838186

   # QuickBooks Desktop path (your local server):
   QBD_COMPANY_FILE_PATH=\\\\your-server\\quickbooks\\company_files
   QBD_ENABLE=true

   # Data Entry Settings:
   DATA_ENTRY_AUTO_MATCH_THRESHOLD=0.85
   DATA_ENTRY_DUPLICATE_CHECK=true
   ```

3. **Get OAuth Tokens:**
   
   You need to authenticate once to get access tokens. Run:
   
   ```cmd
   python -m quickbooks_mcp.tools.authenticate
   ```
   
   This will:
   - Open a browser window
   - Ask you to log in to QuickBooks
   - Authorize the app
   - Save tokens to your `.env` file

### Step 5: Test the MCP Server

Run the server to test:

```cmd
python -m quickbooks_mcp
```

You should see:
```
INFO - Starting QuickBooks MCP Server...
INFO - QBO Auth Manager initialized (environment: production)
INFO - QBO Client initialized
INFO - QuickBooks MCP Server initialized successfully
```

Press `Ctrl+C` to stop the server.

---

## 🔗 Connecting to Your AI Agent

### Option 1: Manual MCP Configuration

Add this to your agent's MCP configuration file:

```json
{
  "mcpServers": {
    "quickbooks": {
      "command": "python",
      "args": ["-m", "quickbooks_mcp"],
      "cwd": "C:\\Users\\YourName\\quickbooks-mcp-server\\src",
      "env": {
        "PYTHONPATH": "C:\\Users\\YourName\\quickbooks-mcp-server\\src"
      }
    }
  }
}
```

### Option 2: Using Machine AI's MCP Tools

If your AI agent has MCP configuration tools, tell it:

"Add a custom MCP server with these details:
- Name: QuickBooks
- Command: python -m quickbooks_mcp
- Working Directory: C:\\Users\\YourName\\quickbooks-mcp-server\\src"

---

## 📖 Usage Examples

Once connected, you can ask your AI agent:

### Data Entry Examples:

**"Import transactions from this bank statement PDF"**
```
Agent will:
1. Parse the PDF
2. Extract transactions
3. Match accounts using AI
4. Show you the results for approval
5. Import to QuickBooks Online
```

**"Import expenses from this CSV file"**
```
Agent will:
1. Read the CSV
2. Auto-detect columns
3. Map to chart of accounts
4. Validate data
5. Batch import to QBO
```

**"Create an expense for $500 to Office Depot for office supplies"**
```
Agent will:
1. Find/create Office Depot vendor
2. Match "office supplies" to correct account
3. Create expense in QBO
4. Confirm creation
```

### Bank Reconciliation Examples:

**"Reconcile Chase checking account for January 2026"**
```
Agent will:
1. Fetch QBO transactions
2. Parse bank statement
3. Auto-match transactions
4. Generate reconciliation report
5. Flag discrepancies
```

### Tax Reporting Examples:

**"Generate tax mapping report for 2025"**
```
Agent will:
1. Extract P&L and Balance Sheet data
2. Organize by tax categories
3. Generate Excel report
4. Format for UltraTax import
```

---

## 🔧 Troubleshooting

### Issue: "No module named 'mcp'"

**Solution:** Install dependencies again:
```cmd
pip install -e .
```

### Issue: "Missing required QuickBooks OAuth credentials"

**Solution:** Make sure your `.env` file has:
- QBO_CLIENT_ID
- QBO_CLIENT_SECRET
- QBO_REDIRECT_URI

### Issue: "Access token expired"

**Solution:** Re-authenticate:
```cmd
python -m quickbooks_mcp.tools.authenticate
```

### Issue: "Cannot connect to QuickBooks"

**Solution:** Check:
1. Internet connection
2. QuickBooks API credentials are correct
3. Company IDs are valid
4. OAuth tokens are not expired

### Issue: "PDF parsing not working"

**Solution:** Install Tesseract OCR:
1. Download: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to: `C:\Program Files\Tesseract-OCR`
3. Add to PATH environment variable

---

## 📁 File Structure

```
quickbooks-mcp-server/
├── src/
│   └── quickbooks_mcp/
│       ├── server.py              # Main MCP server
│       ├── qbo/
│       │   ├── auth.py            # OAuth authentication
│       │   ├── client.py          # API client
│       │   ├── transactions.py    # Transaction operations
│       │   ├── accounts.py        # Chart of accounts
│       │   └── reports.py         # Reporting
│       ├── parsers/
│       │   ├── pdf_parser.py      # PDF extraction
│       │   ├── csv_parser.py      # CSV import
│       │   └── ai_matcher.py      # AI account matching
│       └── utils/
│           ├── validation.py      # Data validation
│           └── excel.py           # Excel generation
├── .env                           # Your credentials (DO NOT SHARE)
├── .env.example                   # Template
├── pyproject.toml                 # Dependencies
└── README.md                      # Documentation
```

---

## 🔐 Security Notes

1. **Never share your `.env` file** - it contains your QuickBooks credentials
2. **Keep tokens secure** - they provide full access to your QuickBooks data
3. **Use production environment** - sandbox is for testing only
4. **Backup your data** - always backup before bulk operations
5. **Test with one company first** - verify everything works before using with all clients

---

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the logs in `quickbooks_mcp.log`
3. Ask your AI agent for help with specific errors

---

## 🎯 Next Steps

1. ✅ Install and configure the MCP server
2. ✅ Test with one company
3. ✅ Try data entry automation with a sample PDF/CSV
4. ✅ Set up for all your client companies
5. ✅ Create scheduled tasks for recurring work
6. 🚧 Implement QuickBooks Desktop integration (Phase 5)

---

## 📝 Notes

- This MCP server runs locally on your Windows 11 machine
- It connects to QuickBooks Online via official APIs
- All data processing happens on your machine
- No data is sent to third parties
- You have full control over the code

Enjoy your automated QuickBooks workflow! 🎉
