import os
import sys
import json
import zipfile
import subprocess
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv

load_dotenv()  # carrega .env local se existir, sem sobrescrever vars da plataforma

# Log de diagnóstico — mostra quais chaves estão configuradas (sem expor valores)
for var in ["GROQ_API_KEY", "RUNWAY_API_KEY"]:
    valor = os.environ.get(var)
    if valor:
        print(f"[env] {var} = configurada ({len(valor)} chars)")
    else:
        print(f"[env] ⚠ {var} = NÃO CONFIGURADA")

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/<path:path>", methods=["OPTIONS"])
@app.route("/", methods=["OPTIONS"])
def options_handler(path=""):
    return "", 204

ROOT = Path(__file__).parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "outputs"
INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

PYTHON = sys.executable  # usa o mesmo python que rodou app.py

progress_status = {"etapa": "", "pct": 0, "concluido": False, "erro": None}


def rodar_script(nome_script: str, timeout: int = 300) -> bool:
    """Executa um script e retorna True se passou, False se falhou."""
    script_path = ROOT / "scripts" / nome_script
    try:
        env = os.environ.copy()
        result = subprocess.run(
            [PYTHON, str(script_path)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=timeout,
            env=env
        )
        print(f"\n=== {nome_script} ===")
        print(result.stdout)
        if result.returncode != 0:
            print(f"STDERR: {result.stderr}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"\n=== {nome_script} — TIMEOUT após {timeout}s ===")
        return False


def rodar_maquina(url_briefing: str):
    global progress_status
    try:
        # Salva o link do briefing (linha 2 fica em branco — assets já foram salvos)
        links_path = INPUT_DIR / "links.txt"
        links_path.write_text(f"{url_briefing}\n", encoding="utf-8")

        # Etapa 1 — Briefing
        progress_status.update({"etapa": "Lendo briefing...", "pct": 10})
        rodar_script("ler_briefing.py")  # continua mesmo se falhar (usa defaults)

        # Etapa 2 — Roteiros (usa briefing extraído)
        progress_status.update({"etapa": "Gerando roteiros...", "pct": 30})
        rodar_script("gerar_roteiros.py")

        # Etapa 3 — Imagens (usa briefing + assets já salvos em assets/)
        progress_status.update({"etapa": "Gerando imagens...", "pct": 55})
        rodar_script("gerar_imagens.py")

        # Etapa 4 — Vídeos com MarIAna (usa roteiros + assets)
        progress_status.update({"etapa": "Gerando vídeos...", "pct": 80})
        rodar_script("gerar_videos.py", timeout=600)

        # Compacta outputs
        progress_status.update({"etapa": "Compactando criativos...", "pct": 95})
        zip_path = ROOT / "criativos_seazone.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for pasta in ["imagens", "videos"]:
                dir_pasta = OUTPUT_DIR / pasta
                if dir_pasta.exists():
                    for arq in dir_pasta.iterdir():
                        zf.write(arq, f"{pasta}/{arq.name}")

        progress_status.update({"etapa": "Concluído!", "pct": 100, "concluido": True})

    except Exception as e:
        progress_status.update({"erro": str(e), "etapa": f"Erro: {e}"})
        with open(OUTPUT_DIR / "erros.log", "a", encoding="utf-8") as f:
            f.write(f"app.py: {e}\n")


@app.route("/")
def index():
    return (ROOT / "index.html").read_text(encoding="utf-8")


@app.route("/gerar", methods=["POST"])
def gerar():
    global progress_status

    url_briefing = request.form.get("url_briefing", "").strip()
    if not url_briefing:
        return jsonify({"erro": "Cole o link do briefing"}), 400

    # Salva imagens enviadas em assets/
    ASSETS_DIR = ROOT / "assets"
    ASSETS_DIR.mkdir(exist_ok=True)

    # Limpa assets anteriores
    for f in ASSETS_DIR.iterdir():
        if f.is_file():
            f.unlink()

    imagens_salvas = 0
    for key in sorted(request.files.keys()):
        file = request.files[key]
        if not file or not file.filename:
            continue
        ext = Path(file.filename).suffix.lower() or ".jpg"
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        destino = ASSETS_DIR / f"asset_{imagens_salvas + 1}{ext}"
        file.save(str(destino))
        print(f"[upload] salvo: {destino.name} ({destino.stat().st_size} bytes)")
        imagens_salvas += 1

    if imagens_salvas == 0:
        return jsonify({"erro": "Selecione ao menos 1 imagem (JPG, PNG ou WEBP)"}), 400

    progress_status = {"etapa": "Iniciando...", "pct": 0, "concluido": False, "erro": None}
    t = threading.Thread(target=rodar_maquina, args=(url_briefing,))
    t.daemon = True
    t.start()

    return jsonify({"ok": True, "imagens": imagens_salvas})


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
    app.run(host="0.0.0.0", port=port, debug=False)
