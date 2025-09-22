import os

def concatenate_files(input_dir: str, output_dir: str, output_filename: str):
    """
    Concatenates all files in the input directory in alphanumeric order into a single file in the output directory.

    Args:
        input_dir (str): Path to the input directory
        output_dir (str): Path to the output directory
        output_filename (str): Name of the output file
    """
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Get a list of files in the input directory, sorted alphanumerically
    files = sorted([f for f in os.listdir(input_dir) if f.endswith('.txt')])

    # Open the output file for writing
    with open(os.path.join(output_dir, output_filename), 'w', encoding='utf-8') as outfile:
        # Iterate over each file in the input directory
        for filename in files:
            file_path = os.path.join(input_dir, filename)
            # Ensure it's a file before reading
            if os.path.isfile(file_path):
                with open(file_path, 'r', encoding='utf-8') as infile:
                    # Read the content of the file and write it to the output file
                    outfile.write(infile.read())
                    # Optionally add a newline or separator between files
                    outfile.write('\n')
