import os
import json
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()
ROOT = Path(__file__).parent.parent
OUTPUTS = ROOT / "outputs" / "roteiros"
OUTPUTS.mkdir(parents=True, exist_ok=True)

def ler_contexto():
    arquivos_fixos = ["contexto/seazone_brand.md", "contexto/mariana_perfil.md", "AGENTS.md"]
    contexto = ""
    for arq in arquivos_fixos:
        caminho = ROOT / arq
        if caminho.exists():
            contexto += f"\n\n---\n## {arq}\n\n" + caminho.read_text(encoding="utf-8")

    briefing_path = ROOT / "input" / "briefing_extraido.json"
    if briefing_path.exists():
        import json
        briefing = json.loads(briefing_path.read_text(encoding="utf-8"))
        contexto += f"\n\n---\n## BRIEFING DO EMPREENDIMENTO\n\n{json.dumps(briefing, ensure_ascii=False, indent=2)}"
    else:
        print("AVISO: Execute ler_briefing.py primeiro.")
    return contexto

def gerar_roteiro(estrutura_num, duracao, contexto):
    estruturas = {
        1: "L|F|RO|RE — Vista aérea → Fachada → MarIAna na praia → Financeiro → Rooftop+CTA",
        2: "L|RO|RE|F — Vista aérea → MarIAna com ROI → Fachada → Rooftop+CTA",
        3: "F|RO|RE|L — Fachada → MarIAna com ROI → Vista aérea → Rooftop+CTA",
    }
    max_palavras = 90 if duracao == "40s" else 45
    prompt = f"""Você é um roteirista especialista em criativos de marketing imobiliário premium.

CONTEXTO COMPLETO:
{contexto}

TAREFA: Crie um roteiro completo para um vídeo de marketing do Novo Campeche SPOT II.

ESPECIFICAÇÕES:
- Estrutura: {estrutura_num} — {estruturas[estrutura_num]}
- Duração: {duracao}
- Narração da MarIAna: máximo {max_palavras} palavras
- Tom: autoridade natural, não vendedora

FORMATO DE RESPOSTA (JSON puro, sem markdown):
{{
  "estrutura": {estrutura_num},
  "duracao": "{duracao}",
  "narracao_mariana": "texto completo da fala da MarIAna",
  "descricao_visual": [
    {{"take": 1, "duracao_aprox": "Xs", "descricao": "o que acontece visualmente"}}
  ],
  "texto_na_tela": [
    {{"momento": "take X", "texto": "texto que aparece na tela", "destaque": true}}
  ],
  "cta_final": "texto exato do call to action"
}}

OBRIGATÓRIO: ROI 16,40%, localização Campeche, rendimento ~R$5.500/mês, fachada.
PROIBIDO: pé na areia, distância exata, vista mar nas unidades, urgência artificial."""

    response = client.messages.create(model="claude-opus-4-5", max_tokens=2000, messages=[{"role": "user", "content": prompt}])
    texto = response.content[0].text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    return json.loads(texto)

def main():
    print("Gerando roteiros...\n")
    contexto = ler_contexto()
    combinacoes = [(1, "40s"), (2, "40s"), (3, "40s"), (1, "20s"), (2, "20s")]
    roteiros = []
    for i, (estrutura, duracao) in enumerate(combinacoes, 1):
        print(f"Roteiro {i}/5 — Estrutura {estrutura} ({duracao})...")
        try:
            roteiro = gerar_roteiro(estrutura, duracao, contexto)
            roteiros.append(roteiro)
            nome = f"roteiro_estrutura{estrutura}_{duracao.replace('s','')}.json"
            (OUTPUTS / nome).write_text(json.dumps(roteiro, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  Salvo: {nome}")
        except Exception as e:
            print(f"  Erro: {e}")
    (OUTPUTS / "todos_roteiros.json").write_text(json.dumps(roteiros, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(roteiros)}/5 roteiros gerados.")

if __name__ == "__main__":
    main()
