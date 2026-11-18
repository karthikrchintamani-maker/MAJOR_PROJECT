import os
import re
import subprocess
import markdown

report_md_path = r"C:\Users\Karthik R\Downloads\roadeye_models-karthik\RoadEye_Major_Project_Report.md"
html_out_path = r"C:\Users\Karthik R\Downloads\roadeye_models-karthik\RoadEye_Major_Project_Report.html"
pdf_out_path = r"C:\Users\Karthik R\Downloads\roadeye_models-karthik\RoadEye_Major_Project_Report.pdf"

with open(report_md_path, "r", encoding="utf-8") as f:
    raw_md = f.read()

# Replace mermaid code blocks with <div class="mermaid">...</div>
def replace_mermaid(match):
    code = match.group(1).strip()
    return f'<div class="mermaid-container"><pre class="mermaid">\n{code}\n</pre></div>'

processed_md = re.sub(r'```mermaid\s*\n(.*?)\n```', replace_mermaid, raw_md, flags=re.DOTALL)

# Convert Markdown to HTML
html_body = markdown.markdown(
    processed_md,
    extensions=['tables', 'fenced_code', 'codehilite', 'toc']
)

# Build full professional HTML document with academic styling
full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>RoadEye – Major Project Report</title>
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700&family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&family=Lora:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
    
    <!-- KaTeX for Math -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>

    <!-- Mermaid.js for Diagrams -->
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'neutral',
            fontFamily: 'Inter, sans-serif',
            securityLevel: 'loose',
            flowchart: {{ htmlLabels: true, curve: 'basis' }}
        }});
    </script>

    <style>
        @page {{
            size: A4;
            margin: 22mm 18mm 22mm 22mm;
            @top-right {{
                content: "RoadEye ADAS & IoT System";
                font-family: 'Inter', sans-serif;
                font-size: 8pt;
                color: #64748b;
            }}
            @bottom-center {{
                content: counter(page);
                font-family: 'Inter', sans-serif;
                font-size: 9pt;
                font-weight: bold;
                color: #1e293b;
            }}
        }}

        *, *::before, *::after {{
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Lora', Georgia, serif;
            font-size: 11pt;
            line-height: 1.65;
            color: #1e293b;
            background-color: #ffffff;
            margin: 0;
            padding: 0;
            text-align: justify;
        }}

        /* Titles and Headings */
        h1, h2, h3, h4, h5, h6 {{
            font-family: 'Inter', sans-serif;
            color: #0f172a;
            page-break-after: avoid;
            margin-top: 1.6em;
            margin-bottom: 0.6em;
        }}

        /* Cover Title Page */
        h1:first-of-type {{
            font-family: 'Cinzel', serif;
            font-size: 20pt;
            text-align: center;
            color: #0f2744;
            margin-top: 50px;
            margin-bottom: 25px;
            line-height: 1.3;
            letter-spacing: 0.5px;
        }}

        /* Chapter Headings */
        h1 {{
            font-size: 17pt;
            border-bottom: 2.5px solid #1e40af;
            padding-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: #1e3a8a;
            margin-top: 0;
            padding-top: 10px;
        }}

        /* Page break on each Chapter 1, Chapter 2, etc. */
        h1:not(:first-of-type) {{
            page-break-before: always;
        }}

        h2 {{
            font-size: 13.5pt;
            color: #1e293b;
            border-bottom: 1px solid #cbd5e1;
            padding-bottom: 4px;
        }}

        h3 {{
            font-size: 12pt;
            color: #1e40af;
        }}

        h4 {{
            font-size: 11pt;
            font-weight: 600;
            color: #334155;
        }}

        p {{
            margin-top: 0;
            margin-bottom: 1em;
            text-indent: 0;
        }}

        /* Table of Contents */
        ul {{
            margin-top: 0.4em;
            margin-bottom: 1em;
            padding-left: 24px;
        }}

        li {{
            margin-bottom: 0.35em;
        }}

        strong {{
            color: #0f172a;
            font-family: 'Inter', sans-serif;
            font-weight: 600;
        }}

        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.4em 0;
            font-family: 'Inter', sans-serif;
            font-size: 9.5pt;
            page-break-inside: avoid;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        th, td {{
            border: 1px solid #cbd5e1;
            padding: 8px 10px;
            vertical-align: top;
        }}

        th {{
            background-color: #f1f5f9;
            color: #0f172a;
            font-weight: 700;
            text-align: left;
            border-bottom: 2px solid #94a3b8;
        }}

        tr:nth-child(even) {{
            background-color: #f8fafc;
        }}

        /* Code & Pre */
        code {{
            font-family: 'JetBrains Mono', Consolas, monospace;
            font-size: 9pt;
            background-color: #f1f5f9;
            padding: 2px 5px;
            border-radius: 4px;
            color: #0f2744;
            border: 1px solid #e2e8f0;
        }}

        pre {{
            background-color: #0f172a;
            color: #f8fafc;
            padding: 14px 16px;
            border-radius: 6px;
            overflow-x: auto;
            font-family: 'JetBrains Mono', Consolas, monospace;
            font-size: 8.5pt;
            line-height: 1.45;
            page-break-inside: avoid;
            margin: 1.2em 0;
            border: 1px solid #334155;
        }}

        pre code {{
            background-color: transparent;
            padding: 0;
            border: none;
            color: inherit;
            font-size: inherit;
        }}

        /* Blockquotes */
        blockquote {{
            margin: 1.2em 0;
            padding: 10px 18px;
            background-color: #f8fafc;
            border-left: 4px solid #2563eb;
            color: #334155;
            font-style: italic;
        }}

        /* Mermaid Container */
        .mermaid-container {{
            margin: 1.6em 0;
            text-align: center;
            page-break-inside: avoid;
        }}

        pre.mermaid {{
            background: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #e2e8f0 !important;
            padding: 16px;
            display: inline-block;
            max-width: 100%;
        }}

        /* Figure captions */
        div[align="center"] {{
            margin-top: 6px;
            margin-bottom: 20px;
            font-family: 'Inter', sans-serif;
            font-size: 9.5pt;
            color: #475569;
            page-break-before: avoid;
        }}

        /* Clean Divider */
        hr {{
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 2em 0;
        }}

        /* Print Specifics */
        @media print {{
            body {{
                font-size: 10.5pt;
                line-height: 1.6;
            }}
            pre {{
                white-space: pre-wrap;
                word-wrap: break-word;
            }}
        }}
    </style>
</head>
<body>
    {html_body}

    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            renderMathInElement(document.body, {{
                delimiters: [
                    {{left: '$$', right: '$$', display: true}},
                    {{left: '$', right: '$', display: false}}
                ]
            }});
        }});
    </script>
</body>
</html>"""

with open(html_out_path, "w", encoding="utf-8") as f:
    f.write(full_html)

print("HTML generated successfully! Size:", os.path.getsize(html_out_path))

# Run Chrome headless to produce PDF
chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
cmd = [
    chrome,
    "--headless=new",
    "--disable-gpu",
    "--no-pdf-header-footer",
    "--run-all-compositor-stages-before-draw",
    "--virtual-time-budget=6000",
    f"--print-to-pdf={pdf_out_path}",
    f"file:///{html_out_path.replace(os.sep, '/')}"
]

print("Executing Chrome headless PDF conversion...")
res = subprocess.run(cmd, capture_output=True, text=True)
print("Chrome Return Code:", res.returncode)
if os.path.exists(pdf_out_path):
    print("PDF GENERATED SUCCESSFULLY!")
    print("PDF Path:", pdf_out_path)
    print("PDF Size:", os.path.getsize(pdf_out_path), "bytes")
else:
    print("PDF generation failed. Stderr:", res.stderr)
