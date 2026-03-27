import os
import re
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

GROQ_KEY = os.environ.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
if not GROQ_KEY:
    print("ERRO FATAL: GROQ_API_KEY não está definida. Configure no Railway ou no .env")
    sys.exit(1)

client = Groq(api_key=GROQ_KEY)
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

TAREFA: Crie um roteiro completo para um vídeo de marketing do empreendimento descrito no briefing.

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

OBRIGATÓRIO: incluir ROI, localização, rendimento mensal e fachada conforme o briefing.
PROIBIDO: pé na areia, distância exata da praia, vista mar nas unidades, urgência artificial."""

    max_tentativas = 3
    for tentativa in range(1, max_tentativas + 1):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.7
            )
            texto = response.choices[0].message.content.strip()
            if texto.startswith("```"):
                texto = texto.split("```")[1]
                if texto.startswith("json"):
                    texto = texto[4:]
            return json.loads(texto)
        except Exception as e:
            erro_str = str(e)
            if "429" in erro_str and tentativa < max_tentativas:
                # Extrai tempo de espera da mensagem do Groq (ex: "35m7.29s")
                match = re.search(r"try again in (\d+)m", erro_str)
                espera = int(match.group(1)) * 60 + 10 if match else 60
                espera = min(espera, 120)  # máx 2 minutos de espera
                print(f"    Rate limit — aguardando {espera}s (tentativa {tentativa}/{max_tentativas})...")
                time.sleep(espera)
            else:
                raise

def main():
    print("Gerando roteiros com Groq (LLaMA 3.3)...\n")
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
            with open(ROOT / "outputs" / "erros.log", "a", encoding="utf-8") as f:
                f.write(f"Roteiro {i}: {e}\n")

    # Consolida: baseline = todos_roteiros.json existente → individuais → recém gerados
    todos_path = OUTPUTS / "todos_roteiros.json"
    existentes = {}

    # 1) Lê o arquivo consolidado já existente como baseline
    if todos_path.exists():
        try:
            for r in json.loads(todos_path.read_text(encoding="utf-8")):
                chave = (r.get("estrutura"), r.get("duracao"))
                existentes[chave] = r
        except Exception:
            pass

    # 2) Sobrescreve com arquivos individuais (versão mais recente no disco)
    for arq in OUTPUTS.glob("roteiro_estrutura*.json"):
        if arq.name == "todos_roteiros.json":
            continue
        try:
            r = json.loads(arq.read_text(encoding="utf-8"))
            chave = (r.get("estrutura"), r.get("duracao"))
            existentes[chave] = r
        except Exception:
            pass

    # 3) Sobrescreve com os recém gerados nesta execução
    for r in roteiros:
        chave = (r.get("estrutura"), r.get("duracao"))
        existentes[chave] = r

    todos = list(existentes.values())
    if todos:  # só salva se tiver conteúdo — nunca sobrescreve com lista vazia
        todos_path.write_text(
            json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"\n{len(todos)}/5 roteiros disponíveis (gerados agora + anteriores).")

    if not roteiros:
        print("ERRO FATAL: Nenhum roteiro gerado. Verifique o rate limit do Groq.")
        sys.exit(1)

if __name__ == "__main__":
    main()
