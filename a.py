import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pdfkit
import os
from urllib.parse import urljoin

async def fetch_html(session, url):
    try:
        async with session.get(url) as response:
            response.raise_for_status()  # HTTP hatalarını yakala
            return await response.text()
    except Exception as e:
        print(f"'{url}' adresinden HTML içeriği çekilirken hata oluştu: {e}")
        return None

async def html_to_pdf_async(session, url, output_filename):
    try:
        html = await fetch_html(session, url)
        if html:
            # wkhtmltopdf'i asyncio ile uyumlu hale getir (subprocess kullan)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: pdfkit.from_string(html, output_filename))
            print(f"'{url}' başarıyla '{output_filename}' dosyasına kaydedildi.")
    except Exception as e:
        print(f"'{url}' PDF'e dönüştürülürken hata oluştu: {e}")

async def process_link(session, base_url, href, output_dir):
    if href.startswith(("/proje/", "/bilgibankasi/")):
        absolute_url = urljoin(base_url, href)
        output_filename = os.path.join(output_dir, href.replace("/", "_").replace(":", "_") + ".pdf")
        if not os.path.exists(output_filename): #zaten varsa tekrar etme
          await html_to_pdf_async(session, absolute_url, output_filename)

async def extract_links_and_save_as_pdf(base_url, output_dir="pdf_outputs"):
    try:
        async with aiohttp.ClientSession() as session:
            html_content = await fetch_html(session, base_url)
            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                links = soup.find_all('a', href=True)

                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)

                tasks = [process_link(session, base_url, link['href'], output_dir) for link in links]
                await asyncio.gather(*tasks)
    except Exception as e:
        print(f"Genel hata: {e}")

# Ana fonksiyon
async def main():
    base_url = "https://www.satso.org.tr"
    await extract_links_and_save_as_pdf(base_url)

# Programı çalıştır
if __name__ == "__main__":
    asyncio.run(main())