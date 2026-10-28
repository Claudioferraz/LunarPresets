# -*- coding: utf-8 -*-
"""
Gera relatório fotográfico A4 horizontal.
Versão 2.2.0 — Generalizada (sem dependência de cliente específico)
"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from datetime import datetime
import pandas as pd
import os
import re
import json
import shutil

# ============================================================
# Caminhos padrão (podem ser sobrescritos)
# ============================================================
ARQUIVO_CONFIG = "config.json"
PASTA_FOTOS = "fotos"
PASTA_SAIDA = "saida"
PASTA_USADAS = os.path.join(PASTA_FOTOS, "_usadas")

NOMES_DESENHO = [
    "desenho_subestacao.jpg", "desenho_subestacao.png",
    "Desenho Subestação.jpg", "Desenho Subestacao.jpg",
    "desenho.jpg", "layout.jpg"
]
NOMES_FOTO_LOCAL = [
    "foto_local.jpg", "foto_local.png",
    "Foto Local.jpg", "foto_local.JPG",
    "local.jpg", "mapa.jpg"
]

PAGE_W, PAGE_H = landscape(A4)
MARGIN = 10 * mm
HEADER_H = 18 * mm
GAP = 4 * mm

REGEX_FOTO = re.compile(
    r"^(?P<camera>.+?)\s*-\s*[Pp]\s*(?P<preset>\d+)\s+(?P<idsage>.+?)\.(?P<ext>jpe?g|png|jng)$",
    re.IGNORECASE
)


# ============================================================
# Utilitários
# ============================================================
def normalizar(s):
    if not s:
        return ""
    return re.sub(r"[_\s]+", "_", str(s)).strip().upper()


def safe_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def safe_int(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def wrap_text(texto, fonte, tamanho, largura_max):
    if not texto:
        return [""]
    palavras = str(texto).split()
    linhas, atual = [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if stringWidth(teste, fonte, tamanho) <= largura_max:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas or [""]


def carregar_config(caminho):
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Config não encontrado: {caminho}")
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def carregar_dados(caminho):
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Excel não encontrado: {caminho}")
    df = pd.read_excel(caminho, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    for col in ["IDSAGE", "Camera", "FASE", "ESTADO"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    df = df.dropna(subset=["IDSAGE"])
    df = df[df["IDSAGE"] != "nan"]
    return df


def agrupar(df):
    grupos = []
    for idsage, g in df.groupby("IDSAGE", sort=False):
        linhas_validas = [
            r for r in g.to_dict("records")
            if safe_int(r.get("Preset")) is not None
        ]
        if not linhas_validas:
            continue
        eh_dj = "_DJ" in idsage.upper()
        grupos.append({
            "idsage": idsage,
            "camera": linhas_validas[0].get("Camera", ""),
            "eh_dj": eh_dj,
            "linhas": linhas_validas,
        })
    grupos.sort(key=lambda x: (x["eh_dj"],))
    return grupos


def montar_paginas(grupos):
    paginas = []
    pendentes_2 = []
    for g in grupos:
        n = len(g["linhas"])
        if n == 2:
            if pendentes_2:
                outro = pendentes_2.pop(0)
                paginas.append([outro, g])
            else:
                pendentes_2.append(g)
        else:
            paginas.append([g])
    for g in pendentes_2:
        paginas.append([g])
    return paginas


def coletar_info_cameras(df):
    por_camera = {}
    for _, row in df.iterrows():
        cam = safe_str(row.get("Camera"))
        if not cam or cam.lower() == "nan":
            continue
        preset = safe_int(row.get("Preset"))
        if cam not in por_camera:
            por_camera[cam] = set()
        if preset is not None:
            por_camera[cam].add(preset)
    resultado = []
    for cam in sorted(por_camera.keys()):
        resultado.append({"camera": cam, "qtd_presets": len(por_camera[cam])})
    return resultado


def coletar_sem_visao(df):
    itens, vistos = [], set()
    col_obs = None
    for c in df.columns:
        if "OBSERV" in c.upper():
            col_obs = c
            break
    for _, row in df.iterrows():
        idsage = safe_str(row.get("IDSAGE"))
        if not idsage or idsage.lower() == "nan":
            continue
        obs = safe_str(row.get(col_obs)) if col_obs else ""
        cam = safe_str(row.get("Camera"))
        fase = safe_str(row.get("FASE")).upper()
        preset = safe_int(row.get("Preset"))
        sem = False
        if not cam or cam.lower() == "nan":
            sem = True
        if preset is None:
            sem = True
        if obs and ("SEM VIS" in obs.upper() or "OBSTRU" in obs.upper()):
            sem = True
        if fase in ("SEM VISÃO", "VISÃO OBSTRUÍDAS", "SEM VISAO", "VISAO OBSTRUIDAS"):
            sem = True
        if sem:
            chave = (idsage, obs)
            if chave in vistos:
                continue
            vistos.add(chave)
            itens.append({"idsage": idsage, "obs": obs or "SEM VISÃO DO EQUIPAMENTO"})
    return itens


def indexar_fotos(pasta):
    indice = {}
    nao_reconhecidas = []
    if not os.path.isdir(pasta):
        return indice, nao_reconhecidas

    especiais = set(NOMES_DESENHO + NOMES_FOTO_LOCAL)

    for nome in os.listdir(pasta):
        caminho = os.path.join(pasta, nome)
        if not os.path.isfile(caminho):
            continue
        if nome == "_usadas":
            continue
        if nome in especiais:
            continue
        m = REGEX_FOTO.match(nome)
        if not m:
            nao_reconhecidas.append((nome, "Nome fora do padrão"))
            continue
        idsage = m.group("idsage").strip()
        try:
            preset = int(m.group("preset"))
        except ValueError:
            nao_reconhecidas.append((nome, "Preset inválido"))
            continue
        indice[(normalizar(idsage), preset)] = caminho
    return indice, nao_reconhecidas


def achar_imagem_especial(pasta, nomes):
    for nome in nomes:
        caminho = os.path.join(pasta, nome)
        if os.path.exists(caminho):
            return caminho
    return None


def desenhar_foto_ajustada(c, caminho, x, y, w, h):
    try:
        img = ImageReader(caminho)
        iw, ih = img.getSize()
        if iw == 0 or ih == 0:
            return False
        escala = min(w / iw, h / ih)
        nw, nh = iw * escala, ih * escala
        nx = x + (w - nw) / 2
        ny = y + (h - nh) / 2
        c.drawImage(img, nx, ny, width=nw, height=nh,
                    preserveAspectRatio=True, mask="auto")
        return True
    except Exception as e:
        print(f"⚠️  Erro ao desenhar {caminho}: {e}")
        return False


def mover_apenas_usadas(indice, problemas_fotos, dry_run=False):
    movidos = []
    if dry_run:
        return movidos
    nomes_com_problema = set(p[0] for p in problemas_fotos)
    os.makedirs(PASTA_USADAS, exist_ok=True)
    for chave, caminho in indice.items():
        if not os.path.exists(caminho):
            continue
        nome = os.path.basename(caminho)
        if nome in nomes_com_problema:
            continue
        destino = os.path.join(PASTA_USADAS, nome)
        try:
            shutil.move(caminho, destino)
            movidos.append((caminho, destino))
        except Exception as e:
            print(f"⚠️  Não foi possível mover {caminho}: {e}")
    return movidos


# ============================================================
# Desenho das páginas
# ============================================================
def _cor(cfg, chave, default):
    cores = cfg.get("cores", {})
    return colors.HexColor(cores.get(chave, default))


def desenhar_capa(c, cfg, fundo_cinza=False):
    if fundo_cinza:
        c.setFillColor(_cor(cfg, "fundo_cinza", "#D9D9D9"))
    else:
        c.setFillColor(_cor(cfg, "fundo_capa", "#F2F0EB"))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    if not fundo_cinza:
        # Detalhe decorativo (pontos)
        cx = PAGE_W / 2 + 30 * mm
        dot_r, passo_y, n_cols, passo_x = 0.9 * mm, 4 * mm, 8, 4 * mm
        n_linhas = int((PAGE_H - 10 * mm) / passo_y)
        for i in range(n_linhas):
            y = PAGE_H - 5 * mm - i * passo_y
            t = i / max(n_linhas - 1, 1)
            cinza = int(200 - 180 * t)
            c.setFillColorRGB(cinza / 255, cinza / 255, cinza / 255)
            for j in range(n_cols):
                c.circle(cx + j * passo_x, y, dot_r, fill=1, stroke=0)

        ano = cfg.get("ano", "")
        box_x, box_y, box_w, box_h = 35 * mm, PAGE_H - 45 * mm, 40 * mm, 22 * mm
        c.setFillColor(colors.HexColor("#F8F6F2"))
        c.rect(box_x, box_y, box_w, box_h, fill=1, stroke=0)
        c.setFillColor(_cor(cfg, "primaria", "#CC0000"))
        c.setFont("Helvetica", 26)
        c.drawCentredString(box_x + box_w / 2, box_y + 7 * mm, str(ano))

        c.setFillColor(colors.black)
        c.setFont("Helvetica", 13)
        c.drawString(35 * mm, PAGE_H - 95 * mm,
                     f"Projeto {cfg.get('numero_do_projeto', '')} {cfg.get('projeto', '')}")
        c.setFont("Helvetica", 13)
        c.drawString(35 * mm, PAGE_H - 135 * mm, "Elaborado por")
        c.setFont("Helvetica", 16)
        c.drawString(35 * mm, PAGE_H - 145 * mm, cfg.get("responsavel", ""))
        c.setFont("Helvetica", 13)
        c.drawString(35 * mm, PAGE_H - 160 * mm, cfg.get("data", ""))

    # Nome do software / marca genérica
    c.setFillColor(_cor(cfg, "secundaria", "#1E88E5"))
    c.setFont("Helvetica-Oblique", 28)
    titulo = cfg.get("titulo_software", "Relatório Fotográfico")
    c.drawRightString(PAGE_W - 20 * mm, PAGE_H / 2 + 8 * mm, titulo)
    c.setFillColor(colors.HexColor("#333333"))
    c.setFont("Helvetica", 11)
    c.drawRightString(PAGE_W - 20 * mm, PAGE_H / 2 - 5 * mm, cfg.get("contratante", ""))


def desenhar_dashboard(c, cfg):
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 30 * mm, "Dashboard do Projeto")
    c.setFont("Helvetica", 18)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 42 * mm, cfg.get("nome_se", cfg.get("projeto", "")))

    y_bar = PAGE_H - 60 * mm
    c.setFillColor(colors.HexColor("#7F7F7F"))
    c.rect(MARGIN, y_bar, PAGE_W - 2 * MARGIN, 3 * mm, fill=1, stroke=0)

    etapas = cfg.get("dashboard", {}).get("etapas", [
        "Projeto Executivo", "Mobilizacao", "Infraestrutura",
        "Instalacao de\nEquipamentos", "Configuracoes", "Testes"
    ])
    n = len(etapas)
    espaco = (PAGE_W - 2 * MARGIN) / max(n, 1)

    for i, nome in enumerate(etapas):
        cx = MARGIN + espaco * i + espaco / 2
        pil_w, pil_h = espaco - 8 * mm, 10 * mm
        pil_x, pil_y = cx - pil_w / 2, y_bar - pil_h + 2 * mm
        c.setFillColor(colors.HexColor("#DDDDDD"))
        c.roundRect(pil_x, pil_y, pil_w, pil_h, pil_h / 2, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8)
        linhas = nome.split("\n")
        if len(linhas) == 1:
            c.drawCentredString(cx, pil_y + pil_h / 2 - 2, linhas[0])
        else:
            c.drawCentredString(cx, pil_y + pil_h - 4 * mm, linhas[0])
            c.drawCentredString(cx, pil_y + pil_h - 8 * mm, linhas[1])
        circ_r, circ_y = 8 * mm, pil_y - 11 * mm
        c.setFillColor(colors.black)
        c.circle(cx, circ_y, circ_r, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(cx, circ_y - 3, "v")
        if i < n - 1:
            x_div = MARGIN + espaco * (i + 1)
            c.setStrokeColor(colors.black)
            c.setLineWidth(2)
            c.setDash(2, 2)
            c.line(x_div, y_bar - 25 * mm, x_div, y_bar)
            c.setDash()

    y_sub = y_bar - 55 * mm
    etapas_finais = cfg.get("dashboard", {}).get("etapas_finais", ["Comissionamento", "Aceite"])
    for i, nome in enumerate(etapas_finais):
        cx = PAGE_W / 2 - 35 * mm + i * 70 * mm
        pil_w, pil_h = 60 * mm, 9 * mm
        c.setFillColor(colors.HexColor("#DDDDDD"))
        c.roundRect(cx - pil_w / 2, y_sub, pil_w, pil_h, pil_h / 2, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10)
        c.drawCentredString(cx, y_sub + 3 * mm, nome)
        c.setStrokeColor(colors.black)
        c.setLineWidth(1)
        c.circle(cx, y_sub - 12 * mm, 6 * mm, fill=0, stroke=1)
        c.line(cx, y_sub - 12 * mm, cx, y_sub - 15 * mm)
        c.line(cx, y_sub - 12 * mm, cx + 3 * mm, y_sub - 11 * mm)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10)
        c.drawCentredString(cx, y_sub - 22 * mm, "Aguardando")

    y_tab = 55 * mm
    colunas = ["Tarefa", "Empresa", "Prazo", "Responsavel"]
    col_w = (PAGE_W - 2 * MARGIN) / len(colunas)
    for i, nome in enumerate(colunas):
        cx = MARGIN + col_w * i + col_w / 2
        pil_w, pil_h = col_w - 10 * mm, 10 * mm
        c.setFillColor(_cor(cfg, "secundaria", "#1E88E5"))
        c.roundRect(cx - pil_w / 2, y_tab, pil_w, pil_h, pil_h / 2, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 10)
        c.drawCentredString(cx, y_tab + 3 * mm, nome)

    tarefas = cfg.get("dashboard", {}).get("tarefas", [])
    y_linha = y_tab - 8 * mm
    for tarefa in tarefas:
        for i, val in enumerate(tarefa):
            cx = MARGIN + col_w * i + col_w / 2
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 9)
            c.drawCentredString(cx, y_linha, str(val)[:35])
        y_linha -= 6 * mm


def desenhar_mapa(c, cfg, caminho_local):
    c.setFillColor(colors.HexColor("#7F7F7F"))
    c.rect(MARGIN, PAGE_H - 15 * mm, PAGE_W - 2 * MARGIN, 2 * mm, fill=1, stroke=0)
    map_w, map_h = 200 * mm, 140 * mm
    map_x = (PAGE_W - map_w) / 2
    map_y = 25 * mm
    if caminho_local and os.path.exists(caminho_local):
        desenhar_foto_ajustada(c, caminho_local, map_x, map_y, map_w, map_h)
    else:
        c.setFillColor(colors.HexColor("#E8E8E8"))
        c.rect(map_x, map_y, map_w, map_h, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont("Helvetica-Oblique", 12)
        c.drawCentredString(PAGE_W / 2, map_y + map_h / 2,
                            "[ foto_local.jpg nao encontrada ]")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 11)
    c.drawString(MARGIN, 15 * mm, f"Endereco: {cfg.get('endereco', '')}")


def desenhar_info_cameras(c, cfg, lista_cameras):
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 20)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 25 * mm, "Informacoes Cameras e Presets")
    y_bar = PAGE_H - 35 * mm
    c.setFillColor(colors.HexColor("#7F7F7F"))
    c.rect(MARGIN, y_bar, PAGE_W - 2 * MARGIN, 1.5 * mm, fill=1, stroke=0)

    colunas = ["Modelo", "ID", "Qtde. Presets", "observacoes", "Analista de", "status"]
    larguras = [40 * mm, 45 * mm, 30 * mm, 40 * mm, 45 * mm, 30 * mm]
    x_inicial = (PAGE_W - sum(larguras)) / 2
    y_topo = y_bar - 12 * mm
    x = x_inicial
    for nome, larg in zip(colunas, larguras):
        pil_w, pil_h = larg - 4 * mm, 10 * mm
        c.setFillColor(_cor(cfg, "secundaria", "#1E88E5"))
        c.roundRect(x + 2 * mm, y_topo, pil_w, pil_h, pil_h / 2, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 9)
        if nome == "Analista de":
            c.drawCentredString(x + 2 * mm + pil_w / 2, y_topo + 6 * mm, "Analista de")
            c.drawCentredString(x + 2 * mm + pil_w / 2, y_topo + 2.5 * mm, "Implantacao")
        else:
            c.drawCentredString(x + 2 * mm + pil_w / 2, y_topo + 3.5 * mm, nome)
        x += larg

    y_linha = y_topo - 12 * mm
    alt_linha = 8 * mm
    modelo = cfg.get("modelo_camera_padrao", "—")
    obs = cfg.get("obs_camera_padrao", "—")
    analista = cfg.get("analista_padrao", "—")
    status = cfg.get("status_padrao", "OK")

    for cam in lista_cameras:
        x = x_inicial
        c.setFillColor(colors.HexColor("#E0E0E0"))
        c.rect(x_inicial + 2 * mm, y_linha, sum(larguras) - 8 * mm,
               alt_linha - 1, fill=1, stroke=0)
        valores = [modelo, cam["camera"], str(cam["qtd_presets"]),
                   obs, analista, status]
        for val, larg in zip(valores, larguras):
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 9)
            c.drawCentredString(x + larg / 2, y_linha + 2.5 * mm, str(val)[:20])
            c.setStrokeColor(colors.white)
            c.setLineWidth(1)
            c.line(x + larg, y_linha, x + larg, y_linha + alt_linha - 1)
            x += larg
        y_linha -= alt_linha
        if y_linha < 20 * mm:
            c.showPage()
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 16)
            c.drawCentredString(PAGE_W / 2, PAGE_H - 20 * mm,
                                "Informacoes Cameras e Presets (cont.)")
            y_linha = PAGE_H - 40 * mm


def desenhar_desenho_subestacao(c, cfg, caminho_img):
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 20)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 25 * mm, "Desenho / Layout")
    c.setFillColor(colors.HexColor("#7F7F7F"))
    c.rect(MARGIN, PAGE_H - 35 * mm, PAGE_W - 2 * MARGIN, 1.5 * mm, fill=1, stroke=0)
    img_x, img_y = MARGIN, 15 * mm
    img_w = PAGE_W - 2 * MARGIN
    img_h = PAGE_H - 55 * mm
    if caminho_img and os.path.exists(caminho_img):
        desenhar_foto_ajustada(c, caminho_img, img_x, img_y, img_w, img_h)
    else:
        c.setFillColor(colors.HexColor("#E8E8E8"))
        c.rect(img_x, img_y, img_w, img_h, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont("Helvetica-Oblique", 12)
        c.drawCentredString(PAGE_W / 2, img_y + img_h / 2,
                            "[ desenho_subestacao.jpg nao encontrado ]")


def desenhar_legenda(c, linha, x, y, box_w, cfg):
    cam_txt = safe_str(linha.get("Camera")).replace("__", "_")
    ids_txt = safe_str(linha.get("IDSAGE"))
    pres_txt = safe_str(linha.get("Preset"))
    fase_txt = safe_str(linha.get("FASE"))
    est_txt = safe_str(linha.get("ESTADO"))

    x_camera = x + 3 * mm
    x_idsage = x + box_w * 0.35
    x_valor_direita = x + box_w - 3 * mm
    x_label_direita = x + box_w - 40 * mm
    ly = y

    c.setFillColor(colors.HexColor("#333333"))
    c.setFont("Helvetica", 7)
    c.drawString(x_camera, ly, "Camera")
    c.drawString(x_idsage, ly, "IDSAGE")
    c.drawString(x_label_direita, ly, "Preset")
    ly -= 3.5 * mm

    cor_destaque = _cor(cfg, "texto_destaque", "#CC0000")
    c.setFillColor(cor_destaque)
    c.setFont("Helvetica", 7)
    c.drawString(x_camera, ly, cam_txt[:25])
    c.drawString(x_idsage, ly, ids_txt[:35])
    c.drawRightString(x_valor_direita, ly, pres_txt)

    y_fase = ly - 3.5 * mm
    c.setFillColor(colors.HexColor("#333333"))
    c.drawString(x_label_direita, y_fase, "Fase")
    c.setFillColor(cor_destaque)
    c.drawRightString(x_valor_direita, y_fase, fase_txt[:25])

    y_estado = ly - 7 * mm
    label_txt = "Estado"
    valor_txt = est_txt
    gap = "    "
    largura_max = box_w - 6 * mm
    fontes = [7, 6.5, 6, 5.5, 5, 4.5, 4]
    fonte_escolhida = None
    for fonte_tam in fontes:
        largura_total = (
            stringWidth(label_txt, "Helvetica", fonte_tam) +
            stringWidth(gap, "Helvetica", fonte_tam) +
            stringWidth(valor_txt, "Helvetica", fonte_tam)
        )
        if largura_total <= largura_max:
            fonte_escolhida = fonte_tam
            break
    if fonte_escolhida is None:
        fonte_escolhida = 4
        largura_label = stringWidth(label_txt + gap, "Helvetica", fonte_escolhida)
        largura_disponivel_valor = largura_max - largura_label
        while valor_txt and stringWidth(valor_txt, "Helvetica", fonte_escolhida) > largura_disponivel_valor:
            valor_txt = valor_txt[:-1]
        if len(valor_txt) < len(est_txt) and valor_txt:
            valor_txt = valor_txt[:-3] + "..."

    largura_label = stringWidth(label_txt, "Helvetica", fonte_escolhida)
    largura_gap = stringWidth(gap, "Helvetica", fonte_escolhida)
    largura_valor = stringWidth(valor_txt, "Helvetica", fonte_escolhida)
    x_inicio_label = x_valor_direita - (largura_label + largura_gap + largura_valor)
    x_inicio_valor = x_inicio_label + largura_label + largura_gap

    c.setFillColor(colors.HexColor("#333333"))
    c.setFont("Helvetica", fonte_escolhida)
    c.drawString(x_inicio_label, y_estado, label_txt)
    c.setFillColor(cor_destaque)
    c.drawString(x_inicio_valor, y_estado, valor_txt)


def _desenhar_quadrante(c, linha, x, y, box_w, box_h, indice_fotos, cfg):
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.setLineWidth(1)
    c.setDash(3, 3)
    c.rect(x, y, box_w, box_h)
    c.setDash()

    if linha is None:
        c.setFillColor(colors.HexColor("#999999"))
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(x + box_w / 2, y + box_h / 2, "(sem foto)")
        return

    desenhar_legenda(c, linha, x, y + box_h - 4 * mm, box_w, cfg)

    foto_x = x + 3 * mm
    foto_y = y + 3 * mm
    foto_w = box_w - 6 * mm
    foto_h = box_h - 30 * mm

    ids_txt = safe_str(linha.get("IDSAGE"))
    pres_int = safe_int(linha.get("Preset"))
    pres_txt = safe_str(linha.get("Preset"))
    caminho = None
    if pres_int is not None:
        caminho = indice_fotos.get((normalizar(ids_txt), pres_int))

    if caminho:
        ok = desenhar_foto_ajustada(c, caminho, foto_x, foto_y, foto_w, foto_h)
        if not ok:
            c.setFillColor(colors.HexColor("#F5F5F5"))
            c.rect(foto_x, foto_y, foto_w, foto_h, fill=1, stroke=1)
    else:
        c.setStrokeColor(colors.HexColor("#DDDDDD"))
        c.setFillColor(colors.HexColor("#F5F5F5"))
        c.rect(foto_x, foto_y, foto_w, foto_h, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(foto_x + foto_w / 2, foto_y + foto_h / 2,
                            f"[ foto preset {pres_txt or '?'} nao encontrada ]")


def desenhar_pagina_fotos(c, grupos_pagina, indice_fotos, cfg):
    nome_se = cfg.get("nome_se", "")
    cameras = [safe_str(g["camera"]).replace("__", "_") for g in grupos_pagina]
    if len(cameras) == 1:
        titulo = f"Relatorio fotografico - {nome_se}_{cameras[0]}" if nome_se else f"Relatorio fotografico - {cameras[0]}"
    else:
        titulo = f"Relatorio fotografico - {nome_se}_{cameras[0]} e {cameras[1]}" if nome_se else f"Relatorio fotografico - {cameras[0]} e {cameras[1]}"

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, PAGE_H - 12 * mm, titulo)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.line(MARGIN, PAGE_H - 15 * mm, PAGE_W - MARGIN, PAGE_H - 15 * mm)

    area_top = PAGE_H - HEADER_H - MARGIN
    area_bottom = MARGIN
    area_left = MARGIN
    area_right = PAGE_W - MARGIN
    area_w = area_right - area_left
    area_h = area_top - area_bottom

    if len(grupos_pagina) == 2:
        box_w = (area_w - GAP) / 2
        box_h = (area_h - GAP) / 2
        quadrantes = [(0, 1), (1, 1), (0, 0), (1, 0)]
        slots = []
        for g in grupos_pagina:
            for linha in g["linhas"][:2]:
                slots.append(linha)
        while len(slots) < 4:
            slots.append(None)
        for (col, row), linha in zip(quadrantes, slots):
            x = area_left + col * (box_w + GAP)
            y = area_bottom + row * (box_h + GAP)
            _desenhar_quadrante(c, linha, x, y, box_w, box_h, indice_fotos, cfg)
        return

    grupo = grupos_pagina[0]
    n = len(grupo["linhas"])

    if n == 1:
        _desenhar_quadrante(c, grupo["linhas"][0], area_left, area_bottom,
                            area_w, area_h, indice_fotos, cfg)
        return
    if n == 2:
        box_h = (area_h - GAP) / 2
        for i, linha in enumerate(grupo["linhas"]):
            y = area_bottom + (1 - i) * (box_h + GAP)
            _desenhar_quadrante(c, linha, area_left, y, area_w, box_h, indice_fotos, cfg)
        return
    if n == 3:
        box_w = (area_w - GAP) / 2
        box_h = (area_h - GAP) / 2
        posicoes = [
            (area_left, area_bottom + box_h + GAP, box_w, box_h),
            (area_left + box_w + GAP, area_bottom + box_h + GAP, box_w, box_h),
            (area_left, area_bottom, area_w, box_h),
        ]
        for linha, (x, y, w, h) in zip(grupo["linhas"][:3], posicoes):
            _desenhar_quadrante(c, linha, x, y, w, h, indice_fotos, cfg)
        return

    box_w = (area_w - GAP) / 2
    box_h = (area_h - GAP) / 2
    quadrantes = [(0, 1), (1, 1), (0, 0), (1, 0)]
    for (col, row), linha in zip(quadrantes, grupo["linhas"][:4]):
        x = area_left + col * (box_w + GAP)
        y = area_bottom + row * (box_h + GAP)
        _desenhar_quadrante(c, linha, x, y, box_w, box_h, indice_fotos, cfg)


def desenhar_pagina_observacao(c, cfg, itens):
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 15 * mm,
                        f"Relatorio fotografico - {cfg.get('nome_se', '')}_OBSERVACAO")
    c.setStrokeColor(colors.HexColor("#7F7F7F"))
    c.setLineWidth(2)
    c.line(MARGIN, PAGE_H - 20 * mm, PAGE_W - MARGIN, PAGE_H - 20 * mm)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(MARGIN, PAGE_H - 33 * mm, "OBSERVACOES :")

    col_gap = 10 * mm
    larg_col = (PAGE_W - 2 * MARGIN - col_gap) / 2
    alt_cab = 7 * mm
    alt_linha = 6 * mm
    linhas_por_pagina = int((PAGE_H - 55 * mm) / alt_linha) - 2

    paginas_itens = [itens[i:i + linhas_por_pagina * 2]
                     for i in range(0, len(itens), linhas_por_pagina * 2)]

    for pagina_idx, pagina in enumerate(paginas_itens):
        if pagina_idx > 0:
            c.showPage()
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 14)
            c.drawCentredString(PAGE_W / 2, PAGE_H - 15 * mm,
                                f"Relatorio fotografico - {cfg.get('nome_se', '')}_OBSERVACAO (cont.)")
            c.setStrokeColor(colors.HexColor("#7F7F7F"))
            c.setLineWidth(2)
            c.line(MARGIN, PAGE_H - 20 * mm, PAGE_W - MARGIN, PAGE_H - 20 * mm)

        metade = (len(pagina) + 1) // 2
        colunas = [pagina[:metade], pagina[metade:]]
        for i, lista in enumerate(colunas):
            x = MARGIN + i * (larg_col + col_gap)
            y_topo = PAGE_H - 45 * mm
            c.setFillColor(_cor(cfg, "secundaria", "#1E88E5"))
            c.rect(x, y_topo, larg_col, alt_cab, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(x + 2 * mm, y_topo + 2 * mm, "IDSAGE")
            c.drawString(x + larg_col * 0.55, y_topo + 2 * mm, "OBSERVACOES")
            y = y_topo - alt_linha
            for item in lista:
                c.setFillColor(colors.HexColor("#E53935"))
                c.rect(x, y, larg_col, alt_linha - 0.5, fill=1, stroke=0)
                c.setFillColor(colors.white)
                c.setFont("Helvetica", 7)
                c.drawString(x + 2 * mm, y + 1.5 * mm, item["idsage"][:40])
                c.drawString(x + larg_col * 0.55, y + 1.5 * mm, item["obs"][:35])
                y -= alt_linha


def desenhar_aceite_presets(c, cfg):
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 20)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 25 * mm, "Aceite de Presets")
    c.setStrokeColor(colors.HexColor("#7F7F7F"))
    c.setLineWidth(2)
    c.line(MARGIN, PAGE_H - 30 * mm, PAGE_W - MARGIN, PAGE_H - 30 * mm)

    texto_template = cfg.get("texto_aceite", (
        "Conforme as Especificações Técnicas em contrato, as partes concordam que o projeto "
        "na Subestação {nome_se} foi concluído com a execução de todas as fases e resultados "
        "previstos e definidos inicialmente, todos os presets validados.\n\n"
        "Lembrando, por fim, que a assinatura deste documento representa a concordância "
        "do Contratante com os termos aqui estabelecidos."
    ))
    texto = texto_template.format(nome_se=cfg.get("nome_se", ""))

    c.setFont("Helvetica", 10)
    y = PAGE_H - 50 * mm
    for paragrafo in texto.split("\n\n"):
        linhas = wrap_text(paragrafo, "Helvetica", 10, PAGE_W - 2 * MARGIN)
        for l in linhas:
            c.drawString(MARGIN, y, l)
            y -= 5 * mm
        y -= 5 * mm

    y_ass = 60 * mm
    bloco_w = 70 * mm
    x1 = MARGIN + 15 * mm
    x2 = PAGE_W - MARGIN - bloco_w - 15 * mm

    c.setFont("Helvetica", 9)
    c.drawString(x1, y_ass + 25 * mm, "Representante")
    c.drawString(x1, y_ass + 20 * mm, f"Contratante: {cfg.get('contratante', '')}")
    c.drawString(x2, y_ass + 25 * mm, "Representante")
    c.drawString(x2, y_ass + 20 * mm, f"Contratada: {cfg.get('contratada', '')}")

    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.line(x1, y_ass + 10 * mm, x1 + bloco_w, y_ass + 10 * mm)
    c.line(x2, y_ass + 10 * mm, x2 + bloco_w, y_ass + 10 * mm)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x1 + bloco_w / 2, y_ass + 7 * mm, "Nome Completo")
    c.drawCentredString(x2 + bloco_w / 2, y_ass + 7 * mm, "Nome Completo")
    c.line(x1, y_ass - 8 * mm, x1 + bloco_w, y_ass - 8 * mm)
    c.line(x2, y_ass - 8 * mm, x2 + bloco_w, y_ass - 8 * mm)
    c.drawCentredString(x1 + bloco_w / 2, y_ass - 11 * mm, "Assinatura")
    c.drawCentredString(x2 + bloco_w / 2, y_ass - 11 * mm, "Assinatura")


# ============================================================
# Função principal
# ============================================================
def gerar_relatorio(config_path=ARQUIVO_CONFIG,
                    excel_path=None,
                    pasta_fotos=PASTA_FOTOS,
                    pasta_saida=PASTA_SAIDA,
                    excluir_usadas=None,
                    log_callback=None):
    def log(msg):
        print(msg)
        if log_callback:
            log_callback(msg)

    os.makedirs(pasta_saida, exist_ok=True)
    arq_pdf = os.path.join(pasta_saida, "relatorio.pdf")
    arq_log = os.path.join(pasta_saida, "log_fotos.txt")

    log("Lendo config...")
    cfg = carregar_config(config_path)
    log(f"   -> {cfg.get('nome_se')} | Ano: {cfg.get('ano')} | v{cfg.get('versao', '2.2')}")

    if excel_path is None:
        excel_path = cfg.get("excel_arquivo", "Excel.xlsx")

    if excluir_usadas is None:
        excluir_usadas = cfg.get("excluir_fotos_usadas", False)

    log("Lendo Excel...")
    df = carregar_dados(excel_path)
    log(f"   -> {len(df)} linhas")

    log("Indexando fotos...")
    indice, nao_reconhecidas = indexar_fotos(pasta_fotos)
    log(f"   -> {len(indice)} fotos reconhecidas")

    idsages_excel = set(normalizar(x) for x in df["IDSAGE"].unique())
    problemas_fotos = []
    for nome, motivo in nao_reconhecidas:
        problemas_fotos.append((nome, motivo))

    for (idsage_norm, preset), caminho in indice.items():
        if idsage_norm not in idsages_excel:
            problemas_fotos.append(
                (os.path.basename(caminho),
                 f"IDSAGE '{idsage_norm}' nao existe no Excel"))

    combos_excel = set()
    for _, row in df.iterrows():
        ids = normalizar(safe_str(row.get("IDSAGE")))
        pres = safe_int(row.get("Preset"))
        if ids and pres is not None:
            combos_excel.add((ids, pres))

    for (idsage_norm, preset), caminho in indice.items():
        if idsage_norm in idsages_excel and (idsage_norm, preset) not in combos_excel:
            problemas_fotos.append(
                (os.path.basename(caminho),
                 f"Preset {preset} nao esta no Excel para IDSAGE '{idsage_norm}'"))

    col_obs = None
    for cc in df.columns:
        if "OBSERV" in cc.upper():
            col_obs = cc
            break

    linhas_sem_foto = []
    for _, row in df.iterrows():
        idsage = safe_str(row.get("IDSAGE"))
        if not idsage or idsage.lower() == "nan":
            continue
        cam = safe_str(row.get("Camera"))
        fase = safe_str(row.get("FASE"))
        estado = safe_str(row.get("ESTADO"))
        obs = safe_str(row.get(col_obs)) if col_obs else ""
        preset_int = safe_int(row.get("Preset"))
        idsage_norm = normalizar(idsage)
        tem_foto = False
        if preset_int is not None:
            tem_foto = (idsage_norm, preset_int) in indice
        if not tem_foto:
            if not cam or cam.lower() == "nan":
                motivo = "Linha sem camera definida (provavelmente SEM VISAO / nao instalada)"
            elif preset_int is None:
                motivo = "Linha sem Preset preenchido no Excel (nao gera pagina, apenas documentada)"
            elif fase.upper() in ("SEM VISAO", "VISAO OBSTRUIDAS", "SEM VISÃO", "VISÃO OBSTRUÍDAS") or \
                 "SEM VIS" in obs.upper() or "OBSTRU" in obs.upper():
                motivo = "Linha marcada como SEM VISAO / VISAO OBSTRUIDA no Excel"
            else:
                motivo = f"Nenhum arquivo com preset {preset_int} encontrado na pasta fotos/"
            linhas_sem_foto.append({
                "idsage": idsage, "preset": preset_int,
                "fase": fase, "estado": estado, "motivo": motivo,
            })

    log("Procurando fotos especiais...")
    desenho = achar_imagem_especial(pasta_fotos, NOMES_DESENHO)
    foto_local = achar_imagem_especial(pasta_fotos, NOMES_FOTO_LOCAL)
    log(f"   -> Desenho: {os.path.basename(desenho) if desenho else 'nao encontrado'}")
    log(f"   -> Foto local: {os.path.basename(foto_local) if foto_local else 'nao encontrada'}")

    log("Coletando info...")
    lista_cameras = coletar_info_cameras(df)
    itens_sem_visao = coletar_sem_visao(df)
    grupos = agrupar(df)
    paginas = montar_paginas(grupos)
    log(f"   -> {len(lista_cameras)} cameras | {len(itens_sem_visao)} SEM VISAO | {len(paginas)} paginas de fotos")

    log("Escrevendo log...")
    total_linhas = len(df)
    ids_problem = set(p[0] for p in problemas_fotos)
    total_fotos_ok = sum(1 for k in indice.keys() if os.path.basename(indice[k]) not in ids_problem)
    total_sem_foto = len(linhas_sem_foto)

    L = []
    L.append("=" * 70)
    L.append(f"  RELATORIO DE FOTOS - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    L.append("=" * 70)
    L.append("")
    L.append("RESUMO")
    L.append("-" * 70)
    L.append(f"Excel:        {total_linhas} linhas")
    L.append(f"Fotos OK:     {total_fotos_ok}")
    L.append(f"Sem foto:     {total_sem_foto}")
    L.append(f"Problemas:    {len(problemas_fotos)}")
    L.append("")
    L.append("PROBLEMAS NAS FOTOS (arquivos):")
    L.append("-" * 70)
    if problemas_fotos:
        for nome, motivo in problemas_fotos:
            L.append(f"  - {nome}")
            L.append(f"     -> {motivo}")
    else:
        L.append("  OK - Nenhum problema detectado.")
    L.append("")
    L.append("LINHAS DO EXCEL SEM FOTO:")
    L.append("-" * 70)
    if linhas_sem_foto:
        for item in linhas_sem_foto:
            pres_txt = f"Preset {item['preset']}" if item['preset'] is not None else "(sem preset)"
            fase_txt = item['fase'] if item['fase'] else "(sem fase)"
            L.append(f"  - IDSAGE: {item['idsage']} | {pres_txt} | Fase: {fase_txt}")
            L.append(f"     -> Motivo: {item['motivo']}")
    else:
        L.append("  OK - Todas as linhas tem foto.")
    L.append("")
    L.append("=" * 70)

    with open(arq_log, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    log(f"   -> Log salvo: {arq_log}")
    log(f"     Fotos OK: {total_fotos_ok} | Sem foto: {total_sem_foto} | Problemas: {len(problemas_fotos)}")

    log("Gerando PDF...")
    c = canvas.Canvas(arq_pdf, pagesize=(PAGE_W, PAGE_H))
    desenhar_capa(c, cfg)
    c.showPage()
    desenhar_dashboard(c, cfg)
    c.showPage()
    desenhar_mapa(c, cfg, foto_local)
    c.showPage()
    desenhar_info_cameras(c, cfg, lista_cameras)
    c.showPage()
    desenhar_desenho_subestacao(c, cfg, desenho)
    c.showPage()
    for pagina in paginas:
        desenhar_pagina_fotos(c, pagina, indice, cfg)
        c.showPage()
    desenhar_pagina_observacao(c, cfg, itens_sem_visao)
    c.showPage()
    desenhar_aceite_presets(c, cfg)
    c.showPage()
    desenhar_capa(c, cfg, fundo_cinza=True)
    c.showPage()
    c.save()
    log(f"OK - PDF: {arq_pdf}")

    if excluir_usadas and indice:
        log("Movendo fotos usadas para fotos/_usadas/...")
        movidos = mover_apenas_usadas(indice, problemas_fotos)
        total_usadas = total_fotos_ok
        log(f"   -> {len(movidos)} de {total_usadas} fotos usadas foram movidas")
        if len(movidos) != total_usadas:
            log(f"   ⚠️  Aviso: esperava mover {total_usadas}, moveu {len(movidos)}")
        with open(arq_log, "a", encoding="utf-8") as f:
            f.write(f"\nFOTOS USADAS MOVIDAS PARA _usadas/: {len(movidos)} de {total_usadas}\n")

    return {
        "pdf": arq_pdf,
        "log": arq_log,
        "total_fotos_ok": total_fotos_ok,
        "total_sem_foto": total_sem_foto,
        "problemas": len(problemas_fotos)
    }


def main():
    gerar_relatorio()


if __name__ == "__main__":
    main()
