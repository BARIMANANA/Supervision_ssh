#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import json
import subprocess
import threading
import time
import sys
import os
import platform
from datetime import datetime

try:
    import customtkinter as ctk
    print("✅ CustomTkinter chargé")
except ImportError:
    print("❌ Installation de customtkinter...")
    os.system("pip install customtkinter")
    import customtkinter as ctk

import tkinter as tk
from tkinter import scrolledtext, messagebox

# Configuration du thème
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SSHClientApp:
    def __init__(self, server_host='127.0.0.1', server_port=2222):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.running = False
        self.connected = False
        self.command_history = []
        
        # Configuration de la fenêtre
        self.window = ctk.CTk()
        self.window.title("🖥️ Client SSH - Supervision")
        self.window.geometry("1100x700")
        self.window.minsize(900, 600)
        
        # Configuration du grid
        self.window.grid_columnconfigure(0, weight=0)  # Menu latéral
        self.window.grid_columnconfigure(1, weight=1)  # Contenu principal
        self.window.grid_rowconfigure(0, weight=1)
        
        self.setup_ui()
        self.update_status()
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        # ===== MENU LATÉRAL =====
        self.sidebar = ctk.CTkFrame(self.window, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        # Logo / Titre
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_frame.pack(fill="x", pady=(20, 10))
        
        ctk.CTkLabel(
            title_frame,
            text="🖥️",
            font=ctk.CTkFont(size=40)
        ).pack()
        
        ctk.CTkLabel(
            title_frame,
            text="Client SSH",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#4CAF50"
        ).pack()
        
        ctk.CTkLabel(
            title_frame,
            text="Supervision",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        ).pack()
        
        # Séparateur
        ctk.CTkFrame(self.sidebar, height=2, fg_color="gray30").pack(fill="x", padx=20, pady=10)
        
        # Statut de connexion
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.status_frame.pack(fill="x", padx=20, pady=5)
        
        self.status_indicator = ctk.CTkLabel(
            self.status_frame,
            text="⛔",
            font=ctk.CTkFont(size=16)
        )
        self.status_indicator.pack(side="left", padx=5)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Déconnecté",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="red"
        )
        self.status_label.pack(side="left", padx=5)
        
        # Informations serveur
        info_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        info_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            info_frame,
            text=f"📡 {self.server_host}",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame,
            text=f"🔌 {self.server_port}",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        ).pack(anchor="w")
        
        # Séparateur
        ctk.CTkFrame(self.sidebar, height=2, fg_color="gray30").pack(fill="x", padx=20, pady=10)
        
        # Boutons de navigation
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=15, pady=5)
        
        # Bouton Connexion
        self.connect_btn = ctk.CTkButton(
            nav_frame,
            text="🔗 Connexion",
            command=self.connect_to_server,
            height=40,
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.connect_btn.pack(fill="x", pady=5)
        
        # Bouton Déconnexion
        self.disconnect_btn = ctk.CTkButton(
            nav_frame,
            text="🔌 Déconnexion",
            command=self.disconnect,
            height=40,
            fg_color="#C62828",
            hover_color="#B71C1C",
            state="disabled",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.disconnect_btn.pack(fill="x", pady=5)
        
        # Séparateur
        ctk.CTkFrame(self.sidebar, height=2, fg_color="gray30").pack(fill="x", padx=20, pady=10)
        
        # Statistiques
        stats_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(
            stats_frame,
            text="📊 Statistiques",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#4CAF50"
        ).pack(anchor="w", pady=(0, 10))
        
        self.cmd_count_label = ctk.CTkLabel(
            stats_frame,
            text="Commandes: 0",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        self.cmd_count_label.pack(anchor="w", pady=2)
        
        self.session_time_label = ctk.CTkLabel(
            stats_frame,
            text="Session: 0s",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        self.session_time_label.pack(anchor="w", pady=2)
        
        # Version
        ctk.CTkLabel(
            self.sidebar,
            text="v1.0",
            font=ctk.CTkFont(size=10),
            text_color="gray50"
        ).pack(side="bottom", pady=10)
        
        # ===== CONTENU PRINCIPAL =====
        self.main_content = ctk.CTkFrame(self.window)
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(0, weight=0)
        self.main_content.grid_rowconfigure(1, weight=1)
        
        # En-tête
        header_frame = ctk.CTkFrame(self.main_content, height=50)
        header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)
        
        ctk.CTkLabel(
            header_frame,
            text="💻 Console de commandes",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, padx=10, sticky="w")
        
        self.connection_time = ctk.CTkLabel(
            header_frame,
            text="⏱️ Non connecté",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        self.connection_time.grid(row=0, column=1, padx=10)
        
        # Zone de commandes (avec onglets)
        self.tab_view = ctk.CTkTabview(self.main_content)
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Onglet 1: Console
        self.tab_view.add("💻 Console")
        self.setup_console_tab()
        
        # Onglet 2: Historique
        self.tab_view.add("📋 Historique")
        self.setup_history_tab()
        
        # Onglet 3: Commandes prédéfinies
        self.tab_view.add("⚡ Commandes")
        self.setup_quick_commands_tab()
    
    def setup_console_tab(self):
        tab = self.tab_view.tab("💻 Console")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        
        # Zone de saisie
        input_frame = ctk.CTkFrame(tab)
        input_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_columnconfigure(1, weight=0)
        input_frame.grid_columnconfigure(2, weight=0)
        
        self.cmd_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Entrez une commande système...",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.cmd_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.cmd_entry.bind('<Return>', lambda e: self.execute_command())
        
        self.execute_btn = ctk.CTkButton(
            input_frame,
            text="▶ Exécuter",
            command=self.execute_command,
            height=40,
            width=120,
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.execute_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.clear_btn = ctk.CTkButton(
            input_frame,
            text="🗑️ Effacer",
            command=self.clear_console,
            height=40,
            width=100,
            fg_color="#E65100",
            hover_color="#BF360C"
        )
        self.clear_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Console d'affichage
        self.console_frame = ctk.CTkFrame(tab)
        self.console_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(0, weight=1)
        
        self.console_text = ctk.CTkTextbox(
            self.console_frame,
            font=ctk.CTkFont(family="Courier", size=12),
            wrap="word"
        )
        self.console_text.grid(row=0, column=0, sticky="nsew")
        
        # Message d'accueil
        self.console_text.insert("1.0", "=" * 60 + "\n")
        self.console_text.insert("end", "🖥️  CLIENT SSH - SUPERVISION\n")
        self.console_text.insert("end", "=" * 60 + "\n")
        self.console_text.insert("end", f"📡 Serveur: {self.server_host}:{self.server_port}\n")
        self.console_text.insert("end", "🔌 Statut: Déconnecté\n")
        self.console_text.insert("end", "=" * 60 + "\n\n")
        self.console_text.insert("end", "💡 Appuyez sur 'Connexion' pour vous connecter\n")
        self.console_text.insert("end", "💡 Tapez une commande et appuyez sur Entrée\n\n")
        self.console_text.configure(state="disabled")
    
    def setup_history_tab(self):
        tab = self.tab_view.tab("📋 Historique")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        # Frame pour l'historique
        history_frame = ctk.CTkFrame(tab)
        history_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        history_frame.grid_columnconfigure(0, weight=1)
        history_frame.grid_rowconfigure(0, weight=1)
        
        # Utilisation de Treeview pour l'historique
        from tkinter import ttk
        columns = ("#", "Commande", "Résultat", "Durée", "Heure")
        self.history_tree = ttk.Treeview(
            history_frame,
            columns=columns,
            show="headings",
            height=15,
            style="Custom.Treeview"
        )
        
        # Style
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
            self.history_tree.heading(col, text=col)
            if col == "Résultat":
                self.history_tree.column(col, width=350)
            elif col == "Commande":
                self.history_tree.column(col, width=200)
            else:
                self.history_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Boutons
        btn_frame = ctk.CTkFrame(tab)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkButton(
            btn_frame,
            text="🔄 Rafraîchir",
            command=self.refresh_history,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="🗑️ Effacer historique",
            command=self.clear_history,
            width=150,
            fg_color="#E65100",
            hover_color="#BF360C"
        ).pack(side="left", padx=5)
    
    def setup_quick_commands_tab(self):
        tab = self.tab_view.tab("⚡ Commandes")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        
        # En-tête
        ctk.CTkLabel(
            tab,
            text="⚡ Commandes Rapides",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=10, pady=10)
        
        # Grille de commandes
        commands_frame = ctk.CTkFrame(tab)
        commands_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        commands_frame.grid_columnconfigure(0, weight=1)
        commands_frame.grid_columnconfigure(1, weight=1)
        commands_frame.grid_columnconfigure(2, weight=1)
        
        # Commandes prédéfinies
        quick_commands = [
            ("📁 ls -la", "ls -la"),
            ("📂 pwd", "pwd"),
            ("👤 whoami", "whoami"),
            ("🕐 date", "date"),
            ("💻 uname -a", "uname -a"),
            ("🌐 ifconfig", "ifconfig"),
            ("📊 ps aux", "ps aux"),
            ("💾 df -h", "df -h"),
            ("🧠 free -h", "free -h"),
            ("🔍 netstat -tlnp", "netstat -tlnp"),
            ("📝 echo 'Test'", "echo 'Test SSH'"),
            ("🔄 ping -c 4", "ping -c 4 127.0.0.1")
        ]
        
        row = 0
        col = 0
        for name, cmd in quick_commands:
            btn = ctk.CTkButton(
                commands_frame,
                text=name,
                command=lambda c=cmd: self.execute_quick_command(c),
                height=50,
                font=ctk.CTkFont(size=13),
                fg_color="#1a1a1a",
                hover_color="#2E7D32",
                border_width=1,
                border_color="#4CAF50"
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            
            col += 1
            if col > 2:
                col = 0
                row += 1
    
    def connect_to_server(self):
        """Se connecter au serveur"""
        if self.connected:
            return
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            self.connected = True
            self.running = True
            
            # Mise à jour de l'UI
            self.status_indicator.configure(text="✅")
            self.status_label.configure(text="Connecté", text_color="#4CAF50")
            self.connect_btn.configure(state="disabled")
            self.disconnect_btn.configure(state="normal")
            
            self.log_console("🔗 Connecté au serveur avec succès!")
            self.log_console(f"📡 Serveur: {self.server_host}:{self.server_port}")
            
            # Démarrer l'écoute
            listener_thread = threading.Thread(target=self.listen_for_commands)
            listener_thread.daemon = True
            listener_thread.start()
            
            # Démarrer le timer de session
            self.session_start = time.time()
            self.update_session_time()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de se connecter:\n{str(e)}")
            self.log_console(f"❌ Erreur de connexion: {str(e)}")
    
    def disconnect(self):
        """Se déconnecter du serveur"""
        if not self.connected:
            return
        
        self.running = False
        self.connected = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        self.status_indicator.configure(text="⛔")
        self.status_label.configure(text="Déconnecté", text_color="red")
        self.connect_btn.configure(state="normal")
        self.disconnect_btn.configure(state="disabled")
        self.connection_time.configure(text="⏱️ Déconnecté")
        
        self.log_console("🔌 Déconnecté du serveur")
    
    def execute_command(self):
        """Exécuter une commande localement"""
        if not self.connected:
            messagebox.showwarning("Attention", "Veuillez vous connecter au serveur d'abord")
            return
        
        command = self.cmd_entry.get().strip()
        if not command:
            return
        
        self.do_execute_command(command)
        self.cmd_entry.delete(0, "end")
    
    def execute_quick_command(self, command):
        """Exécuter une commande rapide"""
        if not self.connected:
            messagebox.showwarning("Attention", "Veuillez vous connecter au serveur d'abord")
            return
        
        self.do_execute_command(command)
    
    def do_execute_command(self, command):
        """Exécuter une commande et envoyer le résultat"""
        try:
            # Exécution locale
            start_time = time.time()
            
            if platform.system() == 'Windows':
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            duration = time.time() - start_time
            
            output = result.stdout + result.stderr
            if not output.strip():
                output = "(aucune sortie)"
            
            # Afficher dans la console
            self.log_console(f"\n💻 $ {command}")
            self.log_console(output.strip())
            self.log_console(f"⏱️ Durée: {duration:.3f}s\n")
            
            # Envoyer au serveur
            if self.connected:
                message = {
                    'type': 'command_result',
                    'command': command,
                    'result': output.strip(),
                    'duration': round(duration, 3)
                }
                try:
                    self.socket.send(json.dumps(message).encode())
                except:
                    self.log_console("❌ Erreur: Impossible d'envoyer le résultat au serveur")
            
            # Ajouter à l'historique
            self.command_history.append({
                'command': command,
                'result': output.strip()[:200],
                'duration': round(duration, 3),
                'time': datetime.now().strftime("%H:%M:%S")
            })
            
            # Mettre à jour les statistiques
            self.cmd_count_label.configure(text=f"Commandes: {len(self.command_history)}")
            
        except Exception as e:
            self.log_console(f"❌ Erreur: {str(e)}")
    
    def listen_for_commands(self):
        """Écouter les commandes du serveur"""
        while self.running and self.connected:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                
                try:
                    message = json.loads(data.decode())
                    if message.get('type') == 'execute':
                        command = message.get('command', '')
                        self.log_console(f"📥 Commande du serveur: {command}")
                        self.do_execute_command(command)
                except:
                    pass
            except:
                break
    
    def log_console(self, message):
        """Ajouter un message à la console"""
        self.console_text.configure(state="normal")
        self.console_text.insert("end", f"{message}\n")
        self.console_text.see("end")
        self.console_text.configure(state="disabled")
    
    def clear_console(self):
        """Effacer la console"""
        self.console_text.configure(state="normal")
        self.console_text.delete("1.0", "end")
        self.console_text.insert("1.0", "=== Console effacée ===\n\n")
        self.console_text.configure(state="disabled")
    
    def refresh_history(self):
        """Rafraîchir l'historique"""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        for idx, cmd in enumerate(self.command_history, 1):
            self.history_tree.insert("", "end", values=(
                idx,
                cmd['command'],
                cmd['result'][:100] + "..." if len(cmd['result']) > 100 else cmd['result'],
                f"{cmd['duration']}s",
                cmd['time']
            ))
    
    def clear_history(self):
        """Effacer l'historique"""
        if messagebox.askyesno("Confirmation", "Effacer tout l'historique des commandes ?"):
            self.command_history = []
            self.refresh_history()
            self.cmd_count_label.configure(text="Commandes: 0")
    
    def update_session_time(self):
        """Mettre à jour le temps de session"""
        if self.connected:
            elapsed = int(time.time() - self.session_start)
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.connection_time.configure(text=f"⏱️ {minutes}m {seconds}s")
            self.window.after(1000, self.update_session_time)
    
    def update_status(self):
        """Mise à jour automatique"""
        if self.connected and self.socket:
            try:
                self.socket.send(b'ping')
            except:
                pass
        self.window.after(5000, self.update_status)
    
    def on_closing(self):
        if self.connected:
            if messagebox.askokcancel("Quitter", "Vous êtes connecté. Voulez-vous vraiment quitter?"):
                self.disconnect()
                self.window.destroy()
        else:
            self.window.destroy()
    
    def run(self):
        self.window.mainloop()

if __name__ == "__main__":
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 2222
    
    print(f"🚀 Lancement du client SSH...")
    print(f"📡 Connexion à {host}:{port}")
    
    app = SSHClientApp(host, port)
    app.run()
