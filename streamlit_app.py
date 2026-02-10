import streamlit as st
import database as db
import pandas as pd
from io import StringIO
import unicodedata
import re
from fpdf import FPDF

# ========================================================
# CONFIGURAÇÃO DA PÁGINA
# ========================================================
st.set_page_config(page_title="Fichamento Cloud", layout="wide")

# Inicializa DB (Conexão com Google Sheets)
try:
    db.init_db()
except Exception as e:
    st.error(f"Erro de conexão: {e}")

# CSS Customizado (Botões Empilhados)
st.markdown("""
<style>
    div.stButton > button { width: 100%; border-radius: 6px; margin-bottom: 4px; }
    div.stDownloadButton > button { width: 100%; border-radius: 6px; margin-bottom: 4px; }
    div[data-testid="column"] { align-self: start; }
</style>
""", unsafe_allow_html=True)

# ========================================================
# CABEÇALHO E CONTROLO DE CACHE
# ========================================================
c_title, c_refresh = st.columns([0.85, 0.15])
with c_title:
    st.title("☁️ Fichamento Analítico")
with c_refresh:
    # Botão vital para limpar o cache de 5 minutos se o utilizador quiser ver dados novos agora
    if st.button("🔄 Atualizar"):
        st.cache_data.clear()
        st.rerun()

if 'dados_preview' not in st.session_state: st.session_state.dados_preview = None

menu = st.sidebar.selectbox("Menu", ["Cadastrar Obra", "Importar", "Fazer Fichamento", "Visualizar Dados"])

# ========================================================
# CLASSES E FUNÇÕES AUXILIARES
# ========================================================

# --- CLASSE PDF (FPDF) ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Ficha de Leitura', 0, 1, 'C')
        self.ln(5)

def criar_pdf_fichamento(f, ref_abnt):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    
    # Função para limpar caracteres não compatíveis com Latin-1 (evita crash do FPDF)
    def clean(text):
        if not text: return ""
        # Normaliza e substitui caracteres estranhos
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    # Referência
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, clean("Referência Bibliográfica:"), ln=1)
    pdf.set_font("Arial", '', 11)
    # Remove negrito do markdown para o PDF
    ref_limpa = ref_abnt.replace('**', '')
    pdf.multi_cell(0, 6, clean(ref_limpa))
    pdf.ln(5)
    
    # Campos do Fichamento
    # f[3]=Conceito, f[4]=Ideia, f[5]=Definição, f[7]=Citação, f[6]=Relação, f[8]=Tags
    campos = [
        ("Conceito Chave", f[3]),
        ("Ideia Central", f[4]),
        ("Definição do Conceito", f[5]),
        ("Citação Direta", f[7]),
        ("Relação Bibliográfica", f[6]),
        ("Tags", f[8])
    ]
    
    for titulo, conteudo in campos:
        if conteudo and str(conteudo).strip() != "":
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, clean(titulo), ln=1)
            pdf.set_font("Arial", '', 11)
            pdf.multi_cell(0, 6, clean(conteudo))
            pdf.ln(4)
            
    return pdf.output(dest='S').encode('latin-1')

# --- HELPERS DE TEXTO ---
def normalizar_coluna(t): 
    return ''.join(c for c in unicodedata.normalize('NFD', str(t)) if unicodedata.category(c) != 'Mn').lower().strip()

def formatar_referencia_abnt_obra(f):
    # Indices OBRAS: 0:id, 1:tit, 2:sub, 3:aut, 4:ano, 5:loc, 6:edit, 7:pag, 8:vol, 9:fol, 10:ser, 11:not, 12:ed, 13:on, 14:url, 15:dat, 16:typ
    titulo = f[1]
    subtitulo = f": {f[2]}" if f[2] else ""
    autor = f[3]
    ano = f[4]
    local = f[5]
    editora = f[6]
    edicao = f"{f[12]} " if f[12] else ""
    tipo = f[16]
    
    detalhes = ""
    if f[8]: detalhes += f"v. {f[8]}, "
    
    if tipo and "Artigo" in tipo:
        ref = f"{autor}. {titulo}{subtitulo}. **{editora}**, {local}, {detalhes}{ano}."
    else:
        ref = f"{autor}. **{titulo}**{subtitulo}. {edicao}{local}: {editora}, {ano}."
    
    if str(f[13]) == "1": ref += f" Disponível em: {f[14]}."
    return ref

def formatar_referencia_abnt_ficha(f):
    # f[0-10] ficha, f[11-27] obra (Joined Data)
    titulo = f[12]
    subtitulo = f": {f[13]}" if f[13] else ""
    autor = f[14]
    ano = f[15]
    local = f[16]
    editora = f[17]
    edicao = f"{f[23]} " if f[23] else ""
    tipo = f[27]
    
    detalhes = ""
    if f[19]: detalhes += f"v. {f[19]}, "
    
    if tipo and "Artigo" in tipo:
        ref = f"{autor}. {titulo}{subtitulo}. **{editora}**, {local}, {detalhes}{ano}."
    else:
        ref = f"{autor}. **{titulo}**{subtitulo}. {edicao}{local}: {editora}, {ano}."
    return ref

# ========================================================
# 1. CADASTRAR OBRA
# ========================================================
if menu == "Cadastrar Obra":
    st.header("Nova Referência Bibliográfica")
    tipo = st.selectbox("Tipo", ["Livro / Monografia", "Artigo de Revista", "Tese", "Outro"])
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        tit = st.text_input("Título *")
        sub = st.text_input("Subtítulo")
        aut = st.text_input("Autor(es) *")
    with c2:
        ed = st.text_input("Edição")
        if "Artigo" in tipo: 
            vol, num, pag = st.text_input("Volume"), st.text_input("Número"), st.text_input("Páginas")
        else: 
            vol, num, pag = st.text_input("Volume"), st.text_input("Folhas"), st.text_input("Páginas Totais")
            
    c3, c4, c5 = st.columns(3)
    with c3: loc = st.text_input("Local *")
    with c4: edit = st.text_input("Revista/Editora *")
    with c5: yr = st.number_input("Ano *", 1000, 2030)
    
    nt = st.text_area("Notas")
    on = st.radio("Online?", ["Não", "Sim"], horizontal=True)
    url, dat = ("", "")
    if on == "Sim":
        url = st.text_input("URL")
        dat = st.text_input("Data Acesso")

    if st.button("Salvar no Google Sheets"):
        if tit and loc and edit and yr and aut:
            with st.spinner("Enviando..."):
                db.add_obra(tit, sub, aut, ed, loc, edit, yr, pag, vol, num, "", nt, 1 if on=="Sim" else 0, url, dat, tipo)
            st.success("Salvo com sucesso!")
        else: st.error("Preencha os campos obrigatórios (*).")

# ========================================================
# 2. IMPORTAR (LAZY LOADING)
# ========================================================
elif menu == "Importar":
    st.header("📥 Importar Referências")
    st.caption("Suporta arquivos .csv (do modelo), .ris e .bib")
    
    arq = st.file_uploader("Selecione o arquivo", type=['csv','ris','bib'])
    
    if arq and st.session_state.dados_preview is None:
        try:
            res = []
            # CSV
            if arq.name.endswith('.csv'):
                try: df = pd.read_csv(arq, sep=None, engine='python')
                except: arq.seek(0); df = pd.read_csv(arq, sep=';', encoding='utf-8-sig')
                df.columns = [normalizar_coluna(c) for c in df.columns]
                if 'titulo' in df.columns:
                    for _, r in df.iterrows():
                        res.append({'titulo': str(r.get('titulo','')), 'subtitulo': str(r.get('subtitulo','')), 'autor': str(r.get('autor','')), 'ano': int(re.search(r'\d{4}', str(r.get('ano',0))).group()) if re.search(r'\d{4}', str(r.get('ano',0))) else 0, 'local': str(r.get('local','S.l.')), 'editora': str(r.get('editora','S.n.')), 'edicao': str(r.get('edicao','')), 'tipo': str(r.get('tipo','Livro')), 'url': str(r.get('url','')), 'paginas': str(r.get('paginas',''))})
            
            # RIS (Lazy Import)
            elif arq.name.endswith('.ris'):
                import rispy
                for e in rispy.load(StringIO(arq.getvalue().decode("utf-8"))):
                    res.append({'titulo':e.get('primary_title',''), 'subtitulo':'', 'autor':"; ".join(e.get('authors',[])), 'ano':int(e.get('year',0)) if e.get('year') else 0, 'local':e.get('place_published','S.l.'), 'editora':e.get('publisher','S.n.'), 'edicao':'', 'tipo':'Artigo' if e.get('type_of_reference')=='JOUR' else 'Livro', 'url':e.get('url',''), 'paginas':''})
            
            # BIB (Lazy Import)
            elif arq.name.endswith('.bib'):
                import bibtexparser
                for e in bibtexparser.loads(arq.getvalue().decode("utf-8")).entries:
                    res.append({'titulo':e.get('title','').replace('{','').replace('}',''), 'subtitulo':'', 'autor':e.get('author','').replace('{','').replace('}',''), 'ano':int(e.get('year',0)) if e.get('year') else 0, 'local':e.get('address','S.l.').replace('{','').replace('}',''), 'editora':e.get('publisher','S.n.').replace('{','').replace('}',''), 'edicao':'', 'tipo':'Livro', 'url':'', 'paginas':''})
            
            if res: st.session_state.dados_preview = res; st.rerun()
        except Exception as e: st.error(f"Erro ao ler arquivo: {e}")

    if st.session_state.dados_preview:
        st.dataframe(pd.DataFrame(st.session_state.dados_preview))
        c1, c2 = st.columns(2)
        if c1.button("❌ Cancelar"): st.session_state.dados_preview = None; st.rerun()
        if c2.button("✅ Confirmar Importação"):
            with st.spinner("Salvando em Lote no Google Sheets..."):
                c=0
                for i in st.session_state.dados_preview:
                    on = 1 if len(i['url'])>5 else 0
                    db.add_obra(i['titulo'], i['subtitulo'], i['autor'], i['edicao'], i['local'], i['editora'], i['ano'], i['paginas'], "", "", "", "Importado", on, i['url'], "", i['tipo'])
                    c+=1
            st.success(f"{c} obras salvas!"); st.session_state.dados_preview = None

# ========================================================
# 3. FAZER FICHAMENTO
# ========================================================
elif menu == "Fazer Fichamento":
    st.header("Novo Fichamento")
    
    # Carrega obras (usando cache)
    obras = db.get_obras()
    
    # Cria dicionário { "Titulo - Autor (Ano)": ID }
    opts = {f"{o[1]} - {o[3]} ({o[4]})": o[0] for o in obras} if obras else {}
    
    if not opts: 
        st.warning("Nenhuma obra cadastrada. Vá em 'Cadastrar Obra' primeiro.")
    else:
        c1,c2,c3 = st.columns([3,1,2])
        # Selectbox retorna a Chave (Texto), usamos o dict para pegar o Valor (ID)
        texto_selecionado = c1.selectbox("Selecione a Obra", list(opts.keys()))
        oid = opts[texto_selecionado]
        
        pag = c2.text_input("Página da Citação")
        conc = c3.text_input("Conceito Chave")
        
        st.markdown("---")
        ic = st.text_area("1. Ideia Central")
        df_txt = st.text_area("2. Definição do Conceito")
        rl = st.text_area("3. Relação Bibliográfica")
        ct = st.text_area("4. Citação Direta")
        tg = st.text_input("Tags (separadas por vírgula)")
        
        if st.button("Salvar Ficha"):
            with st.spinner("Salvando ficha..."):
                db.add_ficha(oid, pag, conc, ic, df_txt, rl, ct, tg)
            st.success("Ficha salva!")

# ========================================================
# 4. VISUALIZAR E DOWNLOADS
# ========================================================
elif menu == "Visualizar Dados":
    st.header("Visualizar e Baixar")
    modo = st.radio("Modo de Visualização:", ["Fichamentos (Detalhado)", "Bibliografia Geral"], horizontal=True)
    termo = st.text_input("Pesquisar:")
    
    # --- MODO FICHAMENTOS ---
    if "Fichamentos" in modo:
        # Busca com Cache
        fichas = db.search_fichas(termo) if termo else db.get_fichas_completas()
        
        if fichas:
            # Preparar CSV Geral
            lista_export = []
            txt_ref = ""
            for f in fichas:
                ref = formatar_referencia_abnt_ficha(f)
                lista_export.append({
                    'ID': f[0], 'Obra': f[12], 'Conceito': f[3], 'Ideia': f[4], 
                    'Definição': f[5], 'Citação': f[7], 'Ref ABNT': ref.replace('**','')
                })
                txt_ref += ref.replace('**','') + "\n\n"
            
            # Botões de Download em Massa
            c_csv, c_txt = st.columns(2)
            c_csv.download_button("📊 Baixar Tabela Completa (CSV)", pd.DataFrame(lista_export).to_csv(index=False).encode('utf-8-sig'), 'fichas_completo.csv')
            c_txt.download_button("📜 Baixar Referências (TXT)", txt_ref, 'referencias.txt')
            
            st.markdown("---")
            st.write(f"**Total:** {len(fichas)} fichas encontradas.")
            
            # Listagem Individual
            for f in fichas:
                # Layout: Dados (85%) | Ações (15%)
                c_data, c_act = st.columns([0.85, 0.15])
                ref_vis = formatar_referencia_abnt_ficha(f)
                
                with c_data:
                    with st.expander(f"📄 {f[3]} | {f[12]}"):
                        st.markdown(f"**Ref:** {ref_vis}")
                        st.write(f"**Ideia Central:** {f[4]}")
                        if f[5]: st.write(f"**Definição:** {f[5]}")
                        st.info(f"**Citação:** \"{f[7]}\"")
                        st.caption(f"Tags: {f[8]}")
                
                with c_act:
                    # Botão PDF
                    try:
                        pdf_bytes = criar_pdf_fichamento(f, ref_vis)
                        st.download_button("📄 PDF", pdf_bytes, file_name=f"ficha_{f[0]}.pdf", mime='application/pdf', key=f"pdf_{f[0]}")
                    except Exception as e: 
                        st.error("Erro PDF")
                    
                    # Botão Excluir
                    if st.button("🗑️", key=f"del_{f[0]}", help="Excluir ficha"):
                        db.delete_ficha(f[0])
                        st.rerun()
        else:
            st.info("Nenhuma ficha encontrada.")
            
    # --- MODO BIBLIOGRAFIA ---
    else:
        obras = db.get_todas_obras_detalhadas(termo)
        if obras:
            cols = ['id', 'titulo', 'subtitulo', 'autor', 'ano', 'local', 'editora', 'paginas', 'volume', 'folhas', 'serie', 'notas', 'edicao', 'is_online', 'url', 'data_acesso', 'tipo']
            
            st.download_button("📊 Baixar Bibliografia (CSV)", pd.DataFrame(obras, columns=cols).to_csv(index=False).encode('utf-8-sig'), 'bibliografia.csv')
            
            st.markdown("---")
            for item in obras:
                ref = formatar_referencia_abnt_obra(item)
                st.markdown(f"**{item[1]}**: {ref}")
        else:
            st.info("Nenhuma obra encontrada.")
