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
        """
        Initialize the TranslationMaster with a specific model and logging path.
        """
        self.model_name = model_name
        # Use provided logging directory or default to the current working directory.
        self.logging_path = logging_path if logging_path else os.getcwd()
        Path(self.logging_path).mkdir(parents=True, exist_ok=True)
        self.setup_logging()

    def setup_logging(self):
        """
        Sets up logging to both file and console.
        Log file names include the current date and a counter if multiple runs occur on the same day.
        """
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        log_files = [f for f in os.listdir(self.logging_path)
                     if f.endswith(".log") and date_str in f]
        count = len(log_files)
        log_filename = f"translation_run_{date_str}_{count}.log" if count > 0 else f"translation_run_{date_str}.log"
        log_path = os.path.join(self.logging_path, log_filename)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_run_directory(self, target_language: str, output_dir: str, output_dir_name: str = None) -> str:
        """
        Creates a unique run directory within the given output directory.
        Directory naming follows the pattern: run_{name}_{run_count}, where "name" is the target language or a custom name.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        run_name = output_dir_name if output_dir_name else target_language
        existing_runs = [
            d for d in os.listdir(output_dir)
            if d.startswith(f"run_{run_name}_") and os.path.isdir(os.path.join(output_dir, d))
        ]
        run_count = len(existing_runs) + 1
        run_dir = os.path.join(output_dir, f"run_{run_name}_{run_count}")
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        return run_dir

    def prompt_ai(self, content: str, target_language: str) -> str:
        """
        Constructs a prompt and calls the translation model.
        The prompt instructs the AI to translate the text while preserving formatting.
        """
        prompt = f"""
{content}
You are a professional translation AI with expertise in technical texts and code files.
Translate the above content into {target_language}, preserving its exact formatting (line breaks, indentation, and spacing).
Important:
- Translate only user-facing strings, labels, messages, and display text.
- Translate file path or import statements only if they include a language code error.
- Ensure the translated output remains a valid code file.
- Do not include additional commentary or explanations.
"""
        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        content_response = response["message"]["content"]
        # Clean up any extraneous tags or formatting added by the model.
        content_response = re.sub(r"<[^>]*>", "", content_response)
        content_response = re.sub(r"^```", "", content_response)
        content_response = re.sub(r"<think>.*?</think>", "", content_response, flags=re.DOTALL)
        return content_response.strip()

    def get_all_files(self, input_dir: str):
        """
        Recursively collects all files from the input directory.
        Returns a list of tuples: (relative_file_path, absolute_file_path)
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
        Replaces any occurrence of an ISO language code in the filename with the target language code.
        If no pattern is found, appends the target language code before the file extension.
        """
        name, ext = os.path.splitext(filename)
        pattern = re.compile(r"_[a-zA-Z]{2,3}(?=(_|$))")
        if pattern.search(name):
            new_name = pattern.sub(f"_{target_lang}", name, count=1) + ext
        else:
            new_name = f"{name}_{target_lang}{ext}"
        return new_name

    def save_translation(self, run_dir: str, rel_file_path: str, translated_text: str, target_lang: str):
        """
        Saves the translated text to the run directory while preserving the file’s relative path.
        The file name is modified to include the target language code.
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
        """
        Main routine: iterates over each file in the input directory,
        translates it using the AI model, and saves the translated file.
        """
        self.logger.info(f"Starting translation for files in '{input_dir}' to language '{target_language}'")
        run_dir = self.create_run_directory(target_language, output_dir, output_dir_name)
        self.logger.info(f"Output will be saved to: {run_dir}")
        all_files = self.get_all_files(input_dir)
        if not all_files:
            self.logger.warning(f"No files found in input directory: {input_dir}")
            return

        for rel_path, abs_path in all_files:
            self.logger.info(f"Translating file: {rel_path}")
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                translated_text = self.prompt_ai(content, target_language)
                self.save_translation(run_dir, rel_path, translated_text, target_language)
            except Exception as e:
                self.logger.error(f"Failed to process file {abs_path}: {str(e)}")
        self.logger.info("Translation complete")


def ask_for_language() -> str:
    """
    Prompt the user for a target language.
    """
    while True:
        language = input("Enter the target language (ISO alpha-2 code or language name): ").strip()
        if len(language) < 2:
            print("Please enter a valid language code or name.")
            continue
        return language


def ask_for_input_dir() -> str:
    """
    Prompt the user for a valid input directory.
    """
    while True:
        input_dir = input("Enter the input directory to translate: ").strip()
        if not os.path.isdir(input_dir):
            print("Please enter a valid directory path.")
            continue
        return input_dir


def pull_model(model_name: str):
    """
    Pulls the specified model using ollama if it is not already installed.
    """
    print(f"Model '{model_name}' not found. Pulling the model...")
    try:
        ollama.pull(model_name)
        print("Model pulled successfully.")
    except Exception as e:
        print(f"Failed to pull model '{model_name}': {str(e)}")
        print("Does the model exist? Make sure the model name is correct.")
        model_list: ListResponse = ollama.list()
        models = model_list["models"]
        available_models = [model["model"] for model in models]
        print(json.dumps(available_models, indent=2))
        exit(1)


def get_arguments():
    """
    Parses command-line arguments and prompts for missing values.
    """
    parser = argparse.ArgumentParser(
        description="Translation Master: Translate technical text and code files while preserving formatting."
    )
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
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    output_dir = args.output_dir if args.output_dir else os.path.join(os.getcwd(), "output", date_str)
    output_dir_name = args.output_dir_name if args.output_dir_name else None
    model = args.model if args.model else "gemma3:1b"
    logging_path = args.logging_path if args.logging_path else os.path.join(os.getcwd(), "logs")

    return language, input_dir, output_dir, output_dir_name, model, logging_path, args.pull


if __name__ == "__main__":
    target_language, input_dir, output_dir, output_dir_name, model, logging_path, auto_pull = get_arguments()

    if len(target_language) < 2:
        print("Please enter a valid language code or name.")
        exit(1)

    model_list: ListResponse = ollama.list()
    models = model_list["models"]
    available_models = [m["model"] for m in models]

    if model not in available_models:
        if auto_pull:
            pull_model(model)
        else:
            print(f"Model '{model}' is not installed. Available models:")
            print(json.dumps(available_models, indent=2))
            print(f"Run 'ollama pull {model}' to install new models, or pass the '--pull' flag to automatically install the model.")
            exit(1)

    master = TranslationMaster(model_name=model, logging_path=logging_path)
    master.start_translating(input_dir, output_dir, target_language, output_dir_name)
    print("Processing complete. Check the output directory and logs for details.")
