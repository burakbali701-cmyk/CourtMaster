import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime
import time

# --- AYARLAR ---
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
    .timeline-container { border-left: 2px solid #333; padding-left: 20px; margin-left: 10px; }
    .timeline-item {
        background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px; padding: 15px; margin-bottom: 15px; position: relative; transition: 0.3s;
    }
    .t-money { border-left: 4px solid #00e676 !important; } 
    .t-lesson { border-left: 4px solid #ccff00 !important; } 
    .t-sys { border-left: 4px solid #00b0ff !important; }
    .time-badge { font-size: 0.8em; color: #888; margin-bottom: 5px; display: block; }
    .log-title { font-size: 1.1em; font-weight: bold; color: white; }
    .log-detail { color: #ccc; font-size: 0.9em; }
    .badge-paid { background-color: #00e676; color: black; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 0.8em; }
    .badge-unpaid { background-color: #ff4b4b; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 0.8em; }
    .badge-frozen { background-color: #00b0ff; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 0.8em; }
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

# --- SÜTUN YAPILARI ---
COL_OGRENCI = ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu", "Notlar"]
COL_FINANS = ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"]
COL_LOG = ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"]
COL_PROG = ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# --- VERİ ÇEKME (SAFE MODE) ---
@st.cache_data(ttl=10)
def get_data_cached(worksheet_name, expected_columns):
    try:
        sheet = baglanti_kur()
        try:
            ws = sheet.worksheet(worksheet_name)
        except:
            return pd.DataFrame(columns=expected_columns)
            
        all_values = ws.get_all_values()
        if len(all_values) < 2: return pd.DataFrame(columns=expected_columns)
        
        data = all_values[1:]
        clean_data = []
        for row in data:
            if len(row) >= len(expected_columns): clean_data.append(row[:len(expected_columns)])
            else: clean_data.append(row + [None]*(len(expected_columns)-len(row)))
                
        df = pd.DataFrame(clean_data, columns=expected_columns)
        
        if "Tutar" in df.columns:
            df["Tutar"] = df["Tutar"].astype(str).str.strip().str.replace(',', '.', regex=False)
            df["Tutar"] = pd.to_numeric(df["Tutar"], errors='coerce').fillna(0)
        if "Kalan Ders" in df.columns:
            df["Kalan Ders"] = pd.to_numeric(df["Kalan Ders"], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame(columns=expected_columns)

def save_data(df, worksheet_name, columns):
    sheet = baglanti_kur(); ws = sheet.worksheet(worksheet_name)
    ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist())
    st.cache_data.clear()

def append_data(row_data, worksheet_name, columns):
    sheet = baglanti_kur(); ws = sheet.worksheet(worksheet_name)
    clean_row = []
    for x in row_data:
        if isinstance(x, (int, float)): clean_row.append(x)
        else: clean_row.append(str(x))
    ws.append_row(clean_row)
    st.cache_data.clear()

# --- 🕵️‍♂️ ZİYARETÇİ ---
if "ziyaret_kaydedildi" not in st.session_state:
    try:
        tarih = datetime.now().strftime("%d-%m-%Y")
        saat = datetime.now().strftime("%H:%M")
        append_data([tarih, saat, "Misafir", "Giriş", "Sayfa Görüntülendi"], "Ders_Gecmisi", COL_LOG)
        st.session_state["ziyaret_kaydedildi"] = True
    except: pass

# --- ARAYÜZ ---
with st.sidebar:
    st.markdown("<h1 style='color: #ccff00; text-align: center;'>Tennis App</h1>", unsafe_allow_html=True)
    with st.expander("🔐 Giriş"):
        if st.text_input("Şifre", type="password") == ADMIN_SIFRE: st.session_state["admin"] = True
        else: st.session_state["admin"] = False
    IS_ADMIN = st.session_state.get("admin", False)
    
    if IS_ADMIN:
        menu = st.radio("MENÜ", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular", "💸 Kasa", "📝 Geçmiş"])
        
        # --- 🛠️ TAMİR BUTONU (SADECE ADMIN) ---
        st.markdown("---")
        if st.button("🔴 VERİTABANINI SIFIRLA VE KUR"):
            with st.spinner("Veritabanı onarılıyor... Lütfen bekleyin..."):
                try:
                    sheet = baglanti_kur()
                    # 1. Ogrenci_Data
                    try: sheet.del_worksheet(sheet.worksheet("Ogrenci_Data"))
                    except: pass
                    time.sleep(1.5) # API Kotası için bekleme
                    ws1 = sheet.add_worksheet("Ogrenci_Data", 1000, 20)
                    ws1.append_row(COL_OGRENCI)
                    
                    # 2. Finans_Kasa
                    try: sheet.del_worksheet(sheet.worksheet("Finans_Kasa"))
                    except: pass
                    time.sleep(1.5)
                    ws2 = sheet.add_worksheet("Finans_Kasa", 1000, 20)
                    ws2.append_row(COL_FINANS)
                    
                    # 3. Ders_Gecmisi
                    try: sheet.del_worksheet(sheet.worksheet("Ders_Gecmisi"))
                    except: pass
                    time.sleep(1.5)
                    ws3 = sheet.add_worksheet("Ders_Gecmisi", 1000, 20)
                    ws3.append_row(COL_LOG)
                    
                    # 4. Ders_Programi
                    try: sheet.del_worksheet(sheet.worksheet("Ders_Programi"))
                    except: pass
                    time.sleep(1.5)
                    ws4 = sheet.add_worksheet("Ders_Programi", 1000, 20)
                    ws4.append_row(COL_PROG)
                    saatler = [[f"{h:02d}:00"] + [""]*7 for h in range(8, 24)]
                    ws4.append_rows(saatler)
                    
                    st.success("✅ Kurulum Başarıyla Tamamlandı! Sayfayı yenileyin.")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")

    else:
        menu = st.radio("MENÜ", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular"])

# Verileri Çek
df_main = get_data_cached("Ogrenci_Data", COL_OGRENCI)
df_finans = get_data_cached("Finans_Kasa", COL_FINANS)
df_logs = get_data_cached("Ders_Gecmisi", COL_LOG)

# --- İÇERİK ---
if menu == "🏠 Kort Paneli":
    st.markdown("<h2 style='color: white;'>🎾 Kort Yönetimi</h2>", unsafe_allow_html=True)
    aktif = df_main[df_main["Durum"]=="Aktif"]
    if not aktif.empty:
        col_select, col_empty = st.columns([2,1])
        with col_select: sec = st.selectbox("Oyuncu Seç", aktif["Ad Soyad"].unique())
        if sec:
            idx = df_main[df_main["Ad Soyad"]==sec].index[0]
            kalan = int(df_main.at[idx, "Kalan Ders"])
            odeme_durumu = df_main.at[idx, "Odeme Durumu"]
            bar_color = "#ccff00" if kalan > 5 else ("#ffa500" if kalan > 2 else "#ff4b4b")
            width = min((kalan / 15) * 100, 100)
            b_class = "badge-paid" if odeme_durumu == "Ödendi" else "badge-unpaid"
            
            st.markdown(f"""
            <div class="player-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <span class="{b_class}">{odeme_durumu.upper()}</span>
                    <span style="color:#aaa; font-size:0.8em;">{df_main.at[idx, "Son Islem"]}</span>
                </div>
                <h1 style="color:#ccff00; margin:0;">{sec}</h1>
                <div style="background:#333; height:10px; border-radius:5px; margin:15px 0; overflow:hidden;">
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
                if durum == "Donduruldu": b_durum_cls, b_durum_txt = "badge-frozen", "DONDURULDU"
                else: b_durum_cls, b_durum_txt = "badge-paid" if durum=="Aktif" else "badge-unpaid", durum.upper()
                b_odeme_cls = "badge-paid" if odeme == "Ödendi" else "badge-unpaid"
                st.markdown(f"""<div style="background:#1e211e; padding:20px; border-radius:15px; border-left:5px solid #ccff00; margin-bottom:20px;"><div style="display:flex; justify-content:space-between; align-items:center;"><h2 style="margin:0; color:white;">{secilen}</h2><div><span class="{b_durum_cls}">{b_durum_txt}</span><span class="{b_odeme_cls}" style="margin-left:10px;">{odeme.upper()}</span></div></div></div>""", unsafe_allow_html=True)
                col_L, col_R = st.columns([1, 1.2])
                with col_L:
                    st.markdown("#### ⚙️ İşlemler")
                    with st.form("ayar_form"):
                        st.write(f"Mevcut Ders: **{df_main.at[idx, 'Kalan Ders']}**")
                        ek = st.number_input("➕ Paket Ekle (Ders)", 0, step=1)
                        st.markdown("---")
                        y_odeme = st.selectbox("Durum", ["Ödenmedi", "Ödendi"], index=0 if odeme=="Ödenmedi" else 1)
                        y_tutar = st.number_input("Tahsilat Yap (TL)", 0.0, step=100.0)
                        y_not = st.text_area("Notlar", str(df_main.at[idx, "Notlar"]))
                        if durum == "Aktif": dondur = st.checkbox("❄️ Kaydı Dondur")
                        else: dondur = st.checkbox("🔥 Kaydı Aktif Et", value=True)
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
                            if dondur and durum == "Aktif": df_main.at[idx, "Durum"] = "Donduruldu"
                            elif dondur and durum == "Donduruldu": df_main.at[idx, "Durum"] = "Aktif"
                            elif df_main.at[idx, "Kalan Ders"] > 0: df_main.at[idx, "Durum"] = "Aktif"
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                            st.success("Kaydedildi"); time.sleep(0.5); st.rerun()
                with col_R:
                    st.markdown("#### 📜 Kişisel Geçmiş")
                    logs = df_logs[df_logs["Ogrenci"]==secilen].copy(); logs["Tip"] = "Ders"
                    fins = df_finans[(df_finans["Ogrenci"]==secilen) & (df_finans["Tip"]=="Gelir")].copy()
                    if not fins.empty:
                        fins["Tutar"] = pd.to_numeric(fins["Tutar"], errors='coerce').fillna(0)
                        fins_fmt = pd.DataFrame({"Tarih": [str(x) for x in fins["Tarih"]], "Saat": ["-"]*len(fins), "Ogrenci": fins["Ogrenci"], "Islem": ["Ödeme"]*len(fins), "Detay": [f"{x:,.0f} TL" for x in fins["Tutar"]], "Tip": ["Para"]*len(fins)})
                        full_log = pd.concat([logs, fins_fmt], ignore_index=True)
                    else: full_log = logs
                    if not full_log.empty:
                        full_log = full_log.iloc[::-1]
                        st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
                        for _, r in full_log.head(10).iterrows():
                            cls = "t-money" if r.get("Tip")=="Para" else "t-lesson"
                            icon = "💰" if r.get("Tip")=="Para" else "🎾"
                            st.markdown(f"""<div class="timeline-item {cls}"><span class="time-badge">{r['Tarih']} {r['Saat']}</span><div class="log-title">{icon} {r['Islem']}</div><div class="log-detail">{r['Detay']}</div></div>""", unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
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

elif menu == "💸 Kasa":
    st.markdown("<h2 style='color: white;'>💸 Kasa</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        if not df_finans.empty:
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
                        append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), "Genel", float(ft), fa, ftp], "Finans_Kasa", COL_FINANS)
                        st.rerun()
            with col_graph:
                gf = df_finans[df_finans["Tip"]=="Gelir"]
                if not gf.empty:
                    fig = px.pie(gf, values="Tutar", names="Ogrenci", title="Gelir Dağılımı", hole=0.4, color_discrete_sequence=px.colors.sequential.Greens_r)
                    fig.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_finans.sort_index(ascending=False), use_container_width=True)
        else: st.info("Veri yok. Kasa boş.")

elif menu == "📝 Geçmiş":
    st.markdown("<h2 style='color: white;'>📝 Geçmiş Kayıtlar</h2>", unsafe_allow_html=True)
    logs = df_logs.copy(); logs["Tip"] = "Ders"
    fins = df_finans.copy()
    if not fins.empty:
        fins["Tutar"] = pd.to_numeric(fins["Tutar"], errors='coerce').fillna(0)
        fins_fmt = pd.DataFrame({"Tarih": [str(x) for x in fins["Tarih"]], "Saat": ["-"]*len(fins), "Ogrenci": fins["Ogrenci"], "Islem": [f"Finans: {x}" for x in fins["Tip"]], "Detay": [f"{x:,.0f} TL - {y}" for x, y in zip(fins["Tutar"], fins["Not"])], "Tip": ["Para" if t=="Gelir" else "Gider" for t in fins["Tip"]]})
        master_log = pd.concat([logs, fins_fmt], ignore_index=True)
    else: master_log = logs
    master_log.loc[master_log["Ogrenci"] == "Misafir", "Tip"] = "Ziyaret"
    if not master_log.empty:
        master_log = master_log.iloc[::-1]
        tab_all, tab_ders, tab_finans, tab_sys = st.tabs(["Tümü", "🎾 Ders Hareketleri", "💰 Finans Raporu", "👀 Ziyaretçi Logu"])
        def render_timeline(df_subset):
            if df_subset.empty:
                st.info("Bu kategoride kayıt yok.")
                return
            st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
            for _, r in df_subset.head(50).iterrows():
                tip = r.get("Tip")
                if tip == "Para": css = "t-money"; icon = "💰"
                elif tip == "Gider": css = "t-sys"; icon = "📉"
                elif tip == "Ziyaret": css = "t-sys"; icon = "👀"
                else: css = "t-lesson"; icon = "🎾"
                st.markdown(f"""<div class="timeline-item {css}"><span class="time-badge">{r['Tarih']} {r['Saat']}</span><div class="log-title">{icon} {r['Ogrenci']} - {r['Islem']}</div><div class="log-detail">{r['Detay']}</div></div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with tab_all: render_timeline(master_log)
        with tab_ders: render_timeline(master_log[(master_log["Tip"] == "Ders") & (master_log["Ogrenci"] != "Misafir")])
        with tab_finans: render_timeline(master_log[master_log["Tip"].isin(["Para", "Gider"])])
        with tab_sys: render_timeline(master_log[master_log["Tip"] == "Ziyaret"])
    else: st.info("Henüz bir hareketlilik yok.")

elif menu == "📅 Çizelge":
    df_prog = get_data_cached("Ders_Programi", COL_PROG)
    if IS_ADMIN:
        ed = st.data_editor(df_prog, use_container_width=True, hide_index=True)
        if not df_prog.equals(ed): save_data(df_prog, "Ders_Programi", COL_PROG)
    else: st.dataframe(df_prog, use_container_width=True)
