import os
import json
import subprocess
from datetime import datetime, timezone, date
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import hashlib

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ============================================================
# CAMINHOS (relativos à pasta server/)
# ============================================================
CAMINHO_MUSICAS   = os.path.join('..', 'public', 'musicas.json')
CAMINHO_PENDENTES = os.path.join('..', 'public', 'pendentes.json')
CAMINHO_ANUNCIOS  = os.path.join('..', 'public', 'anuncios.json')
CAMINHO_EVENTOS   = os.path.join('..', 'public', 'eventos.json')
CAMINHO_CONFIG    = os.path.join('..', 'public', 'config.json')
CAMINHO_VERSAO    = os.path.join('..', 'public', 'versao.json')
CAMINHO_VISITANTES= os.path.join('..', 'public', 'visitantes.json')
CAMINHO_PLAYLISTS = os.path.join('..', 'public', 'playlists_oficiais.json')

# IDs do Google Drive
ID_PASTA_PENDENTE = '1mwOkeaeO8KZnVJNPDkY9PVeKr1T9_zKk'
ID_PASTA_APROVADA = '1JBt9Qi7IVBQWuK6uwpP8quzGRXzmWe3Q'
ID_PLANILHA       = '1EwUiKVzy3bBikekWYgFGmfgLAbocX1lWv8_u_7aH90M'
INTERVALO_SHEET   = 'Página1!A:E'

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def ler_json(caminho, tipo='lista'):
    if not os.path.exists(caminho):
        return [] if tipo == 'lista' else {}
    with open(caminho, 'r', encoding='utf-8') as f:
        conteudo = f.read()
        if not conteudo:
            return [] if tipo == 'lista' else {}
        dados = json.loads(conteudo)
        if tipo == 'lista' and not isinstance(dados, list):
            return []
        if tipo == 'dict' and not isinstance(dados, dict):
            return {}
        return dados

def guardar_json(caminho, dados):
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def atualizar_versao():
    with open(CAMINHO_VERSAO, 'w') as f:
        json.dump({"versao": datetime.now(timezone.utc).isoformat()}, f)

def sincronizar_github():
    """Opcional: sincroniza automaticamente com o repositório Git"""
    try:
        print("📤 Sincronizando com o GitHub...")
        subprocess.run(["git", "add", CAMINHO_MUSICAS, CAMINHO_PENDENTES,
                        CAMINHO_ANUNCIOS, CAMINHO_EVENTOS, CAMINHO_CONFIG,
                        CAMINHO_VERSAO, CAMINHO_VISITANTES, CAMINHO_PLAYLISTS], check=True)
        subprocess.run(["git", "commit", "-m", "Auto-update via Santola Admin"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ GitHub atualizado!")
        return True
    except Exception as e:
        print(f"❌ Erro ao sincronizar GitHub: {e}")
        return False

def obter_credenciais():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Atualizando token expirado...")
            creds.refresh(Request())
        else:
            print("🔑 Iniciando novo login no Google...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def obter_drive():
    return build('drive', 'v3', credentials=obter_credenciais())

def obter_sheets():
    return build('sheets', 'v4', credentials=obter_credenciais())

def calcular_hash_anonimo(ip, user_agent):
    return hashlib.sha256(f"{ip}_{user_agent}".encode()).hexdigest()[:16]

# ============================================================
# ROTAS DA API (existentes + novas)
# ============================================================

# ---------- PENDENTES ----------
@app.route('/listar_pendentes')
def listar_pendentes():
    try:
        pendentes = ler_json(CAMINHO_PENDENTES, tipo='lista')
        return jsonify({"status": "sucesso", "pendentes": pendentes})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ---------- APROVAR MÚSICA ----------
@app.route('/aprovar_musica', methods=['POST'])
def aprovar_musica():
    dados = request.json
    file_id   = dados.get('drive_id')
    id_pendente = dados.get('id_pendente')

    try:
        if file_id:
            drive = obter_drive()
            file = drive.files().get(fileId=file_id, fields='parents').execute()
            prev = ",".join(file.get('parents'))
            drive.files().update(fileId=file_id,
                                 addParents=ID_PASTA_APROVADA,
                                 removeParents=prev).execute()

        musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
        categoria = dados.get('categoria', 'INTERNACIONAL')
        if categoria not in musicas:
            musicas[categoria] = []

        nova = {
            "artista": dados.get('artista'),
            "titulo": dados.get('titulo'),
            "capa": dados.get('capa', 'https://i.postimg.cc/RhnRhFNj/Logo-STP.png'),
            "url": dados.get('link') or dados.get('url'),
            "descricao": dados.get('descricao', ''),
            "video": dados.get('video', ''),
            "direitos_confirmados": True,
            "data_aprovacao": datetime.now().strftime("%Y-%m-%d"),
            "downloads": 100
        }
        musicas[categoria].append(nova)
        guardar_json(CAMINHO_MUSICAS, musicas)

        pendentes = ler_json(CAMINHO_PENDENTES, tipo='lista')
        pendentes = [p for p in pendentes if p.get('id') != id_pendente]
        guardar_json(CAMINHO_PENDENTES, pendentes)

        atualizar_versao()
        # sincronizar_github()
        return jsonify({"status": "sucesso", "mensagem": "Música aprovada e publicada!"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ---------- SALVAR CONTEÚDO ----------
@app.route('/salvar_conteudo', methods=['POST'])
def salvar_conteudo():
    dados = request.json
    try:
        musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
        categoria = dados.get('categoria')
        if categoria not in musicas:
            return jsonify({"status": "erro", "mensagem": "Categoria inválida"}), 400

        for m in musicas[categoria]:
            if m.get('artista') == dados.get('artista') and m.get('titulo') == dados.get('titulo'):
                m['descricao'] = dados.get('descricao', m.get('descricao', ''))
                m['video'] = dados.get('video', m.get('video', ''))
                m['direitos_confirmados'] = dados.get('direitos_confirmados', m.get('direitos_confirmados', True))
                break

        guardar_json(CAMINHO_MUSICAS, musicas)
        atualizar_versao()
        return jsonify({"status": "sucesso", "mensagem": "Conteúdo actualizado!"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ---------- ANÚNCIOS ----------
@app.route('/listar_anuncios')
def listar_anuncios():
    try:
        anuncios = ler_json(CAMINHO_ANUNCIOS, tipo='lista')
        return jsonify({"status": "sucesso", "anuncios": anuncios})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/adicionar_anuncio', methods=['POST'])
def adicionar_anuncio():
    dados = request.json
    try:
        anuncios = ler_json(CAMINHO_ANUNCIOS, tipo='lista')
        anuncios.append({"img": dados.get('img'), "link": dados.get('link')})
        guardar_json(CAMINHO_ANUNCIOS, anuncios)
        atualizar_versao()
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/remover_anuncio', methods=['POST'])
def remover_anuncio():
    dados = request.json
    index = dados.get('index', -1)
    try:
        anuncios = ler_json(CAMINHO_ANUNCIOS, tipo='lista')
        if 0 <= index < len(anuncios):
            del anuncios[index]
            guardar_json(CAMINHO_ANUNCIOS, anuncios)
            atualizar_versao()
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ---------- EVENTOS ----------
@app.route('/listar_eventos')
def listar_eventos():
    try:
        eventos = ler_json(CAMINHO_EVENTOS, tipo='lista')
        return jsonify({"status": "sucesso", "eventos": eventos})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/adicionar_evento', methods=['POST'])
def adicionar_evento():
    dados = request.json
    try:
        eventos = ler_json(CAMINHO_EVENTOS, tipo='lista')
        novo_evento = {
            "nome": dados.get('nome'),
            "data": dados.get('data'),
            "local": dados.get('local', ''),
            "descricao": dados.get('descricao', ''),
            "banner_imagem": dados.get('banner_imagem', ''),
            "banner_link": dados.get('banner_link', '')
        }
        eventos.append(novo_evento)
        guardar_json(CAMINHO_EVENTOS, eventos)
        atualizar_versao()
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/remover_evento', methods=['POST'])
def remover_evento():
    dados = request.json
    index = dados.get('index', -1)
    try:
        eventos = ler_json(CAMINHO_EVENTOS, tipo='lista')
        if 0 <= index < len(eventos):
            del eventos[index]
            guardar_json(CAMINHO_EVENTOS, eventos)
            atualizar_versao()
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ---------- CONFIGURAÇÕES ----------
@app.route('/obter_config')
def obter_config():
    try:
        config = ler_json(CAMINHO_CONFIG, tipo='dict')
        return jsonify(config)
    except Exception as e:
        return jsonify({}), 200

@app.route('/salvar_config', methods=['POST'])
def salvar_config():
    dados = request.json
    try:
        guardar_json(CAMINHO_CONFIG, dados)
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ============================================================
# NOVAS ROTAS (25 MELHORIAS)
# ============================================================

# 1. Contagem de visitantes (real, com identificação anónima)
@app.route('/contar_visita', methods=['POST'])
def contar_visita():
    try:
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'desconhecido')
        identificador = calcular_hash_anonimo(ip, user_agent)

        dados = ler_json(CAMINHO_VISITANTES, tipo='dict')
        hoje = date.today().isoformat()

        dados['total'] = dados.get('total', 0) + 1
        if 'por_dia' not in dados:
            dados['por_dia'] = {}
        if hoje not in dados['por_dia']:
            dados['por_dia'][hoje] = {"visitas": 0, "unicos": 0, "identificadores": []}
        dados['por_dia'][hoje]['visitas'] += 1

        if 'visitantes_unicos' not in dados:
            dados['visitantes_unicos'] = []
        if identificador not in dados['visitantes_unicos']:
            dados['visitantes_unicos'].append(identificador)
            dados['por_dia'][hoje]['unicos'] += 1
            dados['por_dia'][hoje]['identificadores'].append(identificador)

        guardar_json(CAMINHO_VISITANTES, dados)
        return jsonify({
            "status": "sucesso",
            "total": dados['total'],
            "hoje": dados['por_dia'][hoje]['visitas'],
            "unicos_hoje": dados['por_dia'][hoje]['unicos']
        })
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 2. Obter dados completos de visitantes (para painel admin)
@app.route('/obter_visitantes')
def obter_visitantes():
    try:
        dados = ler_json(CAMINHO_VISITANTES, tipo='dict')
        return jsonify(dados)
    except Exception as e:
        return jsonify({"total": 0, "por_dia": {}, "visitantes_unicos": []})

# 3. Estatísticas rápidas
@app.route('/estatisticas')
def estatisticas():
    try:
        musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
        total_musicas = sum(len(v) for v in musicas.values())
        total_downloads = sum(m.get('downloads', 0) for cat in musicas.values() for m in cat)
        categorias = len(musicas)
        return jsonify({
            "total_musicas": total_musicas,
            "total_downloads": total_downloads,
            "categorias": categorias
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# 4. Backup (exportar todos os dados num JSON)
@app.route('/backup_completo')
def backup_completo():
    try:
        backup = {
            "musicas": ler_json(CAMINHO_MUSICAS, tipo='dict'),
            "pendentes": ler_json(CAMINHO_PENDENTES, tipo='lista'),
            "anuncios": ler_json(CAMINHO_ANUNCIOS, tipo='lista'),
            "eventos": ler_json(CAMINHO_EVENTOS, tipo='lista'),
            "config": ler_json(CAMINHO_CONFIG, tipo='dict'),
            "visitantes": ler_json(CAMINHO_VISITANTES, tipo='dict'),
            "playlists": ler_json(CAMINHO_PLAYLISTS, tipo='lista')
        }
        return jsonify(backup)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# 5. Restaurar backup (sobregrava os ficheiros com um JSON completo)
@app.route('/restaurar_backup', methods=['POST'])
def restaurar_backup():
    dados = request.json
    try:
        if 'musicas' in dados:
            guardar_json(CAMINHO_MUSICAS, dados['musicas'])
        if 'pendentes' in dados:
            guardar_json(CAMINHO_PENDENTES, dados['pendentes'])
        if 'anuncios' in dados:
            guardar_json(CAMINHO_ANUNCIOS, dados['anuncios'])
        if 'eventos' in dados:
            guardar_json(CAMINHO_EVENTOS, dados['eventos'])
        if 'config' in dados:
            guardar_json(CAMINHO_CONFIG, dados['config'])
        if 'visitantes' in dados:
            guardar_json(CAMINHO_VISITANTES, dados['visitantes'])
        if 'playlists' in dados:
            guardar_json(CAMINHO_PLAYLISTS, dados['playlists'])
        atualizar_versao()
        return jsonify({"status": "sucesso", "mensagem": "Backup restaurado!"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 6. Listar playlists oficiais
@app.route('/listar_playlists')
def listar_playlists():
    try:
        playlists = ler_json(CAMINHO_PLAYLISTS, tipo='lista')
        return jsonify({"status": "sucesso", "playlists": playlists})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 7. Adicionar playlist oficial
@app.route('/adicionar_playlist', methods=['POST'])
def adicionar_playlist():
    dados = request.json
    try:
        playlists = ler_json(CAMINHO_PLAYLISTS, tipo='lista')
        playlists.append({
            "nome": dados.get('nome'),
            "musicas": dados.get('musicas', [])
        })
        guardar_json(CAMINHO_PLAYLISTS, playlists)
        atualizar_versao()
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 8. Remover playlist oficial
@app.route('/remover_playlist', methods=['POST'])
def remover_playlist():
    dados = request.json
    index = dados.get('index', -1)
    try:
        playlists = ler_json(CAMINHO_PLAYLISTS, tipo='lista')
        if 0 <= index < len(playlists):
            del playlists[index]
            guardar_json(CAMINHO_PLAYLISTS, playlists)
            atualizar_versao()
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 9. Incrementar download (ao baixar uma música)
@app.route('/incrementar_download', methods=['POST'])
def incrementar_download():
    dados = request.json
    artista = dados.get('artista')
    titulo = dados.get('titulo')
    categoria = dados.get('categoria')
    try:
        musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
        if categoria in musicas:
            for m in musicas[categoria]:
                if m.get('artista') == artista and m.get('titulo') == titulo:
                    m['downloads'] = m.get('downloads', 100) + 1
                    guardar_json(CAMINHO_MUSICAS, musicas)
                    atualizar_versao()
                    return jsonify({"status": "sucesso", "downloads": m['downloads']})
        return jsonify({"status": "erro", "mensagem": "Música não encontrada"}), 404
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 10. Marcar/desmarcar direitos autorais via admin
@app.route('/toggle_direitos', methods=['POST'])
def toggle_direitos():
    dados = request.json
    try:
        musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
        categoria = dados.get('categoria')
        if categoria in musicas:
            for m in musicas[categoria]:
                if m.get('artista') == dados.get('artista') and m.get('titulo') == dados.get('titulo'):
                    m['direitos_confirmados'] = not m.get('direitos_confirmados', True)
                    guardar_json(CAMINHO_MUSICAS, musicas)
                    atualizar_versao()
                    return jsonify({"status": "sucesso", "direitos_confirmados": m['direitos_confirmados']})
        return jsonify({"status": "erro", "mensagem": "Música não encontrada"}), 404
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 11. Limpar visitantes (reset ao contador) – útil para testes
@app.route('/reset_visitantes', methods=['POST'])
def reset_visitantes():
    try:
        dados = {"total": 0, "por_dia": {}, "visitantes_unicos": []}
        guardar_json(CAMINHO_VISITANTES, dados)
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 12. Pesquisa avançada (por múltiplos critérios)
@app.route('/pesquisar_musicas')
def pesquisar_musicas():
    q = request.args.get('q', '').lower()
    musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
    resultados = []
    for cat, lista in musicas.items():
        for m in lista:
            if q in m.get('artista','').lower() or q in m.get('titulo','').lower() or q in cat.lower():
                resultados.append({**m, "categoria": cat})
    return jsonify({"resultados": resultados[:20]})

# 13. Rota para obter a versão atual (usada pelo polling manual)
@app.route('/versao_atual')
def versao_atual():
    try:
        with open(CAMINHO_VERSAO) as f:
            return jsonify({"versao": json.load(f)['versao']})
    except:
        return jsonify({"versao": "0"})

# 14. Forçar atualização da versão (disparar polling em clientes)
@app.route('/forcar_atualizacao', methods=['POST'])
def forcar_atualizacao():
    atualizar_versao()
    return jsonify({"status": "sucesso"})

# 15. Contagem de músicas pendentes (rápido)
@app.route('/count_pendentes')
def count_pendentes():
    pendentes = ler_json(CAMINHO_PENDENTES, tipo='lista')
    return jsonify({"count": len(pendentes)})

# 16. Obter uma música específica (para deep linking seguro)
@app.route('/obter_musica')
def obter_musica():
    artista = request.args.get('artista')
    titulo = request.args.get('titulo')
    musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
    for cat, lista in musicas.items():
        for m in lista:
            if m.get('artista') == artista and m.get('titulo') == titulo:
                return jsonify({**m, "categoria": cat})
    return jsonify({"erro": "Não encontrada"}), 404

# 17. Obter lista de categorias (chaves do musicas.json)
@app.route('/categorias')
def categorias():
    musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
    return jsonify({"categorias": list(musicas.keys())})

# 18. Renomear categoria (útil no admin)
@app.route('/renomear_categoria', methods=['POST'])
def renomear_categoria():
    dados = request.json
    antiga = dados.get('antiga')
    nova = dados.get('nova')
    musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
    if antiga in musicas and nova not in musicas:
        musicas[nova] = musicas.pop(antiga)
        guardar_json(CAMINHO_MUSICAS, musicas)
        atualizar_versao()
        return jsonify({"status": "sucesso"})
    return jsonify({"status": "erro", "mensagem": "Categoria inválida"}), 400

# 19. Mover música para outra categoria
@app.route('/mover_musica', methods=['POST'])
def mover_musica():
    dados = request.json
    artista = dados.get('artista')
    titulo = dados.get('titulo')
    origem = dados.get('origem')
    destino = dados.get('destino')
    musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
    if origem in musicas and destino in musicas:
        for i, m in enumerate(musicas[origem]):
            if m.get('artista') == artista and m.get('titulo') == titulo:
                musica = musicas[origem].pop(i)
                musicas[destino].append(musica)
                guardar_json(CAMINHO_MUSICAS, musicas)
                atualizar_versao()
                return jsonify({"status": "sucesso"})
    return jsonify({"status": "erro", "mensagem": "Música não encontrada"}), 404

# 20. Eliminar música permanentemente
@app.route('/eliminar_musica', methods=['POST'])
def eliminar_musica():
    dados = request.json
    categoria = dados.get('categoria')
    artista = dados.get('artista')
    titulo = dados.get('titulo')
    musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
    if categoria in musicas:
        musicas[categoria] = [m for m in musicas[categoria] if not (m.get('artista')==artista and m.get('titulo')==titulo)]
        guardar_json(CAMINHO_MUSICAS, musicas)
        atualizar_versao()
        return jsonify({"status": "sucesso"})
    return jsonify({"status": "erro"}), 400

# 21. Atualizar downloads massivamente (definir valor)
@app.route('/set_downloads', methods=['POST'])
def set_downloads():
    dados = request.json
    categoria = dados.get('categoria')
    artista = dados.get('artista')
    titulo = dados.get('titulo')
    valor = dados.get('valor', 100)
    musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
    if categoria in musicas:
        for m in musicas[categoria]:
            if m.get('artista')==artista and m.get('titulo')==titulo:
                m['downloads'] = valor
                guardar_json(CAMINHO_MUSICAS, musicas)
                return jsonify({"status": "sucesso"})
    return jsonify({"erro": "Música não encontrada"}), 404

# 22. Listar todas as músicas (para exportação)
@app.route('/todas_musicas')
def todas_musicas():
    musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
    todas = []
    for cat, lista in musicas.items():
        for m in lista:
            todas.append({**m, "categoria": cat})
    return jsonify({"musicas": todas})

# 23. Rota de saúde (health check)
@app.route('/ping')
def ping():
    return jsonify({"pong": True, "hora": datetime.now().isoformat()})

# 24. Contagem de eventos ativos (não expirados)
@app.route('/eventos_ativos')
def eventos_ativos():
    eventos = ler_json(CAMINHO_EVENTOS, tipo='lista')
    hoje = date.today().isoformat()
    ativos = [e for e in eventos if e.get('data', '') >= hoje]
    return jsonify({"count": len(ativos), "eventos": ativos})

# 25. Gerar sitemap dinâmico (básico)
@app.route('/gerar_sitemap')
def gerar_sitemap():
    base = "https://punshiline9.github.io/santola_music/"
    urls = [base + "index.html", base + "categorias.html", base + "eventos.html", base + "playlist.html"]
    musicas = ler_json(CAMINHO_MUSICAS, tipo='dict')
    for cat, lista in musicas.items():
        for m in lista:
            urls.append(f"{base}?artista={m.get('artista','')}&titulo={m.get('titulo','')}")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        xml += f"  <url><loc>{url}</loc></url>\n"
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

# ============================================================
# INICIALIZAÇÃO
# ============================================================
if __name__ == '__main__':
    os.system('cls' if os.name == 'nt' else 'clear')
    print("--------------------------------------------------")
    print("🎼 SANTOLA MUSIC - ACTUALIZADOR")
    print("--------------------------------------------------")
    print("📡 Porta: 5001")
    print(f"📁 musicas.json : {os.path.abspath(CAMINHO_MUSICAS)}")
    print(f"📁 pendentes.json: {os.path.abspath(CAMINHO_PENDENTES)}")
    print("--------------------------------------------------\n")
    app.run(port=5001, debug=True)