import subprocess

def comprimir_gif(input_path, output_path):
    subprocess.null([
        'gifsicle',
        '-03',
        '--lossy=80',
        input_path,
        '-o',
        output_path
    ])
    