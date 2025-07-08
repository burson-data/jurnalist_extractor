import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from newspaper import Article
import time
from io import BytesIO
import re

# Konfigurasi halaman
st.set_page_config(
page_title="News Journalist Extractor",
page_icon="📰",
layout="wide"
)

st.title("📰 News Journalist Extractor")
st.markdown("Upload file Excel berisi link berita untuk mengekstrak nama jurnalis secara otomatis")

# Fungsi untuk ekstrak jurnalis menggunakan newspaper
def extract_with_newspaper(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        
        # Coba ambil author dari newspaper
        authors = article.authors
        if authors:
            return ", ".join(authors)
        return None
    except Exception as e:
        st.write(f"Newspaper error for {url}: {str(e)}")
        return None

# Fungsi untuk ekstrak jurnalis menggunakan BeautifulSoup
def extract_with_bs4(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Daftar selector umum untuk nama jurnalis
        selectors = [
            # Kompas
            '.read__author .link-black',
            '.read__author a',
            
            # Detik
            '.detail__author',
            '.author a',
            
            # CNN Indonesia
            '.author-name',
            
            # Tempo
            '.author',
            
            # Liputan6
            '.author-name',
            
            # Umum
            '[rel="author"]',
            '.byline',
            '.author',
            '.writer',
            '.reporter',
            '[class*="author"]',
            '[class*="writer"]',
            '[class*="reporter"]',
            '[class*="byline"]'
        ]
        
        # Coba setiap selector
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if text and len(text) > 2 and len(text) < 100:
                    # Bersihkan teks
                    text = re.sub(r'^(oleh|by|author|penulis)[\s:]*', '', text, flags=re.IGNORECASE)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if text:
                        return text
        
        # Coba cari dalam meta tags
        meta_selectors = [
            'meta[name="author"]',
            'meta[property="article:author"]',
            'meta[name="byl"]'
        ]
        
        for selector in meta_selectors:
            meta = soup.select_one(selector)
            if meta and meta.get('content'):
                return meta.get('content').strip()
        
        return None
        
    except Exception as e:
        st.write(f"BS4 error for {url}: {str(e)}")
        return None

# Fungsi utama untuk ekstrak jurnalis
def extract_journalist(url):
    if not url or pd.isna(url):
        return "URL kosong"

    # Coba dengan newspaper terlebih dahulu
    journalist = extract_with_newspaper(url)

    # Jika gagal, coba dengan BeautifulSoup
    if not journalist:
        journalist = extract_with_bs4(url)

    return journalist if journalist else "Tidak ditemukan"

# Upload file
uploaded_file = st.file_uploader(
"Upload file Excel (.xlsx atau .xls)", 
type=['xlsx', 'xls'],
help="File harus memiliki kolom yang berisi link berita"
)

if uploaded_file is not None:
    try:
        # Baca file Excel
        df = pd.read_excel(uploaded_file)
        
        st.subheader("Preview Data")
        st.dataframe(df.head())
        
        # Pilih kolom yang berisi link
        link_columns = [col for col in df.columns if 'link' in col.lower() or 'url' in col.lower()]
        
        if not link_columns:
            link_columns = df.columns.tolist()
        
        selected_column = st.selectbox(
            "Pilih kolom yang berisi link berita:",
            options=df.columns.tolist(),
            index=df.columns.tolist().index(link_columns[0]) if link_columns else 0
        )
        
        # Nama kolom untuk hasil
        result_column = st.text_input(
            "Nama kolom untuk hasil jurnalis:",
            value="Nama_Jurnalis"
        )
        
        # Opsi untuk memproses sebagian data (untuk testing)
        max_rows = st.number_input(
            "Maksimal baris yang diproses (0 = semua):",
            min_value=0,
            max_value=len(df),
            value=min(10, len(df)),
            help="Gunakan nilai kecil untuk testing terlebih dahulu"
        )
        
        if st.button("🚀 Mulai Ekstraksi", type="primary"):
            # Tentukan jumlah baris yang akan diproses
            rows_to_process = len(df) if max_rows == 0 else min(max_rows, len(df))
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Kolom untuk hasil
            results = []
            
            # Proses setiap link
            for i in range(rows_to_process):
                url = df.iloc[i][selected_column]
                
                # Update status
                status_text.text(f"Memproses {i+1}/{rows_to_process}: {url}")
                
                # Ekstrak jurnalis
                journalist = extract_journalist(url)
                results.append(journalist)
                
                # Update progress
                progress_bar.progress((i + 1) / rows_to_process)
                
                # Delay untuk menghindari rate limiting
                time.sleep(0.5)
            
            # Tambahkan hasil ke dataframe
            df_result = df.copy()
            df_result[result_column] = results + [""] * (len(df) - len(results))
            
            status_text.text("✅ Ekstraksi selesai!")
            
            # Tampilkan hasil
            st.subheader("Hasil Ekstraksi")
            st.dataframe(df_result)
            
            # Statistik hasil
            col1, col2, col3 = st.columns(3)
            with col1:
                found_count = sum(1 for r in results if r not in ["Tidak ditemukan", "URL kosong", ""])
                st.metric("Berhasil Ditemukan", found_count)
            with col2:
                not_found_count = sum(1 for r in results if r == "Tidak ditemukan")
                st.metric("Tidak Ditemukan", not_found_count)
            with col3:
                error_count = sum(1 for r in results if r in ["URL kosong", ""])
                st.metric("Error/Kosong", error_count)
            
            # Download hasil
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_result.to_excel(writer, index=False, sheet_name='Hasil')
            
            st.download_button(
                label="📥 Download Hasil Excel",
                data=output.getvalue(),
                file_name=f"hasil_ekstraksi_jurnalis_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    except Exception as e:
        st.error(f"Error membaca file: {str(e)}")

# Sidebar dengan informasi
with st.sidebar:
    st.markdown("### 📋 Cara Penggunaan")
    st.markdown("""
    1. Upload file Excel yang berisi link berita
    2. Pilih kolom yang berisi link berita
    3. Tentukan nama kolom untuk hasil
    4. Mulai ekstraksi
    5. Download hasil
    """)

    st.markdown("### 🎯 Website yang Didukung")
    st.markdown("""
    - Kompas.com
    - Detik.com  
    - CNN Indonesia
    - Tempo.co
    - Liputan6.com
    - Dan website berita lainnya
    """)

    st.markdown("### ⚙️ Teknologi")
    st.markdown("""
    - **Newspaper3k**: Ekstraksi otomatis
    - **BeautifulSoup**: Fallback parsing
    - **Streamlit**: Interface web
    """)

    # Footer
    st.markdown("---")
    st.markdown("Made with ❤️ using Streamlit | © 2025")