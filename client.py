import socket
import json
import paramiko
import subprocess
import threading
import time
import sys
import os
import platform

class SSHClientApp:
    def __init__(self, server_host='127.0.0.1', server_port=2222):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.running = False
        
    def connect_to_server(self):
        """Se connecter au serveur central"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            print(f"✅ Connecté au serveur {self.server_host}:{self.server_port}")
            return True
        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            return False
    
    def execute_command(self, command):
        """Exécuter une commande système localement"""
        try:
            start_time = time.time()
            
            # Détection du système d'exploitation
            if platform.system() == 'Windows':
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            duration = time.time() - start_time
            
            output = result.stdout + result.stderr
            if not output.strip():
                output = "(aucune sortie)"
            
            return {
                'success': True,
                'output': output.strip(),
                'duration': round(duration, 3)
            }
        except Exception as e:
            return {
                'success': False,
                'output': str(e),
                'duration': 0
            }
    
    def send_result(self, command, result):
        """Envoyer le résultat de la commande au serveur"""
        try:
            message = {
                'type': 'command_result',
                'command': command,
                'result': result['output'],
                'duration': result['duration']
            }
            self.socket.send(json.dumps(message).encode())
            print(f"📤 Résultat envoyé pour '{command}'")
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi: {e}")
    
    def listen_for_commands(self):
        """Écouter les commandes du serveur"""
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                
                message = json.loads(data.decode())
                
                if message['type'] == 'execute':
                    command = message['command']
                    print(f"📥 Commande reçue: '{command}'")
                    
                    # Exécuter la commande
                    result = self.execute_command(command)
                    print(f"✅ Résultat: {result['output'][:100]}...")
                    
                    # Envoyer le résultat
                    self.send_result(command, result)
                    
            except json.JSONDecodeError:
                # Réception d'une commande brute
                command = data.decode().strip()
                if command.lower() in ['quit', 'exit', 'bye']:
                    break
                print(f"📥 Commande brute reçue: '{command}'")
                result = self.execute_command(command)
                self.send_result(command, result)
            except Exception as e:
                if self.running:
                    print(f"❌ Erreur: {e}")
                break
    
    def start(self):
        """Démarrer le client"""
        if not self.connect_to_server():
            return
        
        self.running = True
        
        # Thread pour écouter les commandes
        listener_thread = threading.Thread(target=self.listen_for_commands)
        listener_thread.daemon = True
        listener_thread.start()
        
        print("🔄 En attente des commandes du serveur...")
        print("📝 Tapez 'quit' pour quitter")
        
        try:
            while self.running:
                # Menu interactif simple
                cmd = input("> ").strip()
                if cmd.lower() in ['quit', 'exit']:
                    break
                elif cmd:
                    # Exécuter une commande localement
                    result = self.execute_command(cmd)
                    print(f"📋 Résultat: {result['output']}")
                    self.send_result(cmd, result)
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def stop(self):
        """Arrêter le client"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        print("👋 Client arrêté")

if __name__ == "__main__":
    # Paramètres de connexion
    server_host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    server_port = int(sys.argv[2]) if len(sys.argv) > 2 else 2222
    
    print(f"🚀 Démarrage du client SSH")
    print(f"📡 Connexion à {server_host}:{server_port}")
    
    client = SSHClientApp(server_host, server_port)
    client.start()