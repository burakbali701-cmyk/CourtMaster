import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

# --- AYARLAR & TASARIM ---
st.set_page_config(page_title="Tennis App", page_icon="🎾", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0b140f;}
    .stApp {background-image: linear-gradient(180deg, #0b140f 0%, #1a2e23 100%);}
    .stButton>button {
        width: 100%; border-radius: 12px; height: 3.0em; 
        font-weight: bold; background-color: #ccff00; color: #000;
        border: none; transition: 0.3s;
    }
    .stButton>button:hover {background-color: #e6ff80; transform: scale(1.02);}
    
    /* Kart Tasarımları */
    .player-card {
        background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(204, 255, 0, 0.3);
        padding: 15px; border-radius: 15px; color: white; text-align: center; margin-bottom: 10px;
        position: relative;
    }
    
    /* Log Akışı (Timeline) */
    .timeline-item {
        background: rgba(255, 255, 255, 0.03);
        border-left: 4px solid #ccff00;
        padding: 10px 15px; margin-bottom: 8px; border-radius: 4px;
        color: #ddd; font-size: 0.9em;
    }
    .timeline-date { color: #888; font-size: 0.75em; display: block; margin-bottom: 4px; }
    .timeline-money { border-left-color: #00e676 !important; } /* Para işlemleri yeşil */
    .timeline-lesson { border-left-color: #ccff00 !important; } /* Ders işlemleri sarı */
    
    /* Rozetler */
    .badge-paid { background-color: #00e676; color: black; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; font-weight: bold; }
    .badge-unpaid { background-color: #ff4b4b; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; font-weight: bold; }
    
    [data-testid="stSidebar"] {background-color: #080f0b; border-right: 1px solid #ccff0033;}
    [data-testid="stMetricValue"] {font-size: 1.8rem !important; color: #ccff00 !important;}
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
    sheet = baglanti_kur(); ws = get_worksheet(sheet, worksheet_name, columns)
    ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist())
    st.cache_data.clear()

def append_data(row_data, worksheet_name, columns):
    sheet = baglanti_kur(); ws = get_worksheet(sheet, worksheet_name, columns)
    ws.append_row(row_data); st.cache_data.clear()

# --- ARAYÜZ ---
with st.sidebar:
    st.markdown("<h1 style='color: #ccff00; text-align: center;'>Tennis App</h1>", unsafe_allow_html=True)
    with st.expander("🔐 Yönetici Paneli"):
        if st.text_input("Şifre", type="password") == ADMIN_SIFRE: st.session_state["admin"] = True
        else: st.session_state["admin"] = False
    IS_ADMIN = st.session_state.get("admin", False)
    menu = st.radio("MENÜ", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular", "💸 Finans 2.0", "📝 Loglar"] if IS_ADMIN else ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular"])

# --- TABLO SÜTUNLARI ---
COL_OGRENCI = ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu", "Notlar"]
COL_FINANS = ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"]
COL_LOG = ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"]
COL_PROG = ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Ana Verileri Çek
df_main = get_data_cached("Ogrenci_Data", COL_OGRENCI)
df_finans = get_data_cached("Finans_Kasa", COL_FINANS)
df_logs = get_data_cached("Ders_Gecmisi", COL_LOG)

# --- 1. KORT PANELİ (GELİŞMİŞ) ---
if menu == "🏠 Kort Paneli":
    st.markdown("<h2 style='color: white;'>🎾 Kort Yönetimi</h2>", unsafe_allow_html=True)
    aktif = df_main[df_main["Durum"]=="Aktif"]
    
    if not aktif.empty:
        col_select, col_empty = st.columns([2,1])
        with col_select:
            sec = st.selectbox("Hızlı İşlem (Sporcu Seç)", aktif["Ad Soyad"].unique())
            
        if sec:
            idx = df_main[df_main["Ad Soyad"]==sec].index[0]
            kalan = int(df_main.at[idx, "Kalan Ders"])
            odeme_durumu = df_main.at[idx, "Odeme Durumu"]
            
            # Renkler ve Badge
            bar_color = "#ccff00" if kalan > 5 else ("#ffa500" if kalan > 2 else "#ff4b4b")
            width = min((kalan / 15) * 100, 100)
            badge_class = "badge-paid" if odeme_durumu == "Ödendi" else "badge-unpaid"
            
            st.markdown(f"""
            <div class="player-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="{badge_class}">{odeme_durumu.upper()}</span>
                    <span style="font-size:0.8em; color:#aaa;">Son: {df_main.at[idx, "Son Islem"]}</span>
                </div>
                <h1 style="color:#ccff00; margin: 5px 0;">{sec}</h1>
                <div style="background:#333; height:10px; border-radius:5px; margin:10px 0; overflow:hidden;">
                    <div style="width:{width}%; background:{bar_color}; height:100%;"></div>
                </div>
                <h3 style="margin:0;">{kalan} DERS KALDI</h3>
            </div>
            """, unsafe_allow_html=True)

            if IS_ADMIN:
                c1, c2 = st.columns(2)
                if c1.button("✅ DERS TAMAMLANDI (-1)", type="primary"):
                    if kalan > 0:
                        df_main.at[idx, "Kalan Ders"] -= 1
                        df_main.at[idx, "Son Islem"] = datetime.now().strftime("%d-%m %H:%M")
                        if df_main.at[idx, "Kalan Ders"] == 0: df_main.at[idx, "Durum"] = "Bitti"
                        save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "Ders İşlendi", f"Kalan: {kalan-1}"], "Ders_Gecmisi", COL_LOG)
                        st.balloons(); time.sleep(1); st.rerun()
                
                # SİLME BUTONU
                with c2:
                    if st.button("🗑️ SPORCUYU SİL"):
                        df_main = df_main.drop(idx)
                        save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                        st.warning(f"{sec} sistemden silindi."); time.sleep(1); st.rerun()
    else: st.info("Aktif sporcu yok.")

# --- 2. SPORCULAR (BİRLEŞİK LOG SİSTEMİ) ---
elif menu == "👥 Sporcular":
    st.markdown("<h2 style='color: white;'>👥 Sporcu Profili</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        t1, t2 = st.tabs(["👤 Profil & Geçmiş", "➕ Yeni Sporcu"])
        with t1:
            secilen = st.selectbox("İncelemek için Sporcu Seç", ["Seçiniz..."] + list(df_main["Ad Soyad"].unique()))
            if secilen != "Seçiniz...":
                idx = df_main[df_main["Ad Soyad"] == secilen].index[0]
                
                # --- AYARLAR VE LOGLAR YAN YANA ---
                col_left, col_right = st.columns([1, 1.2])
                
                with col_left:
                    st.markdown("### ⚙️ Ayarlar")
                    with st.form(f"prof_{secilen}"):
                        y_ders = st.number_input("Kalan Ders", value=int(df_main.at[idx, "Kalan Ders"]))
                        y_odeme = st.selectbox("Ödeme Durumu", ["Ödenmedi", "Ödendi"], index=0 if df_main.at[idx, "Odeme Durumu"]=="Ödenmedi" else 1)
                        y_tut = st.number_input("Tahsilat (TL)", 0.0, step=100.0)
                        y_not = st.text_area("Hoca Notu", value=str(df_main.at[idx, "Notlar"]))
                        
                        if st.form_submit_button("KAYDET"):
                            df_main.at[idx, "Kalan Ders"] = y_ders
                            df_main.at[idx, "Odeme Durumu"] = y_odeme
                            df_main.at[idx, "Notlar"] = y_not
                            df_main.at[idx, "Durum"] = "Aktif" if y_ders > 0 else "Bitti"
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                            if y_tut > 0:
                                append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), secilen, y_tut, "Ödeme Alındı", "Gelir"], "Finans_Kasa", COL_FINANS)
                                append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), secilen, "Ödeme", f"{y_tut} TL"], "Ders_Gecmisi", COL_LOG)
                            st.success("Güncellendi!"); time.sleep(1); st.rerun()

                with col_right:
                    st.markdown("### 📜 Aktivite Akışı")
                    # LOGLARI BİRLEŞTİRME: Ders Geçmişi + Finans Geçmişi
                    p_logs = df_logs[df_logs["Ogrenci"] == secilen].copy()
                    p_logs["Tip"] = "Ders"
                    
                    # Finans verisini log formatına çevir
                    p_fin = df_finans[(df_finans["Ogrenci"] == secilen) & (df_finans["Tip"] == "Gelir")].copy()
                    p_fin_formatted = pd.DataFrame({
                        "Tarih": [d.split("-")[2]+"-"+d.split("-")[1]+"-"+d.split("-")[0] if "-" in d else d for d in p_fin["Tarih"]], # Tarih formatı uydurma
                        "Saat": ["-"] * len(p_fin),
                        "Ogrenci": p_fin["Ogrenci"],
                        "Islem": ["Ödeme"] * len(p_fin),
                        "Detay": [f"{t} TL" for t in p_fin["Tutar"]],
                        "Tip": ["Para"] * len(p_fin)
                    })
                    
                    # Birleştir ve Sırala
                    combined_logs = pd.concat([p_logs, p_fin_formatted], ignore_index=True)
                    # Basit sıralama (Tarih string olduğu için en doğru sıralama olmayabilir ama iş görür)
                    combined_logs = combined_logs.iloc[::-1] 

                    # Ekrana Bas
                    if not combined_logs.empty:
                        for _, row in combined_logs.head(10).iterrows():
                            css_class = "timeline-money" if row.get("Tip") == "Para" else "timeline-lesson"
                            icon = "💰" if row.get("Tip") == "Para" else "🎾"
                            st.markdown(f"""
                            <div class="timeline-item {css_class}">
                                <span class="timeline-date">{row['Tarih']} {row['Saat']}</span>
                                <b>{icon} {row['Islem']}</b>: {row['Detay']}
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("Henüz kayıtlı aktivite yok.")

        with t2:
            with st.form("new"):
                ad = st.text_input("Ad Soyad")
                p = st.number_input("Paket", 10)
                u = st.number_input("Peşinat (TL)", 0.0)
                o = st.selectbox("Durum", ["Ödenmedi", "Ödendi"])
                if st.form_submit_button("EKLE"):
                    new_r = {"Ad Soyad": ad, "Paket (Ders)": p, "Kalan Ders": p, "Son Islem": "-", "Durum": "Aktif", "Odeme Durumu": o, "Notlar": "-"}
                    df_main = pd.concat([df_main, pd.DataFrame([new_r])], ignore_index=True)
                    save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                    if u > 0: 
                        append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), ad, u, "İlk Kayıt", "Gelir"], "Finans_Kasa", COL_FINANS)
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), ad, "Ödeme", f"{u} TL"], "Ders_Gecmisi", COL_LOG)
                    st.rerun()
    else: st.dataframe(df_main[["Ad Soyad", "Kalan Ders", "Odeme Durumu"]], use_container_width=True)

# --- 3. FİNANS 2.0 (YEPYENİ TASARIM) ---
elif menu == "💸 Finans 2.0":
    st.markdown("<h2 style='color: white;'>💸 Finans Kontrol Merkezi</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        # Veri Hazırlığı
        if "Tip" not in df_finans.columns: df_finans["Tip"] = "Gelir"
        df_finans["Tutar"] = pd.to_numeric(df_finans["Tutar"], errors='coerce').fillna(0)
        
        # KPI Kartları
        gelir = df_finans[df_finans["Tip"]=="Gelir"]["Tutar"].sum()
        gider = df_finans[df_finans["Tip"]=="Gider"]["Tutar"].sum()
        net = gelir - gider
        alacak_sayisi = len(df_main[df_main["Odeme Durumu"]=="Ödenmedi"])
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Toplam Ciro", f"{gelir:,.0f} TL", "💹")
        k2.metric("Giderler", f"{gider:,.0f} TL", "-🔻", delta_color="inverse")
        k3.metric("Net Kar", f"{net:,.0f} TL", "💰")
        k4.metric("Ödemeyenler", f"{alacak_sayisi} Kişi", "⚠️", delta_color="off")
        
        st.markdown("---")
        
        # Grafikler
        tab_g, tab_d = st.tabs(["📈 Nakit Akışı", "🧾 Detaylı İşlemler"])
        
        with tab_g:
            c_chart1, c_chart2 = st.columns(2)
            # Zaman Grafiği
            zaman_df = df_finans[df_finans["Tip"]=="Gelir"].groupby("Ay")["Tutar"].sum().reset_index()
            fig_line = px.area(zaman_df, x="Ay", y="Tutar", title="Gelir Trendi", markers=True, color_discrete_sequence=['#ccff00'])
            c_chart1.plotly_chart(fig_line, use_container_width=True)
            
            # Pasta Grafiği
            fig_pie = px.pie(df_finans[df_finans["Tip"]=="Gelir"], values="Tutar", names="Ogrenci", title="En İyi Müşteriler", hole=0.4, color_discrete_sequence=px.colors.sequential.Greens_r)
            c_chart2.plotly_chart(fig_pie, use_container_width=True)

        with tab_d:
            with st.expander("➕ Yeni Gelir/Gider Ekle"):
                with st.form("quick_fin"):
                    c_a, c_b = st.columns(2)
                    q_tut = c_a.number_input("Tutar", 0.0)
                    q_tip = c_a.selectbox("Tür", ["Gelir", "Gider"])
                    q_ogr = c_b.text_input("Açıklama / Kişi (Opsiyonel)")
                    if st.form_submit_button("KAYDET"):
                        append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), q_ogr if q_ogr else "Genel", q_tut, "-", q_tip], "Finans_Kasa", COL_FINANS); st.rerun()
            
            st.dataframe(df_finans.sort_index(ascending=False), use_container_width=True)

# --- DİĞER ---
elif menu == "📅 Çizelge":
    df_prog = get_data_cached("Ders_Programi", COL_PROG)
    if IS_ADMIN:
        ed = st.data_editor(df_prog, use_container_width=True, hide_index=True)
        if not df_prog.equals(ed): save_data(ed, "Ders_Programi", COL_PROG)
    else: st.dataframe(df_prog, use_container_width=True)

elif menu == "📝 Loglar":
    st.dataframe(df_logs.sort_index(ascending=False), use_container_width=True)
