#!/usr/bin/env python
"""Update PDF tasks to include original_filename field."""
import re

# Read the tasks file
with open(r'apps/pdf/tasks.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Manually insert the clean_filename generation before specific ConvertedFile creations
# We'll track line numbers where we need to insert code

result_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    result_lines.append(line)
    
    # Check if this is a line with "job.mark_completed" followed by ConvertedFile.objects.create without original_filename
    if 'job.mark_completed(job.output_file.name)' in line:
        # Look ahead to see if next non-empty line is ConvertedFile.objects.create
        j = i + 1
        while j < len(lines) and lines[j].strip() in ['', '\r\n']:
            result_lines.append(lines[j])
            j += 1
        
        if j < len(lines) and 'ConvertedFile.objects.create(' in lines[j]:
            # Check if it has original_filename
            k = j
            has_original_filename = False
            while k < len(lines) and ')' not in lines[k]:
                if 'original_filename' in lines[k]:
                    has_original_filename = True
                    break
                k += 1
            
            if not has_original_filename:
                # Insert the clean_filename generation code
                result_lines.append('        \r\n')
                result_lines.append('        # Generate clean filename for user\r\n')
                result_lines.append('        from apps.core.utils import generate_clean_output_filename\r\n')
                result_lines.append('        clean_filename = generate_clean_output_filename(\r\n')
                result_lines.append("            original_name=job.input_file.name.split('/')[-1],\r\n")
                result_lines.append("            output_format='pdf'\r\n")
                result_lines.append('        )\r\n')
                
                # Now update ConvertedFile.objects.create to include original_filename
                while j < len(lines):
                    if 'output_format=' in lines[j]:
                        result_lines.append(lines[j])
                        j += 1
                        # Insert original_filename line
                        result_lines.append('            original_filename=clean_filename,\r\n')
                        i = j - 1
                        break
                    else:
                        result_lines.append(lines[j])
                        j += 1
    
    i += 1

# Write back
with open(r'apps/pdf/tasks.py', 'w', encoding='utf-8') as f:
    f.writelines(result_lines)

print('Successfully updated PDF tasks file with original_filename')
