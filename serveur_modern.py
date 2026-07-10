import customtkinter as ctk
import socket
import threading
import json
import datetime
import sys
import os
from tkinter import messagebox
from database import DatabaseManager

COLORS = {
    'primary': '#1a73e8',
    'success': '#34a853',
    'danger': '#ea4335',
    'warning': '#fbbc04',
    'dark': '#202124',
    'light': '#f8f9fa'
}

# Personnalisation des widgets
def apply_custom_style():
    # Bouton principal
    ctk.CTkButton(
        fg_color=COLORS['primary'],
        hover_color='#1557b0',
        text_color='white'
    )
# Configuration du thème
ctk.set_appearance_mode("dark")  # Modes: "dark" (default), "light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (default), "green", "dark-blue"

class SSHServer:
    def __init__(self, host='0.0.0.0', port=2222):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = {}
        self.sessions = {}
        self.running = False
        self.db = DatabaseManager()
        
    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            print(f"✅ Serveur SSH démarré sur {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    print(f"🔌 Nouvelle connexion de {address}")
                    client_thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
                    client_thread.daemon = True
                    client_thread.start()
                except:
                    break
        except Exception as e:
            print(f"❌ Erreur du serveur: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def handle_client(self, client_socket, address):
        client_id = f"{address[0]}:{address[1]}"
        self.clients[client_id] = client_socket
        
        session_id = self.db.log_session_start(address[0], address[1], "unknown")
        self.sessions[client_id] = session_id
        
        try:
            client_socket.send(f"Bienvenue sur le serveur SSH! (session ID: {session_id})\n".encode())
        except:
            pass
        
        while self.running:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                message = json.loads(data.decode())
                self.process_message(client_id, message)
                
            except json.JSONDecodeError:
                try:
                    command = data.decode().strip()
                    if command.lower() in ['quit', 'exit', 'bye']:
                        break
                except:
                    break
            except:
                break
        
        if client_id in self.clients:
            del self.clients[client_id]
        if client_id in self.sessions:
            self.db.log_session_end(self.sessions[client_id])
            del self.sessions[client_id]
        
        client_socket.close()
        print(f"🔌 Déconnexion de {address}")
    
    def process_message(self, client_id, message):
        if message['type'] == 'command_result':
            session_id = self.sessions.get(client_id)
            if session_id:
                self.db.log_command(
                    session_id,
                    message['command'],
                    message['result'],
                    message.get('duration', 0)
                )
                print(f"📝 Commande '{message['command']}' exécutée sur {client_id}")
    
    def execute_remote_command(self, client_id, command):
        if client_id not in self.clients:
            return "Client non connecté"
        
        try:
            self.clients[client_id].send(json.dumps({
                'type': 'execute',
                'command': command
            }).encode())
            return "Commande envoyée avec succès"
        except Exception as e:
            return f"Erreur: {str(e)}"
    
    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        for client_socket in self.clients.values():
            try:
                client_socket.close()
            except:
                pass
        self.db.close()

class ModernServerGUI:
    def __init__(self):
        # Configuration de la fenêtre principale
        self.window = ctk.CTk()
        self.window.title("🔐 Supervision SSH - Serveur Central")
        self.window.geometry("1300x800")
        self.window.minsize(1000, 600)
        
        # Configuration du grid
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(0, weight=0)  # Header
        self.window.grid_rowconfigure(1, weight=1)  # Main content
        
        self.server = SSHServer()
        self.server_thread = None
        
        # Initialisation de l'interface
        self.setup_ui()
        
        # Mise à jour automatique
        self.update_status()
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        # ========== HEADER ==========
        self.header_frame = ctk.CTkFrame(self.window, height=80, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.header_frame.grid_columnconfigure(0, weight=0)
        self.header_frame.grid_columnconfigure(1, weight=1)
        self.header_frame.grid_columnconfigure(2, weight=0)
        self.header_frame.grid_columnconfigure(3, weight=0)
        
        # Logo / Titre
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="🔐 Supervision SSH",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#4CAF50"
        )
        self.title_label.grid(row=0, column=0, padx=(20, 10), pady=20)
        
        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="Serveur Central de Contrôle",
            font=ctk.CTkFont(size=14),
            text_color="gray70"
        )
        self.subtitle_label.grid(row=0, column=1, sticky="w", padx=5, pady=20)
        
        # Status en temps réel
        self.status_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.status_frame.grid(row=0, column=2, padx=10, pady=10)
        
        self.status_indicator = ctk.CTkLabel(
            self.status_frame,
            text="⛔",
            font=ctk.CTkFont(size=20)
        )
        self.status_indicator.pack(side="left", padx=5)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Arrêté",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="red"
        )
        self.status_label.pack(side="left", padx=5)
        
        # Clients connectés
        self.clients_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.clients_frame.grid(row=0, column=3, padx=20, pady=10)
        
        self.clients_icon = ctk.CTkLabel(
            self.clients_frame,
            text="🖥️",
            font=ctk.CTkFont(size=20)
        )
        self.clients_icon.pack(side="left", padx=5)
        
        self.clients_label = ctk.CTkLabel(
            self.clients_frame,
            text="0 clients",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.clients_label.pack(side="left", padx=5)
        
        # ========== MAIN CONTENT ==========
        self.main_frame = ctk.CTkFrame(self.window, corner_radius=10)
        self.main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)  # Controls
        self.main_frame.grid_rowconfigure(1, weight=1)  # Tabs
        
        # ---------- Control Bar ----------
        self.control_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        self.control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.control_frame.grid_columnconfigure(0, weight=0)
        self.control_frame.grid_columnconfigure(1, weight=0)
        self.control_frame.grid_columnconfigure(2, weight=0)
        self.control_frame.grid_columnconfigure(3, weight=0)
        self.control_frame.grid_columnconfigure(4, weight=1)
        
        # Boutons de contrôle
        self.start_btn = ctk.CTkButton(
            self.control_frame,
            text="▶ Démarrer",
            command=self.start_server,
            width=120,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        self.start_btn.grid(row=0, column=0, padx=5, pady=5)
        
        self.stop_btn = ctk.CTkButton(
            self.control_frame,
            text="⏹ Arrêter",
            command=self.stop_server,
            width=120,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#C62828",
            hover_color="#B71C1C",
            state="disabled"
        )
        self.stop_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.refresh_btn = ctk.CTkButton(
            self.control_frame,
            text="🔄 Rafraîchir",
            command=self.refresh_all,
            width=120,
            height=40,
            font=ctk.CTkFont(size=14),
            fg_color="#1565C0",
            hover_color="#0D47A1"
        )
        self.refresh_btn.grid(row=0, column=2, padx=5, pady=5)
        
        self.clear_btn = ctk.CTkButton(
            self.control_frame,
            text="🗑️ Effacer logs",
            command=self.clear_logs,
            width=120,
            height=40,
            font=ctk.CTkFont(size=14),
            fg_color="#E65100",
            hover_color="#BF360C"
        )
        self.clear_btn.grid(row=0, column=3, padx=5, pady=5)
        
        # Info serveur
        self.info_label = ctk.CTkLabel(
            self.control_frame,
            text="Port: 2222 | Host: 0.0.0.0",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        self.info_label.grid(row=0, column=4, sticky="e", padx=10)
        
        # ---------- Onglets (Tabs) ----------
        self.tab_view = ctk.CTkTabview(self.main_frame, width=1200, height=500)
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        
        # Onglet 1: Sessions Actives
        self.tab_view.add("🟢 Sessions Actives")
        self.setup_sessions_tab()
        
        # Onglet 2: Historique
        self.tab_view.add("📋 Historique")
        self.setup_history_tab()
        
        # Onglet 3: Commandes
        self.tab_view.add("📝 Commandes")
        self.setup_commands_tab()
        
        # Onglet 4: Console
        self.tab_view.add("💻 Console")
        self.setup_console_tab()
    
    def setup_sessions_tab(self):
        tab = self.tab_view.tab("🟢 Sessions Actives")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        # Treeview avec scrollbar
        self.sessions_frame = ctk.CTkFrame(tab)
        self.sessions_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.sessions_frame.grid_columnconfigure(0, weight=1)
        self.sessions_frame.grid_rowconfigure(0, weight=1)
        
        # Utilisation de Treeview pour l'affichage (CustomTkinter n'a pas de treeview natif)
        from tkinter import ttk
        columns = ("ID", "Host", "Port", "Username", "Début", "Statut")
        self.sessions_tree = ttk.Treeview(
            self.sessions_frame,
            columns=columns,
            show="headings",
            height=15,
            style="Custom.Treeview"
        )
        
        # Style du Treeview
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.Treeview", 
                       background="#2b2b2b",
                       foreground="white",
                       fieldbackground="#2b2b2b",
                       rowheight=25)
        style.map('Custom.Treeview',
                  background=[('selected', '#4CAF50')])
        
        for col in columns:
            self.sessions_tree.heading(col, text=col)
            self.sessions_tree.column(col, width=130)
        
        scrollbar = ttk.Scrollbar(self.sessions_frame, orient="vertical", command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=scrollbar.set)
        
        self.sessions_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def setup_history_tab(self):
        tab = self.tab_view.tab("📋 Historique")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        self.history_frame = ctk.CTkFrame(tab)
        self.history_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.history_frame.grid_columnconfigure(0, weight=1)
        self.history_frame.grid_rowconfigure(0, weight=1)
        
        from tkinter import ttk
        columns = ("ID", "Host", "Port", "Username", "Début", "Fin", "Statut")
        self.history_tree = ttk.Treeview(
            self.history_frame,
            columns=columns,
            show="headings",
            height=15,
            style="Custom.Treeview"
        )
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=130)
        
        scrollbar = ttk.Scrollbar(self.history_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def setup_commands_tab(self):
        tab = self.tab_view.tab("📝 Commandes")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        self.commands_frame = ctk.CTkFrame(tab)
        self.commands_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.commands_frame.grid_columnconfigure(0, weight=1)
        self.commands_frame.grid_rowconfigure(0, weight=1)
        
        from tkinter import ttk
        columns = ("ID", "Session", "Commande", "Résultat", "Durée", "Heure")
        self.commands_tree = ttk.Treeview(
            self.commands_frame,
            columns=columns,
            show="headings",
            height=15,
            style="Custom.Treeview"
        )
        
        for col in columns:
            self.commands_tree.heading(col, text=col)
            if col == "Résultat":
                self.commands_tree.column(col, width=350)
            else:
                self.commands_tree.column(col, width=130)
        
        scrollbar = ttk.Scrollbar(self.commands_frame, orient="vertical", command=self.commands_tree.yview)
        self.commands_tree.configure(yscrollcommand=scrollbar.set)
        
        self.commands_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def setup_console_tab(self):
        tab = self.tab_view.tab("💻 Console")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        
        # Zone de commande
        cmd_frame = ctk.CTkFrame(tab, corner_radius=10)
        cmd_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        cmd_frame.grid_columnconfigure(0, weight=0)
        cmd_frame.grid_columnconfigure(1, weight=1)
        cmd_frame.grid_columnconfigure(2, weight=0)
        cmd_frame.grid_columnconfigure(3, weight=0)
        cmd_frame.grid_columnconfigure(4, weight=0)
        
        ctk.CTkLabel(
            cmd_frame,
            text="💻 Commande SSH:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, padx=10, pady=10)
        
        self.cmd_entry = ctk.CTkEntry(
            cmd_frame,
            placeholder_text="Entrez une commande...",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.cmd_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.cmd_entry.bind('<Return>', lambda e: self.send_console_command())
        
        self.target_combo = ctk.CTkComboBox(
            cmd_frame,
            values=["Tous les clients"],
            height=40,
            width=200,
            font=ctk.CTkFont(size=13)
        )
        self.target_combo.grid(row=0, column=2, padx=5, pady=10)
        self.target_combo.set("Tous les clients")
        
        self.send_btn = ctk.CTkButton(
            cmd_frame,
            text="▶ Exécuter",
            command=self.send_console_command,
            height=40,
            width=120,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        self.send_btn.grid(row=0, column=3, padx=5, pady=10)
        
        self.clear_console_btn = ctk.CTkButton(
            cmd_frame,
            text="🗑️ Effacer",
            command=self.clear_console,
            height=40,
            width=100,
            font=ctk.CTkFont(size=13),
            fg_color="#E65100",
            hover_color="#BF360C"
        )
        self.clear_console_btn.grid(row=0, column=4, padx=5, pady=10)
        
        # Console d'affichage
        self.console_frame = ctk.CTkFrame(tab, corner_radius=10)
        self.console_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(0, weight=1)
        
        self.console_text = ctk.CTkTextbox(
            self.console_frame,
            font=ctk.CTkFont(family="Courier", size=12),
            wrap="word",
            corner_radius=5
        )
        self.console_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.console_text.insert("1.0", "=== Console de Supervision ===\n")
        self.console_text.insert("end", "Démarrage du serveur...\n")
        self.console_text.configure(state="disabled")
    
    # ========== Fonctions de contrôle ==========
    def start_server(self):
        if self.server.running:
            return
        
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="En cours...", text_color="orange")
        self.status_indicator.configure(text="⏳")
        
        self.server_thread = threading.Thread(target=self.server.start)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.status_label.configure(text="En marche", text_color="#4CAF50")
        self.status_indicator.configure(text="✅")
        self.log_console("✅ Serveur démarré avec succès sur le port 2222")
        self.update_targets()
    
    def stop_server(self):
        if not self.server.running:
            return
        
        self.log_console("⏹ Arrêt du serveur en cours...")
        self.server.stop()
        
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="Arrêté", text_color="red")
        self.status_indicator.configure(text="⛔")
        self.clients_label.configure(text="0 clients")
        
        self.log_console("✅ Serveur arrêté")
    
    def refresh_all(self):
        self.refresh_sessions()
        self.refresh_history()
        self.refresh_commands()
        self.log_console("🔄 Toutes les données rafraîchies")
    
    def clear_logs(self):
        # Effacer les logs de la base de données
        if messagebox.askyesno("Confirmation", "Voulez-vous vraiment effacer tous les logs ?"):
            # Implémentation du nettoyage
            self.log_console("🗑️ Logs effacés")
    
    def clear_console(self):
        self.console_text.configure(state="normal")
        self.console_text.delete("1.0", "end")
        self.console_text.insert("1.0", "=== Console de Supervision ===\n")
        self.console_text.configure(state="disabled")
    
    def log_console(self, message):
        self.console_text.configure(state="normal")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.console_text.insert("end", f"[{timestamp}] {message}\n")
        self.console_text.see("end")
        self.console_text.configure(state="disabled")
    
    def update_targets(self):
        targets = ["Tous les clients"] + list(self.server.clients.keys())
        self.target_combo.configure(values=targets)
    
    def send_console_command(self):
        command = self.cmd_entry.get().strip()
        if not command:
            return
        
        target = self.target_combo.get()
        
        if target == "Tous les clients":
            for client_id in self.server.clients.keys():
                self.server.execute_remote_command(client_id, command)
            self.log_console(f"📤 Commande '{command}' envoyée à tous les clients ({len(self.server.clients)} clients)")
        else:
            self.server.execute_remote_command(target, command)
            self.log_console(f"📤 Commande '{command}' envoyée à {target}")
        
        self.cmd_entry.delete(0, "end")
    
    def refresh_sessions(self):
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)
        
        if self.server.db:
            sessions = self.server.db.get_session_history()
            for session in sessions:
                if len(session) > 6 and session[6] == 'active':
                    self.sessions_tree.insert("", "end", values=session[:6])
    
    def refresh_history(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        if self.server.db:
            sessions = self.server.db.get_session_history()
            for session in sessions:
                self.history_tree.insert("", "end", values=session)
    
    def refresh_commands(self):
        for item in self.commands_tree.get_children():
            self.commands_tree.delete(item)
        
        if self.server.db:
            commands = self.server.db.get_command_history()
            for cmd in commands:
                self.commands_tree.insert("", "end", values=cmd)
    
    def update_status(self):
        if self.server.running:
            nb_clients = len(self.server.clients)
            self.clients_label.configure(text=f"{nb_clients} clients")
            self.update_targets()
            self.refresh_sessions()
        
        self.window.after(3000, self.update_status)
    
    def on_closing(self):
        if self.server.running:
            if messagebox.askokcancel("Quitter", "Le serveur est en cours d'exécution. Voulez-vous vraiment quitter ?"):
                self.stop_server()
                self.window.destroy()
        else:
            self.window.destroy()
    
    def run(self):
        self.window.mainloop()

if __name__ == "__main__":
    app = ModernServerGUI()
    app.run()