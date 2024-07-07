import json

def generate_function_summaries_html(summaries_file, decompilations_file, output_dir):
    # Load summaries.jsonl
    functions = {}
    with open(summaries_file, 'r') as f:
        for line in f:
            data = json.loads(line)
            function_name = list(data.keys())[0]
            function_desc = data[function_name]
            functions[function_name] = function_desc

    # Load decompilations.json
    code_snippets = {}
    with open(decompilations_file, 'r') as f:
        code_snippets = json.load(f)

    # Generate HTML content
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Function Summaries</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.24.1/themes/prism-okaidia.min.css">
        <style>
            body {
                font-family: 'Courier New', Courier, monospace;
                background-color: #222;
                color: #ddd;
                padding: 20px;
            }
            .function {
                margin-bottom: 20px;
                padding: 10px;
                border: 1px solid #444;
                border-radius: 5px;
            }
            .function-name {
                font-weight: bold;
                color: #f92672;
                font-size: 18px;
                margin-bottom: 5px;
            }
            .function-desc {
                color: #a6e22e;
                font-size: 14px;
                margin-bottom: 10px;
            }
            .inspect-button {
                background-color: #444;
                color: #ddd;
                border: none;
                padding: 8px 12px;
                cursor: pointer;
                border-radius: 3px;
                transition: background-color 0.3s ease;
            }
            .inspect-button:hover {
                background-color: #666;
            }
            .modal {
                display: none;
                position: fixed;
                z-index: 1;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                overflow: auto;
                background-color: rgba(0,0,0,0.8);
            }
            .modal-content {
                background-color: #333;
                margin: 15% auto;
                padding: 20px;
                border: 1px solid #888;
                width: 80%;
                border-radius: 5px;
                color: white;
            }
            .close {
                color: #aaa;
                float: right;
                font-size: 28px;
                font-weight: bold;
                cursor: pointer;
            }
            .close:hover,
            .close:focus {
                color: #fff;
                text-decoration: none;
            }
            .code-snippet {
                font-family: 'Courier New', Courier, monospace;
                font-size: 14px;
                background-color: #222;
                color: #ddd;
                padding: 10px;
                border-radius: 5px;
                overflow-x: auto;
                margin-top: 15px;
            }
        </style>
    </head>
    <body>
        <h1 style="text-align: center; color: #f92672;">Function Summaries</h1>
    """

    # Function to generate function details HTML
    def generate_function_html(function_name, function_desc):
        return f"""
        <div class="function" id="{function_name}">
            <div class="function-name">{function_name}</div>
            <div class="function-desc">{function_desc}</div>
            <button class="inspect-button" onclick="showModal('{function_name}')">Inspect</button>
            <div id="{function_name}-modal" class="modal">
                <div class="modal-content">
                    <span class="close" onclick="closeModal('{function_name}')">&times;</span>
                    <h2 style="color: #f92672; text-align: center;">{function_name}</h2>
                    <pre class="code-snippet" id="{function_name}-code">{code_snippets.get(function_name, 'Code not available')}</pre>
                </div>
            </div>
        </div>
        """

    # Generate function summaries HTML
    for function_name, function_desc in functions.items():
        html_content += generate_function_html(function_name, function_desc)

    # Add JavaScript for modal functionality
    html_content += """
    <script>
        function showModal(functionName) {
            var modal = document.getElementById(functionName + '-modal');
            modal.style.display = 'block';
            Prism.highlightElement(modal.querySelector('.code-snippet'));
        }

        function closeModal(functionName) {
            var modal = document.getElementById(functionName + '-modal');
            modal.style.display = 'none';
        }
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.24.1/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.24.1/components/prism-c.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.24.1/components/prism-cpp.min.js"></script>
    </body>
    </html>
    """

    # Write HTML content to file
    output_file = f"{output_dir}/function_summaries.html"
    with open(output_file, 'w') as f:
        f.write(html_content)

    print(f"HTML file generated successfully at {output_file}")

# # Example usage:
# generate_function_summaries_html('samples/libpng16.so.16.38.0_stripped/summaries_png_read_info_gpt3.jsonl',
#                                 'samples/libpng16.so.16.38.0_stripped/decompilations.json',
#                                 'output_directory')
