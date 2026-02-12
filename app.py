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
    .main {background-color: #0e1117;}
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold;}
    .metric-card {
        background-color: #262730; border: 1px solid #41444e;
        padding: 15px; border-radius: 10px; color: white; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 10px;
    }
    /* Yeni Progress Bar Stili */
    .progress-container {
        width: 100%;
        background-color: #2b2d3e;
        border-radius: 15px;
        margin: 10px 0;
        overflow: hidden;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
    }
    .progress-bar {
        height: 35px;
        line-height: 35px;
        color: white;
        text-align: center;
        font-weight: bold;
        transition: width 0.5s ease-in-out;
        box-shadow: 2px 0 5px rgba(0,0,0,0.3);
    }
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
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name('secrets.json', scope)
    client = gspread.authorize(creds)
    return client.open("CourtMaster_DB")

# --- VERİ ÇEKME ---
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
                if col not in df.columns: df[col] = "Belirsiz" if col == "Odeme Durumu" else "-"
            if "Tutar" in df.columns: df["Tutar"] = pd.to_numeric(df["Tutar"], errors='coerce').fillna(0)
            if "Kalan Ders" in df.columns: df["Kalan Ders"] = pd.to_numeric(df["Kalan Ders"], errors='coerce').fillna(0)
        return df
    except gspread.WorksheetNotFound:
        sheet = baglanti_kur()
        ws = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
        ws.append_row(columns)
        return pd.DataFrame(columns=columns)
    except Exception as e:
        st.error(f"Veri Çekme Hatası: {e}"); return pd.DataFrame(columns=columns)

# --- VERİ KAYDETME ---
def save_data(df, worksheet_name):
    try:
        sheet = baglanti_kur(); ws = sheet.worksheet(worksheet_name)
        ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist())
        st.cache_data.clear()
    except Exception as e: st.error(f"Kaydetme Hatası: {e}"); time.sleep(1)

def append_data(row_data, worksheet_name, columns):
    try:
        sheet = baglanti_kur()
        try: ws = sheet.worksheet(worksheet_name)
        except: ws = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=20); ws.append_row(columns)
        ws.append_row(row_data); st.cache_data.clear()
    except Exception as e: st.error(f"Ekleme Hatası: {e}")

# --- ARAYÜZ ---
st.title("🎾 Tennis App")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2906/2906260.png", width=80)
    with st.expander("🔒 Yönetici Girişi"):
        if st.text_input("Şifre", type="password") == ADMIN_SIFRE:
            st.session_state["admin"] = True; st.success("Giriş Yapıldı")
        else: st.session_state["admin"] = False
    IS_ADMIN = st.session_state.get("admin", False)
    menu_opts = ["🏠 Yoklama", "📅 Program", "👥 Öğrenci", "💸 Finans"]
    if IS_ADMIN: menu_opts.append("📝 Log Merkezi")
    menu = st.radio("Menü", menu_opts)

df_main = get_data_cached("Ogrenci_Data", ["Ad Soyad", "Paket (Ders)", "Kalan Ders", "Son Islem", "Durum", "Odeme Durumu"])

if menu == "📅 Program":
    st.subheader("📅 Haftalık Çizelge")
    df_prog = get_data_cached("Ders_Programi", ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"])
    if df_prog.empty:
        saatler = [f"{s:02d}:00" for s in range(8, 23)]
        df_prog = pd.DataFrame({"Saat": saatler})
        for gun in ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]: df_prog[gun] = ""
        save_data(df_prog, "Ders_Programi")
    if IS_ADMIN:
        edited = st.data_editor(df_prog, num_rows="fixed", use_container_width=True, height=600, hide_index=True)
        if not df_prog.equals(edited): save_data(edited, "Ders_Programi"); st.toast("Kaydedildi!", icon="✅")
    else: st.dataframe(df_prog, use_container_width=True, height=600, hide_index=True)

elif menu == "👥 Öğrenci":
    if IS_ADMIN:
        t1, t2, t3 = st.tabs(["🔄 Paket Yenile", "➕ Yeni Kayıt", "📋 Liste"])
        with t1:
            tum = df_main["Ad Soyad"].unique()
            if len(tum)>0:
                with st.form("yenile"):
                    c1,c2 = st.columns(2)
                    sec = c1.selectbox("Öğrenci", tum)
                    ek = c1.number_input("Ders Ekle (0-Sınırsız)", 0, step=1)
                    tahsilat = c2.checkbox("Tahsilat?")
                    tut = c2.number_input("Tutar", 0.0, step=100.0)
                    if st.form_submit_button("GÜNCELLE"):
                        idx = df_main[df_main["Ad Soyad"]==sec].index[0]
                        df_main.at[idx, "Kalan Ders"] = int(df_main.at[idx, "Kalan Ders"]) + ek
                        df_main.at[idx, "Durum"] = "Aktif"
                        if tahsilat: 
                            df_main.at[idx, "Odeme Durumu"] = "Ödendi"
                            append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), sec, float(tut), "Paket Yenileme"], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
                        elif ek > 0: df_main.at[idx, "Odeme Durumu"] = "Ödenmedi"
                        save_data(df_main, "Ogrenci_Data")
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "PAKET YENİLENDİ", f"+{ek} Ders"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                        st.success("Tamamlandı"); st.rerun()
        with t2:
            with st.form("yeni"):
                ad = st.text_input("Ad Soyad")
                ilk = st.number_input("Paket (0-Sınırsız)", 0, step=1)
                ode = st.checkbox("Ödeme?")
                tut = st.number_input("Tutar", 0.0, step=100.0)
                if st.form_submit_button("KAYDET"):
                    if ad and ad not in df_main["Ad Soyad"].values:
                        durum = "Ödendi" if ode else "Ödenmedi"
                        yeni = {"Ad Soyad": ad, "Paket (Ders)": ilk, "Kalan Ders": ilk, "Son Islem": "-", "Durum": "Aktif", "Odeme Durumu": durum}
                        df_main = pd.concat([df_main, pd.DataFrame([yeni])], ignore_index=True)
                        save_data(df_main, "Ogrenci_Data")
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), ad, "YENİ KAYIT", f"{ilk} Ders"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                        if ode: append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), ad, float(tut), "İlk Kayıt"], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
                        st.success("Kaydedildi"); st.rerun()
                    else: st.error("İsim hatası")
        with t3: st.dataframe(df_main)
    else: st.dataframe(df_main[["Ad Soyad", "Kalan Ders", "Durum", "Odeme Durumu"]])

# --- YOKLAMA (YENİ GÖRSEL ÇUBUKLU VERSİYON!) ---
elif menu == "🏠 Yoklama":
    c1,c2 = st.columns([2,1])
    with c1:
        aktif = df_main[df_main["Durum"]=="Aktif"]
        if not aktif.empty:
            sec = st.selectbox("Öğrenci Seç", aktif["Ad Soyad"].unique())
            idx = df_main[df_main["Ad Soyad"]==sec].index[0]
            kalan = int(df_main.at[idx, "Kalan Ders"])
            durum = df_main.at[idx, "Odeme Durumu"]
            
            # --- GÖRSEL ÇUBUK MANTIĞI ---
            # Renk Belirleme
            if kalan > 5: bar_color = "#4CAF50" # Yeşil
            elif kalan > 2: bar_color = "#FF9800" # Turuncu
            else: bar_color = "#FF5252" # Kırmızı
            
            # Genişlik Hesaplama (Maksimum 20 derslik bir görsel referans alalım)
            width_percent = min((kalan / 20) * 100, 100)
            if width_percent < 15 and kalan > 0: width_percent = 15 # Sayı görünsün diye min genişlik
            
            # Ödeme İkonu
            ode_ikon = "✅" if durum == "Ödendi" else "❌"

            st.markdown(f"""
            <h3>{sec} <span style="font-size:0.7em; color:{bar_color}">{ode_ikon} {durum}</span></h3>
            <div class="progress-container">
                <div class="progress-bar" style="width: {width_percent}%; background-color: {bar_color};">
                    {kalan} Ders Kaldı
                </div>
            </div>
            """, unsafe_allow_html=True)
            # ---------------------------
            
            if IS_ADMIN:
                if durum != "Ödendi":
                    with st.expander("💰 BORÇ KAPAT"):
                        with st.form("borc"):
                            t = st.number_input("Tutar", 0.0, step=100.0)
                            if st.form_submit_button("KAPAT"):
                                df_main.at[idx, "Odeme Durumu"] = "Ödendi"
                                save_data(df_main, "Ogrenci_Data")
                                append_data([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m"), sec, float(t), "Borç"], "Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
                                st.rerun()
                ca, cb = st.columns(2)
                if ca.button("🎾 DERS İŞLENDİ (-1)", type="primary"):
                    if kalan>0:
                        df_main.at[idx,"Kalan Ders"] -= 1
                        df_main.at[idx,"Son Islem"] = datetime.now().strftime("%d-%m %H:%M")
                        save_data(df_main,"Ogrenci_Data")
                        append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "DERS DÜŞÜLDÜ", f"Kalan: {kalan-1}"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                        st.rerun()
                if cb.button("↩️ GERİ AL"):
                    df_main.at[idx,"Kalan Ders"] += 1
                    save_data(df_main,"Ogrenci_Data")
                    append_data([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%H:%M"), sec, "GERİ ALINDI", "Hata"], "Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
                    st.rerun()
    with c2:
        st.markdown("### ⚡ Son İşlemler")
        st.dataframe(get_data_cached("Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"]).tail(10).iloc[::-1], hide_index=True)

elif menu == "💸 Finans":
    if IS_ADMIN:
        df = get_data_cached("Finans_Kasa", ["Tarih", "Ay", "Ogrenci", "Tutar", "Not"])
        df["Tutar"] = pd.to_numeric(df["Tutar"], errors='coerce').fillna(0)
        c1,c2 = st.columns(2)
        c1.metric("Bu Ay", f"{df[df['Ay']==datetime.now().strftime('%Y-%m')]['Tutar'].sum():,.0f} TL")
        c2.metric("Toplam", f"{df['Tutar'].sum():,.0f} TL")
        t1, t2 = st.tabs(["📊 Grafik", "🧾 Liste"])
        with t1:
            cg1, cg2 = st.columns(2)
            cg1.plotly_chart(px.bar(df.groupby("Ay")["Tutar"].sum().reset_index(), x="Ay", y="Tutar"), use_container_width=True)
            cg2.plotly_chart(px.pie(df.groupby("Ogrenci")["Tutar"].sum().reset_index(), values="Tutar", names="Ogrenci"), use_container_width=True)
        with t2: st.dataframe(df.sort_index(ascending=False), use_container_width=True)
    else: st.error("Yetkisiz")

elif menu == "📝 Log Merkezi":
    st.subheader("📝 Loglar")
    loglar = get_data_cached("Ders_Gecmisi", ["Tarih", "Saat", "Ogrenci", "Islem", "Detay"])
    kisi = st.selectbox("Filtrele", ["Tümü"] + list(df_main["Ad Soyad"].unique()))
    if kisi != "Tümü": loglar = loglar[loglar["Ogrenci"]==kisi]
    st.dataframe(loglar.sort_index(ascending=False), use_container_width=True, height=600)
