import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
IDEOGRAM_API_KEY = os.getenv("IDEOGRAM_API_KEY")
ROOT = Path(__file__).parent.parent
ROTEIROS_DIR = ROOT / "outputs" / "roteiros"
OUTPUTS = ROOT / "outputs" / "imagens"
OUTPUTS.mkdir(parents=True, exist_ok=True)
ERROS_LOG = ROOT / "outputs" / "erros.log"

def construir_prompt(roteiro):
    textos = roteiro.get("texto_na_tela", [])
    destaque = next((t["texto"] for t in textos if t.get("destaque")), "ROI 16,40% ao ano")
    cta = roteiro.get("cta_final", "Fale com a Seazone")
    return f"""Premium real estate marketing image. Campeche beach, Florianópolis, Brazil. Aerial view of Novo Campeche beach, crystal blue water, white sand, modern building facade visible. Location pin labeled SPOT on the building. Style: clean, premium, bright — no dark filters, no borders, no side blur. Natural sunlight. Text overlay (clearly readable, lower third, semi-transparent dark background): Main: "{destaque}" | Secondary: "Rendimento ~R$ 5.500/mês" | CTA: "{cta}" No people. 16:9 ratio."""

def main():
    print("Gerando imagens...\n")
    roteiros_path = ROTEIROS_DIR / "todos_roteiros.json"
    if not roteiros_path.exists():
        print("Execute gerar_roteiros.py primeiro.")
        return
    roteiros = json.loads(roteiros_path.read_text(encoding="utf-8"))
    geradas = 0
    for i, roteiro in enumerate(roteiros[:5], 1):
        estrutura = roteiro.get("estrutura", i)
        duracao = roteiro.get("duracao", "?")
        nome = f"imagem_{i:02d}_estrutura{estrutura}_{duracao.replace('s','')}.jpg"
        print(f"Imagem {i}/5 — Estrutura {estrutura}...")
        try:
            prompt = construir_prompt(roteiro)
            headers = {"Api-Key": IDEOGRAM_API_KEY, "Content-Type": "application/json"}
            payload = {"image_request": {"prompt": prompt, "aspect_ratio": "ASPECT_16_9", "model": "V_2", "magic_prompt_option": "AUTO"}}
            r = requests.post("https://api.ideogram.ai/generate", headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            url = r.json()["data"][0]["url"]
            img = requests.get(url, timeout=30)
            (OUTPUTS / nome).write_bytes(img.content)
            print(f"  Salvo: {nome}")
            geradas += 1
        except Exception as e:
            print(f"  Erro: {e}")
            with open(ERROS_LOG, "a") as f:
                f.write(f"Imagem {i}: {e}\n")
    print(f"\n{geradas}/5 imagens geradas.")

if __name__ == "__main__":
    main()
