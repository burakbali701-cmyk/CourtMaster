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
    
    /* Log Akışı */
    .timeline-item {
        background: rgba(255, 255, 255, 0.03);
        border-left: 4px solid #ccff00;
        padding: 10px 15px; margin-bottom: 8px; border-radius: 4px;
        color: #ddd; font-size: 0.9em;
    }
    .timeline-date { color: #888; font-size: 0.75em; display: block; margin-bottom: 4px; }
    .timeline-money { border-left-color: #00e676 !important; } 
    .timeline-lesson { border-left-color: #ccff00 !important; } 
    
    /* Rozetler */
    .badge-paid { background-color: #00e676; color: black; padding: 4px 10px; border-radius: 10px; font-weight: bold; }
    .badge-unpaid { background-color: #ff4b4b; color: white; padding: 4px 10px; border-radius: 10px; font-weight: bold; }
    .badge-frozen { background-color: #00b0ff; color: white; padding: 4px 10px; border-radius: 10px; font-weight: bold; }
    
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
    menu = st.radio("MENÜ", ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular", "💸 Finans", "📝 Loglar"] if IS_ADMIN else ["🏠 Kort Paneli", "📅 Çizelge", "👥 Sporcular"])

# --- TABLO SÜTUNLARI ---
COL_OGRENCI = ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu", "Notlar"]
COL_FINANS = ["Tarih", "Ay", "Ogrenci", "Tutar", "Not", "Tip"]
COL_LOG = ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"]
COL_PROG = ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Ana Verileri Çek
df_main = get_data_cached("Ogrenci_Data", COL_OGRENCI)
df_finans = get_data_cached("Finans_Kasa", COL_FINANS)
df_logs = get_data_cached("Ders_Gecmisi", COL_LOG)

# --- 1. KORT PANELİ ---
if menu == "🏠 Kort Paneli":
    st.markdown("<h2 style='color: white;'>🎾 Kort Yönetimi</h2>", unsafe_allow_html=True)
    
    # Sadece Aktifleri Göster (Dondurulanlar Kortta Çıkmaz)
    aktif = df_main[df_main["Durum"]=="Aktif"]
    
    if not aktif.empty:
        col_select, col_empty = st.columns([2,1])
        with col_select:
            sec = st.selectbox("Hızlı İşlem (Sporcu Seç)", aktif["Ad Soyad"].unique())
            
        if sec:
            idx = df_main[df_main["Ad Soyad"]==sec].index[0]
            kalan = int(df_main.at[idx, "Kalan Ders"])
            odeme_durumu = df_main.at[idx, "Odeme Durumu"]
            
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
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    if st.button("✅ DERS TAMAMLANDI (-1)", type="primary"):
                        if kalan > 0:
                            df_main.at[idx, "Kalan Ders"] -= 1
                            df_main.at[idx, "Son Islem"] = datetime.now().strftime("%d-%m %H:%M")
                            if df_main.at[idx, "Kalan Ders"] == 0: df_main.at[idx, "Durum"] = "Bitti"
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                            append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "Ders İşlendi", f"Kalan: {kalan-1}"], "Ders_Gecmisi", COL_LOG)
                            st.balloons(); time.sleep(0.5); st.rerun()
                
                with c2:
                    if st.button("↩️ GERİ AL (+1)"):
                        df_main.at[idx, "Kalan Ders"] += 1
                        save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "Ders Geri Alındı", f"Kalan: {kalan+1}"], "Ders_Gecmisi", COL_LOG)
                        st.rerun()
                        
                with c3:
                    if st.button("🗑️ SİL"):
                        df_main = df_main.drop(idx)
                        save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                        st.warning(f"{sec} silindi."); time.sleep(1); st.rerun()
    else: st.info("Kortta şu an aktif kimse yok (Dondurulanlar listelenmez).")

# --- 2. SPORCULAR (PROFESYONEL PROFİL SİSTEMİ) ---
elif menu == "👥 Sporcular":
    st.markdown("<h2 style='color: white;'>👥 Profesyonel Oyuncu Profili</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        t1, t2 = st.tabs(["👤 Oyuncu Kartı", "➕ Yeni Oyuncu Ekle"])
        with t1:
            secilen = st.selectbox("Profilini Görüntüle", ["Seçiniz..."] + list(df_main["Ad Soyad"].unique()))
            if secilen != "Seçiniz...":
                idx = df_main[df_main["Ad Soyad"] == secilen].index[0]
                
                # --- HEADER BÖLÜMÜ (Durum ve Dondurma) ---
                durum = df_main.at[idx, "Durum"]
                odeme_durumu = df_main.at[idx, "Odeme Durumu"]
                toplam_odeme = df_finans[(df_finans["Ogrenci"] == secilen) & (df_finans["Tip"] == "Gelir")]["Tutar"].sum()
                
                # Header Kartı
                st.markdown(f"""
                <div style="background:#1e211e; padding:15px; border-radius:15px; border-left:5px solid #ccff00; margin-bottom:20px;">
                    <h2 style="margin:0; color:white;">{secilen}</h2>
                    <span style="color:#888;">Durum: </span><b style="color:{'#00b0ff' if durum=='Donduruldu' else '#ccff00'}">{durum}</b>
                     | <span style="color:#888;">Finans: </span><b style="color:{'#00e676' if odeme_durumu=='Ödendi' else '#ff4b4b'}">{odeme_durumu}</b>
                </div>
                """, unsafe_allow_html=True)

                # DONDURMA / AKTİF ETME BUTONU
                c_head1, c_head2 = st.columns([1,3])
                with c_head1:
                    if durum == "Aktif":
                        if st.button("❄️ KAYDI DONDUR"):
                            df_main.at[idx, "Durum"] = "Donduruldu"
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                            st.success("Oyuncu donduruldu."); time.sleep(0.5); st.rerun()
                    else:
                        if st.button("🔥 KAYDI AKTİF ET"):
                            df_main.at[idx, "Durum"] = "Aktif"
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                            st.success("Oyuncu sahalara döndü!"); time.sleep(0.5); st.rerun()

                # --- 3 SEKME: GENEL | FİNANS | DERSLER ---
                tab_genel, tab_finans, tab_ders = st.tabs(["📝 Genel & Notlar", "💰 Finans & Borç", "🎾 Ders Geçmişi"])
                
                # 1. SEKME: GENEL AYARLAR
                with tab_genel:
                    with st.form(f"genel_{secilen}"):
                        c1, c2 = st.columns(2)
                        st.write(f"**Mevcut Ders Hakkı:** {df_main.at[idx, 'Kalan Ders']}")
                        ek_ders = c1.number_input("➕ Paket Ekle (Ders)", min_value=0, step=1)
                        y_not = st.text_area("Oyuncu Hakkında Notlar", value=str(df_main.at[idx, "Notlar"]), height=150)
                        
                        if st.form_submit_button("💾 DEĞİŞİKLİKLERİ KAYDET"):
                            if ek_ders > 0:
                                df_main.at[idx, "Kalan Ders"] += ek_ders
                                append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), secilen, "Paket Eklendi", f"+{ek_ders} Ders"], "Ders_Gecmisi", COL_LOG)
                            
                            df_main.at[idx, "Notlar"] = y_not
                            # Eğer dondurulmuş değilse ve dersi varsa Aktif yap
                            if df_main.at[idx, "Durum"] != "Donduruldu" and df_main.at[idx, "Kalan Ders"] > 0:
                                df_main.at[idx, "Durum"] = "Aktif"
                                
                            save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                            st.success("Kaydedildi!"); time.sleep(0.5); st.rerun()

                # 2. SEKME: FİNANS GEÇMİŞİ VE ÖDEME ALMA
                with tab_finans:
                    # Borç Ödeme Alanı (Sadece ödenmediyse veya para girişi yapılacaksa)
                    st.markdown("#### 💳 Hızlı Tahsilat")
                    
                    if odeme_durumu == "Ödenmedi":
                        st.warning(f"⚠️ Bu oyuncunun ödemesi beklemede!")
                    
                    with st.form("tahsilat_form"):
                        col_f1, col_f2 = st.columns(2)
                        tahsilat_tutar = col_f1.number_input("Tahsil Edilecek Tutar (TL)", min_value=0.0, step=100.0)
                        tahsilat_not = col_f2.text_input("Açıklama (Örn: Şubat Aidatı)")
                        
                        if st.form_submit_button("💰 TAHSİLAT YAP & BORCU KAPAT"):
                            if tahsilat_tutar > 0:
                                # 1. Finans Tablosuna Ekle
                                append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), secilen, tahsilat_tutar, tahsilat_not if tahsilat_not else "Borç Tahsilatı", "Gelir"], "Finans_Kasa", COL_FINANS)
                                # 2. Ana Tabloda Durumu Güncelle
                                df_main.at[idx, "Odeme Durumu"] = "Ödendi"
                                save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                                # 3. Loga Yaz
                                append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), secilen, "Ödeme Alındı", f"{tahsilat_tutar} TL"], "Ders_Gecmisi", COL_LOG)
                                st.success("Tahsilat başarılı, borç kapatıldı!"); time.sleep(1); st.rerun()
                            else:
                                st.error("Lütfen bir tutar girin.")

                    st.markdown("#### 📜 Finansal Hareketler (Para Giriş/Çıkış)")
                    # Sadece bu kişiye ait finansal loglar
                    p_finans = df_finans[df_finans["Ogrenci"] == secilen].sort_index(ascending=False)
                    if not p_finans.empty:
                        st.dataframe(p_finans[["Tarih", "Tutar", "Not", "Tip"]], use_container_width=True)
                    else:
                        st.info("Bu oyuncuya ait finansal kayıt yok.")

                # 3. SEKME: DERS GEÇMİŞİ
                with tab_ders:
                    st.markdown("#### 🎾 Ders & Aktivite Logları")
                    # Sadece bu kişiye ait ders logları
                    p_logs = df_logs[df_logs["Ogrenci"] == secilen].sort_index(ascending=False)
                    if not p_logs.empty:
                         for _, row in p_logs.iterrows():
                            # Finansal logları burada gösterme, karışmasın
                            if "Ödeme" not in str(row['Islem']): 
                                st.markdown(f"""
                                <div class="timeline-item timeline-lesson">
                                    <span class="timeline-date">{row['Tarih']} {row['Saat']}</span>
                                    <b>{row['Islem']}</b>: {row['Detay']}
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("Henüz ders aktivitesi yok.")

        with t2:
            st.markdown("### 🆕 Yeni Oyuncu Kaydı")
            with st.form("new"):
                ad = st.text_input("Ad Soyad")
                p = st.number_input("Başlangıç Paketi (Ders)", min_value=0, step=1, value=10)
                
                st.markdown("---")
                c1, c2 = st.columns(2)
                u = c1.number_input("Peşinat / İlk Ödeme (TL)", 0.0)
                o = c2.selectbox("Ödeme Durumu", ["Ödenmedi", "Ödendi"])
                
                if st.form_submit_button("KAYDET"):
                    new_r = {"Ad Soyad": ad, "Paket (Ders)": p, "Kalan Ders": p, "Son Islem": "-", "Durum": "Aktif", "Odeme Durumu": o, "Notlar": "-"}
                    df_main = pd.concat([df_main, pd.DataFrame([new_r])], ignore_index=True)
                    save_data(df_main, "Ogrenci_Data", COL_OGRENCI)
                    if u > 0: 
                        append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), ad, u, "İlk Kayıt", "Gelir"], "Finans_Kasa", COL_FINANS)
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), ad, "Ödeme", f"{u} TL"], "Ders_Gecmisi", COL_LOG)
                    st.success("Oyuncu başarıyla eklendi!"); time.sleep(1); st.rerun()
    else: st.dataframe(df_main[["Ad Soyad", "Kalan Ders", "Odeme Durumu"]], use_container_width=True)

# --- 3. FİNANS (GÜÇLENDİRİLMİŞ) ---
elif menu == "💸 Finans":
    st.markdown("<h2 style='color: white;'>💸 Finans Kontrol Merkezi</h2>", unsafe_allow_html=True)
    if IS_ADMIN:
        # Veri Hazırlığı
        if "Tip" not in df_finans.columns: df_finans["Tip"] = "Gelir"
        df_finans["Tutar"] = pd.to_numeric(df_finans["Tutar"], errors='coerce').fillna(0)
        
        # KPI Kartları
        gelir = df_finans[df_finans["Tip"]=="Gelir"]["Tutar"].sum()
        gider = df_finans[df_finans["Tip"]=="Gider"]["Tutar"].sum()
        net = gelir - gider
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Toplam Ciro", f"{gelir:,.0f} TL", "💹")
        k2.metric("Toplam Gider", f"{gider:,.0f} TL", "-🔻", delta_color="inverse")
        k3.metric("Net Kasa (Kar)", f"{net:,.0f} TL", "💰")
        
        st.markdown("---")
        
        # Grafikler
        if not df_finans.empty:
            tab_g, tab_d = st.tabs(["📈 Genel Analiz", "🧾 İşlem Dökümü"])
            
            with tab_g:
                c_chart1, c_chart2 = st.columns(2)
                gelir_df = df_finans[df_finans["Tip"]=="Gelir"]
                
                if not gelir_df.empty:
                    # Zaman Grafiği
                    zaman_df = gelir_df.groupby("Ay")["Tutar"].sum().reset_index()
                    fig_line = px.bar(zaman_df, x="Ay", y="Tutar", title="Aylık Gelir Akışı", color_discrete_sequence=['#ccff00'])
                    c_chart1.plotly_chart(fig_line, use_container_width=True)
                    
                    # Pasta Grafiği
                    fig_pie = px.pie(gelir_df, values="Tutar", names="Ogrenci", title="Gelir Dağılımı (Kim ne kadar ödedi?)", hole=0.4, color_discrete_sequence=px.colors.sequential.Greens_r)
                    c_chart2.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("Grafik için yeterli gelir verisi yok.")

            with tab_d:
                with st.expander("➕ Hızlı Gelir/Gider Girişi (Manuel)"):
                    with st.form("quick_fin"):
                        c_a, c_b = st.columns(2)
                        q_tut = c_a.number_input("Tutar (TL)", 0.0)
                        q_tip = c_a.selectbox("Tür", ["Gelir", "Gider"])
                        q_ogr = c_b.text_input("Açıklama / Kişi (Opsiyonel)")
                        if st.form_submit_button("KAYDET"):
                            append_data([
                                datetime.now().strftime("%Y-%m-%d"), 
                                datetime.now().strftime("%Y-%m"), 
                                q_ogr if q_ogr else "Genel", 
                                q_tut, 
                                "-", 
                                q_tip
                            ], "Finans_Kasa", COL_FINANS)
                            st.success("İşlem Eklendi!"); time.sleep(0.5); st.rerun()
                
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
