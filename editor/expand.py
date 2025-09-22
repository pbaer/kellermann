import glob
import os
import sys
from openai import OpenAI

def process_streaming_openai_response(response):
    expanded_text = ""
    print("Streaming response:")
    for chunk in response:
        if len(chunk.choices) > 0:
            content = chunk.choices[0].delta.content
            if content:
                print(content, end='', flush=True)
                expanded_text += content
    return expanded_text

def expand_abbreviations(input_stage_dir: str, output_stage_dir: str, max_lines: int):
    """
    Expand abbreviations in .txt files from the input directory and write the results to the output directory.
    
    Args:
        input_stage_dir (str): Path to the input stage directory.
        output_stage_dir (str): Path to the output stage directory.
        max_lines (int): Maximum number of lines to process.
        model_name (str): OpenAI model name to use.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OpenAI API key not found in environment variables.", file=sys.stderr)
        sys.exit(1)
    
    # Get list of .txt files, sorted ascending alphanumerically
    txt_files = sorted(glob.glob(os.path.join(input_stage_dir, "*.txt")))
    
    processed_lines = []
    for file_path in txt_files:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if len(processed_lines) >= max_lines:
                    break
                processed_lines.append(line.strip())
        if len(processed_lines) >= max_lines:
            break
    
    system_prompt = ("Examine the German text provided by the user and replay the content exactly as-is, "
                     "preserving all line breaks, EXCEPT that you should expand all abbreviations and "
                     "shorthand for a) geographical place names and b) military terminology. Therefore, you must pay close attention to "
                     "the surrounding context to infer the correct expansion. Make your best guess, but err on the "
                     "side of NOT modifying the content if you're not confident. When expanding, use terminology that "
                     "would be appropriate for a German WWII soldier writing to his wife (e.g. instead of a formal term "
                     "like 'Tschechoslowakische Republik', use 'Tschechoslowakei').\n\n"
                     "Remember that you MUST preserve the original line breaks EXACTLY as they are, including words that are "
                     "hyphenated across two lines (keep the hyphenation intact). Do not expand anything other than the two "
                     "categories (place names and military terms) mentioned above. In particular, any abbreviations of units of "
                     "measure should be PRESERVED as-is, such as: km (Kilometer), cm (Zentimeter), t (Tonnen), "
                     "C (Celsius), etc. Similarly, PRESERVE all commonly used German abbreviations and "
                     "shorthand such as Lkw (Lastkraftwagen), z.Z. (zur Zeit), bzw. (beziehungsweise), etc. "
                     "that would be easily understood by any German speaker.")

    example_input = ("Durch Neuzugang vieler Wehrpflichtiger und zahlreicher pri-\n"
                     "vater Fahrzeuge wurde da A. R. 256 auf Kriegsstärke gebracht\n"
                     "und am 04. September vorm. erfolgte von der Planitzstraße\n"
                     "aus der Ausmarsch als 3. Welle zum Polenfeldzug vorerst nach\n"
                     "der CSR. Erste Station mit längerem Aufenthalt war Kostelitz\n"
                     "bei Königgrätz.\n\n")

    example_output = ("Durch Neuzugang vieler Wehrpflichtiger und zahlreicher pri-\n"
                     "vater Fahrzeuge wurde da Artillerie Regiment 256 auf Kriegsstärke gebracht\n"
                     "und am 04. September vormittags erfolgte von der Planitzstraße\n"
                     "aus der Ausmarsch als 3. Welle zum Polenfeldzug vorerst nach\n"
                     "der Tschechoslowakei. Erste Station mit längerem Aufenthalt war Kostelitz\n"
                     "bei Königgrätz.\n\n")

    # The following configuration is for use with llm_api_proxy
    # https://o365exchange.visualstudio.com/O365%20Core/_git/LLMApi?path=/sources/examples/llm_api_proxy
    openai_client = OpenAI(
        api_key="sk000",
        base_url="http://localhost:11041/v1"
    );

    try:
        response = openai_client.chat.completions.create(
            model="dev-gpt-o1-preview",
            #model="o1-mini",
            messages=[
                #{"role": "system", "content": system_prompt}, # o1 does not support system messages
                #{"role": "developer", "content": system_prompt}, # for newer models (system is deprecated)
                {"role": "user", "content": system_prompt + "\n\nWe start now."}, # for o1
                {"role": "user", "content": example_input},
                {"role": "assistant", "content": example_output},
                {"role": "user", "content": "\n".join(processed_lines)}                
            ],
            #max_tokens=16384,
            max_completion_tokens=16384, # for o1
            #max_completion_tokens=4096, # for dev-gpt-4o-canvas
            n=1,
            #temperature=0,
            #stream=True, # Note, not supported by LLM API for o1
        )
        
        # non-streaming
        expanded_text = response.choices[0].message.content

        # streaming
        #expanded_text = process_streaming_openai_response(response)
    except Exception as e:
        print(f"Error during OpenAI API call: {str(e)}", file=sys.stderr)
        sys.exit(1)
    
    expanded_lines = expanded_text.splitlines()
    
    output_file_path = os.path.join(output_stage_dir, "output.txt")
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    with open(output_file_path, "w", encoding="utf-8") as f:
        for line in expanded_lines:
            f.write(line + "\n")
