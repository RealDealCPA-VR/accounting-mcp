# QuickBooks MCP Server

A custom Model Context Protocol (MCP) server for QuickBooks Online and Desktop integration, built specifically for accounting professionals during tax season.

## 🎯 Features

### Phase 1: Data Entry Automation (Priority)
- **PDF Parser**: Extract transaction data from bank statements, invoices, and receipts
- **CSV Importer**: Import structured transaction data with intelligent mapping
- **AI-Powered Account Mapping**: Automatically match transactions to chart of accounts
- **Batch Import**: Process multiple transactions with validation and duplicate detection
- **Transaction Creation**: Create invoices, expenses, bills, and journal entries in QuickBooks Online

### Phase 2: Bank Reconciliation
- Fetch bank transactions from QuickBooks Online
- Auto-match transactions using fuzzy matching algorithms
- Generate reconciliation reports
- Flag discrepancies for review

### Phase 3: Tax Mapping & Reporting
- Extract data for tax return preparation
- Generate Excel reports for UltraTax integration
- Create custom financial reports with tax categories
- Audit trail and documentation generation

### Phase 4: QuickBooks Desktop Integration
- Direct access to QBD company files on local network
- QBO ↔ QBD migration tools
- Data validation and integrity checks

## 🚀 Installation

### Prerequisites
- Python 3.10 or higher
- Windows 11 (for QuickBooks Desktop integration)
- QuickBooks Online API credentials
- QuickBooks Desktop installed (for QBD features)

### Setup

1. **Clone or download this MCP server**
   ```bash
   cd quickbooks-mcp-server
   ```

2. **Install dependencies**
   ```bash
   pip install -e .
   ```

3. **Configure credentials**
   - Copy `.env.example` to `.env`
   - Add your QuickBooks Online API credentials
   - Configure company IDs

4. **Run the MCP server**
   ```bash
   python -m quickbooks_mcp
   ```

## 🔧 Configuration

Edit the `.env` file with your credentials:

```env
# QuickBooks Online API Credentials
QBO_CLIENT_ID=your_client_id
QBO_CLIENT_SECRET=your_client_secret
QBO_REDIRECT_URI=https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl
QBO_ENVIRONMENT=production

# Company IDs (from your screenshot)
QBO_COMPANY_IDS=9341455432557951,327838186,1020164455,1041511280,1161420580

# Default company for operations
QBO_DEFAULT_COMPANY_ID=327838186

# QuickBooks Desktop Settings
QBD_COMPANY_FILE_PATH=\\\\server\\quickbooks\\company_files
QBD_ENABLE=true

# Data Entry Settings
DATA_ENTRY_AUTO_MATCH_THRESHOLD=0.85
DATA_ENTRY_DUPLICATE_CHECK=true
```

## 📖 Usage

### Connecting to Your Agent

1. **Add MCP server to your agent configuration**
   - The server will be available at `stdio` transport
   - All tools will be automatically discovered

2. **Available MCP Tools**:
   - `qbo_parse_pdf_transactions`: Extract transactions from PDF files
   - `qbo_import_csv_transactions`: Import transactions from CSV
   - `qbo_create_invoice`: Create invoices in QuickBooks Online
   - `qbo_create_expense`: Create expenses in QuickBooks Online
   - `qbo_create_journal_entry`: Create journal entries
   - `qbo_get_chart_of_accounts`: Fetch chart of accounts
   - `qbo_match_account`: AI-powered account matching
   - `qbo_batch_import`: Batch import with validation
   - `qbo_get_bank_transactions`: Fetch bank transactions
   - `qbo_reconcile_bank`: Auto-reconcile bank accounts
   - `qbo_generate_tax_report`: Generate tax mapping reports
   - `qbd_read_company_file`: Read QuickBooks Desktop data
   - `qbd_migrate_to_qbo`: Migrate QBD to QBO
   - `qbo_migrate_to_qbd`: Migrate QBO to QBD

### Example Workflows

**Data Entry from PDF:**
```
Agent: "Import transactions from this bank statement PDF"
→ Parses PDF → Extracts transactions → Matches accounts → Creates in QBO
```

**CSV Import:**
```
Agent: "Import these expenses from CSV"
→ Reads CSV → Validates data → Maps accounts → Batch imports to QBO
```

**Bank Reconciliation:**
```
Agent: "Reconcile Chase bank account for January 2026"
→ Fetches QBO transactions → Matches with bank data → Generates report
```

## 🏗️ Architecture

```
quickbooks-mcp-server/
├── src/
│   ├── quickbooks_mcp/
│   │   ├── __init__.py
│   │   ├── server.py              # Main MCP server
│   │   ├── qbo/
│   │   │   ├── auth.py            # OAuth authentication
│   │   │   ├── client.py          # QBO API client
│   │   │   ├── transactions.py    # Transaction operations
│   │   │   ├── accounts.py        # Chart of accounts
│   │   │   └── reports.py         # Reporting tools
│   │   ├── qbd/
│   │   │   ├── reader.py          # QBD file reader
│   │   │   └── migration.py       # Migration tools
│   │   ├── parsers/
│   │   │   ├── pdf_parser.py      # PDF extraction
│   │   │   ├── csv_parser.py      # CSV import
│   │   │   └── ai_matcher.py      # AI account matching
│   │   └── utils/
│   │       ├── validation.py      # Data validation
│   │       └── excel.py           # Excel generation
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

## 🔐 Security

- OAuth 2.0 for QuickBooks Online authentication
- Credentials stored in `.env` file (never committed to git)
- Local file access only for QuickBooks Desktop
- All API calls use HTTPS

## 📝 License

Proprietary - Built for internal use

## 🤝 Support

For issues or questions, contact your AI agent administrator.
