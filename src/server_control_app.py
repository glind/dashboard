#!/usr/bin/env python3
"""
Native macOS Server Control Panel
Simple GUI for monitoring and controlling Python web servers
"""

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import threading
import time
from typing import Dict, List
import webbrowser

class ServerControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Server Control Panel")
        self.root.geometry("800x600")
        
        # Configure style for dark theme
        self.style = ttk.Style()
        self.setup_styles()
        
        self.servers = []
        self.dashboard_url = "http://localhost:8008"
        
        self.setup_ui()
        self.start_monitoring()
    
    def setup_styles(self):
        """Configure ttk styles for a modern look"""
        # Configure dark theme
        self.style.theme_use('default')
        
        # Main background
        self.style.configure('TFrame', background='#2d3748')
        self.style.configure('TLabel', background='#2d3748', foreground='white')
        self.style.configure('TButton', padding=(10, 5))
        
        # Status indicators
        self.style.configure('Running.TLabel', foreground='#48bb78', font=('Arial', 12, 'bold'))
        self.style.configure('Stopped.TLabel', foreground='#f56565', font=('Arial', 12, 'bold'))
        
        # Server cards
        self.style.configure('ServerCard.TFrame', 
                           background='#4a5568', 
                           relief='raised', 
                           borderwidth=1)
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root, style='TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = ttk.Frame(main_frame, style='TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ttk.Label(header_frame, 
                               text="🖥️ Python Server Control Panel", 
                               font=('Arial', 18, 'bold'),
                               style='TLabel')
        title_label.pack(side=tk.LEFT)
        
        # Control buttons
        controls_frame = ttk.Frame(header_frame, style='TFrame')
        controls_frame.pack(side=tk.RIGHT)
        
        self.refresh_btn = ttk.Button(controls_frame, 
                                     text="🔄 Refresh", 
                                     command=self.refresh_servers)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.dashboard_btn = ttk.Button(controls_frame, 
                                       text="📊 Open Dashboard", 
                                       command=self.open_dashboard)
        self.dashboard_btn.pack(side=tk.LEFT)
        
        # Server count
        self.server_count_label = ttk.Label(header_frame,
                                           text="0 servers",
                                           font=('Arial', 12),
                                           style='TLabel')
        self.server_count_label.pack(side=tk.RIGHT, padx=(20, 0))
        
        # Scrollable servers area
        self.setup_servers_area(main_frame)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, 
                                textvariable=self.status_var,
                                font=('Arial', 10),
                                style='TLabel')
        status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
    
    def setup_servers_area(self, parent):
        """Setup scrollable area for server cards"""
        # Create frame with scrollbar
        canvas_frame = ttk.Frame(parent, style='TFrame')
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg='#2d3748', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        
        self.servers_frame = ttk.Frame(self.canvas, style='TFrame')
        
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.servers_frame, anchor="nw")
        
        # Bind scroll events
        self.servers_frame.bind('<Configure>', self.on_frame_configure)
        self.canvas.bind('<Configure>', self.on_canvas_configure)
    
    def on_frame_configure(self, event=None):
        """Reset scroll region when frame size changes"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def on_canvas_configure(self, event):
        """Resize frame when canvas size changes"""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
    
    def refresh_servers(self):
        """Refresh the list of servers"""
        self.status_var.set("Refreshing servers...")
        self.refresh_btn.config(state='disabled')
        
        threading.Thread(target=self._fetch_servers, daemon=True).start()
    
    def _fetch_servers(self):
        """Fetch servers from API (runs in background thread)"""
        try:
            response = requests.get(f"{self.dashboard_url}/api/servers", timeout=5)
            result = response.json()
            
            if result.get('success'):
                self.servers = result.get('servers', [])
                # Update UI in main thread
                self.root.after(0, self._update_servers_ui)
            else:
                self.root.after(0, lambda: self.status_var.set(f"Error: {result.get('error', 'Unknown error')}"))
                
        except requests.exceptions.ConnectionError:
            self.root.after(0, lambda: self.status_var.set("Error: Cannot connect to dashboard"))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.refresh_btn.config(state='normal'))
    
    def _update_servers_ui(self):
        """Update the servers UI (runs in main thread)"""
        # Clear existing server cards
        for widget in self.servers_frame.winfo_children():
            widget.destroy()
        
        if not self.servers:
            no_servers_label = ttk.Label(self.servers_frame,
                                        text="No Python servers detected",
                                        font=('Arial', 14),
                                        style='TLabel')
            no_servers_label.pack(pady=50)
        else:
            for i, server in enumerate(self.servers):
                self.create_server_card(server, i)
        
        # Update server count
        count = len(self.servers)
        self.server_count_label.config(text=f"{count} server{'s' if count != 1 else ''}")
        self.status_var.set(f"Found {count} servers")
    
    def create_server_card(self, server: Dict, index: int):
        """Create a card for a server"""
        card_frame = ttk.Frame(self.servers_frame, style='ServerCard.TFrame')
        card_frame.pack(fill=tk.X, padx=5, pady=5, ipady=10, ipadx=10)
        
        # Top row: name, type, status
        top_frame = ttk.Frame(card_frame, style='ServerCard.TFrame')
        top_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Status indicator and name
        left_frame = ttk.Frame(top_frame, style='ServerCard.TFrame')
        left_frame.pack(side=tk.LEFT)
        
        status_style = 'Running.TLabel' if server['status'] == 'running' else 'Stopped.TLabel'
        status_symbol = '🟢' if server['status'] == 'running' else '🔴'
        
        status_label = ttk.Label(left_frame, text=status_symbol, style=status_style)
        status_label.pack(side=tk.LEFT, padx=(0, 8))
        
        name_label = ttk.Label(left_frame, 
                              text=server['name'], 
                              font=('Arial', 14, 'bold'),
                              style='TLabel')
        name_label.pack(side=tk.LEFT)
        
        type_label = ttk.Label(left_frame, 
                              text=f"({server['type']})", 
                              font=('Arial', 10),
                              style='TLabel')
        type_label.pack(side=tk.LEFT, padx=(8, 0))
        
        # Control buttons
        buttons_frame = ttk.Frame(top_frame, style='ServerCard.TFrame')
        buttons_frame.pack(side=tk.RIGHT)
        
        # Open URL button
        open_btn = ttk.Button(buttons_frame, 
                             text="🌐 Open", 
                             command=lambda s=server: self.open_server_url(s['url']))
        open_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Start/Stop button
        if server.get('can_control'):
            if server['status'] == 'running':
                control_btn = ttk.Button(buttons_frame, 
                                       text="⏹️ Stop", 
                                       command=lambda s=server: self.stop_server(s['port']))
            else:
                control_btn = ttk.Button(buttons_frame, 
                                       text="▶️ Start", 
                                       command=lambda s=server: self.start_server(s))
            control_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Map button
        map_btn = ttk.Button(buttons_frame, 
                            text="📋 Map", 
                            command=lambda s=server: self.map_to_dashboard(s))
        map_btn.pack(side=tk.LEFT)
        
        # Details row
        details_frame = ttk.Frame(card_frame, style='ServerCard.TFrame')
        details_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Port and PID
        port_label = ttk.Label(details_frame, 
                              text=f"Port: {server['port']}", 
                              font=('Arial', 10),
                              style='TLabel')
        port_label.pack(side=tk.LEFT)
        
        if server.get('pid'):
            pid_label = ttk.Label(details_frame, 
                                 text=f"PID: {server['pid']}", 
                                 font=('Arial', 10),
                                 style='TLabel')
            pid_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # Resource usage
        if server.get('cpu_percent') is not None:
            cpu_label = ttk.Label(details_frame, 
                                 text=f"CPU: {server['cpu_percent']:.1f}%", 
                                 font=('Arial', 10),
                                 style='TLabel')
            cpu_label.pack(side=tk.RIGHT, padx=(0, 10))
        
        if server.get('memory_mb') is not None:
            memory_label = ttk.Label(details_frame, 
                                    text=f"RAM: {server['memory_mb']:.0f}MB", 
                                    font=('Arial', 10),
                                    style='TLabel')
            memory_label.pack(side=tk.RIGHT, padx=(0, 10))
        
        # Path row
        if server.get('cmdline'):
            path_text = self.extract_path(server['cmdline'])
            if path_text:
                path_label = ttk.Label(card_frame, 
                                      text=f"Path: {path_text}", 
                                      font=('Arial', 9),
                                      style='TLabel')
                path_label.pack(anchor=tk.W)
    
    def extract_path(self, cmdline: str) -> str:
        """Extract path from command line"""
        parts = cmdline.split(' ')
        for part in parts:
            if '/' in part and not part.startswith('-'):
                if '.py' in part:
                    return part.rsplit('/', 1)[0] if '/' in part else part
                return part
        return ""
    
    def open_server_url(self, url: str):
        """Open server URL in browser"""
        webbrowser.open(url)
    
    def stop_server(self, port: int):
        """Stop a server"""
        def _stop():
            try:
                response = requests.post(f"{self.dashboard_url}/api/servers/{port}/stop", timeout=5)
                result = response.json()
                
                if result.get('success'):
                    self.root.after(0, lambda: self.status_var.set(f"Server on port {port} stopped"))
                    self.root.after(1000, self.refresh_servers)  # Refresh after 1 second
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to stop server: {result.get('error')}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error stopping server: {str(e)}"))
        
        threading.Thread(target=_stop, daemon=True).start()
    
    def start_server(self, server: Dict):
        """Start a server (placeholder)"""
        messagebox.showinfo("Not Implemented", 
                           "Server starting not yet implemented.\n" +
                           "Use the dashboard interface to start servers.")
    
    def map_to_dashboard(self, server: Dict):
        """Map server to dashboard (opens dashboard with pre-filled info)"""
        url = f"{self.dashboard_url}/?map_server={server['port']}"
        webbrowser.open(url)
    
    def open_dashboard(self):
        """Open the main dashboard in browser"""
        webbrowser.open(self.dashboard_url)
    
    def start_monitoring(self):
        """Start periodic monitoring of servers"""
        def monitor():
            while True:
                time.sleep(10)  # Check every 10 seconds
                if self.servers:  # Only refresh if we have servers
                    self.root.after(0, self.refresh_servers)
        
        # Initial load
        self.refresh_servers()
        
        # Start background monitoring
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

def main():
    """Main function to run the app"""
    root = tk.Tk()
    
    # Set app icon and style
    if hasattr(tk, 'call'):
        try:
            # Try to use macOS native appearance
            root.call('tk', 'scaling', 2.0)  # Better scaling on retina displays
        except:
            pass
    
    app = ServerControlApp(root)
    
    # Center window on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (800 // 2)
    y = (root.winfo_screenheight() // 2) - (600 // 2)
    root.geometry(f"800x600+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main()