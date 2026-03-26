"""
baixar_assets.py
Baixa imagens e vídeos da pasta pública do Google Drive para assets/
"""
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
INPUT_DIR = ROOT / "input"
ASSETS_DIR = ROOT / "assets"
ASSETS_DIR.mkdir(exist_ok=True)
ERROS_LOG = ROOT / "outputs" / "erros.log"

def extrair_folder_id(link: str) -> str:
    padrao = r"/folders/([a-zA-Z0-9_-]+)"
    match = re.search(padrao, link)
    if not match:
        raise ValueError(f"Link do Google Drive inválido: {link}")
    return match.group(1)

def baixar_arquivo_drive(file_id: str, destino: Path) -> bool:
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    session = requests.Session()
    response = session.get(url, stream=True, timeout=60)
    for key, value in response.cookies.items():
        if "download_warning" in key:
            url = f"{url}&confirm={value}"
            response = session.get(url, stream=True, timeout=60)
    if response.status_code == 200:
        destino.write_bytes(response.content)
        return True
    return False

def listar_arquivos_drive(folder_id: str) -> list:
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
    ids = list(set(re.findall(r'"([a-zA-Z0-9_-]{33})"', response.text)))
    return [{"id": fid, "nome": f"asset_{i+1}.jpg"} for i, fid in enumerate(ids[:20])]

def main():
    link_path = INPUT_DIR / "drive_link.txt"
    if not link_path.exists():
        print("ERRO: drive_link.txt não encontrado. Execute ler_briefing.py primeiro.")
        return

    link = link_path.read_text(encoding="utf-8").strip()
    print(f"Processando pasta do Drive...")

    try:
        folder_id = extrair_folder_id(link)
        arquivos = listar_arquivos_drive(folder_id)

        if not arquivos:
            print("Nenhum arquivo encontrado. Verifique se a pasta é pública.")
            return

        print(f"{len(arquivos)} arquivos encontrados. Baixando...")
        baixados = 0
        for arq in arquivos:
            destino = ASSETS_DIR / arq["nome"]
            print(f"  Baixando {arq['nome']}...")
            try:
                if baixar_arquivo_drive(arq["id"], destino):
                    print(f"  Salvo: {arq['nome']}")
                    baixados += 1
            except Exception as e:
                print(f"  Erro: {e}")
                with open(ERROS_LOG, "a") as f:
                    f.write(f"Asset {arq['nome']}: {e}\n")

        print(f"\n{baixados} assets baixados em assets/")

    except Exception as e:
        print(f"ERRO: {e}")

if __name__ == "__main__":
    main()
