import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime
import time

# --- AYARLAR & TASARIM ---
st.set_page_config(page_title="CourtMaster FINAL", page_icon="🎾", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    .stButton>button {
        width: 100%; border-radius: 8px; height: 3em; font-weight: bold;
    }
    .metric-card {
        background-color: #262730; border: 1px solid #41444e;
        padding: 15px; border-radius: 10px; color: white; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- YÖNETİCİ ŞİFRESİ ---
ADMIN_SIFRE = "1234"

# --- GOOGLE SHEETS BAĞLANTISI (AKILLI VERSİYON) ---
@st.cache_resource
def baglanti_kur():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # 1. Önce Buluta Bak (Streamlit Secrets)
    if "gcp_service_account" in st.secrets:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
    # 2. Bulutta Yoksa Bilgisayarına Bak (Local Dosya)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name('secrets.json', scope)
        
    client = gspread.authorize(creds)
    return client.open("CourtMaster_DB")

# --- VERİ ÇEKME (CACHE İLE HIZLANDIRILMIŞ) ---
@st.cache_data(ttl=10)
def get_data_cached(worksheet_name, columns):
    try:
        ws = sheet.worksheet(worksheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame(columns=columns)
        else:
            # Sütunları garantiye al
            for col in columns:
                if col not in df.columns:
                    df[col] = "Belirsiz" if col == "Odeme Durumu" else "-"
            # Sayısal dönüşümler (Finansın bozulmaması için kritik)
            if "Tutar" in df.columns:
                df["Tutar"] = pd.to_numeric(df["Tutar"], errors='coerce').fillna(0)
            if "Kalan Ders" in df.columns:
                df["Kalan Ders"] = pd.to_numeric(df["Kalan Ders"], errors='coerce').fillna(0)
                
        return df
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
        ws.append_row(columns)
        return pd.DataFrame(columns=columns)

# --- VERİ KAYDETME ---
def save_data(df, worksheet_name):
    try:
        ws = sheet.worksheet(worksheet_name)
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Kaydetme Hatası: {e}")
        time.sleep(1)

def append_data(row_data, worksheet_name, columns):
    try:
        try:
            ws = sheet.worksheet(worksheet_name)
        except:
            ws = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
            ws.append_row(columns)
        ws.append_row(row_data)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Ekleme Hatası: {e}")

# --- ARAYÜZ ---
st.title("🎾 CourtMaster - Yönetim Paneli")

# LOGIN VE MENÜ
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2906/2906260.png", width=80)
    with st.expander("🔒 Yönetici Girişi"):
        sifre = st.text_input("Şifre", type="password")
        if sifre == ADMIN_SIFRE:
            st.session_state["admin"] = True
            st.success("Yönetici")
        else:
            st.session_state["admin"] = False
    
    IS_ADMIN = st.session_state.get("admin", False)
    
    # Menü Seçenekleri
    menu_options = ["🏠 Yoklama", "📅 Program", "👥 Öğrenci", "💸 Finans"]
    if IS_ADMIN:
        menu_options.append("📝 Log Merkezi") # Sadece admine özel sekme
        
    menu = st.radio("Menü", menu_options)

# ANA VERİYİ ÇEK
df_main = get_data_cached("Ogrenci_Data", ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu"])

# --- 1. PROGRAM ---
if menu == "📅 Program":
    st.subheader("📅 Haftalık Çizelge")
    df_prog = get_data_cached("Ders_Programi", ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"])
    
    if df_prog.empty:
        saatler = [f"{s:02d}:00" for s in range(8, 23)]
        df_prog = pd.DataFrame({"Saat": saatler})
        for gun in ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]: df_prog[gun] = ""
        save_data(df_prog, "Ders_Programi")

    if IS_ADMIN:
        edited_df = st.data_editor(df_prog, num_rows="fixed", use_container_width=True, height=600, hide_index=True)
        if not df_prog.equals(edited_df):
            save_data(edited_df, "Ders_Programi")
            st.toast("Program Kaydedildi!", icon="✅")
    else:
        st.dataframe(df_prog, use_container_width=True, height=600, hide_index=True)

# --- 2. ÖĞRENCİ YÖNETİMİ ---
elif menu == "👥 Öğrenci":
    if IS_ADMIN:
        tab1, tab2, tab3 = st.tabs(["🔄 Paket Yenile", "➕ Yeni Kayıt", "📋 Liste"])
        
        with tab1: # PAKET YENİLEME
            tum = df_main["Ad Soyad"].unique()
            if len(tum)>0:
                # FORM KULLANIYORUZ - Böylece sayfa zırt pırt yenilenmez
                with st.form("paket_yenile_form"):
                    c1, c2 = st.columns(2)
                    secilen = c1.selectbox("Öğrenci Seç", tum)
                    # Min value 0 yaptık, step 1
                    ek = c1.number_input("Eklenecek Ders", min_value=0, value=0, step=1)
                    
                    tahsilat = c2.checkbox("Tahsilat Yapıldı mı?")
                    tutar = c2.number_input("Tutar (TL)", min_value=0.0, value=0.0, step=100.0)
                    
                    submitted = st.form_submit_button("GÜNCELLE VE KAYDET")
                    
                    if submitted:
                        if ek == 0 and tutar == 0:
                            st.warning("Hiçbir değer girmediniz.")
                        else:
                            idx = df_main[df_main["Ad Soyad"] == secilen].index[0]
                            eski_kalan = int(df_main.at[idx, "Kalan Ders"])
                            df_main.at[idx, "Kalan Ders"] = eski_kalan + ek
                            df_main.at[idx, "Durum"] = "Aktif"
                            
                            if tahsilat:
                                df_main.at[idx, "Odeme Durumu"] = "Ödendi"
                                append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), secilen, float(tutar), "Paket Yenileme"], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
                            elif ek > 0: # Ders ekledi ama para almadıysa borçlu olur
                                df_main.at[idx, "Odeme Durumu"] = "Ödenmedi"
                            
                            save_data(df_main, "Ogrenci_Data")
                            append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), secilen, "PAKET YENİLENDİ", f"+{ek} Ders"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                            st.success("İşlem Başarılı!")
                            st.rerun()

        with tab2: # YENİ KAYIT
            # FORM KULLANIYORUZ - Kendi kendine kaydetmeyi engeller
            with st.form("yeni_kayit_form"):
                c_ad, c_paket = st.columns(2)
                ad = c_ad.text_input("Ad Soyad")
                # Min value 0 yaptık
                ilk = c_paket.number_input("Başlangıç Paket", min_value=0, value=0, step=1)
                
                st.markdown("---")
                c_odeme, c_tutar = st.columns(2)
                ode = c_odeme.checkbox("Ödeme Alındı mı?")
                tut = c_tutar.number_input("Tutar (TL)", min_value=0.0, value=0.0, step=100.0)
                
                kaydet_btn = st.form_submit_button("KAYDI TAMAMLA")
                
                if kaydet_btn:
                    if not ad:
                        st.error("İsim girmelisiniz!")
                    elif ad in df_main["Ad Soyad"].values:
                        st.error("Bu isim zaten kayıtlı!")
                    else:
                        durum = "Ödendi" if ode else "Ödenmedi"
                        yeni_row = {"Ad Soyad": ad, "Paket (Ders)": ilk, "Kalan Ders": ilk, "Son Islem": "-", "Durum": "Aktif", "Odeme Durumu": durum}
                        df_main = pd.concat([df_main, pd.DataFrame([yeni_row])], ignore_index=True)
                        save_data(df_main, "Ogrenci_Data")
                        
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), ad, "YENİ KAYIT", f"{ilk} Ders"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                        if ode and tut > 0:
                            append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), ad, float(tut), "İlk Kayıt"], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
                        st.success(f"{ad} sisteme eklendi!")
                        st.rerun()
                        
        with tab3:
            st.dataframe(df_main)
    else:
        st.dataframe(df_main[["Ad Soyad", "Kalan Ders", "Durum", "Odeme Durumu"]])

# --- 3. YOKLAMA ---
elif menu == "🏠 Yoklama":
    c1, c2 = st.columns([2,1])
    with c1:
        aktif = df_main[df_main["Durum"] == "Aktif"]
        if not aktif.empty:
            secilen = st.selectbox("Öğrenci Seç", aktif["Ad Soyad"].unique())
            idx = df_main[df_main["Ad Soyad"] == secilen].index[0]
            kalan = int(df_main.at[idx, "Kalan Ders"])
            durum = df_main.at[idx, "Odeme Durumu"]
            renk = "#4CAF50" if durum == "Ödendi" else "#FF5252"
            
            st.markdown(f"""<div class="metric-card" style="border-left:10px solid {renk}"><h3>{secilen}</h3><h1 style="color:white">{kalan} Ders</h1><p style="color:{renk}">{durum}</p></div>""", unsafe_allow_html=True)

            if IS_ADMIN:
                if durum != "Ödendi":
                    with st.expander("💰 BORÇ ÖDEME EKRANI"):
                        with st.form("borc_kapat_form"):
                            tutar_borc = st.number_input("Tahsil Edilen Tutar", min_value=0.0, step=100.0)
                            if st.form_submit_button("BORCU KAPAT"):
                                df_main.at[idx, "Odeme Durumu"] = "Ödendi"
                                save_data(df_main, "Ogrenci_Data")
                                append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), secilen, float(tutar_borc), "Borç Kapama"], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
                                st.success("Borç Kapatıldı!")
                                st.rerun()
                
                col_a, col_b = st.columns(2)
                if col_a.button("🎾 DERS İŞLENDİ (-1)", type="primary"):
                    if kalan > 0:
                        df_main.at[idx, "Kalan Ders"] = kalan - 1
                        df_main.at[idx, "Son Islem"] = datetime.now().strftime("%d-%m %H:%M")
                        save_data(df_main, "Ogrenci_Data")
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), secilen, "DERS DÜŞÜLDÜ", f"Kalan: {kalan-1}"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                        st.rerun()
                
                if col_b.button("↩️ GERİ AL (+1)"):
                    df_main.at[idx, "Kalan Ders"] = kalan + 1
                    save_data(df_main, "Ogrenci_Data")
                    append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), secilen, "GERİ ALINDI", "Hata"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                    st.rerun()
    
    with c2:
        st.markdown("### ⚡ Son Aktiviteler")
        df_log = get_data_cached("Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
        st.dataframe(df_log.tail(10).iloc[::-1], hide_index=True)

# --- 4. FİNANS (DÜZELTİLDİ) ---
elif menu == "💸 Finans":
    if IS_ADMIN:
        df_fin = get_data_cached("Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
        
        bu_ay = datetime.now().strftime("%Y-%m")
        toplam = df_fin["Tutar"].sum()
        aylik = df_fin[df_fin["Ay"] == bu_ay]["Tutar"].sum()
        
        c1, c2 = st.columns(2)
        c1.metric("Bu Ay Ciro", f"{aylik:,.0f} TL")
        c2.metric("Toplam Ciro", f"{toplam:,.0f} TL")
        
        if not df_fin.empty:
            tab_grafik, tab_liste = st.tabs(["📊 Grafikler", "🧾 Liste"])
            with tab_grafik:
                c_g1, c_g2 = st.columns(2)
                c_g1.plotly_chart(px.bar(df_fin.groupby("Ay")["Tutar"].sum().reset_index(), x="Ay", y="Tutar", title="Aylık Gelir"), use_container_width=True)
                c_g2.plotly_chart(px.pie(df_fin.groupby("Ogrenci")["Tutar"].sum().reset_index(), values="Tutar", names="Ogrenci", title="Öğrenci Payı"), use_container_width=True)
            with tab_liste:
                st.dataframe(df_fin.sort_index(ascending=False), use_container_width=True)
    else:
        st.error("Yetkisiz Giriş")

# --- 5. LOG MERKEZİ (YENİ - SADECE ADMİN) ---
elif menu == "📝 Log Merkezi":
    st.subheader("📝 Detaylı Log Kayıtları")
    
    # Tüm logları çek
    df_logs = get_data_cached("Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
    
    # FİLTRELEME ALANI
    filtre_col1, filtre_col2 = st.columns(2)
    
    # Öğrenci Listesini al (Tümü seçeneği ekle)
    ogrenci_listesi = ["Tümü"] + list(df_main["Ad Soyad"].unique())
    secilen_ogrenci_log = filtre_col1.selectbox("Öğrenciye Göre Filtrele", ogrenci_listesi)
    
    # Filtreleme Mantığı
    if secilen_ogrenci_log != "Tümü":
        gosterilecek_log = df_logs[df_logs["Ogrenci"] == secilen_ogrenci_log]
    else:
        gosterilecek_log = df_logs
        
    st.markdown(f"**Toplam Kayıt:** {len(gosterilecek_log)}")
    st.dataframe(gosterilecek_log.sort_index(ascending=False), use_container_width=True, height=600)