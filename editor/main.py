import argparse
import os
import sys
from dotenv import load_dotenv
from concat import concatenate_files
from expand import expand_abbreviations

load_dotenv()

def process_data(method: str, input_dir: str, output_dir: str, max_lines: int):
    """
    Main processing function.
    
    Args:
        input_dir (str): Path to the input directory
        output_dir (str): Path to the output directory
        max_lines (int): Maximum number of lines to process
    """
    print(f"Processing with parameters:")
    print(f"  Method: {method}")
    print(f"  Input: {input_dir}")
    print(f"  Output: {output_dir}")
    print(f"  Max lines: {max_lines}")

    if method == "expand":
        expand_abbreviations(input_dir, output_dir, max_lines)
    elif method == "concat":
        concatenate_files(input_dir, output_dir, "output.txt")
    else:
        raise ValueError(f"Invalid method: {method}")

def main():
    parser = argparse.ArgumentParser(description='Process data with specified dirs and line limit.')
    
    parser.add_argument('--method',
                        type=str,
                        required=True,
                        help='Processing method')

    parser.add_argument('--input', 
                        type=str,
                        required=True,
                        help='Input dir')
    
    parser.add_argument('--output',
                        type=str,
                        required=True,
                        help='Output dir')
    
    parser.add_argument('--max-lines',
                        type=int,
                        required=False,
                        help='Maximum number of lines to process')

    args = parser.parse_args()

    try:
        process_data(args.method, args.input, args.output, args.max_lines)
    except Exception as e:
        print(f"Error processing data: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
