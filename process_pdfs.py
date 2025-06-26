import os
import glob
import re # Import the regular expression module
from pypdf import PdfReader, PdfWriter

def _analyze_outline_levels(outlines, current_level=0, levels_info=None):
    """
    Recursively analyzes the nested outline structure to identify all levels present
    and count the number of entries at each level, providing examples.
    """
    if levels_info is None:
        levels_info = {}

    for outline_item in outlines:
        if isinstance(outline_item, list):
            # This is a nested list, indicating a deeper level of outlines
            _analyze_outline_levels(outline_item, current_level + 1, levels_info)
        else:
            # This is an actual outline entry
            if current_level not in levels_info:
                levels_info[current_level] = {'count': 0, 'examples': []}
            
            levels_info[current_level]['count'] += 1
            if len(levels_info[current_level]['examples']) < 3: # Keep a few examples for clarity
                levels_info[current_level]['examples'].append(outline_item.title)
    return levels_info

def _get_outlines_at_specified_level(outlines, target_level, current_level=0, selected_outlines=None):
    """
    Recursively traverses the outline structure and collects only those
    outline entries that are exactly at the target_level.
    """
    if selected_outlines is None:
        selected_outlines = []

    for outline_item in outlines:
        if isinstance(outline_item, list):
            # If it's a nested list, recurse into it, increasing the current_level
            _get_outlines_at_specified_level(outline_item, target_level, current_level + 1, selected_outlines)
        else:
            # If it's an actual outline entry and matches the target_level, add it
            if current_level == target_level:
                selected_outlines.append(outline_item)
    return selected_outlines

def _normalize_title_for_comparison(title):
    """
    Normalizes a title string for consistent comparison:
    - Removes leading chapter numbers/prefixes
    - Converts to lowercase
    - Removes non-alphanumeric characters (except spaces)
    - Strips leading/trailing whitespace
    """
    # Pattern to match and remove common chapter numbering/prefixes
    chapter_number_pattern = r"^(?:Chapter|Ch|Section)\s*\d+(?:\.\d+)*\s*[\-\.]?\s*|^\d+(?:\.\d+)*(?:[\s\.\-]+|[\s\.]*\b)?"
    processed_title = re.sub(chapter_number_pattern, '', title, 1, re.IGNORECASE).strip()
    
    # Further sanitize for comparison: keep only alphanumeric and spaces, then normalize spaces
    normalized = "".join(c for c in processed_title if c.isalnum() or c.isspace()).lower()
    normalized = re.sub(r'\s+', ' ', normalized).strip() # Replace multiple spaces with single, strip
    return normalized

def split_pdf_by_chapters(pdf_path, output_directory, titles_to_exclude, outlines_to_process):
    """
    Splits a PDF into individual files based on the provided outlines_to_process.
    Renames each new PDF with the chapter name, removing leading chapter numbers
    and retaining spaces in the filenames. Chapters with titles matching the
    exclusion list or that are only one page long are skipped.

    Args:
        pdf_path (str): The full path to the input PDF file.
        output_directory (str): The directory where the split PDF chapters
                                will be saved.
        titles_to_exclude (set): A set of normalized strings representing
                                 chapter titles to be excluded from saving.
        outlines_to_process (list): A list of pypdf outline objects at the
                                    desired splitting level.
    Returns:
        list: A list of file paths to the successfully saved chapter PDFs.
              Returns an empty list if no chapters were saved or an error occurred.
    """
    # Check if the input PDF file exists
    if not os.path.exists(pdf_path):
        print(f"Error: Input PDF file not found at '{pdf_path}'")
        return [] # Indicate failure

    # Ensure the output directory exists
    os.makedirs(output_directory, exist_ok=True) 
    print(f"Output for '{os.path.basename(pdf_path)}' will be saved to '{output_directory}'.")

    saved_chapter_paths = [] # List to store paths of successfully saved chapters
    reader = None 
    try:
        reader = PdfReader(pdf_path)
        
        outlines = outlines_to_process

        if not outlines:
            print(f"No usable outlines provided for splitting '{os.path.basename(pdf_path)}'. Cannot proceed with splitting.")
            return [] # Indicate failure

        print(f"Processing {len(outlines)} selected outlines in '{os.path.basename(pdf_path)}'.")

        num_pages = len(reader.pages)
        print(f"Total pages in '{os.path.basename(pdf_path)}': {num_pages}")

        original_pdf_base_name = os.path.splitext(os.path.basename(pdf_path))[0]

        for i, current_outline in enumerate(outlines):
            try:
                chapter_title = current_outline.title
                start_page_index = reader.get_page_number(current_outline.page)
            except Exception as outline_error:
                print(f"Warning: Could not get title or page for an outline entry (index {i}). Skipping this entry. Error: {outline_error}")
                continue

            normalized_original_title = _normalize_title_for_comparison(chapter_title)
            if normalized_original_title == "introduction":
                chapter_title = f"{original_pdf_base_name} Introduction"
                print(f"  Renaming original 'Introduction' to: '{chapter_title}'")

            normalized_current_title = _normalize_title_for_comparison(chapter_title)

            if normalized_current_title in titles_to_exclude:
                print(f"  Skipping: '{chapter_title}' (matches exclusion list)")
                continue

            end_page_index = num_pages
            if i + 1 < len(outlines):
                try:
                    next_outline = outlines[i+1]
                    end_page_index = reader.get_page_number(next_outline.page)
                except Exception as next_outline_error:
                    print(f"Warning: Could not get page for the next outline entry (index {i+1}). Assuming end of document for current chapter. Error: {next_outline_error}")
                    end_page_index = num_pages 


            writer = PdfWriter()
            
            for page_num in range(start_page_index, end_page_index):
                if page_num < num_pages:
                    writer.add_page(reader.pages[page_num])
                else:
                    print(f"Warning: Attempted to add page {page_num} which is out of bounds for PDF '{os.path.basename(pdf_path)}' with {num_pages} pages. Stopping page addition for this chapter.")
                    break

            if len(writer.pages) == 1:
                print(f"  Skipping: '{chapter_title}' (single-page chapter)")
                continue

            chapter_number_pattern = r"^(?:Chapter|Ch|Section)\s*\d+(?:\.\d+)*\s*[\-\.]?\s*|^\d+(?:\.\d+)*(?:[\s\.\-]+|[\s\.]*\b)?"
            processed_chapter_title = re.sub(chapter_number_pattern, '', chapter_title, 1, re.IGNORECASE).strip()

            sanitized_chapter_title = "".join(c for c in processed_chapter_title if c.isalnum() or c.isspace() or c in ('.', '-',)).strip()
            sanitized_chapter_title = re.sub(r'\s+', ' ', sanitized_chapter_title).strip('-. ')
            
            if not sanitized_chapter_title:
                sanitized_chapter_title = f"{original_pdf_base_name}_Part_{i+1}"
                print(f"  Warning: Original chapter title '{chapter_title}' became empty or invalid after processing. Using fallback: '{sanitized_chapter_title}'")
            
            output_filename = f"{sanitized_chapter_title}.pdf"
            output_filepath = os.path.join(output_directory, output_filename)

            with open(output_filepath, "wb") as output_pdf:
                writer.write(output_pdf)
            print(f"  Saved: '{output_filename}' ({start_page_index + 1}-{end_page_index} of original)")
            saved_chapter_paths.append(output_filepath) # Add to list of saved paths
        
        return saved_chapter_paths # Return the list of paths

    except Exception as e:
        print(f"An error occurred while processing '{os.path.basename(pdf_path)}': {e}")
        print("Please ensure the PDF is not corrupted and has readable outlines.")
        return [] # Indicate failure (no chapters saved)
    
    finally:
        pass # Deletion logic is handled by the caller


# --- Main execution for multiple PDFs ---
if __name__ == "__main__":
    # Define the list of chapter titles to exclude (case-insensitive, cleaned for comparison)
    EXCLUSION_TITLES = {
        "index", "acknowledgements", "resources", "references", "cover", "title",
        "about the author", "dedication", 
        "authors note", "copyright",
        "title page", "contents", "other books by this author", "epigraph", "glossary",
        "notes", "support organizations", "copyright page", "preface", "brief contents",
        "credits", "name index", "subject index", "forward", "tables", "figures",
        "special features", "features", 
        "cover page", 
        "front matter"
    }

    # Normalize the exclusion titles once at the start for efficient lookup
    NORMALIZED_EXCLUSION_TITLES = {
        _normalize_title_for_comparison(title) for title in EXCLUSION_TITLES
    }
    
    # Define the directory where PDFs are located and where output will be stored
    PDF_DATA_DIRECTORY = "data"
    
    # Ensure the data directory exists
    os.makedirs(PDF_DATA_DIRECTORY, exist_ok=True)
    print(f"Ensuring '{PDF_DATA_DIRECTORY}' directory exists.")

    # Get all PDF files from the specified data directory
    pdf_files = glob.glob(os.path.join(PDF_DATA_DIRECTORY, "*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in the '{PDF_DATA_DIRECTORY}' directory. Please place your PDFs there.")
    else:
        print(f"Found {len(pdf_files)} PDF(s) in the '{PDF_DATA_DIRECTORY}' directory.")
        
        # Output will also be stored in the data directory
        current_output_directory = PDF_DATA_DIRECTORY 

        for pdf_file in pdf_files:
            print(f"\n--- Processing: '{pdf_file}' ---")
            
            reader = None 
            
            try:
                reader = PdfReader(pdf_file)
                raw_outlines = reader.outline

                if not raw_outlines:
                    print(f"No outlines (bookmarks) found in '{os.path.basename(pdf_file)}'. Original PDF will NOT be deleted or merged.")
                    print("Please ensure your PDF has a table of contents or bookmarks defined if you wish to split it.")
                    
                else:
                    levels_info = _analyze_outline_levels(raw_outlines)
                    
                    if not levels_info:
                        print(f"No usable outlines found in '{os.path.basename(pdf_file)}' for level analysis. Original PDF will NOT be deleted or merged.")
                        
                    else:
                        print("\nAvailable bookmark levels and their counts/examples for this PDF:")
                        sorted_levels = sorted(levels_info.keys())

                        if len(sorted_levels) == 1 and sorted_levels[0] == 0:
                            chosen_level = 0
                            print(f"  Only Level 0 bookmarks found. Automatically selecting Level 0 for splitting.")
                        else:
                            for level in sorted_levels:
                                info = levels_info[level]
                                examples_str = ", ".join(info['examples'])
                                print(f"  Level {level}: {info['count']} items (e.g., '{examples_str}')")
                            
                            chosen_level = -1
                            while chosen_level not in sorted_levels:
                                try:
                                    user_input = input(f"Enter the desired bookmark level to split by for '{os.path.basename(pdf_file)}' (e.g., {sorted_levels[0]} for main chapters): ")
                                    chosen_level = int(user_input)
                                    if chosen_level not in sorted_levels:
                                        print(f"Invalid level. Please choose from {sorted_levels}.")
                                except ValueError:
                                    print("Invalid input. Please enter a number.")
                        
                        print(f"Splitting '{os.path.basename(pdf_file)}' using Level {chosen_level} outlines.")
                        selected_outlines_for_splitting = _get_outlines_at_specified_level(raw_outlines, chosen_level)

                        if not selected_outlines_for_splitting:
                            print(f"No outlines found at level {chosen_level} for '{os.path.basename(pdf_file)}'. Original PDF will NOT be deleted or merged.")
                            
                        else:
                            # Perform the splitting with the selected outlines
                            saved_chapter_files = split_pdf_by_chapters(
                                pdf_file, current_output_directory, 
                                NORMALIZED_EXCLUSION_TITLES, selected_outlines_for_splitting
                            )
                            
                            # --- Start: Merging Logic (Updated for pypdf 5.0.0+) ---
                            if saved_chapter_files:
                                merged_pdf_name = os.path.basename(pdf_file) # Use original PDF's name
                                merged_pdf_path = os.path.join(current_output_directory, merged_pdf_name)
                                
                                print(f"  Merging {len(saved_chapter_files)} chapters into '{merged_pdf_name}' using PdfWriter...")
                                
                                merger_writer = PdfWriter() # Use PdfWriter for merging
                                for chapter_file_path in saved_chapter_files:
                                    try:
                                        chapter_reader = PdfReader(chapter_file_path)
                                        for page in chapter_reader.pages:
                                            merger_writer.add_page(page)
                                    except Exception as merge_append_error:
                                        print(f"    Warning: Could not add pages from '{os.path.basename(chapter_file_path)}' to merger: {merge_append_error}")
                                
                                try:
                                    with open(merged_pdf_path, "wb") as output_merged_pdf:
                                        merger_writer.write(output_merged_pdf)
                                    print(f"  Successfully merged chapters to '{merged_pdf_name}'.")
                                    
                                    # Delete individual chapter files after successful merge
                                    for chapter_file in saved_chapter_files:
                                        try:
                                            os.remove(chapter_file)
                                        except OSError as e_delete_chapter:
                                            print(f"    Error deleting temporary chapter file '{os.path.basename(chapter_file)}': {e_delete_chapter}")
                                    
                                    # Original PDF is NOT deleted here as per user request
                                    
                                except Exception as merge_save_error:
                                    print(f"Error saving merged PDF '{merged_pdf_name}': {merge_save_error}")
                            else:
                                print(f"  No chapters were saved from '{os.path.basename(pdf_file)}' to merge. Original PDF will NOT be deleted.")
                            # --- End: Merging Logic ---

            except Exception as e:
                print(f"An unexpected error occurred while processing '{os.path.basename(pdf_file)}': {e}")
                
            finally:
                pass 
                
            print(f"--- Finished processing: '{pdf_file}' ---\n")

    print("\nBatch PDF processing complete.")

