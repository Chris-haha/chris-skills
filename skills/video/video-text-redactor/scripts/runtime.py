"""Local executables, metadata and persistent macOS OCR worker."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import cv2

CACHE = Path(os.environ.get('VIDEO_REDACTOR_CACHE', '~/.local/share/video-text-redactor')).expanduser()


def executable(name):
    candidates = [os.environ.get(name.upper()), shutil.which(name),
                  str(Path.home()/'.local/text-video-tools'/name),
                  f'/opt/homebrew/bin/{name}', f'/usr/local/bin/{name}']
    for path in candidates:
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            return path
    raise RuntimeError(f'{name} not found; install FFmpeg or set {name.upper()} to its executable path')


def probe(path):
    data = json.loads(subprocess.check_output([executable('ffprobe'), '-v','error',
         '-show_streams','-show_format','-of','json',str(path)]))
    stream = next(s for s in data['streams'] if s['codec_type']=='video')
    from fractions import Fraction
    rate = stream.get('avg_frame_rate','0/0')
    if rate == '0/0':
        rate = stream['r_frame_rate']
    return dict(width=stream['width'], height=stream['height'], fps=float(Fraction(rate)),
                fps_fraction=rate, duration=float(data['format'].get('duration',0)),
                audio=any(s['codec_type']=='audio' for s in data['streams']),
                video_start=float(stream.get('start_time',0)),
                audio_start=next((float(s.get('start_time',0)) for s in data['streams']
                                  if s['codec_type']=='audio'),0),
                nominal_rate=stream.get('r_frame_rate'), streams=data['streams'])


def timeline(path):
    """Read every presentation timestamp; avoid guessing VFR from r_frame_rate."""
    raw = subprocess.check_output([executable('ffprobe'),'-v','error','-select_streams','v:0',
                '-show_entries','frame=best_effort_timestamp_time','-of','csv=p=0',str(path)],text=True)
    stamps=[]
    for line in raw.splitlines():
        try:
            stamps.append(float(line.split(',')[0]))
        except ValueError:
            pass
    if len(stamps)<2:
        return stamps, False
    import numpy as np
    delta=np.diff(stamps)
    median=float(np.median(delta))
    variable=bool(np.any(np.abs(delta-median)>max(.001,median*.03)))
    return stamps,variable


class VisionOCR:
    def __init__(self, terms=(), width=0, regex=(), all_text=False):
        source=Path(__file__).with_name('VisionOCR.swift')
        digest=hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        CACHE.mkdir(parents=True,exist_ok=True)
        binary=CACHE/f'vision-{digest}'
        if not binary.exists():
            subprocess.run(['swiftc','-O',str(source),'-o',str(binary)],check=True)
        self.process=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        self.width=width
        self.terms=list(terms)
        self.regex=list(regex)
        self.all_text=all_text

    def recognize(self, frame, chars=False):
        height,width=frame.shape[:2]
        if self.width and width>self.width:
            small=cv2.resize(frame,(self.width,round(height*self.width/width)),interpolation=cv2.INTER_AREA)
        else:
            small=frame
        h,w=small.shape[:2]
        rgb=cv2.cvtColor(small,cv2.COLOR_BGR2RGB)
        header={'width':w,'height':h,'chars':chars,'terms':self.terms,
                'regex':self.regex,'all_text':self.all_text}
        self.process.stdin.write(json.dumps(header,ensure_ascii=False).encode()+b'\n')
        self.process.stdin.write(rgb.tobytes())
        self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:
            raise RuntimeError(f'Vision worker exited: {self.process.poll()}')
        result=json.loads(line)
        if 'error' in result:
            raise RuntimeError(result['error'])
        for row in result['rows']:
            row['box']=[v*([width/w,height/h,width/w,height/h][j]) for j,v in enumerate(row['box'])]
            if 'chars' in row:
                row['chars']=[[v*([width/w,height/h,width/w,height/h][j]) for j,v in enumerate(b)]
                               if b else None for b in row['chars']]
        return result['rows']

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.wait(timeout=15)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()
