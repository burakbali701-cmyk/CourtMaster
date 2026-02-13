import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime
import time

# --- AYARLAR & TASARIM ---
st.set_page_config(page_title="Tennis App", page_icon="🎾", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0b140f;}
    .stApp {background-image: linear-gradient(180deg, #0b140f 0%, #1a2e23 100%);}
    .stButton>button {
        width: 100%; border-radius: 12px; height: 3.5em; 
        font-weight: bold; background-color: #ccff00; color: #000;
        border: none; transition: 0.3s;
    }
    .stButton>button:hover {background-color: #e6ff80; transform: scale(1.02);}
    .player-card {
        background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(204, 255, 0, 0.2);
        padding: 20px; border-radius: 20px; color: white; text-align: center; margin-bottom: 15px;
    }
    .progress-container {
        width: 100%; background-color: #222; border-radius: 20px; margin: 15px 0; overflow: hidden;
    }
    .progress-bar { height: 25px; line-height: 25px; color: #000; text-align: center; font-weight: 900; }
    [data-testid="stSidebar"] {background-color: #080f0b; border-right: 1px solid #ccff0033;}
    /* Metrik Kartlar */
    [data-testid="stMetricValue"] {font-size: 2rem !important; color: #ccff00 !important;}
    [data-testid="stMetricLabel"] {color: white !important;}
    </style>
    """, unsafe_allow_html=True)

# --- YÖNETİCİ ŞİFRESİ ---
ADMIN_SIFRE = "1234"

# --- GOOGLE SHEETS BAĞLANTISI ---
@st.cache_resource
def baglanti_kur():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict: creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name('secrets.json', scope)
    client = gspread.authorize(creds)
    return client.open("CourtMaster_DB")

# --- VERİ FONKSİYONLARI ---
def get_worksheet(sheet_obj, name, columns):
    try: return sheet_obj.worksheet(name)
    except gspread.WorksheetNotFound:
        new_ws = sheet_obj.add_worksheet(title=name, rows="1000", cols="20")
        new_ws.append_row(columns)
        return new_ws

@st.cache_data(ttl=5)
def get_data_cached(worksheet_name, columns):
    try:
        sheet = baglanti_kur()
        ws = get_worksheet(sheet, worksheet_name, columns)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: df = pd.DataFrame(columns=columns)
        else:
            for col in columns:
                if col not in df.columns: df[col] = "-"
            if "Tutar" in df.columns: df["Tutar"] = pd.to_numeric(df["Tutar"], errors='coerce').fillna(0)
            if "Kalan Ders" in df.columns: df["Kalan Ders"] = pd.to_numeric(df["Kalan Ders"], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame(columns=columns)

def save_data(df, worksheet_name, columns):
    sheet = baglanti_kur()
    ws = get_worksheet(sheet, worksheet_name, columns)
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())
    st.cache_data.clear()

def append_data(row_data, worksheet_name, columns):
    sheet = baglanti_kur()
    ws = get_worksheet(sheet, worksheet_name, columns)
    ws.append_row(row_data)
    st.cache_data.clear()

# --- ARAYÜZ ---
with st.sidebar:
    st.markdown("<h1 style='color: #ccff00; text-align: center;'>Tennis App</h1>", unsafe_allow_html=True)
    with st.expander("🔐 Yönetici Paneli"):
        if st.text_input("Şifre", type="password") == ADMIN_SIFRE: st.session_state["admin"] = True
        else: st.session_state["admin"] = False
    IS_ADMIN = st.session_state.get("admin", False)
    menu = st.radio("MENÜ", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular", "💸 Kasa", "📝 Geçmiş"] if IS_ADMIN else ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular"])

# --- TABLO YAPILARI ---
COL_OGRENCI = ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu", "Notlar"]
COL_FINANS = ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"]
COL_LOG = ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"]
COL_PROG = ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Ana Verileri Çek
df_main = get_data_cached("Ogrenci_Data", COL_OGRENCI)
df_finans = get_data_cached("Finans_Kasa", COL_FINANS)

# --- 1. KORT PANELİ ---
if menu == "🏠 Kort Paneli":
    st.markdown("<h2 style='color: white;'>🎾 Kort Paneli</h2>", unsafe_allow_html=True)
    aktif = df_main[df_main["Durum"]=="Aktif"]
    if not aktif.empty:
        sec = st.selectbox("İşlem Yapılacak Sporcu", aktif["Ad Soyad"].unique())
        idx = df_main[df_main["Ad Soyad"]==sec].index[0]
        kalan = int(df_main.at[idx, "Kalan Ders"])
        bar_color = "#ccff00" if kalan > 5 else ("#ffa500" if kalan > 2 else "#ff4b4b")
        width = min((kalan / 15) * 100, 100)
        st.markdown(f"""<div class="player-card"><h1 style="color:#ccff00;">{sec}</h1><div class="progress-container"><div class="progress-bar" style="width: {width}%; background-color: {bar_color};"></div></div><h3>{kalan} DERS KALDI</h3></div>""", unsafe_allow_html=True)
        if IS_ADMIN and st.button("🎾 DERSİ İŞLE (-1)", type="primary"):
            if kalan > 0:
                df_main.at[idx, "Kalan Ders"] -= 1
                df_main.at[idx, "Son Islem"] = datetime.now().strftime("%d-%m %H:%M")
                if df_main.at[idx, "Kalan Ders"] == 0: df_main.at[idx, "Durum"] = "Bitti"
                save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "DERS İŞLENDİ", f"Kalan: {kalan-1}"], "Ders_Gecmisi", COL_LOG)
                st.rerun()
    else: st.info("Sporcu kaydı bulunamadı.")

# --- 2. SPORCULAR (DÜZELTİLDİ: CANLI DURUM GÖSTERGESİ) ---
elif menu == "👥 Sporcular":
    st.markdown("<h2 style='color: white;'>👥 Sporcu Yönetimi</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        t1, t2 = st.tabs(["📋 Profil & Güncelle", "➕ Yeni Sporcu"])
        with t1:
            secilen = st.selectbox("Sporcu Seç", ["Seçiniz..."] + list(df_main["Ad Soyad"].unique()))
            if secilen != "Seçiniz...":
                idx = df_main[df_main["Ad Soyad"] == secilen].index[0]
                
                # --- CANLI DURUM KARTI (YENİ EKLENDİ) ---
                # Toplam ödeme hesapla
                toplam_odeme = df_finans[(df_finans["Ogrenci"] == secilen) & (df_finans["Tip"] == "Gelir")]["Tutar"].sum()
                
                st.markdown(f"#### 📊 {secilen} - Mevcut Durum")
                col_info1, col_info2, col_info3 = st.columns(3)
                col_info1.metric("Kalan Ders", int(df_main.at[idx, "Kalan Ders"]))
                col_info2.metric("Ödeme Durumu", df_main.at[idx, "Odeme Durumu"])
                col_info3.metric("Toplam Ödediği", f"{toplam_odeme:,.0f} TL")
                st.markdown("---")
                
                # --- GÜNCELLEME FORMU ---
                st.markdown("#### ✏️ Bilgileri Güncelle")
                with st.form(f"prof_{secilen}"):
                    c1, c2 = st.columns(2)
                    y_ders = c1.number_input("Yeni Ders Sayısı (Üstüne Eklemez, Günceller)", value=int(df_main.at[idx, "Kalan Ders"]))
                    y_odeme = c1.selectbox("Ödeme Durumu", ["Ödenmedi", "Ödendi"], index=0 if df_main.at[idx, "Odeme Durumu"]=="Ödenmedi" else 1)
                    y_tut = c2.number_input("Şu An Tahsilat Yapıldıysa Tutar Girin (TL)", 0.0)
                    y_not = st.text_area("Notlar", value=str(df_main.at[idx, "Notlar"]))
                    
                    if st.form_submit_button("KAYDET VE GÜNCELLE"):
                        df_main.at[idx, "Kalan Ders"] = y_ders
                        df_main.at[idx, "Odeme Durumu"] = y_odeme
                        df_main.at[idx, "Notlar"] = y_not
                        df_main.at[idx, "Durum"] = "Aktif" if y_ders > 0 else "Bitti"
                        save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                        
                        if y_tut > 0:
                            append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), secilen, y_tut, "Paket/Ders Satışı", "Gelir"], "Finans_Kasa", COL_FINANS)
                        
                        st.success("Bilgiler güncellendi!")
                        time.sleep(1)
                        st.rerun()

        with t2:
            with st.form("new"):
                ad = st.text_input("Ad Soyad")
                p = st.number_input("Paket", 10)
                if st.form_submit_button("EKLE"):
                    new_r = {"Ad Soyad": ad, "Paket (Ders)": p, "Kalan Ders": p, "Son Islem": "-", "Durum": "Aktif", "Odeme Durumu": "Ödenmedi", "Notlar": "-"}
                    df_main = pd.concat([df_main, pd.DataFrame([new_r])], ignore_index=True)
                    save_data(df_main, "Ogrenci_Data", COL_OGRENCI); st.rerun()
    else: st.dataframe(df_main[["Ad Soyad", "Kalan Ders", "Odeme Durumu"]], use_container_width=True)

# --- 3. KASA ---
elif menu == "💸 Kasa":
    st.markdown("<h2 style='color: white;'>💸 Kasa</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        with st.expander("➕ Gelir/Gider Ekle"):
            with st.form("kasa"):
                c1, c2 = st.columns(2)
                tutar = c1.number_input("Tutar", 0.0)
                tip = c1.selectbox("Tip", ["Gelir", "Gider"])
                not_ = c2.text_input("Açıklama")
                if st.form_submit_button("KAYDET"):
                    append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), "Genel", tutar, not_, tip], "Finans_Kasa", COL_FINANS); st.rerun()
        
        if not df_finans.empty:
            gelir = df_finans[df_finans["Tip"]=="Gelir"]["Tutar"].sum()
            gider = df_finans[df_finans["Tip"]=="Gider"]["Tutar"].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("GELİR", f"{gelir:,.0f} TL")
            col2.metric("GİDER", f"{gider:,.0f} TL")
            col3.metric("NET", f"{gelir-gider:,.0f} TL")
            
            g_col1, g_col2 = st.columns(2)
            g_col1.plotly_chart(px.bar(df_finans[df_finans["Tip"]=="Gelir"].groupby("Ay")["Tutar"].sum().reset_index(), x="Ay", y="Tutar", title="Aylık Gelir", color_discrete_sequence=['#ccff00']), use_container_width=True)
            g_col2.plotly_chart(px.pie(df_finans[df_finans["Tip"]=="Gelir"].groupby("Ogrenci")["Tutar"].sum().reset_index(), values="Tutar", names="Ogrenci", title="Gelir Dağılımı"), use_container_width=True)
            st.dataframe(df_finans.sort_index(ascending=False), use_container_width=True)

# --- 4. PROGRAM & GEÇMİŞ ---
elif menu == "📅 Çizelge":
    df_prog = get_data_cached("Ders_Programi", COL_PROG)
    if IS_ADMIN:
        ed = st.data_editor(df_prog, use_container_width=True, hide_index=True)
        if not df_prog.equals(ed): save_data(ed, "Ders_Programi", COL_PROG)
    else: st.dataframe(df_prog, use_container_width=True)

elif menu == "📝 Geçmiş":
    st.dataframe(get_data_cached("Ders_Gecmisi", COL_LOG).sort_index(ascending=False), use_container_width=True)
