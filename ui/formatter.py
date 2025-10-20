"""
Formats the combined translation data into an HTML string for display in the tooltip.
"""

def format_combined_data(longdo_data: dict | None, google_translation: str, search_word: str) -> str:
    """
    Combines data from Longdo and Google Translate into a single formatted HTML string.
    """
    output_lines = []

    # 1. Search Term (Header)
    output_lines.append(f"<p style='font-size: 20pt; font-weight: bold; color: #ffffff; margin-bottom: 0px;'>{search_word}</p><hr style='margin: 2px 0 4px 0; border-color: #666;'>")
    
    # 2. Google Translate Section
    output_lines.append("<p style='font-size: 16pt; margin: 5px 0 2px 0;'><u><b>Google Translate:</b></u></p>")
    if google_translation and "Error" not in google_translation and google_translation.lower() != search_word.lower():
        output_lines.append(f"<p style='margin: 0;'>&#8226; {google_translation}</p>")
    else:
        output_lines.append(f"<p style='margin: 0;'><i>(Translation not available)</i></p>")
    
    # 3. Longdo Dict Section
    output_lines.append("<p style='font-size: 16pt; margin: 8px 0 2px 0;'><u><b>Longdo Dict:</b></u></p>")
    
    if longdo_data and longdo_data['translations']:
        for item in longdo_data['translations']:
            line = f"<p style='margin: 0 0 4px 0;'>&#8226; <b>{item['word']}</b> [{item['pos']}] {item['translation']} ({item['dictionary']})</p>"
            output_lines.append(line)
    elif longdo_data:
        output_lines.append("<p style='margin: 0;'><i>(No translation found)</i></p>")
    else:
        output_lines.append("<p style='margin: 0;'><i>(Connection failed)</i></p>")
    
    # 4. Examples Section
    if longdo_data and longdo_data['examples']:
        output_lines.append("<p style='font-size: 16pt; margin: 8px 0 2px 0;'><u><b>Example Sentences (Longdo):</b></u></p>")
        # Show up to 2 examples
        for ex in longdo_data['examples'][:2]: 
            output_lines.append(f"<p style='margin: 0 0 4px 0;'>&#8226; <i>EN:</i> {ex['en']}<br>  <i>&#8594; TH:</i> {ex['th']}</p>")
    
    return f"<div style='font-family: Segoe UI, Arial; font-size: 14pt; line-height: 1.4;'>{''.join(output_lines)}</div>"
