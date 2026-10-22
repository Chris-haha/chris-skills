"""Geometry, matching and local motion used by video_text_redactor.py."""
import re
import unicodedata

import cv2
import numpy as np


def normalized_with_map(text):
    chars, indices = [], []
    for i, char in enumerate(text):
        for c in unicodedata.normalize('NFKC', char).casefold():
            if not c.isspace():
                chars.append(c)
                indices.append(i)
    return ''.join(chars), indices


def match_spans(text, rules):
    norm, mapping = normalized_with_map(text)
    if any(normalized_with_map(t)[0] in norm for t in rules.get('exclude', []) if t):
        return []
    found = []
    for term in rules.get('terms', []):
        needle = normalized_with_map(term)[0]
        if not needle:
            continue
        for m in re.finditer(re.escape(needle), norm):
            found.append((mapping[m.start()], mapping[m.end()-1]+1, term))
    for i, pattern in enumerate(rules.get('regex', [])):
        for m in re.finditer(pattern, text, re.IGNORECASE):
            if m.end() > m.start():
                found.append((m.start(), m.end(), f'regex:{i}'))
    if rules.get('all_text') and text.strip():
        found.append((0, len(text), 'all_text'))
    return sorted(set(found))


def union_boxes(boxes):
    x = min(b[0] for b in boxes)
    y = min(b[1] for b in boxes)
    r = max(b[0]+b[2] for b in boxes)
    d = max(b[1]+b[3] for b in boxes)
    return [float(x), float(y), float(r-x), float(d-y)]


def span_box(obs, start, end):
    chars = obs.get('chars', [])
    if len(chars) == len(obs['text']) and all(b for b in chars[start:end]):
        return union_boxes(chars[start:end])
    # Never approximate substring widths: proportional estimates can expose glyphs.
    return list(obs['box'])


def pad_box(box, size, padding):
    width, height = size
    x, y, w, h = box
    left = max(0, int(np.floor(x-padding)))
    top = max(0, int(np.floor(y-padding)))
    right = min(width, int(np.ceil(x+w+padding)))
    bottom = min(height, int(np.ceil(y+h+padding)))
    return [left, top, max(0, right-left), max(0, bottom-top)]


def fallback_box(origin, age, size):
    # Always grow from the last reliable box, never from the previous expanded box.
    return pad_box(origin, size, min(origin[3]*.75, 8+age*1.5))


def iou(a, b):
    x = max(a[0], b[0]); y = max(a[1], b[1])
    r = min(a[0]+a[2], b[0]+b[2]); d = min(a[1]+a[3], b[1]+b[3])
    common = max(0, r-x)*max(0, d-y)
    return common/max(1, a[2]*a[3]+b[2]*b[3]-common)


def same_target_area(a, b):
    return iou(a,b) > .28


def valid_track_size(anchor, box):
    return (.35*anchor[2] <= box[2] <= 2.2*anchor[2]
            and .35*anchor[3] <= box[3] <= 2.2*anchor[3])


def is_cut(a, b):
    aa = cv2.resize(a, (96, 54)).astype(np.float32)
    bb = cv2.resize(b, (96, 54)).astype(np.float32)
    return float(np.mean(np.abs(aa-bb))) > 48


def track_box(previous, current, box):
    """LK + forward/backward rejection + RANSAC similarity; returns None on loss."""
    # Suppress pixel-frequency aliasing before estimating brightness-consistent motion.
    previous = cv2.GaussianBlur(previous, (5, 5), .8)
    current = cv2.GaussianBlur(current, (5, 5), .8)
    height, width = previous.shape
    mask = np.zeros_like(previous)
    x, y, w, h = pad_box(box, (width, height), max(8, box[3]*.45))
    if w < 2 or h < 2:
        return None
    mask[y:y+h, x:x+w] = 255
    points = cv2.goodFeaturesToTrack(previous, maxCorners=100, qualityLevel=.008,
                                    minDistance=3, mask=mask, blockSize=3)
    if points is None or len(points) < 5:
        return None
    args = dict(winSize=(25, 25), maxLevel=4,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 25, .01))
    forward, status, err = cv2.calcOpticalFlowPyrLK(previous, current, points, None, **args)
    if forward is None:
        return None
    backward, status_back, _ = cv2.calcOpticalFlowPyrLK(current, previous, forward, None, **args)
    if backward is None:
        return None
    good = ((status.ravel() == 1) & (status_back.ravel() == 1)
            & (np.linalg.norm(points-backward, axis=2).ravel() < 1.5)
            & (err.ravel() < 35))
    if np.count_nonzero(good) < 5:
        return None
    matrix, inliers = cv2.estimateAffinePartial2D(points[good], forward[good],
                       method=cv2.RANSAC, ransacReprojThreshold=2.5)
    if matrix is None or inliers is None or inliers.mean() < .6:
        return None
    scale = float(np.hypot(matrix[0, 0], matrix[1, 0]))
    if not .7 < scale < 1.4:
        return None
    x, y, w, h = box
    corners = np.array([[x,y,1], [x+w,y,1], [x,y+h,1], [x+w,y+h,1]]) @ matrix.T
    left, top = corners.min(axis=0); right, bottom = corners.max(axis=0)
    if right < 0 or bottom < 0 or left > width or top > height:
        return None
    return [float(left), float(top), float(right-left), float(bottom-top)]


def obscure(frame, box, mode='mosaic'):
    x, y, w, h = pad_box(box, (frame.shape[1], frame.shape[0]), 0)
    if not w or not h:
        return
    if mode == 'solid':
        frame[y:y+h, x:x+w] = 24
    else:
        # At most 4 x 2 cells per string, including large text. No weak fixed block size.
        tiny = cv2.resize(frame[y:y+h, x:x+w], (min(4, w), min(2, h)),
                          interpolation=cv2.INTER_AREA)
        frame[y:y+h, x:x+w] = cv2.resize(tiny, (w, h), interpolation=cv2.INTER_NEAREST)
