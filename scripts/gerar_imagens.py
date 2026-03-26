"""
gerar_imagens.py
Gera imagens nos 3 formatos Instagram usando as fotos do usuário:
  · 4:5  — 1080×1350  (feed portrait)
  · 1:1  — 1080×1080  (feed square)
  · 16:9 — 1080×607   (landscape / reels thumbnail)
"""
import json
import platform
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT         = Path(__file__).parent.parent
ASSETS_DIR   = ROOT / "assets"
OUTPUTS      = ROOT / "outputs" / "imagens"
OUTPUTS.mkdir(parents=True, exist_ok=True)
ERROS_LOG    = ROOT / "outputs" / "erros.log"


def _encontrar_fonte(candidatos: list[str]) -> str | None:
    """Retorna o primeiro caminho de fonte que existe, ou None."""
    for c in candidatos:
        if Path(c).exists():
            return c
    return None


FONT_BOLD = _encontrar_fonte([
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
])

FONT_REGULAR = _encontrar_fonte([
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
])

FONT_ITALIC = _encontrar_fonte([
    "C:/Windows/Fonts/ariali.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf",
])

FORMATOS = {
    "4x5":  (1080, 1350),
    "1x1":  (1080, 1080),
    "16x9": (1080,  607),
}


# ── Helpers ──────────────────────────────────────────────────────────────────

# Fontes DejaVu/Liberation renderizam ~20% menores que Arial no mesmo tamanho
_USA_WINDOWS = FONT_BOLD and "Windows" in FONT_BOLD
FONT_SCALE = 1.0 if _USA_WINDOWS else 1.25


def fonte(tamanho: int, estilo: str = "bold") -> ImageFont.FreeTypeFont:
    mapa = {"bold": FONT_BOLD, "regular": FONT_REGULAR, "italic": FONT_ITALIC}
    tamanho_real = int(tamanho * FONT_SCALE)
    try:
        return ImageFont.truetype(mapa.get(estilo, FONT_BOLD), tamanho_real)
    except Exception:
        return ImageFont.load_default()


def crop_center(img: Image.Image, w: int, h: int) -> Image.Image:
    ratio_alvo = w / h
    ratio_img  = img.width / img.height
    if ratio_img > ratio_alvo:
        novo_w = int(img.height * ratio_alvo)
        x = (img.width - novo_w) // 2
        img = img.crop((x, 0, x + novo_w, img.height))
    else:
        novo_h = int(img.width / ratio_alvo)
        y = (img.height - novo_h) // 2
        img = img.crop((0, y, img.width, y + novo_h))
    return img.resize((w, h), Image.LANCZOS)


def gradient_v(w: int, h: int, cor: tuple, alpha_max: int, invertido=False) -> Image.Image:
    """Gradiente vertical cor→transparente. Se invertido, transparente→cor."""
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(h):
        t = y / h
        a = int(alpha_max * t) if invertido else int(alpha_max * (1 - t))
        draw.line([(0, y), (w, y)], fill=(*cor, a))
    return overlay


def texto_centrado(draw, y, texto, fnt, fill, largura):
    bb = draw.textbbox((0, 0), texto, font=fnt)
    x = (largura - (bb[2] - bb[0])) // 2
    draw.text((x + 2, y + 2), texto, font=fnt, fill=(0, 0, 0, 60))
    draw.text((x, y), texto, font=fnt, fill=fill)
    return y + (bb[3] - bb[1])


def texto_wrap_center(draw, y, texto, fnt, fill, max_w, largura, gap=6):
    palavras = texto.split()
    linhas, atual = [], ""
    for p in palavras:
        t = (atual + " " + p).strip()
        if draw.textbbox((0, 0), t, font=fnt)[2] <= max_w:
            atual = t
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    for linha in linhas:
        bb = draw.textbbox((0, 0), linha, font=fnt)
        x = (largura - (bb[2] - bb[0])) // 2
        draw.text((x + 2, y + 2), linha, font=fnt, fill=(0, 0, 0, 60))
        draw.text((x, y), linha, font=fnt, fill=fill)
        y += (bb[3] - bb[1]) + gap
    return y


def draw_pill(draw, cx, y, texto, fnt, bg, fg, px=28, py=14):
    bb = draw.textbbox((0, 0), texto, font=fnt)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pw, ph = tw + px * 2, th + py * 2
    rx = cx - pw // 2
    draw.rounded_rectangle([rx, y, rx + pw, y + ph], radius=ph // 2, fill=bg)
    draw.text((rx + px, y + py // 2 + 1), texto, font=fnt, fill=fg)
    return y + ph


def draw_rodape(draw, W, H, logo_fnt, cta_fnt, cta_linha1, cta_linha2, pad=56):
    # Logo esquerda
    draw.text((pad, H - 100), "seazone", font=logo_fnt, fill=(255, 255, 255))
    # CTA direita
    bb1 = draw.textbbox((0, 0), cta_linha1, font=cta_fnt)
    draw.text((W - pad - (bb1[2] - bb1[0]), H - 100), cta_linha1,
              font=cta_fnt, fill=(255, 255, 255))
    if cta_linha2:
        bb2 = draw.textbbox((0, 0), cta_linha2, font=fonte(cta_fnt.size, "italic"))
        draw.text((W - pad - (bb2[2] - bb2[0]), H - 100 + (bb1[3] - bb1[1]) + 4),
                  cta_linha2, font=fonte(cta_fnt.size, "italic"), fill=(255, 220, 50))


def split_cta(cta: str):
    palavras = cta.split()
    meio = len(palavras) // 2 or len(palavras)
    return " ".join(palavras[:meio]), " ".join(palavras[meio:])


def carregar_briefing() -> dict:
    p = ROOT / "input" / "briefing_extraido.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ── Geradores por formato ─────────────────────────────────────────────────────

def gerar_4x5(asset, destino, briefing, idx=1):
    """1080×1350 — texto em cima, foto abaixo."""
    W, H = 1080, 1350
    img = crop_center(Image.open(asset).convert("RGB"), W, H).convert("RGBA")
    img = Image.alpha_composite(img, gradient_v(W, H, (255, 255, 255), 210))
    img = Image.alpha_composite(img, _rodape_overlay(W, H, 0.18, 170))

    draw = ImageDraw.Draw(img)
    headline, subtitulo, dado, bairro, cidade = _conteudo(briefing, idx)

    y = 68
    y = texto_centrado(draw, y, "SEAZONE INVESTIMENTOS", fonte(28, "regular"), (80, 80, 80), W) + 14
    y = texto_wrap_center(draw, y, headline, fonte(90, "bold"), (15, 15, 15), W - 100, W, gap=2) + 12
    y = texto_wrap_center(draw, y, subtitulo, fonte(36, "regular"), (40, 40, 40), W - 140, W, gap=4) + 18
    y = draw_pill(draw, W // 2, y, f"  {bairro}, {cidade} - SC",
                  fonte(32, "bold"), (210, 35, 35), (255, 255, 255)) + 20
    if dado:
        texto_centrado(draw, y, dado, fonte(34, "bold"), (15, 15, 15), W)

    cta1, cta2 = split_cta(CTA_PADRAO)
    draw_rodape(draw, W, H, fonte(42, "bold"), fonte(30, "regular"), cta1, cta2)
    img.convert("RGB").save(destino, "JPEG", quality=93)


def gerar_1x1(asset, destino, briefing, idx=1):
    """1080×1080 — texto em faixa no topo, foto ocupa metade inferior."""
    W, H = 1080, 1080
    img = crop_center(Image.open(asset).convert("RGB"), W, H).convert("RGBA")
    img = Image.alpha_composite(img, gradient_v(W, H, (255, 255, 255), 220))
    img = Image.alpha_composite(img, _rodape_overlay(W, H, 0.20, 170))

    draw = ImageDraw.Draw(img)
    headline, subtitulo, dado, bairro, cidade = _conteudo(briefing, idx)

    y = 56
    y = texto_centrado(draw, y, "SEAZONE INVESTIMENTOS", fonte(26, "regular"), (80, 80, 80), W) + 10
    y = texto_wrap_center(draw, y, headline, fonte(80, "bold"), (15, 15, 15), W - 80, W, gap=2) + 10
    y = texto_wrap_center(draw, y, subtitulo, fonte(32, "regular"), (40, 40, 40), W - 120, W, gap=4) + 14
    y = draw_pill(draw, W // 2, y, f"  {bairro}, {cidade} - SC",
                  fonte(30, "bold"), (210, 35, 35), (255, 255, 255)) + 16
    if dado:
        texto_centrado(draw, y, dado, fonte(30, "bold"), (15, 15, 15), W)

    cta1, cta2 = split_cta(CTA_PADRAO)
    draw_rodape(draw, W, H, fonte(38, "bold"), fonte(26, "regular"), cta1, cta2, pad=48)
    img.convert("RGB").save(destino, "JPEG", quality=93)


def gerar_16x9(asset, destino, briefing, idx=1):
    """1080×607 — foto à direita, faixa escura à esquerda com texto."""
    W, H = 1080, 607
    img = crop_center(Image.open(asset).convert("RGB"), W, H).convert("RGBA")

    faixa_w = int(W * 0.55)
    faixa = Image.new("RGBA", (faixa_w, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(faixa)
    for x in range(faixa_w):
        a = int(190 * (1 - x / faixa_w) ** 0.6)
        fd.line([(x, 0), (x, H)], fill=(10, 10, 10, a))
    img.paste(faixa, (0, 0), faixa)
    img = Image.alpha_composite(img, _rodape_overlay(W, H, 0.22, 150))

    draw = ImageDraw.Draw(img)
    headline, subtitulo, dado, bairro, cidade = _conteudo(briefing, idx)

    pad = 48
    y = 36
    draw.text((pad, y), "SEAZONE INVESTIMENTOS", font=fonte(20, "regular"), fill=(200, 200, 200))
    y += 30

    for linha in _quebrar(headline, fonte(56, "bold"), draw, faixa_w - pad * 2):
        draw.text((pad + 2, y + 2), linha, font=fonte(56, "bold"), fill=(0, 0, 0, 60))
        draw.text((pad, y), linha, font=fonte(56, "bold"), fill=(255, 255, 255))
        y += 62
    y += 6

    # Subtítulo
    for linha in _quebrar(subtitulo, fonte(26, "regular"), draw, faixa_w - pad * 2):
        draw.text((pad, y), linha, font=fonte(26, "regular"), fill=(220, 220, 220))
        y += 32
    y += 8

    pill_txt = f"  {bairro}, {cidade} - SC"
    pbb = draw.textbbox((0, 0), pill_txt, font=fonte(22, "bold"))
    pw, ph = pbb[2] - pbb[0] + 44, pbb[3] - pbb[1] + 22
    draw.rounded_rectangle([pad, y, pad + pw, y + ph], radius=ph // 2, fill=(210, 35, 35))
    draw.text((pad + 22, y + 11), pill_txt, font=fonte(22, "bold"), fill=(255, 255, 255))
    y += ph + 14

    if dado:
        draw.text((pad, y), dado, font=fonte(26, "bold"), fill=(255, 255, 230))

    draw.text((pad, H - 72), "seazone", font=fonte(32, "bold"), fill=(255, 255, 255))
    cta1, cta2 = split_cta(CTA_PADRAO)
    cta_fnt = fonte(22, "regular")
    bb1 = draw.textbbox((0, 0), cta1, font=cta_fnt)
    draw.text((W - 44 - (bb1[2] - bb1[0]), H - 72), cta1, font=cta_fnt, fill=(255, 255, 255))
    if cta2:
        bb2 = draw.textbbox((0, 0), cta2, font=fonte(22, "italic"))
        draw.text((W - 44 - (bb2[2] - bb2[0]), H - 72 + (bb1[3] - bb1[1]) + 3),
                  cta2, font=fonte(22, "italic"), fill=(255, 220, 50))

    img.convert("RGB").save(destino, "JPEG", quality=93)


# ── Utilitários internos ──────────────────────────────────────────────────────

def _rodape_overlay(W, H, pct, alpha_max):
    h_faixa = int(H * pct)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(h_faixa):
        a = int(alpha_max * (1 - y / h_faixa))
        d.line([(0, H - h_faixa + y), (W, H - h_faixa + y)], fill=(0, 0, 0, a))
    return ov


def _conteudo(briefing, idx: int) -> dict:
    """
    Retorna headline, subtitulo e dado_financeiro diferentes por índice (1-5),
    usando exclusivamente dados do briefing — sem inventar nada.
    """
    fin  = briefing.get("dados_financeiros", {})
    loc  = briefing.get("localizacao", {})
    prod = briefing.get("produto", {})

    nome   = briefing.get("nome_empreendimento", "Novo Empreendimento")
    bairro = loc.get("bairro", "Campeche")
    cidade = loc.get("cidade", "Florianópolis")

    roi        = fin.get("roi", "")
    rend       = fin.get("rendimento_mensal", "")
    menor_cota = fin.get("menor_cota", "")
    ticket     = fin.get("ticket_medio", "")
    rent_anual = fin.get("rentabilidade_anual", "")
    valorizacao = fin.get("valorizacao", "")
    num_cotas  = fin.get("num_cotas", "")
    destaques  = loc.get("destaques", [])
    diferenciais = prod.get("diferenciais", [])

    variantes = {
        1: {
            "headline":   nome,
            "subtitulo":  "gere renda passiva investindo em",
            "dado":       f"ROI {roi} ao ano  ·  {rend}/mês" if roi and rend else f"ROI {roi} ao ano",
        },
        2: {
            "headline":   f"A partir de {menor_cota}" if menor_cota else nome,
            "subtitulo":  f"rentabilidade de {rent_anual}" if rent_anual else "investimento acessível em",
            "dado":       f"Ticket médio {ticket}  ·  {num_cotas} cotas" if ticket else f"Valorização {valorizacao}",
        },
        3: {
            "headline":   destaques[0] if destaques else nome,
            "subtitulo":  f"próximo a {destaques[1]}" if len(destaques) > 1 else "no melhor da",
            "dado":       f"{bairro}, {cidade}  ·  ROI {roi}" if roi else f"{bairro}, {cidade}",
        },
        4: {
            "headline":   diferenciais[0] if diferenciais else nome,
            "subtitulo":  diferenciais[1] if len(diferenciais) > 1 else "em",
            "dado":       f"Rendimento {rend}/mês  ·  Valorização {valorizacao}" if rend and valorizacao else f"ROI {roi}",
        },
        5: {
            "headline":   nome,
            "subtitulo":  f"valorização de {valorizacao} ao ano" if valorizacao else "invista agora em",
            "dado":       f"ROI {roi}  ·  Rentabilidade {rent_anual}" if roi and rent_anual else f"Rendimento {rend}",
        },
    }

    v = variantes.get(idx, variantes[1])
    return v["headline"], v["subtitulo"], v["dado"], bairro, cidade


CTA_PADRAO = "Acesse e simule o seu retorno com a Seazone."


def _quebrar(texto, fnt, draw, max_w):
    palavras = texto.split()
    linhas, atual = [], ""
    for p in palavras:
        t = (atual + " " + p).strip()
        if draw.textbbox((0, 0), t, font=fnt)[2] <= max_w:
            atual = t
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def listar_assets():
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    validos = []
    for f in sorted(ASSETS_DIR.iterdir()):
        if f.suffix.lower() not in exts:
            continue
        try:
            with Image.open(f) as im:
                im.verify()
            validos.append(f)
        except Exception:
            pass
    return validos


# ── Main ──────────────────────────────────────────────────────────────────────

GERADORES = {
    "4x5":  gerar_4x5,
    "1x1":  gerar_1x1,
    "16x9": gerar_16x9,
}


NUM_IMAGENS = 5


def main():
    print("Gerando imagens (4:5 · 1:1 · 16:9)...\n")

    assets = listar_assets()
    if not assets:
        print("ERRO: Nenhum asset válido em assets/. Faça upload das imagens.")
        with open(ERROS_LOG, "a", encoding="utf-8") as f:
            f.write("gerar_imagens: nenhum asset válido\n")
        return

    briefing = carregar_briefing()
    total = NUM_IMAGENS * len(GERADORES)
    print(f"{len(assets)} foto(s) · {NUM_IMAGENS} variantes · {total} imagens\n")

    geradas = 0
    for i in range(1, NUM_IMAGENS + 1):
        asset = assets[(i - 1) % len(assets)]

        for fmt, fn in GERADORES.items():
            nome = f"imagem_{i:02d}_{fmt}.jpg"
            print(f"  {nome}  ({asset.name})")
            try:
                fn(asset, OUTPUTS / nome, briefing, idx=i)
                geradas += 1
            except Exception as e:
                print(f"    Erro: {e}")
                with open(ERROS_LOG, "a", encoding="utf-8") as f:
                    f.write(f"Imagem {i} {fmt}: {e}\n")

    print(f"\n{geradas}/{total} imagens geradas em outputs/imagens/")


if __name__ == "__main__":
    main()
