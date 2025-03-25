import os
import json
import logging
import datetime
import re
import argparse
from pathlib import Path
import ollama
from ollama._types import ListResponse

class TranslationMaster:
    def __init__(self, model_name: str = "deepseek-r1:8b", logging_path: str = None):
        self.model_name = model_name
        # Use a provided logging directory or the current directory for logs
        self.logging_path = logging_path if logging_path else os.getcwd()

        # Create the logging directory if it doesn't exist
        Path(self.logging_path).mkdir(parents=True, exist_ok=True)

        self.setup_logging()

    def setup_logging(self):
        # Get current date for the log filename
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        # Find existing log files with today's date in the logging path
        log_files = [f for f in os.listdir(self.logging_path) if f.endswith(".log") and date in f]
        count = len(log_files)
        log_file = f"translation_run_{date}_{count}.log" if count > 0 else f"translation_run_{date}.log"
        log_file = os.path.join(self.logging_path, log_file)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_run_directory(self, language: str, output_dir: str, output_dir_name: str = None) -> str:
        """
        Creates a run directory under the specified output directory.
        The directory name follows the pattern:
          {current_date}/{language}_{run_count}
        """
        # Ensure the output directory exists; if not, create it.
        if not os.path.exists(output_dir):
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Use output_dir_name if provided; otherwise use the input directory's basename.
        base_dir_name = output_dir_name if output_dir_name else os.path.basename(language)

        # Look for existing run directories in output_dir with the same prefix.
        existing_runs = [d for d in os.listdir(output_dir)
                         if d.startswith(f"run_{base_dir_name}_") 
                         and os.path.isdir(os.path.join(output_dir, d))]

        run_count = len(existing_runs) + 1
        run_dir_name = f"run_{base_dir_name}_{run_count}"
        run_dir_path = os.path.join(output_dir, run_dir_name)
        Path(run_dir_path).mkdir(parents=True, exist_ok=True)
        return run_dir_path

    def prompt_ai(self, content: str, target_language: str) -> str:
        """
        Constructs a prompt and calls the translation model.
        The prompt instructs the AI to translate the text while preserving formatting.
        """
        prompt = f"""
{content}
        You are a professional translation AI with expertise in technical texts and code files.
Your task is to translate the human-readable, natural language text in the file below into {target_language} while preserving its exact formatting, including line breaks, indentation, and spacing.
Important:
- Translate only user-facing strings, labels, messages, and display text.
- Only translate file path or import statements if they mention a wrong language code, you update the code to the one of target language.
- Ensure that the translated output fits exactly into the original file structure so that it remains a valid code file.
- Do not include any additional commentary or explanations.

"""
        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        content_response = response["message"]["content"]
        # Remove any tags that the model might include
        content_response = re.sub(r"<[^>]*>", "", content_response)
        # Remove ``` from the start and end of the response (if any)
        content_response = re.sub(r"^```", "", content_response)
        # Remove everything between <think> and </think> tags
        content_response = re.sub(r"<think>.*?</think>", "", content_response, flags=re.DOTALL)

        # Remove any extra newlines at the end
        content_response = content_response.strip()
        return content_response

    def get_all_files(self, input_dir: str):
        """
        Recursively walks through the input directory and returns a list of tuples:
        (relative_file_path, absolute_file_path)
        """
        file_list = []
        for root, _, files in os.walk(input_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, input_dir)
                file_list.append((rel_path, abs_path))
        return file_list

    def replace_language_in_filename(self, filename: str, target_lang: str) -> str:
        """
        Replace any occurrence of an ISO language code in the filename with target_lang.
        Searches for a pattern like '_{code}' where code is 2 to 3 letters, either followed by an underscore or at the end.
        If no such pattern is found, appends _<target_lang> before the extension.
        """
        name, ext = os.path.splitext(filename)
        pattern = re.compile(r"_[a-zA-Z]{2,3}(?=(_|$))")
        if pattern.search(name):
            # Replace only the first occurrence of the language code pattern with the target language.
            new_name = pattern.sub(f"_{target_lang}", name, count=1) + ext
        else:
            new_name = f"{name}_{target_lang}{ext}"
        return new_name

    def save_translation(self, run_dir: str, rel_file_path: str, translated_text: str, target_lang: str):
        """
        Saves the translated text to the run directory while preserving the relative path.
        The file is renamed to include the new language code.
        If a file with the new name already exists, appends a counter to avoid overwriting.
        """
        original_dir, original_file = os.path.split(rel_file_path)
        new_filename = self.replace_language_in_filename(original_file, target_lang)
        output_subdir = os.path.join(run_dir, original_dir)
        Path(output_subdir).mkdir(parents=True, exist_ok=True)

        output_file_path = os.path.join(output_subdir, new_filename)
        base_name, ext = os.path.splitext(new_filename)
        counter = 1
        while os.path.exists(output_file_path):
            output_file_path = os.path.join(output_subdir, f"{base_name}_{counter}{ext}")
            counter += 1

        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(translated_text)
        self.logger.info(f"Saved translated file to {output_file_path}")

    def start_translating(self, input_dir: str, output_dir: str, target_language: str, output_dir_name: str = None):
        self.logger.info(f"Starting translation for files in '{input_dir}' to language '{target_language}'")
        run_dir = self.create_run_directory(target_language, output_dir, output_dir_name)
        self.logger.info(f"Output will be saved to: {run_dir}")
        all_files = self.get_all_files(input_dir)
        all_content = []
        last_path = None
        for rel_path, abs_path in all_files:
            self.logger.info(f"Translating file: {rel_path}")
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    all_content.append(content)
                last_path = rel_path
            except Exception as e:
                self.logger.error(f"Failed to read file {abs_path}: {str(e)}")
                continue

        translated_text = self.prompt_ai(all_content, target_language)
        self.save_translation(run_dir, last_path, translated_text, target_language)
        self.logger.info("Translation complete")

def ask_for_language() -> str:
    while True:
        language = input("Enter the target language (ISO alpha-2 code or language name): ").strip()
        if len(language) < 2:
            print("Please enter a valid language code or name.")
            continue
        return language

def ask_for_input_dir() -> str:
    while True:
        input_dir = input("Enter the input directory to translate: ").strip()
        if not os.path.isdir(input_dir):
            print("Please enter a valid directory path.")
            continue
        return input_dir

def pull_model(model_name: str):
    print(f"Model '{model}' not found. Pulling the model...")
    try:
        ollama.pull(model)
        print("Model pulled successfully.")
    except Exception as e:
        # Does the model exist?
        print(f"Failed to pull model '{model}': {str(e)}")
        print("Does the model exist? Make sure the model name is correct.")
        print("Current installed models:")
        model_list: ListResponse = ollama.list()
        models = model_list["models"]
        available_models = [model["model"] for model in models]
        print(json.dumps(available_models, indent=2))
        exit(1)

def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", help="The target language for translation", type=str, required=False)
    parser.add_argument("--input_dir", help="The input directory to translate", type=str, required=False)
    parser.add_argument("--output_dir", help="The base output directory to save translations", type=str, required=False)
    parser.add_argument("--output_dir_name", help="Optional: custom name for the output run directory", type=str, required=False)
    parser.add_argument("--model", help="The model name to use for translation", type=str, required=False)
    parser.add_argument("--logging_path", help="The directory to save log files", type=str, required=False)
    parser.add_argument("--pull", help="Automatically pull the model if not installed", action="store_true", required=False)
    args = parser.parse_args()

    language = args.language if args.language else ask_for_language()
    input_dir = args.input_dir if args.input_dir else ask_for_input_dir()
    # Default to a directory named "output" in the current working directory if not provided.
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    output_dir = args.output_dir if args.output_dir else os.path.join(os.getcwd(), "output", date)
    output_dir_name = args.output_dir_name if args.output_dir_name else None
    model = args.model if args.model else "gemma3:1b"
    logging_path = args.logging_path if args.logging_path else os.getcwd() + "/logs"

    return language, input_dir, output_dir, output_dir_name, model, logging_path, args.pull

if __name__ == "__main__":
    target_language, input_dir, output_dir, output_dir_name, model, logging_path, auto_pull = get_arguments()

    if len(target_language) < 2:
        print("Please enter a valid language code or name.")
        exit(1)

    # Check if the model is available
    model_list: ListResponse = ollama.list()
    models = model_list["models"]
    available_models = [model["model"] for model in models]

    if model not in available_models:
        if auto_pull:
            pull_model(model)
        else:
            print(f"Model '{model}' is not installed. Please choose from the following models:")
            print(json.dumps(available_models, indent=2))
            print(f"Run 'ollama pull {model}' to install new models. Or pass the '--pull' flag to automatically install the model.")
            exit(1)

    master = TranslationMaster(model_name=model, logging_path=logging_path)
    master.start_translating(input_dir, output_dir, target_language, output_dir_name)
    print("Processing complete. Check the output directory and logs for details.")
