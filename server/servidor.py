from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuração de CORS para evitar erros entre a porta 5500 e 5000
CORS(app, resources={r"/*": {"origins": "*"}})

# Configurações de Pastas
CAMINHO_PENDENTES = os.path.join('..', 'public', 'pendentes.json')  # <-- corrigido!
PASTA_UPLOADS = 'uploads'

# Garante que a pasta de uploads existe
if not os.path.exists(PASTA_UPLOADS):
    os.makedirs(PASTA_UPLOADS)

def ler_json(caminho):
    if not os.path.exists(caminho):
        return []
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            return json.loads(conteudo) if conteudo else []
    except Exception as e:
        print(f"⚠️ Erro ao ler {caminho}: {e}")
        return []

def guardar_json(caminho, dados):
    try:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"❌ Erro ao guardar {caminho}: {e}")
        return False

@app.route('/receber-musica', methods=['POST', 'OPTIONS'])
def receber_musica():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    print("\n--- 📥 Nova Requisição Recebida ---")

    try:
        # 1. Capturar dados do formulário
        artista = request.form.get('artista', 'Artista Desconhecido').strip()
        titulo = request.form.get('titulo', 'Música Sem Título').strip()
        categoria = request.form.get('categoria', 'INTERNACIONAL').strip()
        link_externo = request.form.get('audio_link', '').strip()
        descricao = request.form.get('descricao', '').strip()
        direitos = request.form.get('direitos_confirmados', 'false').lower() == 'true'

        # 2. Verificar se veio arquivo físico
        caminho_arquivo_local = ""
        if 'audio_file' in request.files:
            file = request.files['audio_file']
            if file.filename != '':
                filename = secure_filename(f"{uuid.uuid4().hex[:5]}_{file.filename}")
                filepath = os.path.join(PASTA_UPLOADS, filename)
                file.save(filepath)
                caminho_arquivo_local = filepath
                print(f"✅ Arquivo salvo: {filename}")

        # 3. Validação: Precisa de pelo menos um link ou um arquivo
        if not link_externo and not caminho_arquivo_local:
            print("⚠️ Falha: Nenhum áudio ou link fornecido.")
            return jsonify({"status": "erro", "mensagem": "Falta o áudio!"}), 400

        # 3.5 Validação dos direitos autorais
        if not direitos:
            return jsonify({"status": "erro", "mensagem": "É necessário confirmar os direitos autorais."}), 400

        # 4. Criar o objeto da música
        nova_musica = {
            "id": str(uuid.uuid4())[:8],
            "artista": artista,
            "titulo": titulo,
            "categoria": categoria,
            "url_externa": link_externo,
            "arquivo_local": caminho_arquivo_local,
            "capa": "https://i.postimg.cc/RhnRhFNj/Logo-STP.png",
            "descricao": descricao,
            "video": "",
            "direitos_confirmados": direitos,
            "data_envio": os.popen('date').read().strip(),
            "data_aprovacao": "",
            "downloads": 100,
            "estado": "pendente"
        }

        # 5. Guardar no JSON
        pendentes = ler_json(CAMINHO_PENDENTES)
        pendentes.append(nova_musica)

        if guardar_json(CAMINHO_PENDENTES, pendentes):
            print(f"✅ Sucesso: {titulo} de {artista} adicionado aos pendentes.")
            return jsonify({"status": "sucesso", "mensagem": "Música recebida com sucesso!"}), 200
        else:
            return jsonify({"status": "erro", "mensagem": "Erro ao salvar no banco de dados."}), 500

    except Exception as e:
        print(f"💥 ERRO CRÍTICO NO SERVIDOR: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🌍 SANTOLA MUSIC BACKEND - ATIVO")
    print("📍 Porta: 5000")
    print("📁 Arquivo de dados: " + os.path.abspath(CAMINHO_PENDENTES))
    print("="*50 + "\n")
    app.run(debug=True, port=5000)