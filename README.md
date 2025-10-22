# Floating Dictionary

A dictionary application for Windows that allows you to quickly translate words on your screen. Just point your mouse at a word and press a hotkey.

  <!-- You can capture a screenshot of the program and upload it to get a URL to place here -->

## ✨ Features

- **Instant Translation**: Point your mouse at a word on the screen and press `Ctrl+Alt+D`.
- **Multiple Sources**: Fetches translations from Longdo Dictionary (NECTEC Lexitron, Nontri) and Google Translate.
- **Sentence Translation**: Press `Ctrl+Alt+S` to enter area selection mode, allowing you to select multiple words to form a sentence for translation.
- **Example Sentences**: Displays example sentences from Longdo (if available).
- **Runs in the Background**: The application runs in the System Tray and only appears when invoked.
- **User-Friendly UI**: Shows a flashing red border around the word being translated and displays the results in a beautiful, scrollable tooltip.

---

## ⚙️ Prerequisites

Before you can run this program, you need to install **Tesseract OCR**.

1.  Download Tesseract OCR for Windows from **here (UB-Mannheim builds)**.

    - It is recommended to download the `tesseract-ocr-w64-setup-v5.x.x.exe` file.

2.  **Most Important Step:** After installation, go to the Tesseract installation folder (usually `C:\Program Files\Tesseract-OCR`).

3.  **Copy** the entire `Tesseract-OCR` folder and **Paste** it into the root folder of this project. The final project structure should look like this:

    ```
    FloatingDictionary/
    ├── Tesseract-OCR/   <-- The folder you just copied
    │   ├── tessdata/
    │   ├── tesseract.exe
    │   └── ... (ไฟล์อื่นๆ)
    ├── main.py
    ├── services/
    └── ... (other project files)
    ```

> This step is necessary to ensure the program can always find Tesseract, especially when it is packaged into an `.exe` file in the future.

---

## 🚀 Installation

1.  Clone this repository or download all the code to your machine.

2.  (Recommended) Create and activate a Python Virtual Environment:

    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  Install all necessary libraries via the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

---

## 🏃‍♂️ Usage

1.  Run the program via the `main.py` file:

    ```bash
    python main.py
    ```

2.  The program will display a message indicating it is ready, and an icon will appear in the System Tray (bottom right corner of the screen).

3.  **Using Hotkeys:**
    - `Ctrl + Alt + D`: Capture and translate the word under the mouse cursor.
    - `Ctrl + Alt + S`: Enter area selection mode to translate a sentence.
    - `Esc`: Cancel selection or hide the translation window.
    - `Ctrl + Alt + Q`: Exit the entire program.

---

## Building

To build the application into a single executable:

```bash
pyinstaller --name "FloatingDictionary" --noconsole --windowed --add-data "Tesseract-OCR;Tesseract-OCR" main.py
```
