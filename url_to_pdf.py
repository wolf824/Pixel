import os
import requests
from readability import Document
from weasyprint import HTML, CSS
from urllib.parse import urlparse
import re

# --- Pre-computation ---
# The logic for the file is pre-computed and does not require any external APIs.

def get_sanitized_filename(title):
    """
    Sanitizes a string to be a valid filename.
    Removes illegal characters and limits length.
    """
    if not title:
        return "Untitled_Article"
    # Remove characters that are not safe for filenames
    sanitized = re.sub(r'[\\/*?:"<>|]', "", title)
    # Replace spaces and multiple dots with a single underscore
    sanitized = re.sub(r'[\s.]+', '_', sanitized)
    # Limit filename length to avoid issues with OS limits
    return sanitized[:100]

def load_processed_links(log_file):
    """Loads the set of already processed URLs from the log file."""
    if not os.path.exists(log_file):
        return set()
    try:
        with open(log_file, 'r') as f:
            return {line.strip() for line in f if line.strip()}
    except IOError as e:
        print(f"Warning: Could not read log file '{log_file}'. Error: {e}")
        return set()

def log_processed_link(url, log_file):
    """Appends a successfully processed URL to the log file."""
    try:
        with open(log_file, 'a') as f:
            f.write(url + '\n')
    except IOError as e:
        print(f"Warning: Could not write to log file '{log_file}'. Error: {e}")

def update_links_file(file_path, log_file):
    """
    Rewrites the links file, removing any URLs that have been successfully processed.
    """
    print(f"\nCleaning up '{file_path}'...")
    try:
        # Load all links that were originally in the file
        with open(file_path, 'r') as f:
            original_urls = {line.strip() for line in f if line.strip()}

        # Load all links that have ever been successfully processed
        processed_urls = load_processed_links(log_file)

        # Determine which links remain (were not processed successfully)
        remaining_urls = original_urls - processed_urls

        # Rewrite the links file with only the remaining URLs
        with open(file_path, 'w') as f:
            if remaining_urls:
                f.write('\n'.join(sorted(list(remaining_urls))) + '\n')
            # If nothing remains, the file will be cleared.

        num_removed = len(original_urls) - len(remaining_urls)
        if num_removed > 0:
            print(f"-> Removed {num_removed} successfully processed link(s) from '{file_path}'.")
        else:
            print(f"-> No links were removed from '{file_path}'.")

    except Exception as e:
        print(f"Warning: Could not update '{file_path}'. Error: {e}")


def create_individual_pdfs_from_links(file_path, log_file, data_folder):
    """
    Reads URLs, processes new ones, and saves them as PDFs in a specified data folder.

    Args:
        file_path (str): The path to the text file containing URLs.
        log_file (str): The path to the file that logs processed URLs.
        data_folder (str): The name of the subfolder to store PDFs.
    """
    print("Starting the PDF generation process...")

    # --- 1. Create data folder if it doesn't exist ---
    print(f"Ensuring output directory '{data_folder}' exists...")
    os.makedirs(data_folder, exist_ok=True)


    # --- 2. Load processed links and all target URLs ---
    processed_urls = load_processed_links(log_file)
    print(f"Loaded {len(processed_urls)} previously processed link(s) from '{log_file}'.")

    try:
        with open(file_path, 'r') as f:
            all_urls = {line.strip() for line in f if line.strip()}
        if not all_urls:
            print(f"The file '{file_path}' is empty. Add some URLs to process.")
            return
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        print("Please create it and add the URLs you want to convert, one per line.")
        return

    # --- 3. Determine which links are new ---
    new_urls_to_process = sorted(list(all_urls - processed_urls))
    
    if not new_urls_to_process:
        print("\nNo new links to process. All links in 'link.txt' have already been converted.")
        return
        
    print(f"\nFound {len(new_urls_to_process)} new link(s) to convert.")


    # --- 4. Define CSS for styling the PDFs ---
    pdf_style = CSS(string='''
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: 'Georgia', serif;
            line-height: 1.6;
            font-size: 12pt;
            color: #333;
        }
        h1 {
            font-family: 'Helvetica', sans-serif;
            color: #000;
            font-size: 24pt;
            line-height: 1.2;
            page-break-after: avoid;
            margin-bottom: 1.5cm;
        }
        p { margin-bottom: 1em; }
        a { color: inherit; text-decoration: none; }
        img, svg { max-width: 100% !important; height: auto; display: block; margin: 1em 0; }
        header, footer, nav, .noprint { display: none !important; }
    ''')


    # --- 5. Process each new URL and generate a PDF ---
    success_count = 0
    failure_count = 0
    total_new = len(new_urls_to_process)

    for index, url in enumerate(new_urls_to_process):
        print("-" * 50)
        print(f"Processing new link ({index + 1}/{total_new}): {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()

            doc = Document(response.text)
            article_title = doc.short_title()
            article_content = doc.summary()

            print(f"  -> Extracted Title: '{article_title}'")

            final_html = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"><title>{article_title}</title></head>
            <body><h1>{article_title}</h1>{article_content}</body>
            </html>
            """

            # Create filename and join it with the data folder path
            output_filename = f"{get_sanitized_filename(article_title)}.pdf"
            output_filepath = os.path.join(data_folder, output_filename)

            # Generate and save the PDF inside the data folder
            print(f"  -> Generating PDF: '{output_filepath}'...")
            HTML(string=final_html, base_url=url).write_pdf(
                output_filepath,
                stylesheets=[pdf_style]
            )
            print(f"  -> ✅ Success! Saved '{output_filepath}'")
            
            log_processed_link(url, log_file)
            success_count += 1

        except requests.exceptions.RequestException as e:
            print(f"  -> ❌ Failed to fetch URL {url}. Error: {e}")
            failure_count += 1
        except Exception as e:
            print(f"  -> ❌ An unexpected error occurred while processing {url}. Error: {e}")
            failure_count += 1

    print("-" * 50)
    print("\nProcess complete.")
    print(f"Successfully created {success_count} new PDF(s).")
    if failure_count > 0:
        print(f"Failed to process {failure_count} link(s). They remain in '{file_path}'.")
    
    # --- 6. Clean up the link file ---
    if success_count > 0:
        update_links_file(file_path, log_file)


if __name__ == "__main__":
    # --- Main execution block ---
    links_file = "link.txt"
    processed_log_file = "processed_links.log"
    output_data_folder = "data" # Define the folder name for PDFs
    create_individual_pdfs_from_links(links_file, processed_log_file, output_data_folder)
