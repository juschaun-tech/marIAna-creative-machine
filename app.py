import os
import json
import zipfile
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ROOT = Path(__file__).parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "outputs"
INPUT_DIR.mkdir(exist_ok=True)

progress_status = {"etapa": "", "concluido": False, "erro": None}

def rodar_maquina(url_briefing: str, url_drive: str):
    global progress_status
    try:
        # Salva os links
        links_path = INPUT_DIR / "links.txt"
        links_path.write_text(f"{url_briefing}\n{url_drive}", encoding="utf-8")

        import subprocess, sys
        scripts = [
            ("ler_briefing.py",    "Lendo briefing..."),
            ("baixar_assets.py",   "Baixando assets do Drive..."),
            ("gerar_roteiros.py",  "Gerando roteiros..."),
            ("gerar_imagens.py",   "Gerando imagens..."),
            ("gerar_videos.py",    "Gerando vídeos..."),
        ]

        for script, etapa in scripts:
            progress_status["etapa"] = etapa
            resultado = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / script)],
                cwd=str(ROOT),
                capture_output=True,
                text=True
            )
            if resultado.returncode != 0:
                log_path = OUTPUT_DIR / "erros.log"
                with open(log_path, "a") as f:
                    f.write(f"\n{script}:\n{resultado.stderr}\n")

        # Compacta os outputs em ZIP
        progress_status["etapa"] = "Compactando criativos..."
        zip_path = ROOT / "criativos_seazone.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for pasta in ["roteiros", "imagens", "videos"]:
                pasta_path = OUTPUT_DIR / pasta
                if pasta_path.exists():
                    for arquivo in pasta_path.iterdir():
                        if arquivo.is_file():
                            zf.write(arquivo, f"{pasta}/{arquivo.name}")

        progress_status["etapa"] = "Concluído"
        progress_status["concluido"] = True

    except Exception as e:
        progress_status["erro"] = str(e)
        progress_status["etapa"] = "Erro"

@app.route("/")
def index():
    with open(ROOT / "index.html", encoding="utf-8") as f:
        return f.read()

@app.route("/gerar", methods=["POST"])
def gerar():
    global progress_status
    data = request.json
    url_briefing = data.get("url_briefing", "").strip()
    url_drive = data.get("url_drive", "").strip()

    if not url_briefing or not url_drive:
        return jsonify({"erro": "Preencha os dois links"}), 400

    progress_status = {"etapa": "Iniciando...", "concluido": False, "erro": None}
    thread = threading.Thread(target=rodar_maquina, args=(url_briefing, url_drive))
    thread.daemon = True
    thread.start()

    return jsonify({"ok": True})

@app.route("/progresso")
def progresso():
    return jsonify(progress_status)

@app.route("/download")
def download():
    zip_path = ROOT / "criativos_seazone.zip"
    if not zip_path.exists():
        return jsonify({"erro": "ZIP não encontrado"}), 404
    return send_file(zip_path, as_attachment=True, download_name="criativos_seazone.zip")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
