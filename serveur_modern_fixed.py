#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import threading
import socket
import json
import datetime
from database import DatabaseManager

# Tester si customtkinter est disponible
try:
    import customtkinter as ctk
    print("✅ CustomTkinter chargé")
except ImportError:
    print("❌ CustomTkinter non trouvé. Installation...")
    os.system("pip install customtkinter")
    import customtkinter as ctk

import tkinter as tk
from tkinter import ttk, messagebox

# Configuration du thème
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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
        # Configuration de la fenêtre
        self.window = ctk.CTk()
        self.window.title("🔐 Supervision SSH - Serveur Central")
        self.window.geometry("1200x700")
        self.window.minsize(900, 600)
        
        # Configuration du grid
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(0, weight=1)
        
        self.server = SSHServer()
        self.server_thread = None
        
        self.setup_ui()
        self.update_status()
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        # Frame principal avec padding
        self.main_frame = ctk.CTkFrame(self.window)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # ===== HEADER =====
        header_frame = ctk.CTkFrame(self.main_frame)
        header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        header_frame.grid_columnconfigure(0, weight=0)
        header_frame.grid_columnconfigure(1, weight=1)
        header_frame.grid_columnconfigure(2, weight=0)
        header_frame.grid_columnconfigure(3, weight=0)
        
        # Titre
        title = ctk.CTkLabel(
            header_frame,
            text="🔐 Supervision SSH",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#4CAF50"
        )
        title.grid(row=0, column=0, padx=10, pady=10)
        
        # Statut
        self.status_label = ctk.CTkLabel(
            header_frame,
            text="⛔ Arrêté",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="red"
        )
        self.status_label.grid(row=0, column=1, padx=10, sticky="w")
        
        # Clients
        self.clients_label = ctk.CTkLabel(
            header_frame,
            text="🖥️ 0 clients",
            font=ctk.CTkFont(size=14)
        )
        self.clients_label.grid(row=0, column=2, padx=10)
        
        # Boutons de contrôle
        btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=3, padx=5)
        
        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="▶ Démarrer",
            command=self.start_server,
            width=100,
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        self.start_btn.pack(side="left", padx=2)
        
        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="⏹ Arrêter",
            command=self.stop_server,
            width=100,
            fg_color="#C62828",
            hover_color="#B71C1C",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=2)
        
        # ===== TABS =====
        self.tab_view = ctk.CTkTabview(self.main_frame)
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Tab 1: Sessions
        self.tab_view.add("🟢 Sessions Actives")
        self.setup_sessions_tab()
        
        # Tab 2: Historique
        self.tab_view.add("📋 Historique")
        self.setup_history_tab()
        
        # Tab 3: Commandes
        self.tab_view.add("📝 Commandes")
        self.setup_commands_tab()
        
        # Tab 4: Console
        self.tab_view.add("💻 Console")
        self.setup_console_tab()
    
    def setup_sessions_tab(self):
        tab = self.tab_view.tab("🟢 Sessions Actives")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        # Utilisation de Treeview pour les données
        from tkinter import ttk
        columns = ("ID", "Host", "Port", "Username", "Début", "Statut")
        self.sessions_tree = ttk.Treeview(tab, columns=columns, show="headings", height=12)
        
        for col in columns:
            self.sessions_tree.heading(col, text=col)
            self.sessions_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=scrollbar.set)
        
        self.sessions_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def setup_history_tab(self):
        tab = self.tab_view.tab("📋 Historique")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        from tkinter import ttk
        columns = ("ID", "Host", "Port", "Username", "Début", "Fin", "Statut")
        self.history_tree = ttk.Treeview(tab, columns=columns, show="headings", height=12)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def setup_commands_tab(self):
        tab = self.tab_view.tab("📝 Commandes")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        from tkinter import ttk
        columns = ("ID", "Session", "Commande", "Résultat", "Durée", "Heure")
        self.commands_tree = ttk.Treeview(tab, columns=columns, show="headings", height=12)
        
        for col in columns:
            self.commands_tree.heading(col, text=col)
            if col == "Résultat":
                self.commands_tree.column(col, width=300)
            else:
                self.commands_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.commands_tree.yview)
        self.commands_tree.configure(yscrollcommand=scrollbar.set)
        
        self.commands_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def setup_console_tab(self):
        tab = self.tab_view.tab("💻 Console")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        
        # Zone de commande
        cmd_frame = ctk.CTkFrame(tab)
        cmd_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        cmd_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(cmd_frame, text="💻 Commande:").grid(row=0, column=0, padx=5)
        
        self.cmd_entry = ctk.CTkEntry(cmd_frame, placeholder_text="Entrez une commande...")
        self.cmd_entry.grid(row=0, column=1, padx=5, sticky="ew")
        self.cmd_entry.bind('<Return>', lambda e: self.send_command())
        
        self.target_combo = ctk.CTkComboBox(
            cmd_frame,
            values=["Tous les clients"],
            width=150
        )
        self.target_combo.grid(row=0, column=2, padx=5)
        self.target_combo.set("Tous les clients")
        
        self.send_btn = ctk.CTkButton(
            cmd_frame,
            text="▶ Exécuter",
            command=self.send_command,
            width=100,
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        self.send_btn.grid(row=0, column=3, padx=5)
        
        # Console d'affichage
        self.console_text = ctk.CTkTextbox(tab, font=ctk.CTkFont(family="Courier", size=11))
        self.console_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.console_text.insert("1.0", "=== Console de Supervision ===\n")
        self.console_text.insert("end", "Prêt à démarrer le serveur...\n")
        self.console_text.configure(state="disabled")
    
    def start_server(self):
        if self.server.running:
            return
        
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="🔄 En cours...", text_color="orange")
        
        self.server_thread = threading.Thread(target=self.server.start)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.status_label.configure(text="✅ En marche", text_color="#4CAF50")
        self.log_console("✅ Serveur démarré avec succès!")
        self.update_targets()
    
    def stop_server(self):
        if not self.server.running:
            return
        
        self.log_console("⏹ Arrêt du serveur...")
        self.server.stop()
        
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="⛔ Arrêté", text_color="red")
        self.clients_label.configure(text="🖥️ 0 clients")
        self.log_console("✅ Serveur arrêté")
    
    def update_targets(self):
        targets = ["Tous les clients"] + list(self.server.clients.keys())
        self.target_combo.configure(values=targets)
    
    def send_command(self):
        command = self.cmd_entry.get().strip()
        if not command:
            return
        
        target = self.target_combo.get()
        
        if target == "Tous les clients":
            for client_id in self.server.clients.keys():
                self.server.execute_remote_command(client_id, command)
            self.log_console(f"📤 '{command}' envoyé à {len(self.server.clients)} clients")
        else:
            self.server.execute_remote_command(target, command)
            self.log_console(f"📤 '{command}' envoyé à {target}")
        
        self.cmd_entry.delete(0, "end")
    
    def log_console(self, message):
        self.console_text.configure(state="normal")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.console_text.insert("end", f"[{timestamp}] {message}\n")
        self.console_text.see("end")
        self.console_text.configure(state="disabled")
    
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
            self.clients_label.configure(text=f"🖥️ {nb_clients} clients")
            self.update_targets()
            self.refresh_sessions()
            self.refresh_history()
            self.refresh_commands()
        
        self.window.after(3000, self.update_status)
    
    def on_closing(self):
        if self.server.running:
            if messagebox.askokcancel("Quitter", "Le serveur est en cours. Voulez-vous vraiment quitter?"):
                self.stop_server()
                self.window.destroy()
        else:
            self.window.destroy()
    
    def run(self):
        self.window.mainloop()

if __name__ == "__main__":
    print("🚀 Lancement de l'interface de supervision...")
    app = ModernServerGUI()
    app.run()
