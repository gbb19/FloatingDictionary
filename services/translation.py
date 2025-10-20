"""
Handles fetching translation data from external services (Longdo, Google Translate).
"""
import asyncio
import re
import requests
from bs4 import BeautifulSoup
from googletrans import Translator

# --- Google Translate ---

async def async_translate(text, dest_lang, src_lang):
    """Async function for Google Translate."""
    translator = Translator()
    try:
        result = await translator.translate(text, src=src_lang, dest=dest_lang)
        return result
    except Exception as e:
        print(f"Google Translate Error: {e}")
        return f"Google Error: {e}"

def get_google_translation_sync(text, dest_lang, src_lang='auto'):
    """Wrapper to run async_translate in a new event loop for synchronous calls."""
    loop = None
    try:
        # Create and manage a new event loop for this synchronous function call
        # to avoid conflicts with other running asyncio loops.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(async_translate(text, dest_lang, src_lang))
        return result
    except Exception as e:
        print(f"Sync/Async Loop Error: {e}")
        return f"Sync Error: {e}"
    finally:
        if loop:
            loop.close()

# --- Longdo Dictionary Scraper (EN-TH only) ---

def fetch_longdo_word(word: str) -> BeautifulSoup | None:
    """Fetches the word definition page from Longdo and returns a BeautifulSoup object."""
    url = f"https://dict.longdo.com/mobile.php?search={word}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'utf-8'
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Longdo: {e}")
        return None

def parse_longdo_data(soup: BeautifulSoup) -> dict:
    """Parses translation and example data from the Longdo BeautifulSoup object."""
    results = {"translations": [], "examples": []}
    target_dict_names = [
        'NECTEC Lexitron Dictionary EN-TH',
        'Nontri Dictionary'
    ]
    
    for dict_name in target_dict_names:
        header = soup.find('b', string=dict_name)
        if header:
            table = header.find_next_sibling('table', class_='result-table')
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        word = cells[0].get_text(strip=True)
                        definition_raw = cells[1].get_text(strip=True, separator=' ')
                        
                        pos = "N/A"
                        translation = definition_raw
                        # Attempt to parse part-of-speech and the definition separately
                        match = re.match(r'\s*\((.*?)\)\s*(.*)', definition_raw, re.DOTALL)
                        
                        if match:
                            pos = match.group(1).strip()
                            translation = match.group(2).strip()
                            # Sometimes the POS is also in the translation text, try to extract it.
                            translation_match = re.match(r'^(pron|adj|det|n|v|adv|int|conj)\.?(.*)', translation, re.IGNORECASE | re.DOTALL)
                            if translation_match:
                                pos = translation_match.group(1).strip('.')
                                translation = translation_match.group(2).strip()
                        
                        # Fix common OCR/scraping errors
                        translation = translation.replace("your self", "yourself").replace("your selves", "yourselves")

                        results["translations"].append({
                            "dictionary": dict_name.replace("NECTEC Lexitron Dictionary EN-TH", "NECTEC"),
                            "word": word,
                            "pos": pos,
                            "translation": translation
                        })

    # Find the table for example sentences. The header text is in Thai.
    string_element = soup.find(string=re.compile(r'^\s*ตัวอย่างประโยคจาก Open Subtitles'))
    table = None
    if string_element:
        header = string_element.parent
        if hasattr(header, 'find_next_sibling'):
            table = header.find_next_sibling('table', class_='result-table')

    if table:
        rows = table.find_all('tr')
        for row in rows:
            sentence_parts = row.find_all('font', color='black')
            if len(sentence_parts) == 2:
                eng_sentence = sentence_parts[0].get_text(strip=True, separator=' ')
                thai_sentence = sentence_parts[1].get_text(strip=True, separator=' ')
                results["examples"].append({"en": eng_sentence, "th": thai_sentence})

    return results