"""
Main MCP server implementation for QuickBooks integration.
Provides tools for data entry automation, bank reconciliation, tax reporting, and migrations.
"""
import os
import logging
from typing import Any, Sequence
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from pydantic import AnyUrl
import mcp.server.stdio

from .qbo.auth import QBOAuthManager
from .qbo.client import QBOClient
from .qbo.transactions import TransactionManager
from .qbo.accounts import AccountManager
from .qbo.reports import ReportManager
from .parsers.pdf_parser import PDFParser
from .parsers.csv_parser import CSVParser
from .parsers.ai_matcher import AIAccountMatcher
from .utils.validation import DataValidator

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.getenv("LOG_FILE", "quickbooks_mcp.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize MCP server
app = Server("quickbooks-mcp-server")

# Global instances (initialized on startup)
auth_manager: QBOAuthManager = None
qbo_client: QBOClient = None
transaction_manager: TransactionManager = None
account_manager: AccountManager = None
report_manager: ReportManager = None
pdf_parser: PDFParser = None
csv_parser: CSVParser = None
ai_matcher: AIAccountMatcher = None
validator: DataValidator = None


@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    List all available QuickBooks MCP tools.
    Organized by priority: Data Entry → Bank Rec → Tax Reporting → Migrations
    """
    return [
        # ===== PHASE 1: DATA ENTRY AUTOMATION (PRIORITY) =====
        Tool(
            name="qbo_parse_pdf_transactions",
            description=(
                "Extract transaction data from PDF files (bank statements, invoices, receipts). "
                "Uses OCR and AI to identify dates, amounts, descriptions, and vendors. "
                "Returns structured transaction data ready for import."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_path": {
                        "type": "string",
                        "description": "Path to the PDF file to parse"
                    },
                    "document_type": {
                        "type": "string",
                        "enum": ["bank_statement", "invoice", "receipt", "general"],
                        "description": "Type of document for optimized parsing"
                    },
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID (optional, uses default if not provided)"
                    }
                },
                "required": ["pdf_path"]
            }
        ),
        Tool(
            name="qbo_import_csv_transactions",
            description=(
                "Import transactions from CSV file with intelligent column mapping. "
                "Automatically detects date, amount, description, and vendor columns. "
                "Supports custom mapping and validation before import."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "csv_path": {
                        "type": "string",
                        "description": "Path to the CSV file to import"
                    },
                    "transaction_type": {
                        "type": "string",
                        "enum": ["expense", "invoice", "bill", "journal_entry"],
                        "description": "Type of transactions in the CSV"
                    },
                    "column_mapping": {
                        "type": "object",
                        "description": "Optional custom column mapping (auto-detected if not provided)"
                    },
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    }
                },
                "required": ["csv_path", "transaction_type"]
            }
        ),
        Tool(
            name="qbo_match_account",
            description=(
                "AI-powered account matching for transactions. "
                "Uses fuzzy matching and historical patterns to suggest the best chart of accounts match. "
                "Returns confidence score and alternative suggestions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Transaction description or vendor name"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Transaction amount (optional, helps with matching)"
                    },
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    }
                },
                "required": ["description", "company_id"]
            }
        ),
        Tool(
            name="qbo_create_expense",
            description=(
                "Create an expense transaction in QuickBooks Online. "
                "Supports vendor, account, amount, date, and memo. "
                "Includes duplicate detection and validation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "vendor_name": {
                        "type": "string",
                        "description": "Vendor or payee name"
                    },
                    "account_name": {
                        "type": "string",
                        "description": "Expense account name from chart of accounts"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Transaction amount"
                    },
                    "date": {
                        "type": "string",
                        "description": "Transaction date (YYYY-MM-DD format)"
                    },
                    "memo": {
                        "type": "string",
                        "description": "Optional memo or description"
                    },
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    }
                },
                "required": ["vendor_name", "account_name", "amount", "date", "company_id"]
            }
        ),
        Tool(
            name="qbo_create_invoice",
            description=(
                "Create an invoice in QuickBooks Online. "
                "Supports customer, line items, due date, and terms."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name"
                    },
                    "line_items": {
                        "type": "array",
                        "description": "Invoice line items with description, quantity, rate, and account",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "quantity": {"type": "number"},
                                "rate": {"type": "number"},
                                "account_name": {"type": "string"}
                            }
                        }
                    },
                    "invoice_date": {
                        "type": "string",
                        "description": "Invoice date (YYYY-MM-DD)"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date (YYYY-MM-DD)"
                    },
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    }
                },
                "required": ["customer_name", "line_items", "invoice_date", "company_id"]
            }
        ),
        Tool(
            name="qbo_create_journal_entry",
            description=(
                "Create a journal entry in QuickBooks Online. "
                "Supports multiple debit and credit lines with accounts and amounts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Journal entry date (YYYY-MM-DD)"
                    },
                    "lines": {
                        "type": "array",
                        "description": "Journal entry lines (must balance)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "account_name": {"type": "string"},
                                "debit": {"type": "number"},
                                "credit": {"type": "number"},
                                "description": {"type": "string"}
                            }
                        }
                    },
                    "memo": {
                        "type": "string",
                        "description": "Optional memo"
                    },
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    }
                },
                "required": ["date", "lines", "company_id"]
            }
        ),
        Tool(
            name="qbo_batch_import",
            description=(
                "Batch import multiple transactions with validation and duplicate detection. "
                "Processes transactions in batches, provides progress updates, and error handling. "
                "Returns summary of successful and failed imports."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "transactions": {
                        "type": "array",
                        "description": "Array of transactions to import",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["expense", "invoice", "journal_entry"]},
                                "data": {"type": "object"}
                            }
                        }
                    },
                    "validate_only": {
                        "type": "boolean",
                        "description": "If true, only validates without importing"
                    },
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    }
                },
                "required": ["transactions", "company_id"]
            }
        ),
        Tool(
            name="qbo_get_chart_of_accounts",
            description=(
                "Fetch the complete chart of accounts from QuickBooks Online. "
                "Returns account names, types, and IDs for mapping purposes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    },
                    "account_type": {
                        "type": "string",
                        "enum": ["all", "expense", "income", "asset", "liability", "equity"],
                        "description": "Filter by account type"
                    }
                },
                "required": ["company_id"]
            }
        ),
        
        # ===== PHASE 2: BANK RECONCILIATION =====
        Tool(
            name="qbo_get_bank_transactions",
            description=(
                "Fetch bank transactions from QuickBooks Online for reconciliation. "
                "Supports date range filtering and account selection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "account_name": {
                        "type": "string",
                        "description": "Bank account name"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (YYYY-MM-DD)"
                    },
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    }
                },
                "required": ["account_name", "start_date", "end_date", "company_id"]
            }
        ),
        Tool(
            name="qbo_reconcile_bank",
            description=(
                "Auto-reconcile bank account using fuzzy matching. "
                "Matches QBO transactions with bank statement data. "
                "Returns matched, unmatched, and discrepancy reports."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "account_name": {
                        "type": "string",
                        "description": "Bank account name"
                    },
                    "bank_statement_path": {
                        "type": "string",
                        "description": "Path to bank statement (PDF or CSV)"
                    },
                    "statement_date": {
                        "type": "string",
                        "description": "Statement ending date (YYYY-MM-DD)"
                    },
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    }
                },
                "required": ["account_name", "bank_statement_path", "statement_date", "company_id"]
            }
        ),
        
        # ===== PHASE 3: TAX MAPPING & REPORTING =====
        Tool(
            name="qbo_generate_tax_report",
            description=(
                "Generate tax mapping report for UltraTax integration. "
                "Extracts P&L and Balance Sheet data organized by tax categories. "
                "Exports to Excel format compatible with UltraTax."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Report start date (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Report end date (YYYY-MM-DD)"
                    },
                    "report_type": {
                        "type": "string",
                        "enum": ["profit_loss", "balance_sheet", "both"],
                        "description": "Type of tax report to generate"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save Excel report"
                    }
                },
                "required": ["company_id", "start_date", "end_date", "report_type", "output_path"]
            }
        ),
        Tool(
            name="qbo_get_financial_report",
            description=(
                "Get standard financial reports (P&L, Balance Sheet, Cash Flow). "
                "Returns formatted data with account details and totals."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "QuickBooks company ID"
                    },
                    "report_type": {
                        "type": "string",
                        "enum": ["profit_loss", "balance_sheet", "cash_flow"],
                        "description": "Type of financial report"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Report start date (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Report end date (YYYY-MM-DD)"
                    }
                },
                "required": ["company_id", "report_type", "start_date", "end_date"]
            }
        ),
        
        # ===== PHASE 4: QUICKBOOKS DESKTOP INTEGRATION =====
        Tool(
            name="qbd_read_company_file",
            description=(
                "Read data from QuickBooks Desktop company file on local network. "
                "Extracts chart of accounts, transactions, and reports. "
                "Requires QBD file path on accessible network share."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_file_path": {
                        "type": "string",
                        "description": "Network path to QBD company file"
                    },
                    "data_type": {
                        "type": "string",
                        "enum": ["accounts", "transactions", "customers", "vendors", "all"],
                        "description": "Type of data to extract"
                    },
                    "date_range": {
                        "type": "object",
                        "description": "Optional date range for transactions",
                        "properties": {
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"}
                        }
                    }
                },
                "required": ["company_file_path", "data_type"]
            }
        ),
        Tool(
            name="qbd_migrate_to_qbo",
            description=(
                "Migrate QuickBooks Desktop data to QuickBooks Online. "
                "Handles chart of accounts, customers, vendors, and transactions. "
                "Includes data validation and mapping."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "qbd_file_path": {
                        "type": "string",
                        "description": "Path to QBD company file"
                    },
                    "qbo_company_id": {
                        "type": "string",
                        "description": "Target QBO company ID"
                    },
                    "migration_options": {
                        "type": "object",
                        "description": "Migration settings",
                        "properties": {
                            "include_transactions": {"type": "boolean"},
                            "include_customers": {"type": "boolean"},
                            "include_vendors": {"type": "boolean"},
                            "date_cutoff": {"type": "string"}
                        }
                    }
                },
                "required": ["qbd_file_path", "qbo_company_id"]
            }
        ),
        Tool(
            name="qbo_migrate_to_qbd",
            description=(
                "Migrate QuickBooks Online data to QuickBooks Desktop. "
                "Exports data in IIF format compatible with QBD import. "
                "Includes validation and formatting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "qbo_company_id": {
                        "type": "string",
                        "description": "Source QBO company ID"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save IIF export file"
                    },
                    "migration_options": {
                        "type": "object",
                        "description": "Migration settings",
                        "properties": {
                            "include_transactions": {"type": "boolean"},
                            "include_customers": {"type": "boolean"},
                            "include_vendors": {"type": "boolean"},
                            "date_cutoff": {"type": "string"}
                        }
                    }
                },
                "required": ["qbo_company_id", "output_path"]
            }
        ),
        
        # ===== UTILITY TOOLS =====
        Tool(
            name="qbo_list_companies",
            description=(
                "List all available QuickBooks Online companies configured in this MCP server. "
                "Returns company IDs and names."
            ),
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="qbo_validate_credentials",
            description=(
                "Validate QuickBooks Online API credentials and test connection. "
                "Checks OAuth tokens and company access."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "Company ID to test (optional, tests default if not provided)"
                    }
                }
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """
    Handle tool calls from the MCP client.
    Routes to appropriate handler based on tool name.
    """
    try:
        logger.info(f"Tool called: {name} with arguments: {arguments}")
        
        # Route to appropriate handler
        if name.startswith("qbo_parse_pdf"):
            return await handle_pdf_parse(arguments)
        elif name.startswith("qbo_import_csv"):
            return await handle_csv_import(arguments)
        elif name.startswith("qbo_match_account"):
            return await handle_account_match(arguments)
        elif name.startswith("qbo_create_expense"):
            return await handle_create_expense(arguments)
        elif name.startswith("qbo_create_invoice"):
            return await handle_create_invoice(arguments)
        elif name.startswith("qbo_create_journal"):
            return await handle_create_journal_entry(arguments)
        elif name.startswith("qbo_batch_import"):
            return await handle_batch_import(arguments)
        elif name.startswith("qbo_get_chart"):
            return await handle_get_chart_of_accounts(arguments)
        elif name.startswith("qbo_get_bank"):
            return await handle_get_bank_transactions(arguments)
        elif name.startswith("qbo_reconcile"):
            return await handle_bank_reconciliation(arguments)
        elif name.startswith("qbo_generate_tax"):
            return await handle_generate_tax_report(arguments)
        elif name.startswith("qbo_get_financial"):
            return await handle_get_financial_report(arguments)
        elif name.startswith("qbd_read"):
            return await handle_qbd_read(arguments)
        elif name.startswith("qbd_migrate_to_qbo"):
            return await handle_qbd_to_qbo_migration(arguments)
        elif name.startswith("qbo_migrate_to_qbd"):
            return await handle_qbo_to_qbd_migration(arguments)
        elif name.startswith("qbo_list_companies"):
            return await handle_list_companies(arguments)
        elif name.startswith("qbo_validate"):
            return await handle_validate_credentials(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error executing {name}: {str(e)}"
        )]


# ===== TOOL HANDLERS (Implementations) =====

async def handle_pdf_parse(arguments: dict) -> Sequence[TextContent]:
    """Parse PDF and extract transaction data."""
    pdf_path = arguments["pdf_path"]
    doc_type = arguments.get("document_type", "general")
    company_id = arguments.get("company_id", os.getenv("QBO_DEFAULT_COMPANY_ID"))
    
    logger.info(f"Parsing PDF: {pdf_path} (type: {doc_type})")
    
    # Parse PDF
    transactions = await pdf_parser.parse_pdf(pdf_path, doc_type)
    
    # Match accounts using AI
    for txn in transactions:
        match = await ai_matcher.match_account(
            txn["description"],
            txn.get("amount"),
            company_id
        )
        txn["suggested_account"] = match["account_name"]
        txn["confidence"] = match["confidence"]
    
    result = {
        "success": True,
        "transactions_found": len(transactions),
        "transactions": transactions,
        "message": f"Successfully extracted {len(transactions)} transactions from PDF"
    }
    
    return [TextContent(type="text", text=str(result))]


async def handle_csv_import(arguments: dict) -> Sequence[TextContent]:
    """Import transactions from CSV file."""
    csv_path = arguments["csv_path"]
    txn_type = arguments["transaction_type"]
    column_mapping = arguments.get("column_mapping")
    company_id = arguments.get("company_id", os.getenv("QBO_DEFAULT_COMPANY_ID"))
    
    logger.info(f"Importing CSV: {csv_path} (type: {txn_type})")
    
    # Parse CSV
    transactions = await csv_parser.parse_csv(csv_path, txn_type, column_mapping)
    
    # Validate transactions
    validation_results = await validator.validate_transactions(transactions, company_id)
    
    result = {
        "success": True,
        "transactions_found": len(transactions),
        "valid_transactions": validation_results["valid_count"],
        "invalid_transactions": validation_results["invalid_count"],
        "transactions": transactions,
        "validation_errors": validation_results["errors"]
    }
    
    return [TextContent(type="text", text=str(result))]


async def handle_account_match(arguments: dict) -> Sequence[TextContent]:
    """Match transaction description to chart of accounts."""
    description = arguments["description"]
    amount = arguments.get("amount")
    company_id = arguments["company_id"]
    
    match = await ai_matcher.match_account(description, amount, company_id)
    
    return [TextContent(type="text", text=str(match))]


async def handle_create_expense(arguments: dict) -> Sequence[TextContent]:
    """Create expense in QuickBooks Online."""
    company_id = arguments["company_id"]
    
    result = await transaction_manager.create_expense(
        company_id=company_id,
        vendor_name=arguments["vendor_name"],
        account_name=arguments["account_name"],
        amount=arguments["amount"],
        date=arguments["date"],
        memo=arguments.get("memo", "")
    )
    
    return [TextContent(type="text", text=str(result))]


async def handle_create_invoice(arguments: dict) -> Sequence[TextContent]:
    """Create invoice in QuickBooks Online."""
    company_id = arguments["company_id"]
    
    result = await transaction_manager.create_invoice(
        company_id=company_id,
        customer_name=arguments["customer_name"],
        line_items=arguments["line_items"],
        invoice_date=arguments["invoice_date"],
        due_date=arguments.get("due_date")
    )
    
    return [TextContent(type="text", text=str(result))]


async def handle_create_journal_entry(arguments: dict) -> Sequence[TextContent]:
    """Create journal entry in QuickBooks Online."""
    company_id = arguments["company_id"]
    
    result = await transaction_manager.create_journal_entry(
        company_id=company_id,
        date=arguments["date"],
        lines=arguments["lines"],
        memo=arguments.get("memo", "")
    )
    
    return [TextContent(type="text", text=str(result))]


async def handle_batch_import(arguments: dict) -> Sequence[TextContent]:
    """Batch import multiple transactions."""
    company_id = arguments["company_id"]
    transactions = arguments["transactions"]
    validate_only = arguments.get("validate_only", False)
    
    result = await transaction_manager.batch_import(
        company_id=company_id,
        transactions=transactions,
        validate_only=validate_only
    )
    
    return [TextContent(type="text", text=str(result))]


async def handle_get_chart_of_accounts(arguments: dict) -> Sequence[TextContent]:
    """Get chart of accounts from QuickBooks Online."""
    company_id = arguments["company_id"]
    account_type = arguments.get("account_type", "all")
    
    accounts = await account_manager.get_chart_of_accounts(company_id, account_type)
    
    return [TextContent(type="text", text=str(accounts))]


async def handle_get_bank_transactions(arguments: dict) -> Sequence[TextContent]:
    """Get bank transactions for reconciliation."""
    company_id = arguments["company_id"]
    
    transactions = await transaction_manager.get_bank_transactions(
        company_id=company_id,
        account_name=arguments["account_name"],
        start_date=arguments["start_date"],
        end_date=arguments["end_date"]
    )
    
    return [TextContent(type="text", text=str(transactions))]


async def handle_bank_reconciliation(arguments: dict) -> Sequence[TextContent]:
    """Auto-reconcile bank account."""
    company_id = arguments["company_id"]
    
    result = await transaction_manager.reconcile_bank(
        company_id=company_id,
        account_name=arguments["account_name"],
        bank_statement_path=arguments["bank_statement_path"],
        statement_date=arguments["statement_date"]
    )
    
    return [TextContent(type="text", text=str(result))]


async def handle_generate_tax_report(arguments: dict) -> Sequence[TextContent]:
    """Generate tax mapping report."""
    company_id = arguments["company_id"]
    
    result = await report_manager.generate_tax_report(
        company_id=company_id,
        start_date=arguments["start_date"],
        end_date=arguments["end_date"],
        report_type=arguments["report_type"],
        output_path=arguments["output_path"]
    )
    
    return [TextContent(type="text", text=str(result))]


async def handle_get_financial_report(arguments: dict) -> Sequence[TextContent]:
    """Get financial report."""
    company_id = arguments["company_id"]
    
    report = await report_manager.get_financial_report(
        company_id=company_id,
        report_type=arguments["report_type"],
        start_date=arguments["start_date"],
        end_date=arguments["end_date"]
    )
    
    return [TextContent(type="text", text=str(report))]


async def handle_qbd_read(arguments: dict) -> Sequence[TextContent]:
    """Read QuickBooks Desktop company file."""
    # QBD implementation (Phase 5)
    return [TextContent(type="text", text="QuickBooks Desktop integration coming in Phase 5")]


async def handle_qbd_to_qbo_migration(arguments: dict) -> Sequence[TextContent]:
    """Migrate QBD to QBO."""
    # Migration implementation (Phase 5)
    return [TextContent(type="text", text="QBD to QBO migration coming in Phase 5")]


async def handle_qbo_to_qbd_migration(arguments: dict) -> Sequence[TextContent]:
    """Migrate QBO to QBD."""
    # Migration implementation (Phase 5)
    return [TextContent(type="text", text="QBO to QBD migration coming in Phase 5")]


async def handle_list_companies(arguments: dict) -> Sequence[TextContent]:
    """List available companies."""
    companies = os.getenv("QBO_COMPANY_IDS", "").split(",")
    result = {
        "companies": [{"id": cid.strip()} for cid in companies if cid.strip()],
        "default_company": os.getenv("QBO_DEFAULT_COMPANY_ID")
    }
    return [TextContent(type="text", text=str(result))]


async def handle_validate_credentials(arguments: dict) -> Sequence[TextContent]:
    """Validate QuickBooks credentials."""
    company_id = arguments.get("company_id", os.getenv("QBO_DEFAULT_COMPANY_ID"))
    
    is_valid = await auth_manager.validate_credentials(company_id)
    
    result = {
        "valid": is_valid,
        "company_id": company_id,
        "message": "Credentials are valid" if is_valid else "Credentials are invalid or expired"
    }
    
    return [TextContent(type="text", text=str(result))]


async def main():
    """Main entry point for the MCP server."""
    global auth_manager, qbo_client, transaction_manager, account_manager, report_manager
    global pdf_parser, csv_parser, ai_matcher, validator
    
    logger.info("Starting QuickBooks MCP Server...")
    
    # Initialize components
    auth_manager = QBOAuthManager()
    qbo_client = QBOClient(auth_manager)
    transaction_manager = TransactionManager(qbo_client)
    account_manager = AccountManager(qbo_client)
    report_manager = ReportManager(qbo_client)
    pdf_parser = PDFParser()
    csv_parser = CSVParser()
    ai_matcher = AIAccountMatcher(account_manager)
    validator = DataValidator(account_manager)
    
    logger.info("QuickBooks MCP Server initialized successfully")
    
    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
