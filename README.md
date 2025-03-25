# Translation Master

Translation Master is a Python tool designed to translate technical text and code files into a target language while preserving the original formatting. It leverages the [ollama](https://github.com/ollama) API for AI-powered translations, ensuring that the integrity of code files is maintained.

## Features

- **Precise Translation:** Translates only user-facing text (labels, messages, etc.) while preserving code structure.
- **Batch Processing:** Recursively processes all files in the input directory.
- **Customizable Output:** Saves translations into a dedicated run directory with unique naming.
- **Logging:** Detailed logging to both console and file for troubleshooting.
- **Model Management:** Automatically pulls the specified translation model if it isn’t already installed.

## Requirements

- Python 3.7 or higher
- [ollama](https://github.com/ollama) Python package

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/translation-master.git
   cd translation-master
   ```

2. **Create a Virtual Environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install the Required Packages:**

   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the Script

   ```bash
   python translation_master.py --input_dir <input_dir> --output_dir <output_dir> --model <model> --language <language>
   ```

### Arguments

- `--help`: Show the help message containing the list of arguments.
- `--input_dir`: Path to the directory containing the files to be translated.
- `--output_dir`: Path to the directory where the translated files will be saved.
- `--model`: The translation model to be used 'gemma3:1b', 'deepseek-r1:8b', etc.
- `--language`: The target language for the translation (e.g., 'fr', 'de', 'es', or full names 'french', 'german', etc.).
- `--output_dir_name`: Optional. Name of the output directory. Default is 'date'.
- `--logging_path`: Optional. Path to the log file. Default is './logs'.
- `--pull`: Optional. Pull the specified model if it isn’t already installed.

## Contributing

Contributions are welcome! No need for a formal setup, just fork the repository, make your changes, and submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

