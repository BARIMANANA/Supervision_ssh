#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import customtkinter as ctk
import socket
import threading
import json
import datetime
import sys
import os
import time
from tkinter import messagebox, ttk
from database import DatabaseManager

# Configuration du thème
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SSHServer:
    def __init__(self, host='0.0.0.0', port=2222):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = {}
        self.client_usernames = {}  # Stocker les usernames des clients
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
        
        # Récupérer le username du client
        username = "unknown"
        try:
            # Attendre le message d'authentification
            data = client_socket.recv(4096)
            if data:
                try:
                    msg = json.loads(data.decode())
                    if msg.get('type') == 'auth':
                        username = msg.get('username', 'unknown')
                        print(f"👤 Client {client_id} connecté en tant que: {username}")
                except:
                    pass
        except:
            pass
        
        # Stocker le username
        self.client_usernames[client_id] = username
        
        # Enregistrer la session avec le username
        session_id = self.db.log_session_start(address[0], address[1], username)
        self.sessions[client_id] = session_id
        
        try:
            client_socket.send(f"Bienvenue {username}! (session ID: {session_id})\n".encode())
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
        
        # Nettoyage
        if client_id in self.clients:
            del self.clients[client_id]
        if client_id in self.sessions:
            self.db.log_session_end(self.sessions[client_id])
            del self.sessions[client_id]
        if client_id in self.client_usernames:
            del self.client_usernames[client_id]
        
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
                username = self.client_usernames.get(client_id, 'unknown')
                print(f"📝 Commande '{message['command']}' exécutée par {username} sur {client_id}")
    
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
    
    def get_client_list(self):
        """Retourner la liste des clients avec leurs usernames"""
        clients = []
        for client_id in self.clients.keys():
            username = self.client_usernames.get(client_id, 'unknown')
            clients.append({
                'id': client_id,
                'username': username,
                'status': 'Actif'
            })
        return clients
    
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

class ImprovedServerGUI:
    def __init__(self):
        self.window = ctk.CTk()
        self.window.title("🔐 Supervision SSH - Serveur Central")
        self.window.geometry("1300x750")
        self.window.minsize(1100, 650)
        
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(0, weight=1)
        
        self.server = SSHServer()
        self.server_thread = None
        self.start_time = None
        
        self.setup_ui()
        self.update_status()
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        self.main_frame = ctk.CTkFrame(self.window, corner_radius=15)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # ===== HEADER =====
        self.header_frame = ctk.CTkFrame(self.main_frame, corner_radius=10, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.header_frame.grid_columnconfigure(0, weight=0)
        self.header_frame.grid_columnconfigure(1, weight=1)
        self.header_frame.grid_columnconfigure(2, weight=0)
        self.header_frame.grid_columnconfigure(3, weight=0)
        self.header_frame.grid_columnconfigure(4, weight=0)
        self.header_frame.grid_columnconfigure(5, weight=0)
        
        # Logo et titre
        title_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=(5, 20), pady=5)
        
        ctk.CTkLabel(
            title_frame,
            text="🔐",
            font=ctk.CTkFont(size=32)
        ).pack(side="left")
        
        ctk.CTkLabel(
            title_frame,
            text="Supervision SSH",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=(10, 0))
        
        # Statut
        status_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        status_frame.grid(row=0, column=1, padx=10)
        
        self.status_indicator = ctk.CTkLabel(
            status_frame,
            text="⛔",
            font=ctk.CTkFont(size=18)
        )
        self.status_indicator.pack(side="left", padx=5)
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Arrêté",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="red"
        )
        self.status_label.pack(side="left", padx=5)
        
        # Clients connectés
        clients_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        clients_frame.grid(row=0, column=2, padx=20)
        
        ctk.CTkLabel(
            clients_frame,
            text="🖥️",
            font=ctk.CTkFont(size=18)
        ).pack(side="left", padx=5)
        
        self.clients_label = ctk.CTkLabel(
            clients_frame,
            text="0 clients",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#4CAF50"
        )
        self.clients_label.pack(side="left", padx=5)
        
        # Boutons de contrôle
        self.start_btn = ctk.CTkButton(
            self.header_frame,
            text="▶ Démarrer",
            command=self.start_server,
            width=120,
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        self.start_btn.grid(row=0, column=3, padx=5, pady=5)
        
        self.stop_btn = ctk.CTkButton(
            self.header_frame,
            text="⏹ Arrêter",
            command=self.stop_server,
            width=120,
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#C62828",
            hover_color="#B71C1C",
            state="disabled"
        )
        self.stop_btn.grid(row=0, column=4, padx=5, pady=5)
        
        self.refresh_btn = ctk.CTkButton(
            self.header_frame,
            text="🔄",
            command=self.refresh_all,
            width=40,
            height=38,
            font=ctk.CTkFont(size=16),
            fg_color="#1565C0",
            hover_color="#0D47A1"
        )
        self.refresh_btn.grid(row=0, column=5, padx=5, pady=5)
        
        # ===== CONTENU =====
        self.content_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        
        self.tab_view = ctk.CTkTabview(self.content_frame, width=1200, height=500)
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
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
        
        # Onglet 5: Statistiques
        self.tab_view.add("📊 Statistiques")
        self.setup_stats_tab()
    
    def setup_sessions_tab(self):
        tab = self.tab_view.tab("🟢 Sessions Actives")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        frame = ctk.CTkFrame(tab, corner_radius=10)
        frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        columns = ("ID", "Host", "Port", "Username", "Début", "Statut")
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.Treeview",
                       background="#2b2b2b",
                       foreground="white",
                       fieldbackground="#2b2b2b",
                       rowheight=30)
        style.map('Custom.Treeview',
                  background=[('selected', '#4CAF50')])
        
        self.sessions_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            height=15,
            style="Custom.Treeview"
        )
        
        for col in columns:
            self.sessions_tree.heading(col, text=col)
            if col == "Username":
                self.sessions_tree.column(col, width=120)
            else:
                self.sessions_tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=scrollbar.set)
        
        self.sessions_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        info_frame = ctk.CTkFrame(tab, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        self.sessions_count = ctk.CTkLabel(
            info_frame,
            text="Sessions actives: 0",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        self.sessions_count.pack(side="left", padx=5)
        
        # Bouton pour afficher les usernames
        ctk.CTkButton(
            info_frame,
            text="👤 Voir usernames",
            command=self.show_usernames,
            width=150,
            height=30,
            fg_color="#1565C0",
            hover_color="#0D47A1"
        ).pack(side="right", padx=5)
    
    def setup_history_tab(self):
        tab = self.tab_view.tab("📋 Historique")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        frame = ctk.CTkFrame(tab, corner_radius=10)
        frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        columns = ("ID", "Host", "Port", "Username", "Début", "Fin", "Statut")
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.Treeview",
                       background="#2b2b2b",
                       foreground="white",
                       fieldbackground="#2b2b2b",
                       rowheight=30)
        style.map('Custom.Treeview',
                  background=[('selected', '#1565C0')])
        
        self.history_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            height=15,
            style="Custom.Treeview"
        )
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def setup_commands_tab(self):
        tab = self.tab_view.tab("📝 Commandes")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        frame = ctk.CTkFrame(tab, corner_radius=10)
        frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        columns = ("ID", "Session", "Commande", "Résultat", "Durée", "Heure")
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.Treeview",
                       background="#2b2b2b",
                       foreground="white",
                       fieldbackground="#2b2b2b",
                       rowheight=30)
        style.map('Custom.Treeview',
                  background=[('selected', '#E65100')])
        
        self.commands_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            height=15,
            style="Custom.Treeview"
        )
        
        for col in columns:
            self.commands_tree.heading(col, text=col)
            if col == "Résultat":
                self.commands_tree.column(col, width=400)
            elif col == "Commande":
                self.commands_tree.column(col, width=200)
            else:
                self.commands_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.commands_tree.yview)
        self.commands_tree.configure(yscrollcommand=scrollbar.set)
        
        self.commands_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def setup_console_tab(self):
        tab = self.tab_view.tab("💻 Console")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        
        cmd_frame = ctk.CTkFrame(tab, corner_radius=10)
        cmd_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        cmd_frame.grid_columnconfigure(0, weight=0)
        cmd_frame.grid_columnconfigure(1, weight=1)
        cmd_frame.grid_columnconfigure(2, weight=0)
        cmd_frame.grid_columnconfigure(3, weight=0)
        cmd_frame.grid_columnconfigure(4, weight=0)
        
        ctk.CTkLabel(
            cmd_frame,
            text="💻 Commande:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, padx=10, pady=10)
        
        self.cmd_entry = ctk.CTkEntry(
            cmd_frame,
            placeholder_text="Entrez une commande système...",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.cmd_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.cmd_entry.bind('<Return>', lambda e: self.send_command())
        
        self.target_combo = ctk.CTkComboBox(
            cmd_frame,
            values=["Tous les clients"],
            height=40,
            width=180,
            font=ctk.CTkFont(size=13)
        )
        self.target_combo.grid(row=0, column=2, padx=5, pady=10)
        self.target_combo.set("Tous les clients")
        
        self.send_btn = ctk.CTkButton(
            cmd_frame,
            text="▶ Exécuter",
            command=self.send_command,
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
            fg_color="#E65100",
            hover_color="#BF360C"
        )
        self.clear_console_btn.grid(row=0, column=4, padx=5, pady=10)
        
        console_frame = ctk.CTkFrame(tab, corner_radius=10)
        console_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(0, weight=1)
        
        self.console_text = ctk.CTkTextbox(
            console_frame,
            font=ctk.CTkFont(family="Courier", size=12),
            wrap="word"
        )
        self.console_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        self.console_text.insert("1.0", "=" * 70 + "\n")
        self.console_text.insert("end", "🔐  CONSOLE DE SUPERVISION SSH\n")
        self.console_text.insert("end", "=" * 70 + "\n")
        self.console_text.insert("end", "📡 Serveur: 0.0.0.0:2222\n")
        self.console_text.insert("end", "👤 Support de multiples usernames\n")
        self.console_text.insert("end", "=" * 70 + "\n\n")
        self.console_text.insert("end", "💡 Cliquez sur 'Démarrer' pour lancer le serveur\n")
        self.console_text.insert("end", "💡 Tapez une commande et appuyez sur Entrée\n")
        self.console_text.configure(state="disabled")
    
    def setup_stats_tab(self):
        tab = self.tab_view.tab("📊 Statistiques")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_columnconfigure(2, weight=1)
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=0)
        tab.grid_rowconfigure(2, weight=1)
        
        stat_frame1 = ctk.CTkFrame(tab, corner_radius=15)
        stat_frame1.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(
            stat_frame1,
            text="🖥️",
            font=ctk.CTkFont(size=30)
        ).pack(pady=(10, 0))
        
        self.total_clients_stat = ctk.CTkLabel(
            stat_frame1,
            text="0",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#4CAF50"
        )
        self.total_clients_stat.pack()
        
        ctk.CTkLabel(
            stat_frame1,
            text="Clients connectés",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        ).pack(pady=(0, 10))
        
        stat_frame2 = ctk.CTkFrame(tab, corner_radius=15)
        stat_frame2.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(
            stat_frame2,
            text="📊",
            font=ctk.CTkFont(size=30)
        ).pack(pady=(10, 0))
        
        self.total_sessions_stat = ctk.CTkLabel(
            stat_frame2,
            text="0",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#1565C0"
        )
        self.total_sessions_stat.pack()
        
        ctk.CTkLabel(
            stat_frame2,
            text="Sessions totales",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        ).pack(pady=(0, 10))
        
        stat_frame3 = ctk.CTkFrame(tab, corner_radius=15)
        stat_frame3.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(
            stat_frame3,
            text="📝",
            font=ctk.CTkFont(size=30)
        ).pack(pady=(10, 0))
        
        self.total_commands_stat = ctk.CTkLabel(
            stat_frame3,
            text="0",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#E65100"
        )
        self.total_commands_stat.pack()
        
        ctk.CTkLabel(
            stat_frame3,
            text="Commandes exécutées",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        ).pack(pady=(0, 10))
        
        details_frame = ctk.CTkFrame(tab, corner_radius=15)
        details_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        details_frame.grid_columnconfigure(0, weight=1)
        details_frame.grid_columnconfigure(1, weight=1)
        
        self.uptime_label = ctk.CTkLabel(
            details_frame,
            text="⏱️ Uptime: 0s",
            font=ctk.CTkFont(size=14)
        )
        self.uptime_label.grid(row=0, column=0, padx=10, pady=10)
        
        self.db_size_label = ctk.CTkLabel(
            details_frame,
            text="💾 Base de données: 0 KB",
            font=ctk.CTkFont(size=14)
        )
        self.db_size_label.grid(row=0, column=1, padx=10, pady=10)
    
    # ===== FONCTIONS =====
    
    def show_usernames(self):
        """Afficher les usernames des clients connectés"""
        if not self.server.clients:
            messagebox.showinfo("Info", "Aucun client connecté")
            return
        
        clients_info = []
        for client_id in self.server.clients.keys():
            username = self.server.client_usernames.get(client_id, 'unknown')
            clients_info.append(f"{client_id} → 👤 {username}")
        
        messagebox.showinfo(
            "👤 Usernames des clients",
            "Clients connectés:\n\n" + "\n".join(clients_info)
        )
    
    def start_server(self):
        if self.server.running:
            return
        
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="En cours...", text_color="orange")
        self.status_indicator.configure(text="⏳")
        
        self.start_time = time.time()
        self.server_thread = threading.Thread(target=self.server.start)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.status_label.configure(text="En marche", text_color="#4CAF50")
        self.status_indicator.configure(text="✅")
        self.log_console("✅ Serveur démarré avec succès!")
        self.log_console(f"📡 Port: {self.server.port} | Host: {self.server.host}")
        self.log_console("👤 Support de multiples usernames activé")
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
        self.update_stats()
        self.log_console("🔄 Données rafraîchies")
    
    def send_command(self):
        command = self.cmd_entry.get().strip()
        if not command:
            return
        
        if not self.server.running:
            self.log_console("❌ Le serveur n'est pas en cours d'exécution")
            return
        
        target = self.target_combo.get()
        
        if target == "Tous les clients":
            if not self.server.clients:
                self.log_console("⚠️ Aucun client connecté")
                return
            for client_id in self.server.clients.keys():
                self.server.execute_remote_command(client_id, command)
            self.log_console(f"📤 Commande '{command}' envoyée à {len(self.server.clients)} clients")
        else:
            self.server.execute_remote_command(target, command)
            self.log_console(f"📤 Commande '{command}' envoyée à {target}")
        
        self.cmd_entry.delete(0, "end")
    
    def log_console(self, message):
        self.console_text.configure(state="normal")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.console_text.insert("end", f"[{timestamp}] {message}\n")
        self.console_text.see("end")
        self.console_text.configure(state="disabled")
    
    def clear_console(self):
        self.console_text.configure(state="normal")
        self.console_text.delete("1.0", "end")
        self.console_text.insert("1.0", "=== Console effacée ===\n\n")
        self.console_text.configure(state="disabled")
    
    def update_targets(self):
        targets = ["Tous les clients"] + list(self.server.clients.keys())
        self.target_combo.configure(values=targets)
    
    def refresh_sessions(self):
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)
        
        if self.server.db:
            sessions = self.server.db.get_session_history()
            count = 0
            for session in sessions:
                if len(session) > 6 and session[6] == 'active':
                    # Récupérer le username depuis la base
                    values = list(session[:6])
                    self.sessions_tree.insert("", "end", values=values)
                    count += 1
            self.sessions_count.configure(text=f"Sessions actives: {count}")
    
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
    
    def update_stats(self):
        if self.server.db:
            sessions = self.server.db.get_session_history()
            active = sum(1 for s in sessions if len(s) > 6 and s[6] == 'active')
            commands = self.server.db.get_command_history()
            
            self.total_clients_stat.configure(text=str(active))
            self.total_sessions_stat.configure(text=str(len(sessions)))
            self.total_commands_stat.configure(text=str(len(commands)))
            
            try:
                size = os.path.getsize('ssh_sessions.db') / 1024
                self.db_size_label.configure(text=f"💾 Base de données: {size:.1f} KB")
            except:
                pass
    
    def update_status(self):
        if self.server.running:
            nb_clients = len(self.server.clients)
            self.clients_label.configure(text=f"{nb_clients} clients")
            self.update_targets()
            self.refresh_sessions()
            self.update_stats()
            
            if self.start_time:
                elapsed = int(time.time() - self.start_time)
                minutes = elapsed // 60
                seconds = elapsed % 60
                self.uptime_label.configure(text=f"⏱️ Uptime: {minutes}m {seconds}s")
        
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
    app = ImprovedServerGUI()
    app.run()