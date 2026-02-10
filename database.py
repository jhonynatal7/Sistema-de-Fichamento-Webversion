import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st

# Configuração de Escopo
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Função para conectar ao Google Sheets
@st.cache_resource
def get_connection():
    # Tenta pegar dos segredos do Streamlit
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        # Tenta abrir a planilha
        sheet = client.open("Fichamento_DB") 
        return sheet
    except Exception as e:
        st.error(f"Erro ao conectar na planilha. Verifique se compartilhou com o email do serviço e se o nome é 'Fichamento_DB'. Detalhe: {e}")
        return None

# --- ID HELPERS ---
def get_next_id(worksheet):
    col_values = worksheet.col_values(1) # Coluna A é ID
    if len(col_values) <= 1: return 1
    # Pega o último valor e soma 1 (tenta converter para int)
    try:
        last_val = int(col_values[-1])
        return last_val + 1
    except:
        return len(col_values) + 1

# --- CREATE ---
def add_obra(titulo, subtitulo, autor, edicao, local, editora, ano, 
             paginas, volume, folhas, serie, notas, is_online, url, data_acesso, tipo):
    sh = get_connection()
    if not sh: return
    wk = sh.worksheet("obras")
    new_id = get_next_id(wk)
    
    # Ordem das colunas: id, titulo, subtitulo, autor, edicao, local, editora, ano, paginas, volume, folhas, serie, notas, is_online, url, data_acesso, tipo
    row = [new_id, titulo, subtitulo, autor, edicao, local, editora, ano, 
           paginas, volume, folhas, serie, notas, is_online, url, data_acesso, tipo]
    wk.append_row(row)

def add_ficha(obra_id, pagina, conceito, ideia_central, definicao, relacao, citacoes, tags):
    sh = get_connection()
    if not sh: return
    wk = sh.worksheet("fichas")
    new_id = get_next_id(wk)
    
    # Ordem: id, obra_id, pagina, conceito, ideia_central, definicao_conceito, relacao_biblio, citacoes, tags
    row = [new_id, obra_id, pagina, conceito, ideia_central, definicao, relacao, citacoes, tags]
    wk.append_row(row)

# --- READ ---
def get_obras():
    sh = get_connection()
    if not sh: return []
    wk = sh.worksheet("obras")
    data = wk.get_all_records()
    # Retorna lista de tuplas para o dropdown: (id, titulo, subtitulo, autor, ano)
    return [(d['id'], d['titulo'], d['subtitulo'], d['autor'], d['ano']) for d in data]

def get_todas_obras_detalhadas(termo=""):
    sh = get_connection()
    if not sh: return []
    wk = sh.worksheet("obras")
    data = wk.get_all_records()
    df = pd.DataFrame(data)
    
    if df.empty: return []
    
    # Converter tudo para string para evitar erros de busca
    df = df.astype(str)
    
    if termo:
        mask = df.apply(lambda x: x.str.contains(termo, case=False)).any(axis=1)
        df = df[mask]
        
    # Ordenar colunas para garantir consistência com o app
    cols_order = ['id', 'titulo', 'subtitulo', 'autor', 'ano', 'local', 'editora', 
                  'paginas', 'volume', 'folhas', 'serie', 'notas', 'edicao', 
                  'is_online', 'url', 'data_acesso', 'tipo']
    
    # Garante que colunas existam
    for c in cols_order:
        if c not in df.columns: df[c] = ""
            
    return df[cols_order].values.tolist()

def get_fichas_completas():
    sh = get_connection()
    if not sh: return []
    
    try:
        data_fichas = sh.worksheet("fichas").get_all_records()
        data_obras = sh.worksheet("obras").get_all_records()
    except:
        return []

    df_fichas = pd.DataFrame(data_fichas)
    df_obras = pd.DataFrame(data_obras)
    
    if df_fichas.empty: return []
    if df_obras.empty: return []

    # Converter IDs para string para garantir o merge correto
    df_fichas['obra_id'] = df_fichas['obra_id'].astype(str)
    df_obras['id'] = df_obras['id'].astype(str)

    # Renomear ID da obra
    df_obras = df_obras.rename(columns={'id': 'obra_id_ref'})
    
    # JOIN
    full_df = pd.merge(df_fichas, df_obras, left_on='obra_id', right_on='obra_id_ref', how='inner')
    
    lista_final = []
    for _, row in full_df.iterrows():
        # Monta a lista gigante que o app.py espera (Ficha + Obra)
        ficha_part = [
            row.get('id', ''), row.get('obra_id', ''), row.get('pagina', ''), row.get('conceito', ''),
            row.get('ideia_central', ''), row.get('definicao_conceito', ''), row.get('relacao_biblio', ''),
            row.get('citacoes', ''), row.get('tags', ''), None, None # None, None são placeholders de PDF antigo
        ]
        obra_part = [
            row.get('obra_id_ref', ''), row.get('titulo', ''), row.get('subtitulo', ''), row.get('autor', ''),
            row.get('ano', ''), row.get('local', ''), row.get('editora', ''), row.get('paginas', ''),
            row.get('volume', ''), row.get('folhas', ''), row.get('serie', ''), row.get('notas', ''),
            row.get('edicao', ''), row.get('is_online', ''), row.get('url', ''), row.get('data_acesso', ''),
            row.get('tipo', '')
        ]
        lista_final.append(ficha_part + obra_part)
        
    return lista_final

def search_fichas(termo):
    todos = get_fichas_completas()
    resultado = []
    t = str(termo).lower()
    for item in todos:
        # Busca em conceito, citação, tags, titulo da obra
        texto = f"{item[3]} {item[7]} {item[8]} {item[12]}".lower()
        if t in texto:
            resultado.append(item)
    return resultado

def delete_ficha(ficha_id):
    sh = get_connection()
    if not sh: return
    wk = sh.worksheet("fichas")
    try:
        cell = wk.find(str(ficha_id), in_column=1)
        if cell: wk.delete_rows(cell.row)
    except: pass

# Setup inicial (cria cabeçalhos se vazio)
def init_db():
    sh = get_connection()
    if not sh: return

    # Obras
    try: wk_o = sh.worksheet("obras")
    except: wk_o = sh.add_worksheet("obras", 1000, 20)
    if not wk_o.row_values(1):
        wk_o.append_row(['id', 'titulo', 'subtitulo', 'autor', 'edicao', 'local', 'editora', 'ano', 
                         'paginas', 'volume', 'folhas', 'serie', 'notas', 'is_online', 'url', 'data_acesso', 'tipo'])
        
    # Fichas
    try: wk_f = sh.worksheet("fichas")
    except: wk_f = sh.add_worksheet("fichas", 1000, 20)
    if not wk_f.row_values(1):
        wk_f.append_row(['id', 'obra_id', 'pagina', 'conceito', 'ideia_central', 'definicao_conceito', 
                         'relacao_biblio', 'citacoes', 'tags'])