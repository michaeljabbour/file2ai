#!/usr/bin/env python3
import os

def create_test_html():
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test HTML Document</title>
    <style>
        body { font-family: Arial, sans-serif; }
        .test-div { padding: 20px; background-color: #f0f0f0; }
    </style>
</head>
<body>
    <h1>Test HTML Document</h1>
    <div class="test-div">
        <p>This is a test paragraph for file2ai conversion testing.</p>
        <p>It includes multiple paragraphs and formatting to test conversion.</p>
        <table border="1">
            <tr><th>Header 1</th><th>Header 2</th></tr>
            <tr><td>Value 1</td><td>Value 2</td></tr>
        </table>
    </div>
</body>
</html>"""

    with open('test.html', 'w') as f:
        f.write(html_content)
    print("Test HTML file created successfully!")

if __name__ == '__main__':
    create_test_html()
