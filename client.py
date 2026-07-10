#!/usr/bin/env python3
import socket
import json
import subprocess
import threading
import sys
import getpass
import time
import os

class ClientWithUsername:
    def __init__(self, host, port, username=None):
        self.host = host
        self.port = port
        self.username = username or getpass.getuser()
        self.sock = None
        self.running = False
        self.connected = False
    
    def connect(self):
        """Se connecter au serveur avec username"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)  # Timeout de 5 secondes
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)  # Reset timeout
            
            # Envoyer le username au serveur
            auth_msg = json.dumps({
                'type': 'auth',
                'username': self.username
            })
            self.sock.send(auth_msg.encode())
            
            self.connected = True
            self.running = True
            print("=" * 50)
            print(f"✅ Connecté au serveur {self.host}:{self.port}")
            print(f"👤 Username: {self.username}")
            print("=" * 50)
            
            # Démarrer le thread d'écoute
            listener = threading.Thread(target=self.listen, daemon=True)
            listener.start()
            
            # Boucle principale
            print("📝 Tapez 'quit' pour quitter")
            print("💡 Tapez une commande pour l'exécuter")
            print("=" * 50)
            
            while self.running:
                try:
                    cmd = input("> ").strip()
                    if cmd.lower() in ['quit', 'exit', 'q']:
                        break
                    if cmd:
                        self.execute_and_send(cmd)
                except EOFError:
                    break
                except KeyboardInterrupt:
                    break
                    
        except ConnectionRefusedError:
            print(f"❌ Connexion refusée. Le serveur est-il démarré sur {self.host}:{self.port} ?")
            print("💡 Vérifiez que le serveur est lancé avec 'python3 serveur_improved_with_username.py'")
        except socket.timeout:
            print("❌ Timeout - Le serveur ne répond pas")
        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
        finally:
            self.close()
    
    def execute_and_send(self, command):
        """Exécuter une commande et envoyer le résultat"""
        try:
            print(f"💻 Exécution: {command}")
            start_time = time.time()
            
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=30
            )
            
            duration = time.time() - start_time
            output = result.stdout + result.stderr
            
            if not output.strip():
                output = "(aucune sortie)"
            
            # Afficher le résultat
            print("📋 Résultat:")
            print("-" * 40)
            print(output[:500])
            if len(output) > 500:
                print(f"... (truncated, total {len(output)} chars)")
            print("-" * 40)
            print(f"⏱️ Durée: {duration:.3f}s")
            
            # Envoyer au serveur
            if self.connected and self.sock:
                msg = {
                    'type': 'command_result',
                    'command': command,
                    'result': output,
                    'duration': round(duration, 3),
                    'username': self.username
                }
                try:
                    self.sock.send(json.dumps(msg).encode())
                    print("✅ Résultat envoyé au serveur")
                except Exception as e:
                    print(f"❌ Erreur lors de l'envoi: {e}")
            
        except subprocess.TimeoutExpired:
            print("❌ La commande a expiré (30s)")
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    def listen(self):
        """Écouter les commandes du serveur"""
        while self.running and self.connected:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                
                try:
                    msg = json.loads(data.decode())
                    if msg.get('type') == 'execute':
                        command = msg.get('command', '')
                        print(f"\n📥 Commande du serveur: {command}")
                        self.execute_and_send(command)
                except json.JSONDecodeError:
                    pass
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Erreur d'écoute: {e}")
                break
    
    def close(self):
        """Fermer la connexion"""
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        print("\n👋 Client déconnecté")

if __name__ == "__main__":
    # Paramètres
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 2222
    username = sys.argv[3] if len(sys.argv) > 3 else None
    
    print("=" * 50)
    print("🚀 CLIENT SSH - SUPERVISION")
    print("=" * 50)
    print(f"📡 Serveur: {host}:{port}")
    print(f"👤 Username: {username or getpass.getuser()}")
    print("=" * 50)
    
    client = ClientWithUsername(host, port, username)
    client.connect()
