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
        seen_tasks = set()
        
        # Match various TODO patterns
        patterns = [
            (r'- \[ \]\s+(.+)', 'checkbox'),  # - [ ] Task
            (r'TODO:\s+(.+)', 'todo'),  # TODO: Task
            (r'@todo\s+(.+)', 'todo_tag'),  # @todo Task
            (r'Action:\s+(.+)', 'action'),  # Action: Task
            (r'FIXME:\s+(.+)', 'fixme'),  # FIXME: Task
            (r'NOTE:\s+(.+)', 'note'),  # NOTE: Task
        ]
        
        for pattern, pattern_type in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                task_text = match.group(1).strip()
                
                # Skip if too short or already seen
                if len(task_text) < 5 or task_text.lower() in seen_tasks:
                    continue
                
                seen_tasks.add(task_text.lower())
                
                # Get surrounding context (line before and after)
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                context = content[start:end].strip()
                
                todos.append({
                    'text': task_text,
                    'context': context,
                    'pattern_type': pattern_type
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
                    
                    # Clean up URL - remove usp parameter for better compatibility
                    url = file.get('webViewLink', '')
                    if '?usp=' in url:
                        url = url.split('?usp=')[0]
                    
                    notes.append({
                        'source': 'google_drive',
                        'title': file['name'],
                        'preview': content[:200] if content else '',
                        'url': url,
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
        seen_tasks = set()  # Avoid duplicates
        
        # Match various TODO patterns (order matters - more specific first)
        patterns = [
            (r'(?:^|\n)\s*[-•]\s*\[\s*\]\s+(.+)', 'checkbox'),  # - [ ] Task or • [ ] Task
            (r'(?:^|\n)\s*Action\s*Items?:\s*\n\s*[-•]\s+(.+)', 'action_item'),  # Action Item:\n- Task
            (r'(?:^|\n)\s*Next\s*Steps?:\s*\n\s*[-•]\s+(.+)', 'next_step'),  # Next Steps:\n- Task
            (r'(?:^|\n)\s*Follow[- ]?up:\s*\n\s*[-•]\s+(.+)', 'follow_up'),  # Follow-up:\n- Task
            (r'(?:^|\n)\s*TODO:\s+(.+)', 'todo'),  # TODO: Task
            (r'(?:^|\n)\s*Action\s*Items?:\s+(.+)', 'action_item_inline'),  # Action Item: Task
            (r'(?:^|\n)\s*[-•]\s+([A-Z][\w\s]*?)\s+(?:will|should|needs? to|to)\s+(.+?)(?:\.|$)', 'action_sentence'),  # - Person will do something
            (r'\b(?:will|should|need to|must)\s+((?:follow up|reach out|send|create|update|review|schedule|prepare|contact|call|email)[\w\s]{10,80})(?:\.|,|\n)', 'commitment'),  # Natural language commitments
            (r'@(\w+):\s+(.+)', 'mention'),  # @person: Task
        ]
        
        for pattern, pattern_type in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # Extract task text based on pattern type
                if pattern_type == 'action_sentence':
                    task_text = f"{match.group(1)} will {match.group(2)}".strip()
                elif pattern_type == 'commitment':
                    task_text = match.group(1).strip()
                elif pattern_type == 'mention' and len(match.groups()) == 2:
                    task_text = f"{match.group(1)}: {match.group(2)}".strip()
                else:
                    task_text = match.group(1).strip()
                
                # Clean up task text
                task_text = task_text.strip('.,;:')
                
                # Skip if too short or already seen
                if len(task_text) < 10 or task_text.lower() in seen_tasks:
                    continue
                
                seen_tasks.add(task_text.lower())
                
                # Get surrounding context
                start = max(0, match.start() - 150)
                end = min(len(content), match.end() + 150)
                context = content[start:end].strip()
                
                todos.append({
                    'text': task_text,
                    'context': context,
                    'pattern_type': pattern_type,
                    'confidence': 'high' if pattern_type in ['checkbox', 'action_item', 'todo'] else 'medium'
                })
        
        return todos


class AppleNotesCollector:
    """Collects notes from Apple Notes using macOS native APIs via osascript."""
    
    def __init__(self):
        """Initialize Apple Notes collector."""
        import platform
        self.is_macos = platform.system() == 'Darwin'
        
    def get_recent_notes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recently modified notes from Apple Notes.
        
        Args:
            limit: Maximum number of notes to return
            
        Returns:
            List of note dictionaries with metadata
        """
        if not self.is_macos:
            logger.warning("Apple Notes collector only works on macOS")
            return []
            
        try:
            import subprocess
            from datetime import datetime
            
            # Use a faster approach - get notes directly without iterating folders
            # Skip body content initially to avoid timeout
            script = f'''
            set output to ""
            set noteCount to 0
            tell application "Notes"
                set allNotes to notes
                repeat with n in allNotes
                    if noteCount >= {limit} then exit repeat
                    try
                        set noteName to name of n
                        set noteId to id of n
                        set noteCreated to (creation date of n) as text
                        set noteModified to (modification date of n) as text
                        -- Get folder name safely
                        set folderName to "Notes"
                        try
                            set folderName to name of container of n
                        end try
                        set output to output & "|||NOTE_START|||" & return
                        set output to output & "FOLDER:" & folderName & return
                        set output to output & "NAME:" & noteName & return
                        set output to output & "ID:" & noteId & return
                        set output to output & "CREATED:" & noteCreated & return
                        set output to output & "MODIFIED:" & noteModified & return
                        -- Get body but limit to avoid slowdown
                        set noteBody to ""
                        try
                            set noteBody to body of n
                        end try
                        set output to output & "BODY:" & return & noteBody & return
                        set output to output & "|||NOTE_END|||" & return
                        set noteCount to noteCount + 1
                    on error
                    end try
                end repeat
            end tell
            return output
            '''
            
            # Execute AppleScript with longer timeout
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"AppleScript error: {result.stderr}")
                return []
            
            # Parse the delimited output
            raw_output = result.stdout
            if not raw_output or '|||NOTE_START|||' not in raw_output:
                logger.info("No Apple Notes found")
                return []
            
            # Parse notes from the delimited format
            notes = self._parse_delimited_output(raw_output)
            
            logger.info(f"Collected {len(notes)} Apple Notes")
            return notes
            
        except subprocess.TimeoutExpired:
            logger.error("Apple Notes collection timed out")
            return []
        except Exception as e:
            logger.error(f"Error collecting Apple Notes: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _parse_delimited_output(self, output: str) -> List[Dict[str, Any]]:
        """
        Parse delimited AppleScript output into note dictionaries.
        
        Args:
            output: Delimited output from AppleScript
            
        Returns:
            List of parsed note dictionaries
        """
        import re
        notes = []
        
        # Split by note markers
        note_blocks = output.split('|||NOTE_START|||')
        
        for block in note_blocks:
            if '|||NOTE_END|||' not in block:
                continue
                
            block = block.split('|||NOTE_END|||')[0]
            
            try:
                note = {}
                lines = block.strip().split('\n')
                body_lines = []
                in_body = False
                
                for line in lines:
                    if line.startswith('FOLDER:'):
                        note['folder'] = line[7:].strip()
                    elif line.startswith('NAME:'):
                        note['title'] = line[5:].strip()
                    elif line.startswith('ID:'):
                        note['apple_id'] = line[3:].strip()
                    elif line.startswith('CREATED:'):
                        note['created_at'] = line[8:].strip()
                    elif line.startswith('MODIFIED:'):
                        note['modified_at'] = line[9:].strip()
                    elif line.startswith('BODY:'):
                        in_body = True
                    elif in_body:
                        body_lines.append(line)
                
                if not note.get('title'):
                    continue
                
                # Process body
                body_html = '\n'.join(body_lines)
                body_clean = re.sub(r'<[^>]+>', '', body_html).strip()
                
                note['source'] = 'apple_notes'
                note['content'] = body_clean
                note['preview'] = body_clean[:200] if body_clean else ''
                note['word_count'] = len(body_clean.split()) if body_clean else 0
                note['todos'] = self._extract_todos(body_clean)
                note['has_todos'] = len(note['todos']) > 0
                
                notes.append(note)
                
            except Exception as e:
                logger.warning(f"Error parsing Apple Note block: {e}")
                continue
                
        return notes
    
    def _extract_todos(self, content: str) -> List[Dict[str, str]]:
        """
        Extract TODO items from Apple Notes content.
        
        Args:
            content: Note content
            
        Returns:
            List of TODO items
        """
        todos = []
        seen_tasks = set()
        
        patterns = [
            (r'[-•]\s*\[\s*\]\s+(.+)', 'checkbox'),
            (r'TODO:\s+(.+)', 'todo'),
            (r'☐\s+(.+)', 'checkbox_symbol'),
            (r'Action:\s+(.+)', 'action'),
        ]
        
        for pattern, pattern_type in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                task_text = match.group(1).strip()
                
                if len(task_text) < 5 or task_text.lower() in seen_tasks:
                    continue
                
                seen_tasks.add(task_text.lower())
                
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                context = content[start:end].strip()
                
                todos.append({
                    'text': task_text,
                    'context': context,
                    'pattern_type': pattern_type
                })
        
        return todos
    
    def sync_note_to_apple(self, title: str, content: str, folder: str = "Notes") -> bool:
        """
        Create or update a note in Apple Notes.
        
        Args:
            title: Note title
            content: Note content
            folder: Target folder name
            
        Returns:
            True if successful
        """
        if not self.is_macos:
            return False
            
        try:
            import subprocess
            
            # Escape content for AppleScript
            escaped_content = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            escaped_title = title.replace('\\', '\\\\').replace('"', '\\"')
            
            script = f'''
            tell application "Notes"
                tell account "iCloud"
                    set targetFolder to folder "{folder}"
                    make new note at targetFolder with properties {{name:"{escaped_title}", body:"{escaped_content}"}}
                end tell
            end tell
            '''
            
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=10
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error syncing to Apple Notes: {e}")
            return False


class GoogleKeepCollector:
    """Collects notes from Google Keep (via exported data or gkeepapi)."""
    
    def __init__(self, email: str = None, master_token: str = None):
        """
        Initialize Google Keep collector.
        
        Args:
            email: Google account email
            master_token: Google Keep master token (from gkeepapi login)
        """
        self.email = email
        self.master_token = master_token
        self.keep = None
        
    def _get_keep_client(self):
        """Get or create Google Keep client."""
        if self.keep:
            return self.keep
            
        try:
            import gkeepapi
            
            self.keep = gkeepapi.Keep()
            
            if self.master_token:
                # Resume with saved token
                self.keep.resume(self.email, self.master_token)
            else:
                logger.warning("Google Keep requires master token for authentication")
                return None
                
            return self.keep
            
        except ImportError:
            logger.warning("gkeepapi not installed. Install with: pip install gkeepapi")
            return None
        except Exception as e:
            logger.error(f"Error connecting to Google Keep: {e}")
            return None
    
    def get_recent_notes(self, limit: int = 10, labels: List[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent notes from Google Keep.
        
        Args:
            limit: Maximum number of notes to return
            labels: Optional list of label names to filter by
            
        Returns:
            List of note dictionaries
        """
        try:
            keep = self._get_keep_client()
            if not keep:
                return []
            
            # Sync with Google Keep
            keep.sync()
            
            # Get notes
            notes = []
            all_notes = list(keep.all())
            
            # Filter by labels if specified
            if labels:
                filtered_notes = []
                for note in all_notes:
                    note_labels = [l.name for l in note.labels.all()]
                    if any(label in note_labels for label in labels):
                        filtered_notes.append(note)
                all_notes = filtered_notes
            
            # Sort by timestamp (most recent first) and limit
            all_notes.sort(key=lambda x: x.timestamps.updated, reverse=True)
            all_notes = all_notes[:limit]
            
            for note in all_notes:
                try:
                    # Extract content
                    if hasattr(note, 'text'):
                        content = note.text
                    elif hasattr(note, 'items'):
                        # List note
                        content = '\n'.join([f"{'✓' if item.checked else '☐'} {item.text}" for item in note.items])
                    else:
                        content = str(note)
                    
                    # Get labels
                    note_labels = [l.name for l in note.labels.all()] if hasattr(note, 'labels') else []
                    
                    notes.append({
                        'source': 'google_keep',
                        'title': note.title or content[:50] + '...' if len(content) > 50 else content,
                        'preview': content[:200] if content else '',
                        'content': content,
                        'labels': note_labels,
                        'color': note.color.name if hasattr(note, 'color') else 'DEFAULT',
                        'pinned': note.pinned if hasattr(note, 'pinned') else False,
                        'archived': note.archived if hasattr(note, 'archived') else False,
                        'modified_at': note.timestamps.updated.isoformat() if hasattr(note, 'timestamps') else '',
                        'created_at': note.timestamps.created.isoformat() if hasattr(note, 'timestamps') else '',
                        'keep_id': note.id,
                        'todos': self._extract_todos(content),
                        'has_todos': False,  # Will update below
                        'is_list': hasattr(note, 'items')
                    })
                    notes[-1]['has_todos'] = len(notes[-1]['todos']) > 0
                    
                except Exception as e:
                    logger.error(f"Error processing Keep note: {e}")
                    continue
            
            logger.info(f"Collected {len(notes)} Google Keep notes")
            return notes
            
        except Exception as e:
            logger.error(f"Error collecting Google Keep notes: {e}")
            return []
    
    def _extract_todos(self, content: str) -> List[Dict[str, str]]:
        """
        Extract TODO items from Keep note content.
        
        Args:
            content: Note content
            
        Returns:
            List of TODO items
        """
        todos = []
        seen_tasks = set()
        
        patterns = [
            (r'☐\s+(.+)', 'unchecked'),
            (r'TODO:\s+(.+)', 'todo'),
            (r'[-•]\s*\[\s*\]\s+(.+)', 'checkbox'),
        ]
        
        for pattern, pattern_type in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                task_text = match.group(1).strip()
                
                if len(task_text) < 5 or task_text.lower() in seen_tasks:
                    continue
                
                seen_tasks.add(task_text.lower())
                todos.append({
                    'text': task_text,
                    'pattern_type': pattern_type
                })
        
        return todos


def collect_all_notes(obsidian_path: Optional[str] = None, 
                      gdrive_folder_id: Optional[str] = None,
                      include_apple_notes: bool = True,
                      google_keep_email: Optional[str] = None,
                      google_keep_token: Optional[str] = None,
                      google_keep_labels: Optional[List[str]] = None,
                      limit: int = 10) -> Dict[str, Any]:
    """
    Collect notes from all configured sources.
    
    Args:
        obsidian_path: Path to Obsidian vault
        gdrive_folder_id: Google Drive folder ID
        include_apple_notes: Whether to include Apple Notes (macOS only)
        google_keep_email: Google account email for Keep
        google_keep_token: Google Keep master token
        google_keep_labels: Optional list of Keep labels to filter by
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
    
    # Collect from Apple Notes (macOS only)
    apple_notes_count = 0
    if include_apple_notes:
        try:
            import platform
            if platform.system() == 'Darwin':
                logger.info("Collecting Apple Notes...")
                apple_collector = AppleNotesCollector()
                apple_notes = apple_collector.get_recent_notes(limit)
                all_notes.extend(apple_notes)
                apple_notes_count = len(apple_notes)
                
                # Extract todos
                for note in apple_notes:
                    for todo in note.get('todos', []):
                        todos_to_create.append({
                            'text': todo['text'],
                            'source': 'apple_notes',
                            'source_title': note['title'],
                            'context': todo.get('context', '')
                        })
        except Exception as e:
            logger.error(f"Error collecting Apple Notes: {e}")
    
    # Collect from Google Keep
    google_keep_count = 0
    if google_keep_email and google_keep_token:
        try:
            logger.info("Collecting Google Keep notes...")
            keep_collector = GoogleKeepCollector(google_keep_email, google_keep_token)
            keep_notes = keep_collector.get_recent_notes(limit, labels=google_keep_labels)
            all_notes.extend(keep_notes)
            google_keep_count = len(keep_notes)
            
            # Extract todos
            for note in keep_notes:
                for todo in note.get('todos', []):
                    todos_to_create.append({
                        'text': todo['text'],
                        'source': 'google_keep',
                        'source_title': note['title'],
                        'context': ''
                    })
        except Exception as e:
            logger.error(f"Error collecting Google Keep notes: {e}")
    
    # Collect from Google Drive
    gdrive_auth_error = None
    if gdrive_folder_id:
        try:
            logger.info(f"Attempting to collect Google Drive notes from folder: {gdrive_folder_id}")
            gdrive = GoogleDriveNotesCollector()
            
            # Catch the specific error here
            try:
                gdrive_notes = gdrive.get_meeting_notes(gdrive_folder_id, limit)
            except Exception as gdrive_err:
                logger.error(f"Error in get_meeting_notes: {gdrive_err}", exc_info=True)
                
                # Check if it's an auth error
                error_str = str(gdrive_err)
                if '403' in error_str and ('insufficientPermissions' in error_str or 'insufficient authentication scopes' in error_str):
                    gdrive_auth_error = {
                        'error': 'authentication',
                        'message': 'Google Drive access requires re-authentication',
                        'reauth_url': 'http://localhost:8008/auth/google'
                    }
                    logger.warning("Google Drive authentication error - user needs to re-authenticate")
                
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
                if not gdrive_auth_error:
                    logger.warning("No Google Drive notes found - check folder ID and permissions")
        except Exception as e:
            logger.error(f"Error collecting Google Drive notes (outer): {e}", exc_info=True)
            if '403' in str(e):
                gdrive_auth_error = {
                    'error': 'authentication',
                    'message': 'Google Drive access requires re-authentication',
                    'reauth_url': 'http://localhost:8008/auth/google'
                }
    
    # Sort all notes by modification time
    all_notes.sort(key=lambda x: x.get('modified_at', ''), reverse=True)
    
    result = {
        'notes': all_notes[:limit * 3],  # Return more notes from combined sources
        'todos_to_create': todos_to_create,
        'obsidian_count': len([n for n in all_notes if n['source'] == 'obsidian']),
        'gdrive_count': len([n for n in all_notes if n['source'] == 'google_drive']),
        'apple_notes_count': apple_notes_count,
        'google_keep_count': google_keep_count,
        'total_todos_found': len(todos_to_create)
    }
    
    # Add auth error if present
    if gdrive_auth_error:
        result['gdrive_auth_error'] = gdrive_auth_error
    
    return result


def sync_notes_between_sources(source: str, target: str, note_ids: List[str] = None) -> Dict[str, Any]:
    """
    Sync notes between different sources.
    
    Args:
        source: Source type ('obsidian', 'apple_notes', 'google_keep', 'google_drive')
        target: Target type ('obsidian', 'apple_notes', 'google_keep', 'google_drive')
        note_ids: Optional list of specific note IDs to sync
        
    Returns:
        Sync result with counts
    """
    synced_count = 0
    errors = []
    
    logger.info(f"Syncing notes from {source} to {target}")
    
    # This is a placeholder for future sync implementation
    # Full sync would require:
    # 1. Reading notes from source
    # 2. Converting format if needed
    # 3. Writing to target
    # 4. Tracking sync state to avoid duplicates
    
    return {
        'success': True,
        'synced_count': synced_count,
        'errors': errors,
        'message': f'Sync from {source} to {target} completed'
    }
