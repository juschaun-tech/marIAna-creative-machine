import os
import io
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

# Descrição flat illustration — alinhada com o novo perfil da MarIAna
MARIANA_DESC = (
    "Flat digital illustration style character MarIAna: young woman ~28 years old, "
    "brown skin, wavy brown hair with highlights, wearing beige blazer, white t-shirt, "
    "light blue jeans, white sneakers. Confident and welcoming posture. "
    "Color palette: beige #DCCFC3, coastal blue #28A9E1, warm neutral #C7C1B3. "
    "Smooth animation, speaking directly to viewer."
)


def listar_assets() -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted([f for f in ASSETS_DIR.iterdir() if f.suffix.lower() in exts])


def imagem_para_base64(path: Path, max_dim: int = 1024) -> str:
    """Redimensiona para max_dim antes de codificar (limita tamanho do payload)."""
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/jpeg;base64,{b64}"


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

    partes = [
        f"Cinematic real estate marketing video for {nome}, {bairro}, {cidade}, Brazil.",
        f"Flow: {flow}.",
        MARIANA_DESC,
    ]
    if take1:
        partes.append(f"Scene: {take1}")
    partes += [
        f"Narration context: '{narracao[:120]}'",
        f"On-screen text overlay: '{texto_tela}'.",
        f"CTA at end: '{cta}'.",
        "Style: premium real estate, bright natural lighting, no dark filters,",
        "no borders, no side blur, smooth transitions.",
        "Location pin labeled SPOT visible on the building.",
        f"Duration feel: {duracao}.",
    ]
    return " ".join(partes)


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

    # Carrega roteiros — tenta todos_roteiros.json, cai nos individuais se vazio
    roteiros_path = ROTEIROS_DIR / "todos_roteiros.json"
    roteiros = []
    if roteiros_path.exists():
        try:
            roteiros = json.loads(roteiros_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    if not roteiros:
        print("todos_roteiros.json vazio — carregando arquivos individuais...")
        for arq in sorted(ROTEIROS_DIR.glob("roteiro_estrutura*.json")):
            try:
                roteiros.append(json.loads(arq.read_text(encoding="utf-8")))
            except Exception:
                pass

    if not roteiros:
        print("ERRO: nenhum roteiro encontrado. Execute gerar_roteiros.py primeiro.")
        with open(ERROS_LOG, "a") as f:
            f.write("gerar_videos: nenhum roteiro disponível\n")
        return

    print(f"{len(roteiros)} roteiro(s) carregado(s).")

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
            print(f"  Runway POST status: {r.status_code}")
            if r.status_code != 200:
                raise ValueError(f"Runway erro {r.status_code}: {r.text[:300]}")
            resp_json = r.json()
            job_id = resp_json.get("id")
            if not job_id:
                raise ValueError(f"Runway sem job_id: {resp_json}")
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
            import traceback
            detalhe = traceback.format_exc()
            print(f"  Erro: {e}")
            print(f"  Detalhe:\n{detalhe}")
            with open(ERROS_LOG, "a") as f:
                f.write(f"Video {i}: {e}\n{detalhe}\n")

    print(f"\n{gerados}/5 vídeos gerados em outputs/videos/")


if __name__ == "__main__":
    main()
