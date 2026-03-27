"""
gerar_videos.py
Gera 5 vídeos com a persona MarIAna apresentando o empreendimento.
Usa RunwayML image_to_video: foto do empreendimento como base visual
+ prompt rico com narração da MarIAna extraída do roteiro.
"""
import os
import json
import time
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

RUNWAY_API_KEY = os.environ.get("RUNWAY_API_KEY") or os.getenv("RUNWAY_API_KEY")
ROTEIROS_DIR   = ROOT / "outputs" / "roteiros"
ASSETS_DIR     = ROOT / "assets"
OUTPUTS        = ROOT / "outputs" / "videos"
OUTPUTS.mkdir(parents=True, exist_ok=True)
ERROS_LOG      = ROOT / "outputs" / "erros.log"
BASE_URL       = "https://api.dev.runwayml.com/v1"

MARIANA_DESC = (
    "Presenter MarIAna: Brazilian woman 32-38 years old, naturally bronzed skin, "
    "wavy brown medium-length hair, clean sophisticated style, neutral coastal colors "
    "(off-white, beige, light blue). Confident posture, natural body language. "
    "Speaking directly to camera as a knowledgeable local investor, not as an actress."
)


def listar_assets() -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted([f for f in ASSETS_DIR.iterdir() if f.suffix.lower() in exts])


def imagem_para_base64(path: Path) -> str:
    ext_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
    mime = ext_map.get(path.suffix.lower(), "jpeg")
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/{mime};base64,{b64}"


def construir_prompt(roteiro: dict, briefing: dict) -> str:
    narracao   = roteiro.get("narracao_mariana", "")
    visuais    = roteiro.get("descricao_visual", [])
    cta        = roteiro.get("cta_final", "Acesse e simule o seu retorno com a Seazone.")
    estrutura  = roteiro.get("estrutura", 1)
    duracao    = roteiro.get("duracao", "40s")

    loc  = briefing.get("localizacao", {})
    fin  = briefing.get("dados_financeiros", {})
    nome = briefing.get("nome_empreendimento", "empreendimento")

    bairro = loc.get("bairro", "Campeche")
    cidade = loc.get("cidade", "Florianópolis")
    roi    = fin.get("roi", "")
    rend   = fin.get("rendimento_mensal", "")

    # Descrição visual do primeiro take
    take1 = visuais[0].get("descricao", "") if visuais else ""

    flows = {
        1: "aerial view of the property, then facade, then presenter speaking to camera",
        2: "presenter walking toward camera near the building, then aerial view",
        3: "building facade reveal, presenter presenting financial data, aerial view",
    }
    flow = flows.get(estrutura, flows[1])

    texto_tela = ""
    if roi:
        texto_tela += f"ROI {roi} | "
    if rend:
        texto_tela += f"{rend}/mês | "
    texto_tela += f"{bairro}, {cidade} - SC"

    prompt = (
        f"Cinematic real estate marketing video for {nome}, {bairro}, {cidade}, Brazil. "
        f"Flow: {flow}. "
        f"{MARIANA_DESC} "
        f"Scene: {take1} " if take1 else ""
        f"Narration context: '{narracao[:120]}' "
        f"On-screen text overlay: '{texto_tela}'. "
        f"CTA at end: '{cta}'. "
        f"Style: premium real estate, bright natural lighting, no dark filters, "
        f"no borders, no side blur, smooth transitions. "
        f"Location pin labeled SPOT visible on the building. "
        f"Duration feel: {duracao}."
    )
    return prompt.strip()


def carregar_briefing() -> dict:
    p = ROOT / "input" / "briefing_extraido.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def main():
    print("Gerando vídeos com MarIAna...\n")

    if not RUNWAY_API_KEY:
        print("ERRO: RUNWAY_API_KEY não configurada.")
        with open(ERROS_LOG, "a") as f:
            f.write("gerar_videos: RUNWAY_API_KEY não configurada\n")
        return

    roteiros_path = ROTEIROS_DIR / "todos_roteiros.json"
    if not roteiros_path.exists():
        print("ERRO: Execute gerar_roteiros.py primeiro.")
        return

    roteiros = json.loads(roteiros_path.read_text(encoding="utf-8"))
    if not roteiros:
        print("ERRO: todos_roteiros.json está vazio.")
        return

    assets = listar_assets()
    if not assets:
        print("ERRO: Nenhum asset em assets/.")
        return

    briefing = carregar_briefing()
    headers  = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type":  "application/json",
        "X-Runway-Version": "2024-11-06",
    }

    gerados = 0
    for i, roteiro in enumerate(roteiros[:5], 1):
        estrutura = roteiro.get("estrutura", i)
        duracao   = roteiro.get("duracao", "40s")
        segundos  = int(str(duracao).replace("s", ""))
        nome      = f"video_{i:02d}_estrutura{estrutura}_{str(duracao).replace('s','')}.mp4"

        print(f"Vídeo {i}/5 — Estrutura {estrutura} ({duracao})...")

        try:
            asset     = assets[(i - 1) % len(assets)]
            prompt    = construir_prompt(roteiro, briefing)
            img_b64   = imagem_para_base64(asset)

            payload = {
                "promptImage": img_b64,
                "promptText":  prompt,
                "model":       "gen4_turbo",
                "ratio":       "1280:720",
                "duration":    10 if segundos >= 30 else 5,
            }

            r = requests.post(
                f"{BASE_URL}/image_to_video",
                headers=headers,
                json=payload,
                timeout=60,
            )
            r.raise_for_status()
            job_id = r.json().get("id")
            print(f"  Job: {job_id}")

            for t in range(90):
                time.sleep(10)
                s      = requests.get(f"{BASE_URL}/tasks/{job_id}", headers=headers, timeout=30).json()
                status = s.get("status")
                print(f"  Status ({t+1}/90): {status}")
                if status == "SUCCEEDED":
                    video_url = s.get("output", [None])[0]
                    video     = requests.get(video_url, timeout=120)
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

    print(f"\n{gerados}/5 vídeos gerados em outputs/videos/")


if __name__ == "__main__":
    main()
