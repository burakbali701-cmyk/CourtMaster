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
    .profile-box {
        background: rgba(204, 255, 0, 0.05);
        padding: 25px; border-radius: 15px; border: 1px solid #ccff00;
        margin-top: 20px;
    }
    .progress-container {
        width: 100%; background-color: #222;
        border-radius: 20px; margin: 10px 0; overflow: hidden;
    }
    .progress-bar {
        height: 15px; line-height: 15px; transition: width 0.8s ease;
    }
    [data-testid="stSidebar"] {background-color: #080f0b; border-right: 1px solid #ccff0033;}
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
    st.markdown("<h1 style='color: #ccff00; text-align: center;'>TENNIS APP</h1>", unsafe_allow_html=True)
    st.image("https://cdn-icons-png.flaticon.com/512/2906/2906260.png", width=100)
    st.markdown("---")
    with st.expander("🔐 Hoca Girişi"):
        if st.text_input("Şifre", type="password") == ADMIN_SIFRE:
            st.session_state["admin"] = True
            st.success("Admin Aktif")
        else: st.session_state["admin"] = False
    
    IS_ADMIN = st.session_state.get("admin", False)
    menu = st.radio("MENÜ", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular", "💸 Kasa", "📝 Geçmiş"] if IS_ADMIN else ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular"])

df_main = get_data_cached("Ogrenci_Data", ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu", "Notlar"])

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
        if IS_ADMIN:
            if st.button("🎾 DERSİ İŞLE (-1)", type="primary"):
                if kalan > 0:
                    df_main.at[idx, "Kalan Ders"] -= 1
                    df_main.at[idx, "Son Islem"] = datetime.now().strftime("%d-%m %H:%M")
                    if df_main.at[idx, "Kalan Ders"] == 0: df_main.at[idx, "Durum"] = "Bitti"
                    save_data(df_main, "Ogrenci_Data")
                    append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "DERS İŞLENDİ", f"Kalan: {kalan-1}"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                    st.balloons(); st.rerun()
    else: st.info("Şu an aktif sporcu kaydı yok.")

# --- 2. ÇİZELGE ---
elif menu == "📅 Çizelge":
    st.markdown("<h2 style='color: white;'>📅 Haftalık Program</h2>", unsafe_allow_html=True)
    df_prog = get_data_cached("Ders_Programi", ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"])
    if IS_ADMIN:
        edited = st.data_editor(df_prog, num_rows="fixed", use_container_width=True, height=600, hide_index=True)
        if not df_prog.equals(edited): save_data(edited, "Ders_Programi"); st.toast("Kaydedildi!")
    else: st.dataframe(df_prog, use_container_width=True, height=600, hide_index=True)

# --- 3. SPORCULAR ---
elif menu == "👥 Sporcular":
    st.markdown("<h2 style='color: white;'>👥 Sporcu Veritabanı</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        t_list, t_new = st.tabs(["📋 Liste & Profil", "➕ Yeni Sporcu"])
        with t_list:
            search = st.text_input("🔍 Sporcu Ara", "")
            filtered = df_main[df_main["Ad Soyad"].str.contains(search, case=False)] if search else df_main
            st.dataframe(filtered[["Ad Soyad", "Kalan Ders", "Odeme Durumu"]], use_container_width=True, hide_index=True)
            st.markdown("---")
            secilen = st.selectbox("Düzenlemek İçin Seçin", ["Seçiniz..."] + list(filtered["Ad Soyad"].unique()))
            if secilen != "Seçiniz...":
                idx = df_main[df_main["Ad Soyad"] == secilen].index[0]
                with st.form(f"profile_{secilen}"):
                    c1, c2 = st.columns(2)
                    y_ders = c1.number_input("Kalan Ders", value=int(df_main.at[idx, "Kalan Ders"]))
                    y_odeme = c1.selectbox("Durum", ["Ödendi", "Ödenmedi"], index=0 if df_main.at[idx, "Odeme Durumu"]=="Ödendi" else 1)
                    y_not = st.text_area("Notlar", value=str(df_main.at[idx, "Notlar"]))
                    if st.form_submit_button("PROFİLİ GÜNCELLE"):
                        df_main.at[idx, "Kalan Ders"] = y_ders
                        df_main.at[idx, "Odeme Durumu"] = y_odeme
                        df_main.at[idx, "Notlar"] = y_not
                        df_main.at[idx, "Durum"] = "Aktif" if y_ders > 0 else "Bitti"
                        save_data(df_main, "Ogrenci_Data")
                        st.success("Güncellendi!"); st.rerun()
        with t_new:
            with st.form("new_player"):
                ad = st.text_input("Ad Soyad")
                p = st.number_input("Başlangıç Paket", 10)
                if st.form_submit_button("SPORCUYU EKLE"):
                    new_r = {"Ad Soyad": ad, "Paket (Ders)": p, "Kalan Ders": p, "Son Islem": "-", "Durum": "Aktif", "Odeme Durumu": "Ödenmedi", "Notlar": "-"}
                    df_main = pd.concat([df_main, pd.DataFrame([new_r])], ignore_index=True)
                    save_data(df_main, "Ogrenci_Data"); st.success("Eklendi!"); st.rerun()
    else: st.dataframe(df_main[["Ad Soyad", "Kalan Ders", "Odeme Durumu"]], use_container_width=True, hide_index=True)

# --- 4. KASA (YENİLENMİŞ & GELİŞMİŞ) ---
elif menu == "💸 Kasa":
    st.markdown("<h2 style='color: white;'>💸 Muhasebe & Kasa</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        # Tutar, Tip (Gelir/Gider), Not kolonlarını içeren veriyi çek
        df_f = get_data_cached("Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"])
        
        # Eğer Tip kolonu yoksa (eski veriler için) hepsini Gelir yap
        if "Tip" not in df_f.columns: df_f["Tip"] = "Gelir"
        
        with st.expander("➕ Yeni İşlem Ekle (Gelir / Gider)", expanded=False):
            with st.form("kasa_islem"):
                c1, c2 = st.columns(2)
                f_tutar = c1.number_input("Miktar (TL)", min_value=0.0, step=100.0)
                f_tip = c1.selectbox("İşlem Tipi", ["Gelir", "Gider"])
                f_ogrenci = c2.selectbox("İlgili Kişi", ["Genel/Diğer"] + list(df_main["Ad Soyad"].unique()))
                f_not = c2.text_input("Açıklama (Örn: Kort kirası, Top alımı)")
                if st.form_submit_button("KASAYA İŞLE"):
                    append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), f_ogrenci, f_tutar, f_not, f_tip], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"])
                    st.success("İşlem başarıyla kaydedildi!"); st.rerun()

        if not df_f.empty:
            # Hesaplamalar
            toplam_gelir = df_f[df_f["Tip"] == "Gelir"]["Tutar"].sum()
            toplam_gider = df_f[df_f["Tip"] == "Gider"]["Tutar"].sum()
            net_kar = toplam_gelir - toplam_gider
            
            m1, m2, m3 = st.columns(3)
            m1.metric("TOPLAM GELİR", f"{toplam_gelir:,.0f} TL", delta_color="normal")
            m2.metric("TOPLAM GİDER", f"{toplam_gider:,.0f} TL", delta_color="inverse")
            m3.metric("NET KASA (KAR)", f"{net_kar:,.0f} TL", delta=f"{net_kar:,.0f} TL")
            
            st.markdown("---")
            
            g_col1, g_col2 = st.columns(2)
            
            with g_col1:
                # Aylık Gelir Grafiği (Onarılmış)
                aylik_df = df_f[df_f["Tip"] == "Gelir"].groupby("Ay")["Tutar"].sum().reset_index()
                fig_bar = px.bar(aylik_df, x="Ay", y="Tutar", title="Aylık Gelir Akışı", color_discrete_sequence=['#ccff00'])
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with g_col2:
                # Dağılım Grafiği (YENİ!)
                dağılım_df = df_f[df_f["Tip"] == "Gelir"].groupby("Ogrenci")["Tutar"].sum().reset_index()
                fig_pie = px.pie(dağılım_df, values='Tutar', names='Ogrenci', title='Gelir Dağılımı (%)', hole=.4, color_discrete_sequence=px.colors.sequential.Greens_r)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            st.dataframe(df_f.sort_index(ascending=False), use_container_width=True, hide_index=True)
        else: st.warning("Henüz kasa hareketi bulunmuyor.")

# --- 5. GEÇMİŞ ---
elif menu == "📝 Geçmiş":
    st.markdown("<h2 style='color: white;'>📝 İşlem Geçmişi</h2>", unsafe_allow_html=True)
    logs = get_data_cached("Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
    kisi = st.selectbox("Filtrele", ["Tümü"] + list(df_main["Ad Soyad"].unique()))
    if kisi != "Tümü": logs = logs[logs["Ogrenci"]==kisi]
    st.dataframe(logs.sort_index(ascending=False), use_container_width=True, hide_index=True)
