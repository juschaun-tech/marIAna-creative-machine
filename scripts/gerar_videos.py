import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
RUNWAY_API_KEY = os.environ.get("RUNWAY_API_KEY") or os.getenv("RUNWAY_API_KEY")
ROTEIROS_DIR = ROOT / "outputs" / "roteiros"
OUTPUTS = ROOT / "outputs" / "videos"
OUTPUTS.mkdir(parents=True, exist_ok=True)
ERROS_LOG = ROOT / "outputs" / "erros.log"
BASE_URL = "https://api.dev.runwayml.com/v1"

def construir_prompt(roteiro):
    estrutura = roteiro.get("estrutura", 1)
    flows = {
        1: "Aerial beach view, building facade, presenter on beach, financial highlight, rooftop CTA",
        2: "Aerial beach view, presenter talking ROI, building facade, rooftop CTA",
        3: "Building facade opening, presenter with ROI data, aerial beach view, rooftop CTA",
    }
    return f"""Cinematic real estate marketing video. Florianópolis, Brazil. Campeche neighborhood. Flow: {flows.get(estrutura, "")} Visual: Bright natural lighting, no dark filters, no borders, no side blur. Smooth light transitions. Location pin labeled SPOT visible on the building. Presenter MarIAna: Brazilian woman 32-38, naturally bronzed, wavy brown hair, clean sophisticated style, neutral coastal colors. Confident, natural posture. Location: Campeche beach — blue ocean, white sand, modern building facade, rooftop with ocean view. Ending: Rooftop shot, clear sky, ocean view, CTA text overlay. Style: Premium real estate, Brazilian coastal, investor audience."""

def main():
    print("Gerando vídeos...\n")
    roteiros_path = ROTEIROS_DIR / "todos_roteiros.json"
    if not roteiros_path.exists():
        print("Execute gerar_roteiros.py primeiro.")
        return
    roteiros = json.loads(roteiros_path.read_text(encoding="utf-8"))
    headers = {"Authorization": f"Bearer {RUNWAY_API_KEY}", "Content-Type": "application/json", "X-Runway-Version": "2024-11-06"}
    gerados = 0
    for i, roteiro in enumerate(roteiros[:5], 1):
        estrutura = roteiro.get("estrutura", i)
        duracao = roteiro.get("duracao", "40s")
        segundos = int(duracao.replace("s", ""))
        nome = f"video_{i:02d}_estrutura{estrutura}_{duracao.replace('s','')}.mp4"
        print(f"Vídeo {i}/5 — Estrutura {estrutura} ({duracao})...")
        try:
            prompt = construir_prompt(roteiro)
            payload = {"promptText": prompt, "model": "gen4_turbo", "ratio": "1280:720", "duration": 10 if segundos >= 30 else 5}
            r = requests.post(f"{BASE_URL}/image_to_video", headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            job_id = r.json().get("id")
            print(f"  Job: {job_id}")
            for t in range(60):
                time.sleep(10)
                s = requests.get(f"{BASE_URL}/tasks/{job_id}", headers=headers, timeout=30).json()
                status = s.get("status")
                print(f"  Status ({t+1}/60): {status}")
                if status == "SUCCEEDED":
                    video_url = s.get("output", [None])[0]
                    video = requests.get(video_url, timeout=120)
                    (OUTPUTS / nome).write_bytes(video.content)
                    print(f"  Salvo: {nome}")
                    gerados += 1
                    break
                elif status == "FAILED":
                    raise ValueError(s.get("failure", "desconhecido"))
        except Exception as e:
            print(f"  Erro: {e}")
            with open(ERROS_LOG, "a") as f:
                f.write(f"Video {i}: {e}\n")
    print(f"\n{gerados}/5 vídeos gerados.")

if __name__ == "__main__":
    main()
