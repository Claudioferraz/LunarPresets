# -*- coding: utf-8 -*-
"""
Painel de Relatórios Fotográficos
Versão 2.2.0 — Generalizada
Desenvolvedor: Claudio Ibarrola
"""
import os
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime
import threading
import json

# ============================================================
# Cores do tema
# ============================================================
COR_BG = "#1a1a1a"
COR_PAINEL = "#2b2b2b"
COR_DESTAQUE = "#CC0000"
COR_VERDE = "#2E7D32"
COR_VERMELHO = "#8B0000"
COR_AMARELO = "#E53935"
COR_TEXTO = "#FFFFFF"
COR_SUBTEXTO = "#B0B0B0"

ARQUIVO_CONFIG = "config.json"

FUNCOES_OBRIGATORIAS_MAIN = [
    "carregar_dados", "carregar_config", "indexar_fotos",
    "normalizar", "safe_str", "safe_int", "gerar_relatorio",
]


def ler_config():
    if not os.path.exists(ARQUIVO_CONFIG):
        raise FileNotFoundError(f"{ARQUIVO_CONFIG} não encontrado.")
    with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def escrever_config(cfg):
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def verificar_main_integro(log_fn):
    if not os.path.exists("main.py"):
        log_fn("❌ ERRO: 'main.py' NÃO ENCONTRADO na pasta!")
        return False, None
    try:
        import importlib
        import main
        importlib.reload(main)
    except SyntaxError as e:
        log_fn(f"❌ ERRO: main.py tem erro de sintaxe na linha {e.lineno}: {e.msg}")
        return False, None
    except Exception as e:
        log_fn(f"❌ ERRO ao importar main.py: {e}")
        return False, None
    faltando = [f for f in FUNCOES_OBRIGATORIAS_MAIN if not hasattr(main, f)]
    if faltando:
        log_fn("❌ ERRO: main.py está INCOMPLETO.")
        log_fn(f"   Faltam: {', '.join(faltando)}")
        return False, None
    return True, main


class PainelRelatorio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Painel de Relatórios Fotográficos")
        self.geometry("920x680")
        self.configure(bg=COR_BG)
        self.minsize(820, 600)
        self._construir_header()
        self._construir_status()
        self._construir_botoes()
        self._construir_log()
        self.atualizar_status()

    def _construir_header(self):
        frame = tk.Frame(self, bg=COR_DESTAQUE, height=78)
        frame.pack(fill="x")
        frame.pack_propagate(False)

        tk.Label(frame, text="📋  PAINEL DE RELATÓRIOS",
                 font=("Segoe UI", 17, "bold"),
                 bg=COR_DESTAQUE, fg="white").pack(side="left", padx=20)

        sub = tk.Frame(frame, bg=COR_DESTAQUE)
        sub.pack(side="left", padx=10)
        tk.Label(sub, text="Claudio Ibarrola", font=("Segoe UI", 11, "bold"),
                 bg=COR_DESTAQUE, fg="white").pack(anchor="w")
        tk.Label(sub, text="Desenvolvedor", font=("Segoe UI", 8),
                 bg=COR_DESTAQUE, fg="#FFCDD2").pack(anchor="w")

        tk.Label(frame, text="v2.2.0", font=("Segoe UI", 10),
                 bg=COR_DESTAQUE, fg="white").pack(side="right", padx=20)

    def _construir_status(self):
        frame = tk.Frame(self, bg=COR_BG, pady=10)
        frame.pack(fill="x", padx=20)
        self.lbl_status = tk.Label(frame, text="Aguardando...",
                                   font=("Segoe UI", 10, "bold"),
                                   bg=COR_BG, fg=COR_SUBTEXTO, anchor="w")
        self.lbl_status.pack(fill="x")
        self.lbl_info = tk.Label(frame, text="", font=("Segoe UI", 9),
                                 bg=COR_BG, fg=COR_SUBTEXTO, anchor="w")
        self.lbl_info.pack(fill="x")

    def _construir_botoes(self):
        frame = tk.Frame(self, bg=COR_BG)
        frame.pack(fill="x", padx=20, pady=8)

        linha1 = tk.Frame(frame, bg=COR_BG)
        linha1.pack(fill="x", pady=4)

        self.btn_produzir = self._botao(linha1, "▶  INICIAR PRODUÇÃO",
                                        COR_VERDE, self.acao_produzir, width=26)
        self.btn_produzir.pack(side="left", padx=(0, 8))

        self.btn_verificar = self._botao(linha1, "🔍  CONFERIR DADOS",
                                         COR_AMARELO, self.acao_verificar, width=22)
        self.btn_verificar.pack(side="left", padx=8)

        linha2 = tk.Frame(frame, bg=COR_BG)
        linha2.pack(fill="x", pady=4)

        self._botao(linha2, "⚙  CONFIGURAÇÕES", COR_DESTAQUE,
                    self.acao_config, width=20).pack(side="left", padx=(0, 8))
        self._botao(linha2, "📂  ABRIR SAÍDA", COR_PAINEL,
                    self.acao_abrir_saida, width=16).pack(side="left", padx=6)
        self._botao(linha2, "🗑  ABRIR _usadas", COR_PAINEL,
                    self.acao_abrir_usadas, width=16).pack(side="left", padx=6)
        self._botao(linha2, "❌  SAIR", COR_VERMELHO,
                    self.destroy, width=10).pack(side="right")

    def _botao(self, parent, texto, cor, comando, width=18):
        return tk.Button(parent, text=texto, command=comando,
                         bg=cor, fg="white", font=("Segoe UI", 10, "bold"),
                         relief="flat", cursor="hand2",
                         activebackground=cor, activeforeground="white",
                         width=width, height=2)

    def _construir_log(self):
        frame = tk.Frame(self, bg=COR_BG)
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 18))

        topo = tk.Frame(frame, bg=COR_BG)
        topo.pack(fill="x")
        tk.Label(topo, text="LOG DE EXECUÇÃO", font=("Segoe UI", 9, "bold"),
                 bg=COR_BG, fg=COR_SUBTEXTO).pack(side="left")
        tk.Button(topo, text="Limpar", command=self._limpar_log,
                  bg=COR_PAINEL, fg=COR_TEXTO, relief="flat",
                  font=("Segoe UI", 8), cursor="hand2").pack(side="right")

        self.log = scrolledtext.ScrolledText(frame, bg="#141414", fg=COR_TEXTO,
                                             font=("Consolas", 9),
                                             relief="flat", wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _limpar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _set_status(self, texto, cor=COR_SUBTEXTO):
        self.lbl_status.configure(text=texto, fg=cor)

    def atualizar_status(self):
        try:
            cfg = ler_config()
            nome = cfg.get("nome_se", "?")
            excel_nome = cfg.get("excel_arquivo", "Excel.xlsx")
            excel_ok = os.path.exists(excel_nome)
            main_ok = os.path.exists("main.py")
            fotos_ok = os.path.isdir("fotos")
            total_fotos = 0
            if fotos_ok:
                total_fotos = len([f for f in os.listdir("fotos")
                                   if os.path.isfile(os.path.join("fotos", f))])
            usadas = 0
            if os.path.isdir("fotos/_usadas"):
                usadas = len(os.listdir("fotos/_usadas"))

            self.lbl_info.configure(
                text=f"SE: {nome}  |  Excel: {'OK' if excel_ok else 'FALTANDO'} ({excel_nome})  |  "
                     f"main.py: {'OK' if main_ok else 'FALTANDO'}  |  "
                     f"Fotos: {total_fotos}  |  Já usadas: {usadas}"
            )
            if not excel_ok:
                self._set_status(f"⚠️  {excel_nome} não encontrado.", COR_VERMELHO)
            elif not main_ok:
                self._set_status("⚠️  main.py não encontrado.", COR_VERMELHO)
            else:
                self._set_status("Pronto para iniciar.", COR_VERDE)
        except Exception as e:
            self._set_status(f"Erro ao ler config: {e}", COR_VERMELHO)

    def acao_produzir(self):
        try:
            cfg = ler_config()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro no config.json:\n{e}")
            return

        excel_nome = cfg.get("excel_arquivo", "Excel.xlsx")
        if not os.path.exists(excel_nome):
            messagebox.showerror("Erro", f"{excel_nome} não encontrado.")
            return
        if not os.path.isdir("fotos"):
            messagebox.showerror("Erro", "Pasta fotos/ não encontrada.")
            return

        confirmar = messagebox.askyesno(
            "Iniciar Produção",
            f"Gerar relatório para:\n\n{cfg.get('nome_se', '?')}\n\nContinuar?")
        if not confirmar:
            return

        self._set_status("⚙ Produzindo...", COR_AMARELO)
        self._limpar_log()
        self._log(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando produção...")
        self.btn_produzir.configure(state="disabled")
        self.btn_verificar.configure(state="disabled")
        threading.Thread(target=self._thread_produzir, daemon=True).start()

    def _thread_produzir(self):
        try:
            ok, main_mod = verificar_main_integro(
                lambda m: self.after(0, self._log, m))
            if not ok:
                self.after(0, self._pos_produzir, None, "main.py inválido")
                return
            resultado = main_mod.gerar_relatorio(
                config_path=ARQUIVO_CONFIG,
                excluir_usadas=None,
                log_callback=lambda m: self.after(0, self._log, m))
            self.after(0, self._pos_produzir, resultado, None)
        except Exception:
            import traceback
            self.after(0, self._pos_produzir, None, traceback.format_exc())

    def _pos_produzir(self, resultado, erro):
        self.btn_produzir.configure(state="normal")
        self.btn_verificar.configure(state="normal")
        if erro:
            self._log("❌ ERRO:\n" + erro)
            self._set_status("Erro na produção.", COR_VERMELHO)
            messagebox.showerror("Erro", "Falha ao gerar relatório. Veja o log.")
        else:
            self._log(f"\n✅ PDF: {resultado['pdf']}")
            self._set_status("✅ Produção concluída.", COR_VERDE)
            self.atualizar_status()
            messagebox.showinfo(
                "Sucesso",
                f"PDF gerado com sucesso!\n\n"
                f"Fotos OK: {resultado['total_fotos_ok']}\n"
                f"Sem foto: {resultado['total_sem_foto']}\n"
                f"Problemas: {resultado['problemas']}"
            )

    def acao_verificar(self):
        self._limpar_log()
        self._log(f"[{datetime.now().strftime('%H:%M:%S')}] Conferindo dados...\n")
        ok, main_mod = verificar_main_integro(self._log)
        if not ok:
            self._set_status("❌ main.py com problema.", COR_VERMELHO)
            return
        try:
            cfg = ler_config()
            self._log(f"✅ config.json OK (SE: {cfg.get('nome_se', '?')})")

            excel_nome = cfg.get("excel_arquivo", "Excel.xlsx")
            if not os.path.exists(excel_nome):
                self._log(f"❌ ERRO: {excel_nome} não encontrado!")
                self._set_status("❌ Excel não encontrado.", COR_VERMELHO)
                return
            if not os.path.isdir("fotos"):
                self._log("❌ ERRO: pasta 'fotos/' não encontrada!")
                self._set_status("❌ Pasta fotos/ não encontrada.", COR_VERMELHO)
                return

            self._log(f"✅ {excel_nome} e pasta fotos/ encontrados")
            df = main_mod.carregar_dados(excel_nome)
            self._log(f"✅ Excel lido: {len(df)} linhas")
            indice, nao_rec = main_mod.indexar_fotos("fotos")
            self._log(f"✅ Fotos reconhecidas: {len(indice)}")

            idsages_excel = set(main_mod.normalizar(x) for x in df["IDSAGE"].unique())
            self._log("\n" + "=" * 55)
            self._log("📊 RESUMO")
            self._log("=" * 55)
            self._log(f"   Excel: {len(df)} linhas")
            self._log(f"   Fotos reconhecidas: {len(indice)}")
            self._log(f"   Fora do padrão: {len(nao_rec)}")

            problemas = 0
            self._log("\n🔎 Checagem 1: IDSAGE das fotos existem no Excel?")
            for (idsage_norm, preset), caminho in indice.items():
                if idsage_norm not in idsages_excel:
                    self._log(f"   ⚠️  {os.path.basename(caminho)} → IDSAGE '{idsage_norm}' não existe")
                    problemas += 1

            combos_excel = set()
            for _, row in df.iterrows():
                ids = main_mod.normalizar(main_mod.safe_str(row.get("IDSAGE")))
                pres = main_mod.safe_int(row.get("Preset"))
                if ids and pres is not None:
                    combos_excel.add((ids, pres))

            self._log("\n🔎 Checagem 2: Presets das fotos existem no Excel?")
            for (idsage_norm, preset), caminho in indice.items():
                if idsage_norm in idsages_excel and (idsage_norm, preset) not in combos_excel:
                    self._log(f"   ⚠️  {os.path.basename(caminho)} → Preset {preset} não está")
                    problemas += 1

            self._log("\n🔎 Checagem 3: Nomes seguem o padrão?")
            for nome, motivo in nao_rec:
                self._log(f"   ⚠️  {nome} → {motivo}")
                problemas += 1

            self._log("\n" + "=" * 55)
            if problemas == 0:
                self._log("✅ TUDO OK — pode iniciar a produção!")
                self._set_status("✅ Verificação OK.", COR_VERDE)
            else:
                self._log(f"⚠️  {problemas} problema(s) — corrija antes de produzir")
                self._set_status(f"⚠️  {problemas} problema(s).", COR_AMARELO)
        except Exception as e:
            self._log(f"❌ Erro inesperado: {e}")
            import traceback
            self._log(traceback.format_exc())
            self._set_status("❌ Erro na verificação.", COR_VERMELHO)

    def acao_config(self):
        JanelaConfig(self)

    def acao_abrir_saida(self):
        caminho = os.path.abspath("saida")
        if not os.path.exists(caminho):
            messagebox.showinfo("Info", "Pasta saida/ ainda não existe.")
            return
        if sys.platform == "win32":
            os.startfile(caminho)
        else:
            os.system(f'xdg-open "{caminho}"')

    def acao_abrir_usadas(self):
        caminho = os.path.abspath("fotos/_usadas")
        if not os.path.exists(caminho):
            messagebox.showinfo("Info", "Pasta _usadas/ ainda não existe.")
            return
        if sys.platform == "win32":
            os.startfile(caminho)
        else:
            os.system(f'xdg-open "{caminho}"')


class JanelaConfig(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("⚙ Configurações")
        self.geometry("680x780")
        self.configure(bg=COR_BG)
        self.transient(parent)
        self.grab_set()
        self.cfg = ler_config()
        self._construir()

    def _construir(self):
        tk.Label(self, text="⚙ CONFIGURAÇÕES",
                 font=("Segoe UI", 14, "bold"), bg=COR_BG, fg="white").pack(pady=12)

        # Canvas com scroll para caber tudo
        container = tk.Frame(self, bg=COR_BG)
        container.pack(fill="both", expand=True, padx=20, pady=5)

        canvas = tk.Canvas(container, bg=COR_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=COR_BG)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.campos = {}
        campos_lista = [
            ("ano", "Ano"),
            ("projeto", "Nome do Projeto"),
            ("nome_se", "Nome da Subestação / Local"),
            ("responsavel", "Responsável"),
            ("data", "Data"),
            ("endereco", "Endereço"),
            ("numero_do_projeto", "Número do Projeto"),
            ("contratante", "Contratante"),
            ("contratada", "Contratada"),
            ("excel_arquivo", "Nome do arquivo Excel"),
            ("titulo_software", "Título do Software (capa)"),
        ]
        for chave, rotulo in campos_lista:
            self._add_campo(scrollable, chave, rotulo)

        self.var_excluir = tk.BooleanVar(value=self.cfg.get("excluir_fotos_usadas", False))
        tk.Checkbutton(scrollable, text="🗑  Mover fotos usadas após gerar PDF",
                       variable=self.var_excluir,
                       bg=COR_BG, fg=COR_TEXTO, selectcolor=COR_PAINEL,
                       font=("Segoe UI", 10), activebackground=COR_BG,
                       cursor="hand2").pack(anchor="w", pady=(12, 6))

        tk.Label(scrollable, text="Tarefas do Dashboard (Tarefa|Empresa|Prazo|Responsável)",
                 bg=COR_BG, fg=COR_SUBTEXTO, font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 3))
        self.txt_tarefas = tk.Text(scrollable, height=5, bg=COR_PAINEL, fg=COR_TEXTO,
                                   font=("Consolas", 9), relief="flat", insertbackground="white")
        self.txt_tarefas.pack(fill="x", pady=4)
        tarefas = self.cfg.get("dashboard", {}).get("tarefas", [])
        self.txt_tarefas.insert("1.0", "\n".join("|".join(str(x) for x in t) for t in tarefas))

        tk.Label(scrollable, text="Texto de Aceite (use {nome_se} onde quiser o nome do local)",
                 bg=COR_BG, fg=COR_SUBTEXTO, font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 3))
        self.txt_aceite = tk.Text(scrollable, height=6, bg=COR_PAINEL, fg=COR_TEXTO,
                                  font=("Consolas", 9), relief="flat", insertbackground="white")
        self.txt_aceite.pack(fill="x", pady=4)
        self.txt_aceite.insert("1.0", self.cfg.get("texto_aceite", ""))

        # Botões
        botoes = tk.Frame(self, bg=COR_BG)
        botoes.pack(fill="x", padx=20, pady=15)
        tk.Button(botoes, text="💾  SALVAR", command=self.salvar,
                  bg=COR_VERDE, fg="white", font=("Segoe UI", 11, "bold"),
                  relief="flat", width=14, height=2, cursor="hand2").pack(side="left")
        tk.Button(botoes, text="❌  CANCELAR", command=self.destroy,
                  bg=COR_VERMELHO, fg="white", font=("Segoe UI", 11, "bold"),
                  relief="flat", width=14, height=2, cursor="hand2").pack(side="right")

    def _add_campo(self, parent, chave, rotulo):
        f = tk.Frame(parent, bg=COR_BG)
        f.pack(fill="x", pady=3)
        tk.Label(f, text=rotulo, bg=COR_BG, fg=COR_SUBTEXTO,
                 font=("Segoe UI", 9), width=26, anchor="w").pack(side="left")
        var = tk.StringVar(value=str(self.cfg.get(chave, "")))
        entry = tk.Entry(f, textvariable=var, bg=COR_PAINEL, fg=COR_TEXTO,
                         font=("Segoe UI", 10), relief="flat", insertbackground="white")
        entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.campos[chave] = var

    def salvar(self):
        try:
            novo = dict(self.cfg)
            for chave, var in self.campos.items():
                novo[chave] = var.get().strip()
            novo["excluir_fotos_usadas"] = self.var_excluir.get()

            # Tarefas
            tarefas = []
            for linha in self.txt_tarefas.get("1.0", "end").strip().split("\n"):
                if not linha.strip():
                    continue
                partes = [p.strip() for p in linha.split("|")]
                while len(partes) < 4:
                    partes.append("")
                tarefas.append(partes[:4])

            if "dashboard" not in novo:
                novo["dashboard"] = {}
            novo["dashboard"]["tarefas"] = tarefas
            novo["texto_aceite"] = self.txt_aceite.get("1.0", "end").strip()

            escrever_config(novo)
            messagebox.showinfo("Sucesso", "config.json atualizado!")
            self.destroy()
            # Atualiza o painel principal se possível
            if hasattr(self.master, "atualizar_status"):
                self.master.atualizar_status()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar:\n{e}")


if __name__ == "__main__":
    app = PainelRelatorio()
    app.mainloop()
