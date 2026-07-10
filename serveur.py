import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import paramiko
import datetime
import json
import sys
import os
from database import DatabaseManager

class SSHServer:
    def __init__(self, host='0.0.0.0', port=2222):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = {}
        self.sessions = {}
        self.running = False
        self.db = DatabaseManager()
        self.ssh_commands = {}
        
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
        
        # Enregistrer la session dans la base de données
        username = "unknown"
        session_id = self.db.log_session_start(address[0], address[1], username)
        self.sessions[client_id] = session_id
        
        # Envoyer un message de bienvenue
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
                    # Réception d'une commande au format texte
                    command = data.decode().strip()
                    if command.lower() in ['quit', 'exit', 'bye']:
                        break
                    self.execute_remote_command(client_id, command)
                except:
                    break
            except:
                break
        
        # Nettoyer la connexion
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
        """Exécute une commande sur un client distant via la session SSH"""
        if client_id not in self.clients:
            return "Client non connecté"
        
        try:
            # Envoyer la commande au client
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

class ServerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🔐 Supervision SSH - Serveur Central")
        self.root.geometry("1200x700")
        
        self.server = SSHServer()
        self.server_thread = None
        self.connected_clients = {}
        
        self.setup_ui()
        self.update_status()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        # Menu
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Fichier", menu=file_menu)
        file_menu.add_command(label="Démarrer le serveur", command=self.start_server)
        file_menu.add_command(label="Arrêter le serveur", command=self.stop_server)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.on_closing)
        
        # Panneau principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # 1. Section contrôle
        control_frame = ttk.LabelFrame(main_frame, text="Contrôle du Serveur", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        control_frame.columnconfigure(2, weight=1)
        control_frame.columnconfigure(3, weight=1)
        
        self.status_label = ttk.Label(control_frame, text="Statut: Arrêté", foreground="red")
        self.status_label.grid(row=0, column=0, sticky=tk.W, padx=5)
        
        self.start_btn = ttk.Button(control_frame, text="▶ Démarrer", command=self.start_server)
        self.start_btn.grid(row=0, column=1, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹ Arrêter", command=self.stop_server, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=2, padx=5)
        
        self.clients_label = ttk.Label(control_frame, text="Clients connectés: 0")
        self.clients_label.grid(row=0, column=3, sticky=tk.E, padx=5)
        
        # 2. Onglets pour l'affichage
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Onglet Sessions actives
        self.sessions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sessions_frame, text="🟢 Sessions Actives")
        self.setup_sessions_tab()
        
        # Onglet Historique des sessions
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="📋 Historique")
        self.setup_history_tab()
        
        # Onglet Commandes
        self.commands_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.commands_frame, text="📝 Commandes exécutées")
        self.setup_commands_tab()
        
        # Onglet Console
        self.console_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.console_frame, text="💻 Console")
        self.setup_console_tab()
    
    def setup_sessions_tab(self):
        self.sessions_frame.columnconfigure(0, weight=1)
        self.sessions_frame.rowconfigure(0, weight=1)
        
        columns = ("ID", "Host", "Port", "Username", "Début", "Statut")
        self.sessions_tree = ttk.Treeview(self.sessions_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.sessions_tree.heading(col, text=col)
            self.sessions_tree.column(col, width=100 if col != "Host" else 150)
        
        scrollbar = ttk.Scrollbar(self.sessions_frame, orient=tk.VERTICAL, command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=scrollbar.set)
        
        self.sessions_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Boutons d'action
        btn_frame = ttk.Frame(self.sessions_frame)
        btn_frame.grid(row=1, column=0, sticky=tk.W, pady=10)
        
        ttk.Button(btn_frame, text="🔄 Rafraîchir", command=self.refresh_sessions).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Fermer session", command=self.close_session).pack(side=tk.LEFT, padx=5)
    
    def setup_history_tab(self):
        self.history_frame.columnconfigure(0, weight=1)
        self.history_frame.rowconfigure(0, weight=1)
        
        columns = ("ID", "Host", "Port", "Username", "Début", "Fin", "Statut")
        self.history_tree = ttk.Treeview(self.history_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=100 if col not in ["Host", "Statut"] else 150)
        
        scrollbar = ttk.Scrollbar(self.history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        btn_frame = ttk.Frame(self.history_frame)
        btn_frame.grid(row=1, column=0, sticky=tk.W, pady=10)
        
        ttk.Button(btn_frame, text="🔄 Rafraîchir", command=self.refresh_history).pack(side=tk.LEFT, padx=5)
    
    def setup_commands_tab(self):
        self.commands_frame.columnconfigure(0, weight=1)
        self.commands_frame.rowconfigure(0, weight=1)
        
        columns = ("ID", "Session", "Commande", "Résultat", "Durée", "Heure")
        self.commands_tree = ttk.Treeview(self.commands_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.commands_tree.heading(col, text=col)
            self.commands_tree.column(col, width=100 if col not in ["Commande", "Résultat", "Heure"] else 150)
            if col == "Résultat":
                self.commands_tree.column(col, width=300)
        
        scrollbar = ttk.Scrollbar(self.commands_frame, orient=tk.VERTICAL, command=self.commands_tree.yview)
        self.commands_tree.configure(yscrollcommand=scrollbar.set)
        
        self.commands_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        btn_frame = ttk.Frame(self.commands_frame)
        btn_frame.grid(row=1, column=0, sticky=tk.W, pady=10)
        
        ttk.Button(btn_frame, text="🔄 Rafraîchir", command=self.refresh_commands).pack(side=tk.LEFT, padx=5)
    
    def setup_console_tab(self):
        self.console_frame.columnconfigure(0, weight=1)
        self.console_frame.rowconfigure(0, weight=0)
        self.console_frame.rowconfigure(1, weight=1)
        
        # Zone de saisie
        input_frame = ttk.Frame(self.console_frame)
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        
        ttk.Label(input_frame, text="Commande SSH:").grid(row=0, column=0, sticky=tk.W)
        
        self.cmd_entry = ttk.Entry(input_frame, width=60)
        self.cmd_entry.grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        self.cmd_entry.bind('<Return>', lambda e: self.send_console_command())
        
        self.target_host = ttk.Combobox(input_frame, width=20)
        self.target_host.grid(row=0, column=2, padx=5)
        self.target_host.set("Tous les clients")
        
        ttk.Button(input_frame, text="▶ Exécuter", command=self.send_console_command).grid(row=0, column=3, padx=5)
        
        # Zone d'affichage de la console
        self.console_text = scrolledtext.ScrolledText(self.console_frame, wrap=tk.WORD, height=20)
        self.console_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.console_text.config(state=tk.DISABLED)
    
    def start_server(self):
        if self.server.running:
            return
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Statut: En cours...", foreground="orange")
        
        self.server_thread = threading.Thread(target=self.server.start)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.status_label.config(text="Statut: En marche", foreground="green")
        self.log_console("✅ Serveur démarré avec succès!")
        
        # Mettre à jour les clients connectés
        self.update_clients_list()
    
    def stop_server(self):
        if not self.server.running:
            return
        
        self.log_console("⏹ Arrêt du serveur en cours...")
        self.server.stop()
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Statut: Arrêté", foreground="red")
        self.clients_label.config(text="Clients connectés: 0")
        
        self.log_console("✅ Serveur arrêté")
    
    def update_status(self):
        """Mettre à jour l'affichage des clients connectés"""
        if self.server.running:
            nb_clients = len(self.server.clients)
            self.clients_label.config(text=f"Clients connectés: {nb_clients}")
            self.update_targets()
            self.refresh_sessions()
        
        self.root.after(3000, self.update_status)
    
    def update_targets(self):
        """Mettre à jour la liste des cibles dans la console"""
        targets = ["Tous les clients"] + list(self.server.clients.keys())
        self.target_host['values'] = targets
    
    def update_clients_list(self):
        """Mettre à jour la liste des clients dans l'arbre"""
        pass
    
    def refresh_sessions(self):
        """Rafraîchir la liste des sessions actives"""
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)
        
        if self.server.db:
            sessions = self.server.db.get_session_history()
            for session in sessions:
                if session[6] == 'active':  # statut actif
                    self.sessions_tree.insert("", "end", values=session)
    
    def refresh_history(self):
        """Rafraîchir l'historique des sessions"""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        if self.server.db:
            sessions = self.server.db.get_session_history()
            for session in sessions:
                self.history_tree.insert("", "end", values=session)
    
    def refresh_commands(self):
        """Rafraîchir l'historique des commandes"""
        for item in self.commands_tree.get_children():
            self.commands_tree.delete(item)
        
        if self.server.db:
            commands = self.server.db.get_command_history()
            for cmd in commands:
                # Format: id, command, result, execution_time, duration
                self.commands_tree.insert("", "end", values=cmd)
    
    def close_session(self):
        """Fermer une session sélectionnée"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une session")
            return
        
        item = self.sessions_tree.item(selection[0])
        session_id = item['values'][0]
        client_host = item['values'][1]
        
        if messagebox.askyesno("Confirmation", f"Fermer la session avec {client_host}?"):
            # Trouver le client associé
            for client_id, socket in self.server.clients.items():
                if client_host in client_id:
                    try:
                        socket.close()
                        self.log_console(f"🔌 Session fermée avec {client_id}")
                        break
                    except:
                        pass
            
            self.refresh_sessions()
    
    def send_console_command(self):
        """Envoyer une commande depuis la console"""
        command = self.cmd_entry.get().strip()
        if not command:
            return
        
        target = self.target_host.get()
        
        if target == "Tous les clients":
            for client_id, socket in self.server.clients.items():
                self.server.execute_remote_command(client_id, command)
            self.log_console(f"📤 Commande '{command}' envoyée à tous les clients")
        else:
            self.server.execute_remote_command(target, command)
            self.log_console(f"📤 Commande '{command}' envoyée à {target}")
        
        self.cmd_entry.delete(0, tk.END)
    
    def log_console(self, message):
        """Ajouter un message à la console"""
        self.console_text.config(state=tk.NORMAL)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.console_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.console_text.see(tk.END)
        self.console_text.config(state=tk.DISABLED)
    
    def on_closing(self):
        self.stop_server()
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ServerGUI()
    app.run()