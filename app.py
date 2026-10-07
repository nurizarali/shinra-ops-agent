import os
import streamlit as st
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="SHINRA OPS Multi-Agent Network",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ SHINRA OPS — Otonom Ajan Ağ Paneli")
st.markdown("---")

# --- API VE GÜVENLİK KONTROLÜ ---
openai_api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    st.error("⚠️ OpenAI API anahtarı bulunamadı! Lütfen Streamlit Secrets ayarlarından tanımlayın.")
    st.stop()

client = OpenAI(api_key=openai_api_key)

# Shinra OPS Klasör ID'si (Context Baseline'dan)
SHINRA_OPS_FOLDER_ID = "14KCNmz6E7zB0qmhvdmAkSRSFEwC9Lin9"

# Google Drive ve Sheets Servis Kurulumu
def get_services():
    try:
        gcp_creds = st.secrets.get("gcp_service_account")
        if not gcp_creds:
            return None, None
        creds_dict = dict(gcp_creds)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
        )
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        return drive_service, sheets_service
    except Exception as e:
        st.warning(f"Google servis bağlantı uyarısı: {e}")
        return None, None

# Master Tablo Bulma veya Oluşturma Fonksiyonu
def get_or_create_master_sheet(drive_service, sheets_service):
    sheet_name = "SHINRA_OPS_Master_Takip"
    try:
        # Klasör içinde bu isimde dosya var mı arayalım
        query = f"trashed = false and name = '{sheet_name}' and '{SHINRA_OPS_FOLDER_ID}' in parents"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
        else:
            # Yoksa 3 sekmeli yeni bir e-tablo oluşturalım
            spreadsheet_body = {
                'properties': {'title': sheet_name},
                'sheets': [
                    {'properties': {'title': 'Yeni Konular'}},
                    {'properties': {'title': 'Devam Edenler'}},
                    {'properties': {'title': 'Kapananlar'}}
                ]
            }
            spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet_body, fields='spreadsheetId').execute()
            sheet_id = spreadsheet.get('spreadsheetId')
            
            # Dosyayı doğrudan Shinra OPS klasörüne taşıyalım
            file = drive_service.files().get(fileId=sheet_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents'))
            drive_service.files().update(
                fileId=sheet_id,
                addParents=SHINRA_OPS_FOLDER_ID,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            
            # Sekmelere başlık satırları atalım
            header_body = {'values': [['Tarih', 'Konu / Girdi', 'Ajan Sentez Raporu', 'Durum']]}
            for tab_name in ['Yeni Konular', 'Devam Edenler', 'Kapananlar']:
                sheets_service.spreadsheets().values().append(
                    spreadsheetId=sheet_id,
                    range=f"{tab_name}!A1",
                    valueInputOption="RAW",
                    body=header_body
                ).execute()
                
            return sheet_id
    except Exception as e:
        st.error(f"Master tablo yönetilirken hata oluştu: {e}")
        return None

# --- SIDEBAR: KURUMSAL BAĞLAM ---
with st.sidebar:
    st.header("🗂️ Kurumsal Bağlam")
    st.markdown("**Aktif Pilot:** Petrol Ofisi / Lena Accredit")
    st.markdown("**Mimari:** Çözüm Ortaklığı Modeli")
    st.markdown("**Ajanlar:** SPARKLE, SHINRA, ATLAS, GUARDIAN")
    
    drive_service, sheets_service = get_services()
    if drive_service and sheets_service:
        st.success("🟢 Google Drive & Sheets Aktif")
    else:
        st.warning("🟡 Servis Bağlantısı Bekleniyor")

# --- AJAN AKIŞ ALANI ---
st.subheader("💬 Ajanlar Arası Müzakere ve Çözüm Konsolü")

user_input = st.text_area(
    "Çözülmesini istediğiniz operasyonel problemi veya görevi girin:",
    placeholder="Örn: Yüklenici akreditasyon süreçlerindeki darboğazı inceleyin ve çözüm önerin..."
)

# Konunun durumunu seçme alanı (Hangi sekmeye gideceğini belirler)
status_choice = st.selectbox(
    "Konunun İş Akış Durumu (Master Tabloda Kaydedileceği Sekme):",
    ["Yeni Konular", "Devam Edenler", "Kapananlar"]
)

if st.button("🚀 Ajan Ağını Çalıştır ve Master Tabloyu Güncelle"):
    if user_input:
        with st.spinner("SPARKLE görevi karşılıyor; SHINRA, ATLAS ve GUARDIAN müzakere ediyor..."):
            
            try:
                # 1. LLM Çağrısı ile Ajan Sentezi
                prompt_system = (
                    "Sen SHINRA OPS otonom ajan ağının yöneticisisin. "
                    "Sistemde SPARKLE (İş Akışı), SHINRA (Stratejik Uyum), "
                    "ATLAS (Saha Güvenilirliği) ve GUARDIAN (Risk ve Yönetişim) rollerini koordine ediyorsun. "
                    "Kullanıcının girdisini bu perspektiflerden süzerek yapılandırılmış, çelişkileri giderilmiş "
                    "ve ortak bir çözüme ulaştırılmış detaylı bir Rapor sun."
                )
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt_system},
                        {"role": "user", "content": user_input}
                    ],
                    temperature=0.3
                )
                
                agent_output = response.choices[0].message.content
                
                # --- EKRANDA GÖSTERME ---
                st.markdown("### 📊 Sentezlenmiş Çözüm Raporu")
                st.info(f"**Girdi:** {user_input}")
                st.write(agent_output)
                
                # 2. Master Tabloya (Google Sheets) Kayıt
                if drive_service and sheets_service:
                    import datetime
                    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    master_sheet_id = get_or_create_master_sheet(drive_service, sheets_service)
                    if master_sheet_id:
                        row_data = [[current_date, user_input, agent_output, status_choice]]
                        sheets_service.spreadsheets().values().append(
                            spreadsheetId=master_sheet_id,
                            range=f"{status_choice}!A:D",
                            valueInputOption="USER_ENTERED",
                            body={'values': row_data}
                        ).execute()
                        
                        st.success(f"✅ Rapor ekranda sunuldu ve Shinra OPS klasöründeki master tabloya (**{status_choice}** sekmesine) başarıyla işlendi.")
                    else:
                        st.warning("⚠️ Master tablo oluşturulamadı veya bulunamadı.")
                else:
                    st.warning("⚠️ Google servisleri aktif olmadığı için tablo güncellenemedi.")
                
            except Exception as e:
                st.error(f"Ajan ağı çalıştırılırken bir hata oluştu: {e}")
                
    else:
        st.warning("Lütfen bir görev veya problem girin.")
