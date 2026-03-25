"""
ler_briefing.py
Acessa o link da página web do briefing, extrai o conteúdo e estrutura
as informações usando Claude. Salva em input/briefing_extraido.json
"""
import json
import requests
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()
ROOT = Path(__file__).parent.parent
INPUT_DIR = ROOT / "input"
INPUT_DIR.mkdir(exist_ok=True)

def ler_links() -> tuple:
    links_path = INPUT_DIR / "links.txt"
    if not links_path.exists():
        raise FileNotFoundError("Coloque os links em input/links.txt")
    linhas = links_path.read_text(encoding="utf-8").strip().splitlines()
    if len(linhas) < 2:
        raise ValueError("input/links.txt deve ter 2 linhas: link do briefing e link do Drive")
    return linhas[0].strip(), linhas[1].strip()

def buscar_conteudo_pagina(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text

def extrair_briefing(conteudo_html: str, url: str) -> dict:
    prompt = f"""Você é um especialista em marketing imobiliário. Abaixo está o conteúdo HTML de uma página de briefing de um empreendimento imobiliário. Extraia todas as informações relevantes e retorne APENAS JSON puro sem markdown.

URL da página: {url}

Estrutura esperada:
{{
  "nome_empreendimento": "",
  "endereco": "",
  "dados_financeiros": {{
    "ticket_medio": "",
    "menor_cota": "",
    "rentabilidade_anual": "",
    "rendimento_mensal": "",
    "roi": "",
    "valorizacao": "",
    "num_cotas": ""
  }},
  "localizacao": {{
    "bairro": "",
    "cidade": "",
    "destaques": []
  }},
  "produto": {{
    "diferenciais": [],
    "estrutura_videos": []
  }},
  "publico_alvo": [],
  "dos": [],
  "donts": [],
  "pontos_fortes_obrigatorios": [],
  "regras_visuais": [],
  "pitch_central": ""
}}

CONTEÚDO DA PÁGINA:
{conteudo_html[:15000]}"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    texto = response.content[0].text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    return json.loads(texto)

def main():
    print("Lendo links de input/links.txt...")
    try:
        url_briefing, url_drive = ler_links()
        print(f"Briefing: {url_briefing}")
        print(f"Drive: {url_drive}")

        # Salva o link do drive para o próximo script usar
        (INPUT_DIR / "drive_link.txt").write_text(url_drive, encoding="utf-8")

        print("\nAcessando página do briefing...")
        conteudo = buscar_conteudo_pagina(url_briefing)

        print("Extraindo informações com Claude...")
        briefing = extrair_briefing(conteudo, url_briefing)

        saida = INPUT_DIR / "briefing_extraido.json"
        saida.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\nBriefing extraído com sucesso!")
        print(f"Empreendimento: {briefing.get('nome_empreendimento', '?')}")
        print(f"ROI: {briefing.get('dados_financeiros', {}).get('roi', '?')}")
        print(f"Rendimento mensal: {briefing.get('dados_financeiros', {}).get('rendimento_mensal', '?')}")

    except Exception as e:
        print(f"ERRO: {e}")
        with open(ROOT / "outputs" / "erros.log", "a") as f:
            f.write(f"ler_briefing: {e}\n")

if __name__ == "__main__":
    main()
