import requests
from bs4 import BeautifulSoup
import re
from pprint import pprint # Import pprint เพื่อให้ print Dict/List สวยงาม

def fetch_word(word: str) -> BeautifulSoup | None:
    """
    ดึงหน้า HTML ของคำที่ค้นหาและแปลงเป็น BeautifulSoup object
    """
    url = f"https://dict.longdo.com/mobile.php?search={word}"
    try:
        response = requests.get(url, timeout=5)
        response.encoding = 'utf-8'
        response.raise_for_status() # เช็คว่า request สำเร็จ (HTTP 200)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
        
    except requests.exceptions.RequestException as e:
        print(f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")
        return None

def parse_data(soup: BeautifulSoup) -> dict:
    """
    สกัดข้อมูลคำแปลและตัวอย่างประโยคจาก soup
    """
    results = {
        "translations": [],
        "examples": []
    }

    # --- ### นี่คือส่วนที่แก้ไข ### ---
    # 1. กำหนดชื่อ Dictionary ที่เราต้องการดึงข้อมูลเท่านั้น
    target_dict_names = [
        'NECTEC Lexitron Dictionary EN-TH',
        'Nontri Dictionary'
    ]
    
    print("--- กำลังดึงข้อมูลจาก Dictionary ที่ระบุ ---")
    
    for dict_name in target_dict_names:
        # 2. ค้นหา <b> ด้วยชื่อที่ตรงกันเป๊ะๆ
        header = soup.find('b', string=dict_name)
        
        if header:
            print(f"  [✓] พบ Section: {dict_name}")
            table = header.find_next_sibling('table', class_='result-table')
        
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        word = cells[0].get_text(strip=True, separator=' ')
                        definition_raw = cells[1].get_text(strip=True, separator=' ')
                        
                        pos = "N/A"
                        translation = definition_raw
                        
                        match = re.match(r'\s*\((.*?)\)\s*(.*)', definition_raw, re.DOTALL)
                        
                        if match:
                            pos = match.group(1).strip()
                            translation = match.group(2).strip()
                            
                            # (โค้ดจัดการ pos ที่ซับซ้อน เช่น (ยัวร์) pron. ... )
                            translation_match = re.match(r'^(pron|adj|det|n|v|adv|int|conj)\.?(.*)', translation, re.IGNORECASE | re.DOTALL)
                            if translation_match:
                                pos = translation_match.group(1).strip('.')
                                translation = translation_match.group(2).strip()
                        
                        results["translations"].append({
                            "dictionary": dict_name,
                            "word": word,
                            "pos": pos,
                            "translation": translation
                        })
            else:
                print(f"  [!] ไม่พบตาราง (table) สำหรับ {dict_name}")
        else:
            print(f"  [X] ไม่พบ Section: {dict_name}")

    # --- จบส่วนที่แก้ไข ---


    # --- ส่วนที่ 2: ค้นหาตัวอย่างประโยค (ยังคงทำงานเหมือนเดิม) ---
    string_element = soup.find(string=re.compile(r'^\s*ตัวอย่างประโยคจาก Open Subtitles'))
    table = None

    if string_element:
        header = string_element.parent
        if hasattr(header, 'find_next_sibling'):
            table = header.find_next_sibling('table', class_='result-table')

    if table:
        rows = table.find_all('tr')
        for i, row in enumerate(rows):
            sentence_parts = row.find_all('font', color='black')
            if len(sentence_parts) == 2:
                eng_sentence = sentence_parts[0].get_text(strip=True, separator=' ')
                thai_sentence = sentence_parts[1].get_text(strip=True, separator=' ')
                
                results["examples"].append({
                    "en": eng_sentence,
                    "th": thai_sentence
                })

    return results

# --- ส่วนหลักในการรันโปรแกรม ---
if __name__ == "__main__":
    
    search_word = "what"
    print(f"กำลังค้นหาคำว่า: {search_word}\n")
    
    main_soup = fetch_word(search_word)
    
    if main_soup:
        data = parse_data(main_soup)
        
        print("\n--- ผลลัพธ์ (รูปแบบข้อมูล) ---")
        pprint(data)
        
        print(f"\n--- สรุปคำแปล ---")
        if data['translations']:
            for item in data['translations']:
                if item['word'].lower() == search_word:
                    print(f"[{item['pos']}] {item['translation']}  ({item['dictionary']})")
        else:
            print("(ไม่พบคำแปลจาก Dictionary ที่ระบุ)")

        print(f"\n--- สรุปตัวอย่างประโยค ---")
        if data['examples']:
            for i, item in enumerate(data['examples']):
                 print(f"{i+1}. {item['en']}\n   -> {item['th']}\n")
        else:
            print("(ไม่พบตัวอย่างประโยค)")
    else:
        print("ไม่สามารถดึงข้อมูลได้")