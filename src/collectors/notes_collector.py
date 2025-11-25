#!/usr/bin/env python3
"""
Notes Collector
==============
Collects recent notes from Obsidian vault and Google Drive meeting notes.
Extracts TODOs and creates tasks automatically.
"""

import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ObsidianNotesCollector:
    """Collects recent notes from Obsidian vault."""
    
    def __init__(self, vault_path: str):
        """
        Initialize Obsidian collector.
        
        Args:
            vault_path: Path to Obsidian vault directory
        """
        self.vault_path = Path(vault_path)
        
    def get_recent_notes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recently modified notes from Obsidian vault.
        
        Args:
            limit: Maximum number of notes to return
            
        Returns:
            List of note dictionaries with metadata
        """
        try:
            if not self.vault_path.exists():
                logger.error(f"Obsidian vault not found: {self.vault_path}")
                return []
            
            # Find all markdown files
            md_files = []
            for md_file in self.vault_path.rglob('*.md'):
                # Skip hidden files and folders
                if any(part.startswith('.') for part in md_file.parts):
                    continue
                    
                try:
                    stat = md_file.stat()
                    md_files.append({
                        'path': md_file,
                        'mtime': stat.st_mtime,
                        'ctime': stat.st_ctime,
                        'size': stat.st_size
                    })
                except Exception as e:
                    logger.warning(f"Error reading file {md_file}: {e}")
                    continue
            
            # Sort by modification time (most recent first)
            md_files.sort(key=lambda x: x['mtime'], reverse=True)
            
            # Get top N files
            recent_files = md_files[:limit]
            
            # Extract note details
            notes = []
            for file_info in recent_files:
                try:
                    note = self._parse_note(file_info['path'])
                    note['modified_at'] = datetime.fromtimestamp(file_info['mtime']).isoformat()
                    note['created_at'] = datetime.fromtimestamp(file_info['ctime']).isoformat()
                    note['size_bytes'] = file_info['size']
                    notes.append(note)
                except Exception as e:
                    logger.error(f"Error parsing note {file_info['path']}: {e}")
                    continue
            
            logger.info(f"Collected {len(notes)} recent Obsidian notes")
            return notes
            
        except Exception as e:
            logger.error(f"Error collecting Obsidian notes: {e}")
            return []
    
    def _parse_note(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a markdown note file.
        
        Args:
            file_path: Path to the note file
            
        Returns:
            Dictionary with note metadata and content
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title (first # heading or filename)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else file_path.stem
        
        # Extract preview (first non-heading paragraph)
        lines = content.split('\n')
        preview = ''
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('[['):
                preview = line[:200]
                break
        
        # Extract tags
        tags = re.findall(r'#(\w+)', content)
        
        # Extract TODO items
        todos = self._extract_todos(content)
        
        # Get relative path from vault root
        relative_path = file_path.relative_to(self.vault_path)
        
        return {
            'source': 'obsidian',
            'title': title,
            'preview': preview,
            'path': str(file_path),
            'relative_path': str(relative_path),
            'tags': list(set(tags)),  # Remove duplicates
            'todos': todos,
            'word_count': len(content.split()),
            'line_count': len(lines),
            'has_todos': len(todos) > 0
        }
    
    def _extract_todos(self, content: str) -> List[Dict[str, str]]:
        """
        Extract TODO items from note content.
        
        Args:
            content: Note content
            
        Returns:
            List of TODO items with context
        """
        todos = []
        
        # Match various TODO patterns
        patterns = [
            r'- \[ \]\s+(.+)',  # - [ ] Task
            r'TODO:\s+(.+)',     # TODO: Task
            r'@todo\s+(.+)',     # @todo Task
            r'Action:\s+(.+)',   # Action: Task
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                task_text = match.group(1).strip()
                
                # Get surrounding context (line before and after)
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                context = content[start:end].strip()
                
                todos.append({
                    'text': task_text,
                    'context': context,
                    'pattern': pattern
                })
        
        return todos


class GoogleDriveNotesCollector:
    """Collects meeting notes from Google Drive."""
    
    def __init__(self, credentials_path: str = None):
        """
        Initialize Google Drive collector.
        
        Args:
            credentials_path: Path to Google credentials
        """
        self.credentials_path = credentials_path
        self.service = None
        
    def _get_service(self):
        """Get or create Google Drive service."""
        if self.service:
            return self.service
            
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from pathlib import Path
            
            # Try to load existing token (try both names)
            token_path = Path(__file__).parent.parent.parent / 'tokens' / 'google_token.json'
            if not token_path.exists():
                token_path = Path(__file__).parent.parent.parent / 'tokens' / 'google_credentials.json'
            
            if not token_path.exists():
                logger.error("Google token not found. Please authenticate first.")
                return None
            
            import json
            logger.info(f"Loading Google Drive token from: {token_path}")
            
            with open(token_path, 'r') as f:
                try:
                    token_data = json.load(f)
                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON decode error in token file: {json_err}")
                    return None
            
            creds = Credentials(
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri'),
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret'),
                scopes=token_data.get('scopes')
            )
            
            logger.info("Building Google Drive service...")
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("Google Drive service created successfully")
            return self.service
            
        except Exception as e:
            logger.error(f"Error creating Google Drive service: {e}", exc_info=True)
            return None
    
    def get_meeting_notes(self, folder_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent meeting notes from Google Drive folder.
        
        Args:
            folder_id: Google Drive folder ID
            limit: Maximum number of notes to return
            
        Returns:
            List of note dictionaries
        """
        try:
            service = self._get_service()
            if not service:
                return []
            
            # Query for Google Docs in the folder
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            
            results = service.files().list(
                q=query,
                pageSize=limit,
                orderBy='modifiedTime desc',
                fields='files(id, name, modifiedTime, createdTime, webViewLink, description)'
            ).execute()
            
            files = results.get('files', [])
            
            notes = []
            for file in files:
                try:
                    # Get document content
                    content = self._get_document_content(service, file['id'])
                    
                    # Extract TODOs from content
                    todos = self._extract_todos_from_gdoc(content)
                    
                    notes.append({
                        'source': 'google_drive',
                        'title': file['name'],
                        'preview': content[:200] if content else '',
                        'url': file['webViewLink'],
                        'modified_at': file['modifiedTime'],
                        'created_at': file['createdTime'],
                        'todos': todos,
                        'has_todos': len(todos) > 0,
                        'doc_id': file['id']
                    })
                except Exception as e:
                    logger.error(f"Error processing Google Doc {file['name']}: {e}")
                    continue
            
            logger.info(f"Collected {len(notes)} Google Drive meeting notes")
            return notes
            
        except Exception as e:
            logger.error(f"Error collecting Google Drive notes: {e}")
            return []
    
    def _get_document_content(self, service, doc_id: str) -> str:
        """
        Get plain text content from Google Doc.
        
        Args:
            service: Google Drive service
            doc_id: Document ID
            
        Returns:
            Document content as plain text
        """
        try:
            logger.info(f"Fetching content for doc: {doc_id}")
            
            # Use export (not export_media) and specify mimeType
            # This returns bytes directly
            content_bytes = service.files().export(
                fileId=doc_id,
                mimeType='text/plain'
            ).execute()
            
            logger.info(f"Received content type: {type(content_bytes)}, length: {len(content_bytes) if content_bytes else 0}")
            
            # Decode bytes to string
            if isinstance(content_bytes, bytes):
                return content_bytes.decode('utf-8', errors='ignore')
            elif isinstance(content_bytes, str):
                return content_bytes
            else:
                logger.warning(f"Unexpected content type: {type(content_bytes)}")
                return str(content_bytes)
            
        except Exception as e:
            logger.error(f"Error getting document content for {doc_id}: {e}", exc_info=True)
            return ""
    
    def _extract_todos_from_gdoc(self, content: str) -> List[Dict[str, str]]:
        """
        Extract TODO items from Google Doc content.
        
        Args:
            content: Document content
            
        Returns:
            List of TODO items
        """
        todos = []
        
        # Match various TODO patterns
        patterns = [
            r'(?:^|\n)\s*[-•]\s*\[\s*\]\s+(.+)',  # - [ ] Task or • [ ] Task
            r'(?:^|\n)\s*TODO:\s+(.+)',            # TODO: Task
            r'(?:^|\n)\s*Action\s*Item:\s+(.+)',   # Action Item: Task
            r'(?:^|\n)\s*@(\w+):\s+(.+)',          # @person: Task
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if len(match.groups()) == 2:
                    task_text = f"{match.group(1)}: {match.group(2)}"
                else:
                    task_text = match.group(1).strip()
                
                # Get surrounding context
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                context = content[start:end].strip()
                
                todos.append({
                    'text': task_text,
                    'context': context,
                    'pattern': pattern
                })
        
        return todos


def collect_all_notes(obsidian_path: Optional[str] = None, 
                      gdrive_folder_id: Optional[str] = None,
                      limit: int = 10) -> Dict[str, Any]:
    """
    Collect notes from all configured sources.
    
    Args:
        obsidian_path: Path to Obsidian vault
        gdrive_folder_id: Google Drive folder ID
        limit: Max notes per source
        
    Returns:
        Dictionary with notes from all sources
    """
    all_notes = []
    todos_to_create = []
    
    # Collect from Obsidian
    if obsidian_path:
        obsidian = ObsidianNotesCollector(obsidian_path)
        obsidian_notes = obsidian.get_recent_notes(limit)
        all_notes.extend(obsidian_notes)
        
        # Extract todos for auto-creation
        for note in obsidian_notes:
            for todo in note.get('todos', []):
                todos_to_create.append({
                    'text': todo['text'],
                    'source': 'obsidian',
                    'source_title': note['title'],
                    'source_path': note.get('path'),
                    'context': todo.get('context', '')
                })
    
    # Collect from Google Drive
    if gdrive_folder_id:
        try:
            logger.info(f"Attempting to collect Google Drive notes from folder: {gdrive_folder_id}")
            gdrive = GoogleDriveNotesCollector()
            
            # Catch the specific error here
            try:
                gdrive_notes = gdrive.get_meeting_notes(gdrive_folder_id, limit)
            except Exception as gdrive_err:
                logger.error(f"Error in get_meeting_notes: {gdrive_err}", exc_info=True)
                gdrive_notes = []
            
            if gdrive_notes:
                logger.info(f"Successfully collected {len(gdrive_notes)} notes from Google Drive")
                all_notes.extend(gdrive_notes)
                
                # Extract todos for auto-creation
                for note in gdrive_notes:
                    for todo in note.get('todos', []):
                        todos_to_create.append({
                            'text': todo['text'],
                            'source': 'google_drive',
                            'source_title': note['title'],
                            'source_url': note.get('url'),
                            'context': todo.get('context', '')
                        })
            else:
                logger.warning("No Google Drive notes found - check folder ID and permissions")
        except Exception as e:
            logger.error(f"Error collecting Google Drive notes (outer): {e}", exc_info=True)
    
    # Sort all notes by modification time
    all_notes.sort(key=lambda x: x.get('modified_at', ''), reverse=True)
    
    return {
        'notes': all_notes[:limit * 2],  # Return more notes from combined sources
        'todos_to_create': todos_to_create,
        'obsidian_count': len([n for n in all_notes if n['source'] == 'obsidian']),
        'gdrive_count': len([n for n in all_notes if n['source'] == 'google_drive']),
        'total_todos_found': len(todos_to_create)
    }
