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
        padding: 20px; border-radius: 20px; color: white;
        text-align: center; margin-bottom: 15px;
    }
    .timeline-item {
        background: rgba(255, 255, 255, 0.03); border-left: 4px solid #ccff00;
        padding: 10px 15px; margin-bottom: 8px; border-radius: 4px; color: #ddd; font-size: 0.9em;
    }
    .timeline-money { border-left-color: #00e676 !important; } 
    .timeline-lesson { border-left-color: #ccff00 !important; }
    .badge-paid { background-color: #00e676; color: black; padding: 4px 10px; border-radius: 10px; font-weight: bold; }
    .badge-unpaid { background-color: #ff4b4b; color: white; padding: 4px 10px; border-radius: 10px; font-weight: bold; }
    [data-testid="stSidebar"] {background-color: #080f0b; border-right: 1px solid #ccff0033;}
    </style>
    """, unsafe_allow_html=True)

# --- YÖNETİCİ ŞİFRESİ ---
ADMIN_SIFRE = "1234"

# --- GOOGLE BAĞLANTISI ---
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

@st.cache_data(ttl=1)
def get_data_cached(worksheet_name, expected_columns):
    """
    Bu fonksiyon artık başlık isimlerine GÜVENMEZ.
    Sütun sırasına göre okur. Bu sayede 'Tip' sütunu kaymış olsa bile
    6. sıradaki veriyi 'Tip' olarak kabul eder.
    """
    try:
        sheet = baglanti_kur()
        ws = get_worksheet(sheet, worksheet_name, expected_columns)
        
        # get_all_records yerine get_all_values kullanıyoruz (Header bağımsız okuma)
        all_values = ws.get_all_values()
        
        if len(all_values) < 2: # Sadece başlık varsa veya boşsa
            return pd.DataFrame(columns=expected_columns)
            
        # İlk satır başlıktır, veriyi 2. satırdan itibaren al
        data = all_values[1:]
        
        # Veriyi DataFrame'e çevirirken bizim belirlediğimiz sütun isimlerini zorla
        # Eğer sheet'te fazla sütun varsa kırp, eksikse None ekle
        clean_data = []
        for row in data:
            # Satırı beklenen uzunluğa getir
            if len(row) >= len(expected_columns):
                clean_data.append(row[:len(expected_columns)])
            else:
                clean_data.append(row + [None]*(len(expected_columns)-len(row)))
                
        df = pd.DataFrame(clean_data, columns=expected_columns)
        
        # --- VERİ TİPİ DÜZELTME ---
        if "Tutar" in df.columns:
            # Temizlik: boşlukları sil, virgülü nokta yap
            df["Tutar"] = df["Tutar"].astype(str).str.strip().str.replace(',', '.', regex=False)
            df["Tutar"] = pd.to_numeric(df["Tutar"], errors='coerce').fillna(0)
            
        if "Kalan Ders" in df.columns:
            df["Kalan Ders"] = pd.to_numeric(df["Kalan Ders"], errors='coerce').fillna(0)
            
        return df
    except Exception as e:
        # Hata olursa boş dön ama hatayı konsola bas (streamlit logs)
        print(f"Veri çekme hatası: {e}") 
        return pd.DataFrame(columns=expected_columns)

def save_data(df, worksheet_name, columns):
    sheet = baglanti_kur(); ws = get_worksheet(sheet, worksheet_name, columns)
    ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist())
    st.cache_data.clear()

def append_data(row_data, worksheet_name, columns):
    sheet = baglanti_kur(); ws = get_worksheet(sheet, worksheet_name, columns)
    clean_row = []
    for x in row_data:
        if isinstance(x, (int, float)): clean_row.append(x)
        else: clean_row.append(str(x))
    ws.append_row(clean_row)
    st.cache_data.clear()

# --- ARAYÜZ ---
with st.sidebar:
    st.markdown("<h1 style='color: #ccff00; text-align: center;'>TENNIS APP</h1>", unsafe_allow_html=True)
    with st.expander("🔐 Giriş"):
        if st.text_input("Şifre", type="password") == ADMIN_SIFRE: st.session_state["admin"] = True
        else: st.session_state["admin"] = False
    IS_ADMIN = st.session_state.get("admin", False)
    menu = st.radio("MENÜ", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular", "💸 Kasa", "📝 Loglar"] if IS_ADMIN else ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular"])

# Sütun Tanımları (SIRALAMA ÇOK ÖNEMLİ)
# Google Sheets'te sütun sırası tam olarak böyle olmalı:
COL_OGRENCI = ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu", "Notlar"]
COL_FINANS = ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"] # 0:Tarih, 1:Ay, 2:Ogr, 3:Tutar, 4:Not, 5:Tip
COL_LOG = ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"]
COL_PROG = ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Verileri Çek
df_main = get_data_cached("Ogrenci_Data", COL_OGRENCI)
df_finans = get_data_cached("Finans_Kasa", COL_FINANS)
df_logs = get_data_cached("Ders_Gecmisi", COL_LOG)

# --- 1. KORT PANELİ ---
if menu == "🏠 Kort Paneli":
    st.markdown("<h2 style='color: white;'>🎾 Kort Yönetimi</h2>", unsafe_allow_html=True)
    aktif = df_main[df_main["Durum"]=="Aktif"]
    
    if not aktif.empty:
        col_select, col_empty = st.columns([2,1])
        with col_select:
            sec = st.selectbox("Oyuncu Seç", aktif["Ad Soyad"].unique())
            
        if sec:
            idx = df_main[df_main["Ad Soyad"]==sec].index[0]
            kalan = int(df_main.at[idx, "Kalan Ders"])
            odeme_durumu = df_main.at[idx, "Odeme Durumu"]
            bar_color = "#ccff00" if kalan > 5 else ("#ffa500" if kalan > 2 else "#ff4b4b")
            width = min((kalan / 15) * 100, 100)
            badge = "badge-paid" if odeme_durumu == "Ödendi" else "badge-unpaid"
            
            st.markdown(f"""
            <div class="player-card">
                <div style="display:flex; justify-content:space-between;">
                    <span class="{badge}">{odeme_durumu}</span>
                    <span style="color:#aaa;">{df_main.at[idx, "Son Islem"]}</span>
                </div>
                <h1 style="color:#ccff00; margin:5px;">{sec}</h1>
                <div style="background:#333; height:10px; border-radius:5px; margin:10px 0; overflow:hidden;">
                    <div style="width:{width}%; background:{bar_color}; height:100%;"></div>
                </div>
                <h3>{kalan} DERS KALDI</h3>
            </div>
            """, unsafe_allow_html=True)

            if IS_ADMIN:
                c1, c2, c3 = st.columns([2,1,1])
                with c1:
                    if st.button("✅ DERS TAMAMLANDI (-1)", type="primary"):
                        if kalan > 0:
                            df_main.at[idx, "Kalan Ders"] -= 1
                            df_main.at[idx, "Son Islem"] = datetime.now().strftime("%d-%m %H:%M")
                            if df_main.at[idx, "Kalan Ders"] == 0: df_main.at[idx, "Durum"] = "Bitti"
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                            append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "Ders İşlendi", f"Kalan: {kalan-1}"], "Ders_Gecmisi", COL_LOG)
                            st.rerun()
                with c2:
                    if st.button("↩️ GERİ (+1)"):
                        df_main.at[idx, "Kalan Ders"] += 1
                        save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "Geri Alındı", f"Kalan: {kalan+1}"], "Ders_Gecmisi", COL_LOG)
                        st.rerun()
                with c3:
                    if st.button("🗑️ SİL"):
                        df_main = df_main.drop(idx)
                        save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                        st.warning("Silindi"); time.sleep(1); st.rerun()
    else: st.info("Kortta kimse yok.")

# --- 2. SPORCULAR ---
elif menu == "👥 Sporcular":
    st.markdown("<h2 style='color: white;'>👥 Oyuncu Profilleri</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        t1, t2 = st.tabs(["👤 Profil Kartı", "➕ Yeni Kayıt"])
        with t1:
            secilen = st.selectbox("Oyuncu Seç", ["Seçiniz..."] + list(df_main["Ad Soyad"].unique()))
            if secilen != "Seçiniz...":
                idx = df_main[df_main["Ad Soyad"] == secilen].index[0]
                durum = df_main.at[idx, "Durum"]
                odeme = df_main.at[idx, "Odeme Durumu"]

                c_h1, c_h2 = st.columns([3, 1])
                with c_h1:
                    st.markdown(f"### {secilen} <span style='font-size:0.6em; color:{'#00b0ff' if durum=='Donduruldu' else '#ccff00'}'>({durum})</span>", unsafe_allow_html=True)
                with c_h2:
                    if durum == "Aktif":
                        if st.button("❄️ DONDUR"):
                            df_main.at[idx, "Durum"] = "Donduruldu"
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI); st.rerun()
                    else:
                        if st.button("🔥 AKTİF ET"):
                            df_main.at[idx, "Durum"] = "Aktif"
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI); st.rerun()

                col_L, col_R = st.columns([1, 1.2])
                with col_L:
                    st.markdown("#### ⚙️ Ayarlar")
                    with st.form("ayar_form"):
                        st.write(f"Mevcut Ders: **{df_main.at[idx, 'Kalan Ders']}**")
                        ek = st.number_input("➕ Paket Ekle (Ders)", 0, step=1)
                        st.markdown("---")
                        y_odeme = st.selectbox("Durum", ["Ödenmedi", "Ödendi"], index=0 if odeme=="Ödenmedi" else 1)
                        y_tutar = st.number_input("Tahsilat Yap (TL)", 0.0, step=100.0)
                        y_not = st.text_area("Notlar", str(df_main.at[idx, "Notlar"]))
                        
                        if st.form_submit_button("KAYDET"):
                            if ek > 0:
                                df_main.at[idx, "Kalan Ders"] += ek
                                append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), secilen, "Paket Eklendi", f"+{ek} Ders"], "Ders_Gecmisi", COL_LOG)
                            if y_tutar > 0:
                                append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), secilen, float(y_tutar), "Ödeme Alındı", "Gelir"], "Finans_Kasa", COL_FINANS)
                                append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), secilen, "Ödeme", f"{y_tutar} TL"], "Ders_Gecmisi", COL_LOG)
                                y_odeme = "Ödendi"
                            
                            df_main.at[idx, "Odeme Durumu"] = y_odeme
                            df_main.at[idx, "Notlar"] = y_not
                            if df_main.at[idx, "Durum"] != "Donduruldu" and df_main.at[idx, "Kalan Ders"] > 0: df_main.at[idx, "Durum"] = "Aktif"
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                            st.success("Kaydedildi"); time.sleep(0.5); st.rerun()

                with col_R:
                    st.markdown("#### 📜 Geçmiş Akışı")
                    logs = df_logs[df_logs["Ogrenci"]==secilen].copy()
                    logs["Tip"] = "Ders"
                    fins = df_finans[(df_finans["Ogrenci"]==secilen) & (df_finans["Tip"]=="Gelir")].copy()
                    if not fins.empty:
                        fins_fmt = pd.DataFrame({
                            "Tarih": [str(x) for x in fins["Tarih"]],
                            "Saat": ["-"]*len(fins),
                            "Ogrenci": fins["Ogrenci"],
                            "Islem": ["Ödeme"]*len(fins),
                            "Detay": [f"{x:,.0f} TL" for x in fins["Tutar"]],
                            "Tip": ["Para"]*len(fins)
                        })
                        full_log = pd.concat([logs, fins_fmt], ignore_index=True)
                    else: full_log = logs
                    
                    if not full_log.empty:
                        full_log = full_log.iloc[::-1]
                        for _, r in full_log.head(15).iterrows():
                            cls = "timeline-money" if r.get("Tip")=="Para" else "timeline-lesson"
                            icon = "💰" if r.get("Tip")=="Para" else "🎾"
                            st.markdown(f"""<div class="timeline-item {cls}"><span class="timeline-date">{r['Tarih']} {r['Saat']}</span><b>{icon} {r['Islem']}</b>: {r['Detay']}</div>""", unsafe_allow_html=True)
                    else: st.info("Kayıt yok.")

        with t2:
            st.markdown("### 🆕 Yeni Kayıt")
            with st.form("new_user"):
                ad = st.text_input("Ad Soyad")
                p = st.number_input("Paket (Ders)", 0, step=1, value=10)
                u = st.number_input("Peşinat (TL)", 0.0, step=100.0)
                o = st.selectbox("Durum", ["Ödenmedi", "Ödendi"])
                if st.form_submit_button("EKLE"):
                    new_r = {"Ad Soyad": ad, "Paket (Ders)": p, "Kalan Ders": p, "Son Islem": "-", "Durum": "Aktif", "Odeme Durumu": o, "Notlar": "-"}
                    df_main = pd.concat([df_main, pd.DataFrame([new_r])], ignore_index=True)
                    save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                    if u > 0:
                        append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), ad, float(u), "İlk Kayıt", "Gelir"], "Finans_Kasa", COL_FINANS)
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), ad, "Ödeme", f"{u} TL"], "Ders_Gecmisi", COL_LOG)
                    st.success("Eklendi"); time.sleep(0.5); st.rerun()
    else: st.dataframe(df_main, use_container_width=True)

# --- 3. FİNANS (GÜÇLENDİRİLMİŞ & KÖR OKUMA) ---
elif menu == "💸 Kasa":
    st.markdown("<h2 style='color: white;'>💸 Kasa</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        if not df_finans.empty:
            # Artık Tip sütunu kaymış olsa bile COL_FINANS sıralamasına göre 5. indeksi Tip kabul eder.
            # Veri tipi garantisi
            df_finans["Tutar"] = pd.to_numeric(df_finans["Tutar"], errors='coerce').fillna(0)
            
            # Tip sütunundaki boşlukları temizle
            df_finans["Tip"] = df_finans["Tip"].astype(str).str.strip()
            
            gelir = df_finans[df_finans["Tip"]=="Gelir"]["Tutar"].sum()
            gider = df_finans[df_finans["Tip"]=="Gider"]["Tutar"].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("GELİR", f"{gelir:,.0f} TL")
            c2.metric("GİDER", f"{gider:,.0f} TL")
            c3.metric("NET", f"{gelir-gider:,.0f} TL")
            
            st.markdown("---")
            col_add, col_graph = st.columns([1, 1.5])
            
            with col_add:
                st.markdown("#### ➕ Hızlı Ekle")
                with st.form("fin_hizli"):
                    ft = st.number_input("Tutar", 0.0, step=100.0)
                    ftp = st.selectbox("Tür", ["Gelir", "Gider"])
                    fa = st.text_input("Açıklama", "Genel")
                    if st.form_submit_button("EKLE"):
                        append_data([
                            datetime.now().strftime("%Y-%m-%d"), 
                            datetime.now().strftime("%Y-%m"), 
                            "Genel", 
                            float(ft), 
                            fa, 
                            ftp
                        ], "Finans_Kasa", COL_FINANS)
                        st.rerun()
            
            with col_graph:
                gf = df_finans[df_finans["Tip"]=="Gelir"]
                if not gf.empty:
                    fig = px.pie(gf, values="Tutar", names="Ogrenci", title="Gelir Dağılımı", hole=0.4, color_discrete_sequence=px.colors.sequential.Greens_r)
                    fig.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df_finans.sort_index(ascending=False), use_container_width=True)
        else: st.info("Finans verisi yok.")

# --- DİĞER ---
elif menu == "📅 Çizelge":
    df_prog = get_data_cached("Ders_Programi", COL_PROG)
    if IS_ADMIN:
        ed = st.data_editor(df_prog, use_container_width=True, hide_index=True)
        if not df_prog.equals(ed): save_data(ed, "Ders_Programi", COL_PROG)
    else: st.dataframe(df_prog, use_container_width=True)

elif menu == "📝 Loglar":
    st.dataframe(df_logs.sort_index(ascending=False), use_container_width=True)
