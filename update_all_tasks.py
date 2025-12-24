#!/usr/bin/env python
"""
Master script to update ALL tool tasks (audio, video, image) to create ConvertedFile records
with original_filename for unified download architecture.
"""
import os
import re

def update_task_file(filepath, tool_type):
    """Update a task file to add ConvertedFile creation with original_filename."""
    print(f"Processing {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern: Find job.mark_completed NOT followed by ConvertedFile.objects.create
    # We'll add the ConvertedFile creation code after job.mark_completed
    
    # Split into lines for easier manipulation
    lines = content.split('\n')
    result_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        result_lines.append(line)
        
        # Check if this line calls job.mark_completed
        if 'job.mark_completed(' in line and 'job.output_file' in line:
            # Look ahead - is there a ConvertedFile.objects.create nearby?
            j = i + 1
            found_converted_file = False
            
            # Look 10 lines ahead
            for k in range(j, min(j + 10, len(lines))):
                if 'ConvertedFile.objects.create' in lines[k]:
                    found_converted_file = True
                    break
                # If we hit another function or except, stop looking
                if lines[k].startswith('def ') or lines[k].startswith('except'):
                    break
            
            if not found_converted_file:
                # Insert Conv

ertedFile creation code
                indent = '        '  # 8 spaces for task function level
                result_lines.append('')
                result_lines.append(f'{indent}# Generate clean filename and create ConvertedFile')
                result_lines.append(f'{indent}from apps.core.utils import generate_clean_output_filename')
                result_lines.append(f'{indent}clean_filename = generate_clean_output_filename(')
                result_lines.append(f"{indent}    original_name=job.input_file.name.split('/')[-1],")
                result_lines.append(f"{indent}    output_format=job.output_format")
                result_lines.append(f'{indent})')
                result_lines.append('')
                result_lines.append(f'{indent}ConvertedFile.objects.create(')
                result_lines.append(f'{indent}    conversion_job=job,')
                result_lines.append(f'{indent}    output_file=job.output_file,')
                result_lines.append(f'{indent}    original_filename=clean_filename,')
                result_lines.append(f'{indent}    output_format=job.output_format,')
                result_lines.append(f'{indent}    file_size=get_file_size(output_path)')
                result_lines.append(f'{indent})')
                print(f"  Added ConvertedFile creation at line {i+1}")
        
        i += 1
    
    # Write back
    new_content = '\n'.join(result_lines)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"  Completed {filepath}")

# Update all task files
task_files = [
    ('apps/audio/tasks.py', 'audio'),
    ('apps/video/tasks.py', 'video'),
    ('apps/image/tasks.py', 'image'),
]

for filepath, tool_type in task_files:
    if os.path.exists(filepath):
        update_task_file(filepath, tool_type)
    else:
        print(f"WARNING: {filepath} not found!")

print("\nAll task files updated successfully!")
print("Audio, Video, and Image tasks now create ConvertedFile records with original_filename")
