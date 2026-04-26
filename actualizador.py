import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app) # Permite que o enviar.html comunique com este script

CAMINHO_JSON = '../musicas.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# ---------------------------------------------------------
# LÓGICA DO GOOGLE DRIVE (Mantida e melhorada)
# ---------------------------------------------------------
def obter_servico_drive():
    creds = None
    # O token.json evita que tenhas de fazer login no navegador toda a hora
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)

# ---------------------------------------------------------
# LÓGICA DO SERVIDOR LOCAL (Automação do Blog)
# ---------------------------------------------------------
@app.route('/adicionar_musica', methods=['POST'])
def adicionar_musica():
    dados_musica = request.json
    
    try:
        # 1. Ler o ficheiro JSON atual
        if os.path.exists(CAMINHO_JSON):
            with open(CAMINHO_JSON, 'r', encoding='utf-8') as f:
                musicas = json.load(f)
        else:
            musicas = []
            
        # 2. Criar um ID único para a nova música
        novo_id = len(musicas) + 1
        dados_musica['id'] = novo_id
        
        # 3. Adicionar a nova música à lista
        musicas.append(dados_musica)
        
        # 4. Guardar as alterações no JSON
        with open(CAMINHO_JSON, 'w', encoding='utf-8') as f:
            json.dump(musicas, f, indent=4, ensure_ascii=False)
            
        return jsonify({"status": "sucesso", "mensagem": "Música adicionada com sucesso ao Santola Music!"})
        
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Servidor do Santola Music a iniciar na porta 5000...")
    print("Deixe este terminal aberto e use o enviar.html no navegador.")
    # Executa o servidor local
    app.run(port=5000, debug=True)
