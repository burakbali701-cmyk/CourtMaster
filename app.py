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
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(204, 255, 0, 0.2);
        padding: 20px; border-radius: 20px; color: white;
        text-align: center; margin-bottom: 15px;
    }
    .status-badge {
        padding: 5px 12px; border-radius: 20px; font-size: 0.8em; font-weight: bold;
    }
    .unpaid { background-color: #ff4b4b; color: white; }
    .paid { background-color: #ccff00; color: black; }
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
@st.cache_data(ttl=5)
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
    except: return pd.DataFrame(columns=columns)

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
with st.sidebar:
    st.markdown("<h1 style='color: #ccff00; text-align: center;'>Tennis App</h1>", unsafe_allow_html=True)
    with st.expander("🔒 Yönetici"):
        if st.text_input("Şifre", type="password") == ADMIN_SIFRE: st.session_state["admin"] = True
        else: st.session_state["admin"] = False
    IS_ADMIN = st.session_state.get("admin", False)
    menu = st.radio("MENÜ", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular", "💸 Kasa", "📝 Geçmiş"] if IS_ADMIN else ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular"])

df_main = get_data_cached("Ogrenci_Data", ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu", "Notlar"])

# --- 3. SPORCULAR (ÖDEME TAKİBİ DÜZELTİLDİ) ---
if menu == "👥 Sporcular":
    st.markdown("<h2 style='color: white;'>👥 Sporcu Yönetimi</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        t_list, t_new = st.tabs(["📋 Liste & Profil", "➕ Yeni Sporcu"])
        with t_list:
            # Liste Görünümü
            display_df = df_main.copy()
            st.dataframe(display_df[["Ad Soyad", "Kalan Ders", "Odeme Durumu", "Durum"]], use_container_width=True, hide_index=True)
            
            st.markdown("---")
            secilen = st.selectbox("Düzenlemek İçin Sporcu Seçin", ["Seçiniz..."] + list(df_main["Ad Soyad"].unique()))
            if secilen != "Seçiniz...":
                idx = df_main[df_main["Ad Soyad"] == secilen].index[0]
                status_color = "#ff4b4b" if df_main.at[idx, "Odeme Durumu"] == "Ödenmedi" else "#ccff00"
                st.markdown(f"<div style='border-left: 5px solid {status_color}; padding-left: 15px;'><h3>{secilen} - {df_main.at[idx, 'Odeme Durumu']}</h3></div>", unsafe_allow_html=True)
                
                with st.form(f"prof_{secilen}"):
                    c1, c2 = st.columns(2)
                    y_ders = c1.number_input("Kalan Ders", value=int(df_main.at[idx, "Kalan Ders"]))
                    y_odeme = c1.selectbox("Ödeme Durumu", ["Ödenmedi", "Ödendi"], index=0 if df_main.at[idx, "Odeme Durumu"]=="Ödenmedi" else 1)
                    y_tutar = c2.number_input("Eğer Ödeme Alındıysa Tutarı Girin", 0.0, step=100.0)
                    y_not = st.text_area("Özel Notlar", value=str(df_main.at[idx, "Notlar"]))
                    
                    if st.form_submit_button("KAYDET VE GÜNCELLE"):
                        df_main.at[idx, "Kalan Ders"] = y_ders
                        df_main.at[idx, "Odeme Durumu"] = y_odeme
                        df_main.at[idx, "Notlar"] = y_not
                        df_main.at[idx, "Durum"] = "Aktif" if y_ders > 0 else "Bitti"
                        save_data(df_main, "Ogrenci_Data")
                        if y_tutar > 0:
                            append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), secilen, y_tutar, "Paket/Ders Ücreti", "Gelir"], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"])
                        st.success("Veriler Google Sheets'e işlendi!"); st.rerun()

        with t_new:
            with st.form("new_player"):
                ad = st.text_input("Sporcu Ad Soyad")
                p = st.number_input("Ders Paketi", 10)
                ode = st.selectbox("Ödeme Durumu", ["Ödenmedi", "Ödendi"])
                tut = st.number_input("Alınan Ücret (0 ise kasa işlemez)", 0.0)
                if st.form_submit_button("SİSTEME EKLE"):
                    new_r = {"Ad Soyad": ad, "Paket (Ders)": p, "Kalan Ders": p, "Son Islem": "-", "Durum": "Aktif", "Odeme Durumu": ode, "Notlar": "-"}
                    df_main = pd.concat([df_main, pd.DataFrame([new_r])], ignore_index=True)
                    save_data(df_main, "Ogrenci_Data")
                    if tut > 0:
                        append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), ad, tut, "Yeni Kayıt", "Gelir"], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"])
                    st.success("Sporcu başarıyla eklendi!"); st.rerun()
    else:
        st.dataframe(df_main[["Ad Soyad", "Kalan Ders", "Odeme Durumu"]], use_container_width=True, hide_index=True)

# --- 4. KASA (GRAFİKLER ONARILDI) ---
elif menu == "💸 Kasa":
    st.markdown("<h2 style='color: white;'>💸 Kasa & Hasılat Yönetimi</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        df_f = get_data_cached("Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"])
        if "Tip" not in df_f.columns: df_f["Tip"] = "Gelir"
        
        with st.expander("➕ Manuel İşlem (Gelir/Gider)"):
            with st.form("manuel_kasa"):
                c1, c2 = st.columns(2)
                m_tut = c1.number_input("Tutar (TL)", 0.0)
                m_tip = c1.selectbox("İşlem Tipi", ["Gelir", "Gider"])
                m_not = c2.text_input("Açıklama")
                if st.form_submit_button("İŞLE"):
                    append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), "Genel", m_tut, m_not, m_tip], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"])
                    st.rerun()

        if not df_f.empty:
            gelir = df_f[df_f["Tip"] == "Gelir"]["Tutar"].sum()
            gider = df_f[df_f["Tip"] == "Gider"]["Tutar"].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("TOPLAM GELİR", f"{gelir:,.0f} TL")
            col2.metric("TOPLAM GİDER", f"{gider:,.0f} TL", delta_color="inverse")
            col3.metric("NET KASA", f"{gelir - gider:,.0f} TL")
            
            st.markdown("---")
            g1, g2 = st.columns(2)
            # Grafik 1: Aylık Gelir
            ay_data = df_f[df_f["Tip"]=="Gelir"].groupby("Ay")["Tutar"].sum().reset_index()
            fig_bar = px.bar(ay_data, x="Ay", y="Tutar", title="Aylık Gelir Akışı", color_discrete_sequence=['#ccff00'])
            g1.plotly_chart(fig_bar, use_container_width=True)
            
            # Grafik 2: Dağılım (Pasta)
            pie_data = df_f[df_f["Tip"]=="Gelir"].groupby("Ogrenci")["Tutar"].sum().reset_index()
            fig_pie = px.pie(pie_data, values="Tutar", names="Ogrenci", title="Gelir Kaynakları (%)", hole=0.4, color_discrete_sequence=px.colors.sequential.Greens_r)
            g2.plotly_chart(fig_pie, use_container_width=True)
            
            st.dataframe(df_f.sort_index(ascending=False), use_container_width=True)

# --- DİĞER MENÜLER (KISA) ---
elif menu == "🏠 Kort Paneli":
    st.markdown("<h2 style='color: white;'>🎾 Kort Paneli</h2>", unsafe_allow_html=True)
    aktif = df_main[df_main["Durum"]=="Aktif"]
    if not aktif.empty:
        sec = st.selectbox("Sporcu", aktif["Ad Soyad"].unique())
        idx = df_main[df_main["Ad Soyad"]==sec].index[0]
        kalan = int(df_main.at[idx, "Kalan Ders"])
        st.markdown(f"<div class='player-card'><h1 style='color:#ccff00;'>{sec}</h1><h3>{kalan} DERS KALDI</h3></div>", unsafe_allow_html=True)
        if IS_ADMIN and st.button("DERSİ İŞLE (-1)"):
            if kalan > 0:
                df_main.at[idx, "Kalan Ders"] -= 1
                save_data(df_main, "Ogrenci_Data")
                append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "Ders Düşüldü", "-", "Hizmet"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                st.rerun()
elif menu == "📅 Çizelge":
    df_prog = get_data_cached("Ders_Programi", ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"])
    if IS_ADMIN:
        ed = st.data_editor(df_prog, use_container_width=True, hide_index=True)
        if not df_prog.equals(ed): save_data(ed, "Ders_Programi")
    else: st.dataframe(df_prog, use_container_width=True, hide_index=True)
elif menu == "📝 Geçmiş":
    st.dataframe(get_data_cached("Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"]).sort_index(ascending=False), use_container_width=True)
