#!/usr/bin/env python3
"""Copy a portable editable Remotion starter into a new directory."""
import argparse
from pathlib import Path
import shutil

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Output must be empty; existing projects are never overwritten')
    starter=Path(__file__).resolve().parents[1]/'assets'/'starter'
    shutil.copytree(starter,output,dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('node_modules','out','.cache','__pycache__','.DS_Store'))
    shutil.copytree(Path(__file__).resolve().parent,output/'pipeline',ignore=shutil.ignore_patterns('__pycache__','init_project.py'))
    (output/'public'/'audio').mkdir(parents=True,exist_ok=True)
    print(output)

if __name__=='__main__':
    main()
