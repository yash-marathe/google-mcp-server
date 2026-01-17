"""
Google MCP Server - Complete Implementation

A comprehensive Model Context Protocol server for Google Workspace integration.
Provides tools for Google Docs, Sheets, and Drive operations.

Author: Yash Marathe
License: MIT
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime
import asyncio

# MCP and Google API imports
try:
    import mcp.types as types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ImportError:
    raise ImportError("Please install mcp package: pip install mcp")

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
except ImportError:
    raise ImportError(
        "Please install Google API packages: "
        "pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google API Scopes
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

# Modal deployment configuration (optional)
try:
    import modal
    MODAL_AVAILABLE = True
except ImportError:
    MODAL_AVAILABLE = False
    logger.warning("Modal not available. Deployment features disabled.")


class GoogleAPIClient:
    """Manages Google API authentication and service clients."""
    
    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        """
        Initialize Google API client.
        
        Args:
            credentials_path: Path to OAuth2 credentials JSON file
            token_path: Path to store/load authentication token
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds: Optional[Credentials] = None
        self._docs_service = None
        self._sheets_service = None
        self._drive_service = None
    
    def authenticate(self) -> None:
        """Authenticate with Google APIs using OAuth2."""
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found at {self.credentials_path}. "
                        "Please download OAuth2 credentials from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            
            # Save credentials for future use
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())
        
        logger.info("Successfully authenticated with Google APIs")
    
    @property
    def docs_service(self):
        """Get or create Google Docs service."""
        if self._docs_service is None:
            self._docs_service = build('docs', 'v1', credentials=self.creds)
        return self._docs_service
    
    @property
    def sheets_service(self):
        """Get or create Google Sheets service."""
        if self._sheets_service is None:
            self._sheets_service = build('sheets', 'v4', credentials=self.creds)
        return self._sheets_service
    
    @property
    def drive_service(self):
        """Get or create Google Drive service."""
        if self._drive_service is None:
            self._drive_service = build('drive', 'v3', credentials=self.creds)
        return self._drive_service


class GoogleDocsTools:
    """Google Docs operations tools."""
    
    def __init__(self, api_client: GoogleAPIClient):
        self.api_client = api_client
    
    async def get_document_content(self, document_id: str) -> Dict[str, Any]:
        """
        Retrieve content from a Google Doc.
        
        Args:
            document_id: The ID of the Google Doc
            
        Returns:
            Dictionary containing document content and metadata
        """
        try:
            document = self.api_client.docs_service.documents().get(
                documentId=document_id
            ).execute()
            
            # Extract text content
            content = []
            for element in document.get('body', {}).get('content', []):
                if 'paragraph' in element:
                    for text_run in element['paragraph'].get('elements', []):
                        if 'textRun' in text_run:
                            content.append(text_run['textRun']['content'])
            
            return {
                "title": document.get('title', ''),
                "document_id": document_id,
                "content": ''.join(content),
                "revision_id": document.get('revisionId', ''),
            }
        except HttpError as e:
            logger.error(f"Error retrieving document: {e}")
            raise Exception(f"Failed to retrieve document: {str(e)}")
    
    async def create_document(self, title: str) -> Dict[str, Any]:
        """
        Create a new Google Doc.
        
        Args:
            title: Title for the new document
            
        Returns:
            Dictionary containing document ID and URL
        """
        try:
            document = self.api_client.docs_service.documents().create(
                body={'title': title}
            ).execute()
            
            return {
                "document_id": document['documentId'],
                "title": document['title'],
                "url": f"https://docs.google.com/document/d/{document['documentId']}/edit",
            }
        except HttpError as e:
            logger.error(f"Error creating document: {e}")
            raise Exception(f"Failed to create document: {str(e)}")
    
    async def update_document_content(
        self, document_id: str, content: str, start_index: int = 1
    ) -> Dict[str, Any]:
        """
        Replace content in a Google Doc.
        
        Args:
            document_id: The ID of the Google Doc
            content: New content to insert
            start_index: Character index to start insertion (default: 1)
            
        Returns:
            Dictionary with update status
        """
        try:
            requests = [
                {
                    'insertText': {
                        'location': {'index': start_index},
                        'text': content
                    }
                }
            ]
            
            result = self.api_client.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()
            
            return {
                "document_id": document_id,
                "status": "success",
                "replies": result.get('replies', [])
            }
        except HttpError as e:
            logger.error(f"Error updating document: {e}")
            raise Exception(f"Failed to update document: {str(e)}")
    
    async def append_to_document(self, document_id: str, content: str) -> Dict[str, Any]:
        """
        Add content to the end of a Google Doc.
        
        Args:
            document_id: The ID of the Google Doc
            content: Content to append
            
        Returns:
            Dictionary with append status
        """
        try:
            # Get current document to find end index
            document = self.api_client.docs_service.documents().get(
                documentId=document_id
            ).execute()
            
            end_index = document.get('body', {}).get('content', [{}])[-1].get('endIndex', 1) - 1
            
            requests = [
                {
                    'insertText': {
                        'location': {'index': end_index},
                        'text': content
                    }
                }
            ]
            
            result = self.api_client.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()
            
            return {
                "document_id": document_id,
                "status": "success",
                "appended_at_index": end_index
            }
        except HttpError as e:
            logger.error(f"Error appending to document: {e}")
            raise Exception(f"Failed to append to document: {str(e)}")
    
    async def delete_document_content(
        self, document_id: str, start_index: int, end_index: int
    ) -> Dict[str, Any]:
        """
        Remove content from a Google Doc.
        
        Args:
            document_id: The ID of the Google Doc
            start_index: Start position of content to delete
            end_index: End position of content to delete
            
        Returns:
            Dictionary with deletion status
        """
        try:
            requests = [
                {
                    'deleteContentRange': {
                        'range': {
                            'startIndex': start_index,
                            'endIndex': end_index
                        }
                    }
                }
            ]
            
            result = self.api_client.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()
            
            return {
                "document_id": document_id,
                "status": "success",
                "deleted_range": f"{start_index}-{end_index}"
            }
        except HttpError as e:
            logger.error(f"Error deleting document content: {e}")
            raise Exception(f"Failed to delete content: {str(e)}")
    
    async def format_document_text(
        self,
        document_id: str,
        start_index: int,
        end_index: int,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        underline: Optional[bool] = None,
        font_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Apply formatting to document text.
        
        Args:
            document_id: The ID of the Google Doc
            start_index: Start position for formatting
            end_index: End position for formatting
            bold: Apply bold formatting
            italic: Apply italic formatting
            underline: Apply underline formatting
            font_size: Set font size in points
            
        Returns:
            Dictionary with formatting status
        """
        try:
            text_style = {}
            if bold is not None:
                text_style['bold'] = bold
            if italic is not None:
                text_style['italic'] = italic
            if underline is not None:
                text_style['underline'] = underline
            if font_size is not None:
                text_style['fontSize'] = {'magnitude': font_size, 'unit': 'PT'}
            
            requests = [
                {
                    'updateTextStyle': {
                        'range': {
                            'startIndex': start_index,
                            'endIndex': end_index
                        },
                        'textStyle': text_style,
                        'fields': ','.join(text_style.keys())
                    }
                }
            ]
            
            result = self.api_client.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()
            
            return {
                "document_id": document_id,
                "status": "success",
                "formatted_range": f"{start_index}-{end_index}",
                "applied_styles": list(text_style.keys())
            }
        except HttpError as e:
            logger.error(f"Error formatting document text: {e}")
            raise Exception(f"Failed to format text: {str(e)}")
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete a Google Doc.
        
        Args:
            document_id: The ID of the Google Doc to delete
            
        Returns:
            Dictionary with deletion status
        """
        try:
            self.api_client.drive_service.files().delete(fileId=document_id).execute()
            
            return {
                "document_id": document_id,
                "status": "deleted",
                "timestamp": datetime.now().isoformat()
            }
        except HttpError as e:
            logger.error(f"Error deleting document: {e}")
            raise Exception(f"Failed to delete document: {str(e)}")


class GoogleSheetsTools:
    """Google Sheets operations tools."""
    
    def __init__(self, api_client: GoogleAPIClient):
        self.api_client = api_client
    
    async def get_sheet_data(
        self, spreadsheet_id: str, range_name: str
    ) -> Dict[str, Any]:
        """
        Get data from a spreadsheet range.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: A1 notation range (e.g., 'Sheet1!A1:D10')
            
        Returns:
            Dictionary containing range data
        """
        try:
            result = self.api_client.sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "range": result.get('range', ''),
                "values": result.get('values', []),
                "row_count": len(result.get('values', [])),
            }
        except HttpError as e:
            logger.error(f"Error getting sheet data: {e}")
            raise Exception(f"Failed to get sheet data: {str(e)}")
    
    async def create_spreadsheet(self, title: str) -> Dict[str, Any]:
        """
        Create a new Google Spreadsheet.
        
        Args:
            title: Title for the new spreadsheet
            
        Returns:
            Dictionary containing spreadsheet ID and URL
        """
        try:
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            
            result = self.api_client.sheets_service.spreadsheets().create(
                body=spreadsheet
            ).execute()
            
            return {
                "spreadsheet_id": result['spreadsheetId'],
                "title": title,
                "url": result['spreadsheetUrl'],
            }
        except HttpError as e:
            logger.error(f"Error creating spreadsheet: {e}")
            raise Exception(f"Failed to create spreadsheet: {str(e)}")
    
    async def update_sheet_data(
        self, spreadsheet_id: str, range_name: str, values: List[List[Any]]
    ) -> Dict[str, Any]:
        """
        Update specific cells/ranges in a sheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: A1 notation range
            values: 2D array of values to update
            
        Returns:
            Dictionary with update status
        """
        try:
            body = {
                'values': values
            }
            
            result = self.api_client.sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "updated_range": result.get('updatedRange', ''),
                "updated_rows": result.get('updatedRows', 0),
                "updated_columns": result.get('updatedColumns', 0),
                "updated_cells": result.get('updatedCells', 0),
            }
        except HttpError as e:
            logger.error(f"Error updating sheet data: {e}")
            raise Exception(f"Failed to update sheet data: {str(e)}")
    
    async def append_sheet_data(
        self, spreadsheet_id: str, range_name: str, values: List[List[Any]]
    ) -> Dict[str, Any]:
        """
        Add new rows to a sheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: A1 notation range
            values: 2D array of values to append
            
        Returns:
            Dictionary with append status
        """
        try:
            body = {
                'values': values
            }
            
            result = self.api_client.sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "updated_range": result.get('updates', {}).get('updatedRange', ''),
                "updated_rows": result.get('updates', {}).get('updatedRows', 0),
                "updated_cells": result.get('updates', {}).get('updatedCells', 0),
            }
        except HttpError as e:
            logger.error(f"Error appending sheet data: {e}")
            raise Exception(f"Failed to append sheet data: {str(e)}")
    
    async def clear_sheet_range(
        self, spreadsheet_id: str, range_name: str
    ) -> Dict[str, Any]:
        """
        Clear content from a range.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: A1 notation range to clear
            
        Returns:
            Dictionary with clear status
        """
        try:
            result = self.api_client.sheets_service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body={}
            ).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "cleared_range": result.get('clearedRange', ''),
                "status": "success"
            }
        except HttpError as e:
            logger.error(f"Error clearing sheet range: {e}")
            raise Exception(f"Failed to clear range: {str(e)}")
    
    async def add_sheet_rows(
        self, spreadsheet_id: str, sheet_id: int, start_index: int, count: int
    ) -> Dict[str, Any]:
        """
        Insert new rows in a sheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            sheet_id: The ID of the sheet (0 for first sheet)
            start_index: Index to insert rows at
            count: Number of rows to insert
            
        Returns:
            Dictionary with insertion status
        """
        try:
            requests = [
                {
                    'insertDimension': {
                        'range': {
                            'sheetId': sheet_id,
                            'dimension': 'ROWS',
                            'startIndex': start_index,
                            'endIndex': start_index + count
                        },
                        'inheritFromBefore': False
                    }
                }
            ]
            
            result = self.api_client.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "sheet_id": sheet_id,
                "rows_inserted": count,
                "start_index": start_index,
                "status": "success"
            }
        except HttpError as e:
            logger.error(f"Error adding sheet rows: {e}")
            raise Exception(f"Failed to add rows: {str(e)}")
    
    async def add_sheet_columns(
        self, spreadsheet_id: str, sheet_id: int, start_index: int, count: int
    ) -> Dict[str, Any]:
        """
        Insert new columns in a sheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            sheet_id: The ID of the sheet (0 for first sheet)
            start_index: Index to insert columns at
            count: Number of columns to insert
            
        Returns:
            Dictionary with insertion status
        """
        try:
            requests = [
                {
                    'insertDimension': {
                        'range': {
                            'sheetId': sheet_id,
                            'dimension': 'COLUMNS',
                            'startIndex': start_index,
                            'endIndex': start_index + count
                        },
                        'inheritFromBefore': False
                    }
                }
            ]
            
            result = self.api_client.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "sheet_id": sheet_id,
                "columns_inserted": count,
                "start_index": start_index,
                "status": "success"
            }
        except HttpError as e:
            logger.error(f"Error adding sheet columns: {e}")
            raise Exception(f"Failed to add columns: {str(e)}")
    
    async def delete_sheet_rows(
        self, spreadsheet_id: str, sheet_id: int, start_index: int, end_index: int
    ) -> Dict[str, Any]:
        """
        Delete rows from a sheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            sheet_id: The ID of the sheet (0 for first sheet)
            start_index: Start row index (inclusive)
            end_index: End row index (exclusive)
            
        Returns:
            Dictionary with deletion status
        """
        try:
            requests = [
                {
                    'deleteDimension': {
                        'range': {
                            'sheetId': sheet_id,
                            'dimension': 'ROWS',
                            'startIndex': start_index,
                            'endIndex': end_index
                        }
                    }
                }
            ]
            
            result = self.api_client.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "sheet_id": sheet_id,
                "rows_deleted": end_index - start_index,
                "status": "success"
            }
        except HttpError as e:
            logger.error(f"Error deleting sheet rows: {e}")
            raise Exception(f"Failed to delete rows: {str(e)}")
    
    async def delete_sheet_columns(
        self, spreadsheet_id: str, sheet_id: int, start_index: int, end_index: int
    ) -> Dict[str, Any]:
        """
        Delete columns from a sheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            sheet_id: The ID of the sheet (0 for first sheet)
            start_index: Start column index (inclusive)
            end_index: End column index (exclusive)
            
        Returns:
            Dictionary with deletion status
        """
        try:
            requests = [
                {
                    'deleteDimension': {
                        'range': {
                            'sheetId': sheet_id,
                            'dimension': 'COLUMNS',
                            'startIndex': start_index,
                            'endIndex': end_index
                        }
                    }
                }
            ]
            
            result = self.api_client.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "sheet_id": sheet_id,
                "columns_deleted": end_index - start_index,
                "status": "success"
            }
        except HttpError as e:
            logger.error(f"Error deleting sheet columns: {e}")
            raise Exception(f"Failed to delete columns: {str(e)}")
    
    async def format_sheet_cells(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        start_row: int,
        end_row: int,
        start_col: int,
        end_col: int,
        background_color: Optional[Dict[str, float]] = None,
        text_color: Optional[Dict[str, float]] = None,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Apply formatting to cells.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            sheet_id: The ID of the sheet
            start_row: Start row index
            end_row: End row index
            start_col: Start column index
            end_col: End column index
            background_color: RGB color dict (values 0-1)
            text_color: RGB color dict (values 0-1)
            bold: Apply bold formatting
            italic: Apply italic formatting
            
        Returns:
            Dictionary with formatting status
        """
        try:
            cell_format = {}
            
            if background_color:
                cell_format['backgroundColor'] = background_color
            
            if text_color or bold is not None or italic is not None:
                text_format = {}
                if text_color:
                    text_format['foregroundColor'] = text_color
                if bold is not None:
                    text_format['bold'] = bold
                if italic is not None:
                    text_format['italic'] = italic
                cell_format['textFormat'] = text_format
            
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': start_row,
                            'endRowIndex': end_row,
                            'startColumnIndex': start_col,
                            'endColumnIndex': end_col
                        },
                        'cell': {
                            'userEnteredFormat': cell_format
                        },
                        'fields': 'userEnteredFormat(' + ','.join(cell_format.keys()) + ')'
                    }
                }
            ]
            
            result = self.api_client.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "sheet_id": sheet_id,
                "formatted_range": f"R{start_row}C{start_col}:R{end_row}C{end_col}",
                "status": "success"
            }
        except HttpError as e:
            logger.error(f"Error formatting sheet cells: {e}")
            raise Exception(f"Failed to format cells: {str(e)}")


class GoogleDriveTools:
    """Google Drive operations tools."""
    
    def __init__(self, api_client: GoogleAPIClient):
        self.api_client = api_client
    
    async def list_drive_files(
        self,
        page_size: int = 10,
        query: Optional[str] = None,
        order_by: str = "modifiedTime desc"
    ) -> Dict[str, Any]:
        """
        List files in Google Drive.
        
        Args:
            page_size: Number of files to return (max 1000)
            query: Search query (e.g., "name contains 'report'")
            order_by: Sort order
            
        Returns:
            Dictionary containing file list
        """
        try:
            results = self.api_client.drive_service.files().list(
                pageSize=page_size,
                q=query,
                orderBy=order_by,
                fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size)"
            ).execute()
            
            files = results.get('files', [])
            
            return {
                "file_count": len(files),
                "files": [
                    {
                        "id": file['id'],
                        "name": file['name'],
                        "mime_type": file.get('mimeType', ''),
                        "created_time": file.get('createdTime', ''),
                        "modified_time": file.get('modifiedTime', ''),
                        "size": file.get('size', '0'),
                    }
                    for file in files
                ],
                "next_page_token": results.get('nextPageToken', '')
            }
        except HttpError as e:
            logger.error(f"Error listing drive files: {e}")
            raise Exception(f"Failed to list files: {str(e)}")
    
    async def upload_file_to_drive(
        self,
        file_path: str,
        name: Optional[str] = None,
        mime_type: Optional[str] = None,
        folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Path to the file to upload
            name: Name for the file in Drive (defaults to original filename)
            mime_type: MIME type of the file
            folder_id: Optional parent folder ID
            
        Returns:
            Dictionary with uploaded file info
        """
        try:
            file_name = name or os.path.basename(file_path)
            file_metadata = {'name': file_name}
            
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            
            file = self.api_client.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType, webViewLink'
            ).execute()
            
            return {
                "file_id": file['id'],
                "name": file['name'],
                "mime_type": file.get('mimeType', ''),
                "url": file.get('webViewLink', ''),
                "status": "uploaded"
            }
        except HttpError as e:
            logger.error(f"Error uploading file: {e}")
            raise Exception(f"Failed to upload file: {str(e)}")
    
    async def delete_drive_file(self, file_id: str) -> Dict[str, Any]:
        """
        Delete a file from Google Drive.
        
        Args:
            file_id: The ID of the file to delete
            
        Returns:
            Dictionary with deletion status
        """
        try:
            self.api_client.drive_service.files().delete(fileId=file_id).execute()
            
            return {
                "file_id": file_id,
                "status": "deleted",
                "timestamp": datetime.now().isoformat()
            }
        except HttpError as e:
            logger.error(f"Error deleting file: {e}")
            raise Exception(f"Failed to delete file: {str(e)}")
    
    async def share_drive_file(
        self,
        file_id: str,
        email: str,
        role: str = "reader",
        send_notification: bool = True
    ) -> Dict[str, Any]:
        """
        Share a file with permissions.
        
        Args:
            file_id: The ID of the file to share
            email: Email address to share with
            role: Permission role (reader, writer, commenter)
            send_notification: Send email notification
            
        Returns:
            Dictionary with sharing status
        """
        try:
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            
            result = self.api_client.drive_service.permissions().create(
                fileId=file_id,
                body=permission,
                sendNotificationEmail=send_notification,
                fields='id'
            ).execute()
            
            return {
                "file_id": file_id,
                "permission_id": result['id'],
                "shared_with": email,
                "role": role,
                "status": "shared"
            }
        except HttpError as e:
            logger.error(f"Error sharing file: {e}")
            raise Exception(f"Failed to share file: {str(e)}")
    
    async def copy_drive_file(
        self, file_id: str, new_name: str, folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make a copy of a file.
        
        Args:
            file_id: The ID of the file to copy
            new_name: Name for the copied file
            folder_id: Optional parent folder ID for the copy
            
        Returns:
            Dictionary with copied file info
        """
        try:
            body = {'name': new_name}
            if folder_id:
                body['parents'] = [folder_id]
            
            copied_file = self.api_client.drive_service.files().copy(
                fileId=file_id,
                body=body,
                fields='id, name, webViewLink'
            ).execute()
            
            return {
                "original_file_id": file_id,
                "copied_file_id": copied_file['id'],
                "name": copied_file['name'],
                "url": copied_file.get('webViewLink', ''),
                "status": "copied"
            }
        except HttpError as e:
            logger.error(f"Error copying file: {e}")
            raise Exception(f"Failed to copy file: {str(e)}")
    
    async def move_drive_file(
        self, file_id: str, new_folder_id: str, old_folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Move a file to a different location.
        
        Args:
            file_id: The ID of the file to move
            new_folder_id: ID of the destination folder
            old_folder_id: Optional ID of current folder
            
        Returns:
            Dictionary with move status
        """
        try:
            if not old_folder_id:
                # Get current parents
                file = self.api_client.drive_service.files().get(
                    fileId=file_id,
                    fields='parents'
                ).execute()
                old_folder_id = ','.join(file.get('parents', []))
            
            file = self.api_client.drive_service.files().update(
                fileId=file_id,
                addParents=new_folder_id,
                removeParents=old_folder_id,
                fields='id, name, parents'
            ).execute()
            
            return {
                "file_id": file_id,
                "name": file['name'],
                "new_parent": new_folder_id,
                "status": "moved"
            }
        except HttpError as e:
            logger.error(f"Error moving file: {e}")
            raise Exception(f"Failed to move file: {str(e)}")
    
    async def create_drive_folder(
        self, name: str, parent_folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new folder in Google Drive.
        
        Args:
            name: Name for the new folder
            parent_folder_id: Optional parent folder ID
            
        Returns:
            Dictionary with folder info
        """
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]
            
            folder = self.api_client.drive_service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink'
            ).execute()
            
            return {
                "folder_id": folder['id'],
                "name": folder['name'],
                "url": folder.get('webViewLink', ''),
                "status": "created"
            }
        except HttpError as e:
            logger.error(f"Error creating folder: {e}")
            raise Exception(f"Failed to create folder: {str(e)}")
    
    async def search_drive_files(
        self, search_term: str, file_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for files by name or type.
        
        Args:
            search_term: Search term for file names
            file_type: Optional MIME type filter
            
        Returns:
            Dictionary containing search results
        """
        try:
            query_parts = [f"name contains '{search_term}'"]
            
            if file_type:
                query_parts.append(f"mimeType='{file_type}'")
            
            query = ' and '.join(query_parts)
            
            results = self.api_client.drive_service.files().list(
                q=query,
                pageSize=20,
                fields="files(id, name, mimeType, modifiedTime, webViewLink)"
            ).execute()
            
            files = results.get('files', [])
            
            return {
                "search_term": search_term,
                "result_count": len(files),
                "files": [
                    {
                        "id": file['id'],
                        "name": file['name'],
                        "mime_type": file.get('mimeType', ''),
                        "modified_time": file.get('modifiedTime', ''),
                        "url": file.get('webViewLink', ''),
                    }
                    for file in files
                ]
            }
        except HttpError as e:
            logger.error(f"Error searching files: {e}")
            raise Exception(f"Failed to search files: {str(e)}")


class GoogleMCPServer:
    """Main MCP Server implementation for Google Workspace."""
    
    def __init__(self):
        self.server = Server("google-mcp-server")
        self.api_client = GoogleAPIClient()
        
        # Initialize tool handlers
        self.docs_tools = GoogleDocsTools(self.api_client)
        self.sheets_tools = GoogleSheetsTools(self.api_client)
        self.drive_tools = GoogleDriveTools(self.api_client)
        
        # Register all tools
        self._register_tools()
    
    def _register_tools(self):
        """Register all MCP tools with their handlers."""
        
        # Google Docs Tools
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                # Google Docs tools
                types.Tool(
                    name="get_document_content",
                    description="Retrieve content from a Google Doc",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_id": {
                                "type": "string",
                                "description": "The ID of the Google Doc"
                            }
                        },
                        "required": ["document_id"]
                    }
                ),
                types.Tool(
                    name="create_document",
                    description="Create a new Google Doc",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Title for the new document"
                            }
                        },
                        "required": ["title"]
                    }
                ),
                types.Tool(
                    name="update_document_content",
                    description="Replace content in a Google Doc",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_id": {"type": "string"},
                            "content": {"type": "string"},
                            "start_index": {"type": "integer", "default": 1}
                        },
                        "required": ["document_id", "content"]
                    }
                ),
                types.Tool(
                    name="append_to_document",
                    description="Add content to the end of a Google Doc",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_id": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["document_id", "content"]
                    }
                ),
                types.Tool(
                    name="delete_document_content",
                    description="Remove content from a Google Doc",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_id": {"type": "string"},
                            "start_index": {"type": "integer"},
                            "end_index": {"type": "integer"}
                        },
                        "required": ["document_id", "start_index", "end_index"]
                    }
                ),
                types.Tool(
                    name="format_document_text",
                    description="Apply formatting (bold, italic, etc.) to document text",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_id": {"type": "string"},
                            "start_index": {"type": "integer"},
                            "end_index": {"type": "integer"},
                            "bold": {"type": "boolean"},
                            "italic": {"type": "boolean"},
                            "underline": {"type": "boolean"},
                            "font_size": {"type": "integer"}
                        },
                        "required": ["document_id", "start_index", "end_index"]
                    }
                ),
                types.Tool(
                    name="delete_document",
                    description="Delete a Google Doc",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_id": {"type": "string"}
                        },
                        "required": ["document_id"]
                    }
                ),
                # Google Sheets tools
                types.Tool(
                    name="get_sheet_data",
                    description="Get data from a spreadsheet range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string"},
                            "range_name": {"type": "string", "description": "A1 notation (e.g., 'Sheet1!A1:D10')"}
                        },
                        "required": ["spreadsheet_id", "range_name"]
                    }
                ),
                types.Tool(
                    name="create_spreadsheet",
                    description="Create a new Google Spreadsheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"}
                        },
                        "required": ["title"]
                    }
                ),
                types.Tool(
                    name="update_sheet_data",
                    description="Update specific cells/ranges in a sheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string"},
                            "range_name": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "array"}}
                        },
                        "required": ["spreadsheet_id", "range_name", "values"]
                    }
                ),
                types.Tool(
                    name="append_sheet_data",
                    description="Add new rows to a sheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string"},
                            "range_name": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "array"}}
                        },
                        "required": ["spreadsheet_id", "range_name", "values"]
                    }
                ),
                types.Tool(
                    name="clear_sheet_range",
                    description="Clear content from a range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string"},
                            "range_name": {"type": "string"}
                        },
                        "required": ["spreadsheet_id", "range_name"]
                    }
                ),
                types.Tool(
                    name="add_sheet_rows",
                    description="Insert new rows",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string"},
                            "sheet_id": {"type": "integer"},
                            "start_index": {"type": "integer"},
                            "count": {"type": "integer"}
                        },
                        "required": ["spreadsheet_id", "sheet_id", "start_index", "count"]
                    }
                ),
                types.Tool(
                    name="add_sheet_columns",
                    description="Insert new columns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string"},
                            "sheet_id": {"type": "integer"},
                            "start_index": {"type": "integer"},
                            "count": {"type": "integer"}
                        },
                        "required": ["spreadsheet_id", "sheet_id", "start_index", "count"]
                    }
                ),
                types.Tool(
                    name="delete_sheet_rows",
                    description="Delete rows from a sheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string"},
                            "sheet_id": {"type": "integer"},
                            "start_index": {"type": "integer"},
                            "end_index": {"type": "integer"}
                        },
                        "required": ["spreadsheet_id", "sheet_id", "start_index", "end_index"]
                    }
                ),
                types.Tool(
                    name="delete_sheet_columns",
                    description="Delete columns from a sheet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string"},
                            "sheet_id": {"type": "integer"},
                            "start_index": {"type": "integer"},
                            "end_index": {"type": "integer"}
                        },
                        "required": ["spreadsheet_id", "sheet_id", "start_index", "end_index"]
                    }
                ),
                types.Tool(
                    name="format_sheet_cells",
                    description="Apply formatting to cells",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string"},
                            "sheet_id": {"type": "integer"},
                            "start_row": {"type": "integer"},
                            "end_row": {"type": "integer"},
                            "start_col": {"type": "integer"},
                            "end_col": {"type": "integer"},
                            "background_color": {"type": "object"},
                            "text_color": {"type": "object"},
                            "bold": {"type": "boolean"},
                            "italic": {"type": "boolean"}
                        },
                        "required": ["spreadsheet_id", "sheet_id", "start_row", "end_row", "start_col", "end_col"]
                    }
                ),
                # Google Drive tools
                types.Tool(
                    name="list_drive_files",
                    description="List files in Drive",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_size": {"type": "integer", "default": 10},
                            "query": {"type": "string"},
                            "order_by": {"type": "string", "default": "modifiedTime desc"}
                        }
                    }
                ),
                types.Tool(
                    name="upload_file_to_drive",
                    description="Upload a file to Drive",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"},
                            "name": {"type": "string"},
                            "mime_type": {"type": "string"},
                            "folder_id": {"type": "string"}
                        },
                        "required": ["file_path"]
                    }
                ),
                types.Tool(
                    name="delete_drive_file",
                    description="Delete a file from Drive",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string"}
                        },
                        "required": ["file_id"]
                    }
                ),
                types.Tool(
                    name="share_drive_file",
                    description="Share a file with permissions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string"},
                            "email": {"type": "string"},
                            "role": {"type": "string", "default": "reader"},
                            "send_notification": {"type": "boolean", "default": True}
                        },
                        "required": ["file_id", "email"]
                    }
                ),
                types.Tool(
                    name="copy_drive_file",
                    description="Make a copy of a file",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string"},
                            "new_name": {"type": "string"},
                            "folder_id": {"type": "string"}
                        },
                        "required": ["file_id", "new_name"]
                    }
                ),
                types.Tool(
                    name="move_drive_file",
                    description="Move a file to different location",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string"},
                            "new_folder_id": {"type": "string"},
                            "old_folder_id": {"type": "string"}
                        },
                        "required": ["file_id", "new_folder_id"]
                    }
                ),
                types.Tool(
                    name="create_drive_folder",
                    description="Create a new folder",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "parent_folder_id": {"type": "string"}
                        },
                        "required": ["name"]
                    }
                ),
                types.Tool(
                    name="search_drive_files",
                    description="Search for files by name/type",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search_term": {"type": "string"},
                            "file_type": {"type": "string"}
                        },
                        "required": ["search_term"]
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> Sequence[types.TextContent]:
            """Route tool calls to appropriate handlers."""
            try:
                # Google Docs tools
                if name == "get_document_content":
                    result = await self.docs_tools.get_document_content(**arguments)
                elif name == "create_document":
                    result = await self.docs_tools.create_document(**arguments)
                elif name == "update_document_content":
                    result = await self.docs_tools.update_document_content(**arguments)
                elif name == "append_to_document":
                    result = await self.docs_tools.append_to_document(**arguments)
                elif name == "delete_document_content":
                    result = await self.docs_tools.delete_document_content(**arguments)
                elif name == "format_document_text":
                    result = await self.docs_tools.format_document_text(**arguments)
                elif name == "delete_document":
                    result = await self.docs_tools.delete_document(**arguments)
                
                # Google Sheets tools
                elif name == "get_sheet_data":
                    result = await self.sheets_tools.get_sheet_data(**arguments)
                elif name == "create_spreadsheet":
                    result = await self.sheets_tools.create_spreadsheet(**arguments)
                elif name == "update_sheet_data":
                    result = await self.sheets_tools.update_sheet_data(**arguments)
                elif name == "append_sheet_data":
                    result = await self.sheets_tools.append_sheet_data(**arguments)
                elif name == "clear_sheet_range":
                    result = await self.sheets_tools.clear_sheet_range(**arguments)
                elif name == "add_sheet_rows":
                    result = await self.sheets_tools.add_sheet_rows(**arguments)
                elif name == "add_sheet_columns":
                    result = await self.sheets_tools.add_sheet_columns(**arguments)
                elif name == "delete_sheet_rows":
                    result = await self.sheets_tools.delete_sheet_rows(**arguments)
                elif name == "delete_sheet_columns":
                    result = await self.sheets_tools.delete_sheet_columns(**arguments)
                elif name == "format_sheet_cells":
                    result = await self.sheets_tools.format_sheet_cells(**arguments)
                
                # Google Drive tools
                elif name == "list_drive_files":
                    result = await self.drive_tools.list_drive_files(**arguments)
                elif name == "upload_file_to_drive":
                    result = await self.drive_tools.upload_file_to_drive(**arguments)
                elif name == "delete_drive_file":
                    result = await self.drive_tools.delete_drive_file(**arguments)
                elif name == "share_drive_file":
                    result = await self.drive_tools.share_drive_file(**arguments)
                elif name == "copy_drive_file":
                    result = await self.drive_tools.copy_drive_file(**arguments)
                elif name == "move_drive_file":
                    result = await self.drive_tools.move_drive_file(**arguments)
                elif name == "create_drive_folder":
                    result = await self.drive_tools.create_drive_folder(**arguments)
                elif name == "search_drive_files":
                    result = await self.drive_tools.search_drive_files(**arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "tool": name}, indent=2)
                )]
    
    async def run(self):
        """Run the MCP server."""
        logger.info("Starting Google MCP Server...")
        
        # Authenticate with Google APIs
        self.api_client.authenticate()
        
        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


# Modal deployment configuration
if MODAL_AVAILABLE:
    app = modal.App("google-mcp-server")
    
    image = modal.Image.debian_slim().pip_install(
        "mcp",
        "google-auth",
        "google-auth-oauthlib",
        "google-auth-httplib2",
        "google-api-python-client",
    )
    
    @app.function(image=image)
    async def run_server():
        """Modal deployment entry point."""
        server = GoogleMCPServer()
        await server.run()


async def main():
    """Main entry point for local execution."""
    server = GoogleMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
