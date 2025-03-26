import sys
import os
import json
import shlex
import logging
import subprocess
import shutil
from clang import cindex

def setup_logging():
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(levelname)s] %(message)s')

def load_compile_commands(compile_commands_path):
    """Load and return compile commands from the JSON file."""
    try:
        logging.debug(f"Loading compile commands from {compile_commands_path}")
        with open(compile_commands_path, 'r') as f:
            commands = json.load(f)
        logging.info(f"Loaded {len(commands)} compile commands.")
        return commands
    except Exception as e:
        logging.error(f"Error loading {compile_commands_path}: {e}")
        return []

def extract_flags_from_entry(entry, file_to_ignore=None):
    if "arguments" in entry:
        args = entry["arguments"]
    elif "command" in entry:
        args = shlex.split(entry["command"])
    else:
        args = []
    
    # Remove the compiler executable (first token)
    if args:
        args = args[1:]
    
    # Remove '-o' and its following argument
    filtered_args = []
    skip_next = False
    for token in args:
        if skip_next:
            skip_next = False
            continue
        if token == "-o":
            skip_next = True
        else:
            filtered_args.append(token)
    
    args = filtered_args

    if file_to_ignore:
        args = [arg for arg in args if os.path.basename(arg) != os.path.basename(file_to_ignore)]
    #logging.debug(f"Extracted flags: {args}")
    return args

def find_entry_for_file(commands, file_path):
    """Return the compile command entry that exactly matches the file_path."""
    file_abs = os.path.abspath(file_path)
    for entry in commands:
        entry_file = entry.get("file")
        if not os.path.isabs(entry_file):
            entry_file = os.path.abspath(os.path.join(entry.get("directory", ""), entry_file))
        if file_abs == entry_file:
            logging.debug(f"Found matching entry for {file_path} in {entry.get('directory')}")
            return entry
    logging.debug(f"No matching entry found for {file_path}")
    return None

def get_compile_flags_for_file(source_file, compile_commands_path):
    """
    Return a list of compile flags for source_file based on compile_commands.json.
    For header files, if a direct entry isn’t found, attempt to reuse flags from a nearby source file.
    """
    commands = load_compile_commands(compile_commands_path)
    if not commands:
        logging.warning("No compile commands loaded.")
        return []

    # Try to get flags for the file directly.
    entry = find_entry_for_file(commands, source_file)
    if entry:
        logging.info(f"Using compile flags from direct entry for {source_file}")
        return extract_flags_from_entry(entry, file_to_ignore=source_file)

    # If source_file is a header, try to find an entry in the same directory.
    header_extensions = ['.h', '.hpp', '.hh', '.hxx']
    _, ext = os.path.splitext(source_file)
    if ext.lower() in header_extensions:
        source_dir = os.path.dirname(os.path.abspath(source_file))
        logging.debug(f"{source_file} is a header. Looking for compatible entries in directory: {source_dir}")
        for entry in commands:
            # Compare the directory of the candidate source file rather than the build directory.
            entry_file = os.path.abspath(entry.get("file", ""))
            entry_dir = os.path.dirname(entry_file)
            #logging.debug(f"Checking entry: {entry.get('file')} in directory: {entry_dir}")
            if entry_dir == source_dir:
                flags = extract_flags_from_entry(entry, file_to_ignore=entry.get("file"))
                # Prepend the header file as the file to be parsed.
                flags.insert(0, source_file)
                logging.info(f"Using compile flags from {entry.get('file')} for header {source_file}")
                return flags
        logging.warning(f"No compatible entry found in directory {source_dir} for header {source_file}.")

    logging.warning(f"No compile flags found for {source_file}.")
    return []

def process_cursor(cursor, indent=0):
    """
    Recursively process the clang AST.
    Prints:
      - Macro definitions
      - Inclusion directives
      - Declarations (functions, variables, classes, etc.) with their kinds.
    """
    prefix = " " * indent
    if cursor.kind == cindex.CursorKind.MACRO_DEFINITION:
        logging.debug(f"{prefix}Macro Definition: {cursor.spelling}")
        print(f"{prefix}Macro Definition: {cursor.spelling}")
    elif cursor.kind == cindex.CursorKind.INCLUSION_DIRECTIVE:
        logging.debug(f"{prefix}Inclusion Directive: {cursor.spelling}")
        print(f"{prefix}Inclusion Directive: {cursor.spelling}")
    elif cursor.kind.is_declaration() and cursor.spelling:
        logging.debug(f"{prefix}Declaration: {cursor.spelling} ({cursor.kind})")
        print(f"{prefix}Declaration: {cursor.spelling} ({cursor.kind})")
    
    for child in cursor.get_children():
        process_cursor(child, indent + 2)

def create_temp_cpp_including(header_file):
    """Create a temporary .cpp file that includes the header file."""
    import tempfile
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".cpp", mode="w", encoding="utf-8")
    # Use an absolute include path to the header to ensure it is found.
    header_abs = os.path.abspath(header_file)
    temp.write(f'#include "{header_abs}"\n')
    temp.close()
    logging.info(f"Created temporary source file {temp.name} including {header_file}")
    return temp.name

def run_preprocessor(source_file, args):
    """
    Runs the source file through the preprocessor using g++ or clang++ (whichever is found first)
    and writes the output to a temporary file. Returns the temporary file path.
    """
    import tempfile
    preproc = shutil.which("g++") or shutil.which("clang++")
    if preproc is None:
        logging.error("No C++ preprocessor (g++ or clang++) found.")
        sys.exit(1)
    temp_preprocessed = tempfile.NamedTemporaryFile(delete=False, suffix=".i", mode="w", encoding="utf-8")
    temp_preprocessed.close()
    # Remove any instance of the source file from the flags to avoid duplicates.
    clean_args = [arg for arg in args if os.path.abspath(arg) != os.path.abspath(source_file)]
    cmd = [preproc, "-E"] + clean_args + [source_file, "-o", temp_preprocessed.name]
    logging.info(f"Running preprocessor: {' '.join(cmd)}")
    ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if ret.returncode != 0:
        logging.error("Preprocessor failed:")
        logging.error(ret.stderr)
        sys.exit(1)
    return temp_preprocessed.name

def main():
    setup_logging()

    if len(sys.argv) < 2:
        logging.error("Usage: {} [-P|--preprocess] <source_file> [compile_commands.json]".format(sys.argv[0]))
        sys.exit(1)
    
    # Check if we should run in preprocessor mode.
    preprocess_mode = False
    arg_index = 1
    if sys.argv[1] in ("-P", "--preprocess"):
        preprocess_mode = True
        arg_index += 1

    source_file = sys.argv[arg_index]
    default_flags = ['-std=c++11']
    args = default_flags[:]
    
    if len(sys.argv) > arg_index + 1:
        compile_commands_path = sys.argv[arg_index + 1]
        if os.path.exists(compile_commands_path):
            flags = get_compile_flags_for_file(source_file, compile_commands_path)
            if flags:
                args = flags
            else:
                logging.warning(f"No compile flags found for {source_file}. Using default flags.")
        else:
            logging.warning(f"{compile_commands_path} does not exist. Using default compile flags.")
    
    file_to_parse = source_file
    temp_file = None
    if preprocess_mode:
        # Run the file through the preprocessor and use its output.
        file_to_parse = run_preprocessor(source_file, args)
        logging.info(f"Preprocessed file saved to {file_to_parse}")
    else:
        # If not in preprocessor mode and parsing a header, create a temporary .cpp file that includes it.
        _, ext = os.path.splitext(source_file)
        is_header = ext.lower() in ['.h', '.hpp', '.hh', '.hxx']
        if is_header:
            temp_file = create_temp_cpp_including(source_file)
            file_to_parse = temp_file

    logging.info(f"Parsing {file_to_parse} with flags: {args}")
    index = cindex.Index.create()
    try:
        tu = index.parse(
            file_to_parse,
            args=args,
            options=cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
        )
    except cindex.TranslationUnitLoadError as e:
        logging.error("Failed to parse the translation unit.")
        try:
            tu = index.parse(
                file_to_parse,
                args=args,
                options=cindex.TranslationUnit.PARSE_INCOMPLETE
            )
            logging.error("Diagnostics from incomplete parse:")
            for diag in tu.diagnostics:
                logging.error(diag)
        except Exception as inner_e:
            logging.error(f"Unable to get diagnostics: {inner_e}")
        sys.exit(1)
    
    process_cursor(tu.cursor)
    
    # Clean up temporary file if created.
    if temp_file:
        try:
            os.remove(temp_file)
            logging.info(f"Removed temporary file {temp_file}")
        except Exception as e:
            logging.error(f"Error removing temporary file {temp_file}: {e}")

if __name__ == '__main__':
    main()
