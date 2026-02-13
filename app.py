import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime
import time

# --- AYARLAR & TASARIM (TENİS TEMALI) ---
st.set_page_config(page_title="Tennis App", page_icon="🎾", layout="wide")

# Tenis topu sarısı: #ccff00 | Kort yeşili: #1a472a | Koyu Kort: #0b1a10
st.markdown("""
    <style>
    .main {background-color: #0b140f;}
    .stApp {background-image: linear-gradient(180deg, #0b140f 0%, #1a2e23 100%);}
    
    /* Buton Tasarımları */
    .stButton>button {
        width: 100%; border-radius: 12px; height: 3.5em; 
        font-weight: bold; background-color: #ccff00; color: #000;
        border: none; transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #e6ff80; transform: scale(1.02);
    }
    
    /* Oyuncu Kartı */
    .player-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(204, 255, 0, 0.2);
        padding: 20px; border-radius: 20px; color: white;
        text-align: center; margin-bottom: 15px;
    }
    
    /* Enerji Barı */
    .progress-container {
        width: 100%; background-color: #222;
        border-radius: 20px; margin: 15px 0; overflow: hidden;
        border: 1px solid #444;
    }
    .progress-bar {
        height: 25px; line-height: 25px; color: #000;
        text-align: center; font-weight: 900; transition: width 0.8s ease;
    }
    
    /* Yan Menü */
    [data-testid="stSidebar"] {background-color: #080f0b; border-right: 1px solid #ccff0033;}
    .stRadio>label {color: #ccff00 !important; font-weight: bold;}
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
@st.cache_data(ttl=10)
def get_data_cached(worksheet_name, columns):
    try:
        sheet = baglanti_kur()
        ws = sheet.worksheet(worksheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: df = pd.DataFrame(columns=columns)
        else:
            for col in columns:
                if col not in df.columns: df[col] = "-"
            if "Tutar" in df.columns: df["Tutar"] = pd.to_numeric(df["Tutar"], errors='coerce').fillna(0)
            if "Kalan Ders" in df.columns: df["Kalan Ders"] = pd.to_numeric(df["Kalan Ders"], errors='coerce').fillna(0)
        return df
    except Exception as e: return pd.DataFrame(columns=columns)

def save_data(df, worksheet_name):
    sheet = baglanti_kur(); ws = sheet.worksheet(worksheet_name)
    ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist())
    st.cache_data.clear()

def append_data(row_data, worksheet_name, columns):
    sheet = baglanti_kur()
    try: ws = sheet.worksheet(worksheet_name)
    except: ws = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=20); ws.append_row(columns)
    ws.append_row(row_data); st.cache_data.clear()

# --- ARAYÜZ ---
# Sidebar Tasarımı
with st.sidebar:
    st.markdown("<h1 style='color: #ccff00; text-align: center;'>TENNIS APP</h1>", unsafe_allow_html=True)
    st.image("https://cdn-icons-png.flaticon.com/512/2906/2906260.png", width=100)
    st.markdown("---")
    
    with st.expander("🔐 Hocaya Özel"):
        if st.text_input("Şifre", type="password") == ADMIN_SIFRE:
            st.session_state["admin"] = True
            st.success("Admin Aktif")
        else: st.session_state["admin"] = False
    
    IS_ADMIN = st.session_state.get("admin", False)
    menu = st.radio("ANA MENÜ", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular", "💸 Kasa"])
    if IS_ADMIN: menu = st.radio("YÖNETİM", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular", "💸 Kasa", "📝 Geçmiş"], index=menu_opts.index(menu) if 'menu_opts' in locals() else 0)

# Verileri Çek
df_main = get_data_cached("Ogrenci_Data", ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu"])

# --- 1. KORT PANELİ (YOKLAMA) ---
if menu == "🏠 Kort Paneli":
    st.markdown("<h2 style='color: white;'>🎾 Kortta Kim Var?</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns([2,1])
    
    with c1:
        aktif = df_main[df_main["Durum"]=="Aktif"]
        if not aktif.empty:
            sec = st.selectbox("Sporcu Seçiniz", aktif["Ad Soyad"].unique())
            idx = df_main[df_main["Ad Soyad"]==sec].index[0]
            kalan = int(df_main.at[idx, "Kalan Ders"])
            durum = df_main.at[idx, "Odeme Durumu"]
            
            # Renk skalası
            bar_color = "#ccff00" if kalan > 5 else ("#ffa500" if kalan > 2 else "#ff4b4b")
            width = min((kalan / 15) * 100, 100) # 15 dersi %100 kabul et
            
            st.markdown(f"""
            <div class="player-card">
                <p style="margin:0; font-size:1.2em; opacity:0.8;">SPORCU</p>
                <h1 style="margin:0; color:#ccff00; font-size:3em;">{sec}</h1>
                <div class="progress-container">
                    <div class="progress-bar" style="width: {width}%; background-color: {bar_color};">
                        {kalan} DERS
                    </div>
                </div>
                <p style="color:{bar_color}; font-weight:bold;">Ödeme: {durum}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if IS_ADMIN:
                col_a, col_b = st.columns(2)
                if col_a.button("🎾 DERS TAMAMLANDI", type="primary"):
                    if kalan > 0:
                        df_main.at[idx, "Kalan Ders"] -= 1
                        df_main.at[idx, "Son Islem"] = datetime.now().strftime("%d-%m %H:%M")
                        if df_main.at[idx, "Kalan Ders"] == 0: df_main.at[idx, "Durum"] = "Bitti"
                        save_data(df_main, "Ogrenci_Data")
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "DERS İŞLENDİ", f"Kalan: {kalan-1}"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                        st.balloons(); st.rerun()
                if col_b.button("↩️ HATA DÜZELT (+1)"):
                    df_main.at[idx, "Kalan Ders"] += 1
                    save_data(df_main, "Ogrenci_Data"); st.rerun()
        else: st.info("Kortta şu an kimse yok.")

    with c2:
        st.markdown("<h4 style='color:white;'>📝 Son Kort Girişleri</h4>", unsafe_allow_html=True)
        log_data = get_data_cached("Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
        st.dataframe(log_data.tail(7).iloc[::-1], use_container_width=True, hide_index=True)

# --- 2. ÇİZELGE ---
elif menu == "📅 Çizelge":
    st.markdown("<h2 style='color: white;'>📅 Haftalık Antrenman Programı</h2>", unsafe_allow_html=True)
    df_prog = get_data_cached("Ders_Programi", ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"])
    if IS_ADMIN:
        edited = st.data_editor(df_prog, num_rows="fixed", use_container_width=True, height=600, hide_index=True)
        if not df_prog.equals(edited): save_data(edited, "Ders_Programi"); st.toast("Program Güncellendi!")
    else:
        st.dataframe(df_prog.style.highlight_null(color='transparent'), use_container_width=True, height=600, hide_index=True)

# --- 3. SPORCULAR ---
elif menu == "👥 Sporcular":
    if IS_ADMIN:
        t1, t2 = st.tabs(["🎾 Paket Güncelle", "➕ Yeni Sporcu"])
        with t1:
            with st.form("yenile"):
                s = st.selectbox("Sporcu Seç", df_main["Ad Soyad"].unique())
                e = st.number_input("Eklenen Ders", 0, step=1)
                t = st.checkbox("Ödeme Alındı")
                f = st.number_input("Tutar", 0.0)
                if st.form_submit_button("GÜNCELLE"):
                    idx = df_main[df_main["Ad Soyad"]==s].index[0]
                    df_main.at[idx, "Kalan Ders"] += e
                    if t: 
                        df_main.at[idx, "Odeme Durumu"] = "Ödendi"
                        append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), s, f, "Paket"], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
                    save_data(df_main, "Ogrenci_Data"); st.success("Güncellendi")
        with t2:
            with st.form("yeni"):
                ad = st.text_input("Sporcu Ad Soyad")
                p = st.number_input("Başlangıç Paket", 10)
                if st.form_submit_button("KAYDET"):
                    new_row = {"Ad Soyad": ad, "Paket (Ders)": p, "Kalan Ders": p, "Son Islem": "-", "Durum": "Aktif", "Odeme Durumu": "Ödenmedi"}
                    df_main = pd.concat([df_main, pd.DataFrame([new_row])], ignore_index=True)
                    save_data(df_main, "Ogrenci_Data"); st.success("Sporcu Eklendi")
    else:
        st.dataframe(df_main[["Ad Soyad", "Kalan Ders", "Odeme Durumu"]], use_container_width=True)

# --- 4. KASA ---
elif menu == "💸 Kasa":
    if IS_ADMIN:
        df_f = get_data_cached("Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
        ay = datetime.now().strftime("%Y-%m")
        st.columns(2)[0].metric("BU AYIN HASILATI", f"{df_f[df_f['Ay']==ay]['Tutar'].sum():,.0f} TL")
        st.plotly_chart(px.bar(df_f.groupby("Ay")["Tutar"].sum().reset_index(), x="Ay", y="Tutar", color_discrete_sequence=['#ccff00']))
    else: st.error("Bu alan antrenörlere özeldir.")

elif menu == "📝 Geçmiş":
    loglar = get_data_cached("Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
    kisi = st.selectbox("Sporcuya Göre Bak", ["Tümü"] + list(df_main["Ad Soyad"].unique()))
    if kisi != "Tümü": loglar = loglar[loglar["Ogrenci"]==kisi]
    st.dataframe(loglar.sort_index(ascending=False), use_container_width=True)
