"""
rodar_teste.py
Roda apenas as etapas de briefing, assets, roteiros e imagens — sem vídeos.
Uso: py rodar_teste.py
"""
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
INPUT_DIR = ROOT / "input"

def verificar_inputs():
    erros = []
    links_path = INPUT_DIR / "links.txt"
    if not links_path.exists():
        erros.append("FALTANDO: input/links.txt com os dois links")
    else:
        linhas = links_path.read_text(encoding="utf-8").strip().splitlines()
        if len(linhas) < 2:
            erros.append("input/links.txt deve ter 2 linhas: link do briefing e link do Drive")
    if not (ROOT / ".env").exists():
        erros.append("FALTANDO: .env com as chaves de API")
    return erros

def rodar_script(nome: str) -> bool:
    print(f"\n{'='*50}")
    print(f"Executando: {nome}")
    print("="*50)
    resultado = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / nome)],
        cwd=str(ROOT)
    )
    return resultado.returncode == 0

def main():
    print("MÁQUINA DE CRIATIVOS — TESTE (sem vídeos)\n")

    erros = verificar_inputs()
    if erros:
        print("Corrija os problemas abaixo antes de continuar:\n")
        for e in erros:
            print(f"  {e}")
        print("\nComo usar:")
        print("  1. Crie input/links.txt")
        print("  2. Linha 1: link da página web do briefing")
        print("  3. Linha 2: link da pasta do Google Drive com os assets")
        return

    scripts = [
        "ler_briefing.py",
        "baixar_assets.py",
        "gerar_roteiros.py",
        "gerar_imagens.py",
    ]

    for script in scripts:
        ok = rodar_script(script)
        if not ok:
            print(f"\nERRO em {script} — verifique outputs/erros.log")
            continuar = input("Continuar mesmo assim? (s/n): ")
            if continuar.lower() != "s":
                break

    print("\nTeste finalizado!")
    print("Roteiros em:  outputs/roteiros/")
    print("Imagens em:   outputs/imagens/")

if __name__ == "__main__":
    main()
