# Template: phone photo of a label/plate -> flat "scan" (PNG + PDF).
# Copy, set PATH and the four CORNERS, run with the toolchain python that has cv2:
#   ~/.hermes/tools/python-*/bin/python label_scan.py
#
# CORNERS are the intersections of the label's PRINTED table border lines
# (Hough -> near-horizontal / near-vertical -> line-line intersection),
# in original-photo pixels, TL, TR, BR, BL. Never the paper edge, never by eye.
# If you have no corners yet, run the detector below first and print candidates.

import cv2
import numpy as np
from PIL import Image

PATH = '<path-to-photo>'
CORNERS = [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]   # TL, TR, BR, BL
FLIP = 0            # cv2.flip code that makes the text readable: 0=vertical, 1=horizontal, -1=both
WT, HT = 2560, 1650  # rectified table size
MX, MY = 170, 340    # margins for header above / barcode below


def detect_lines(img):
    """Print candidate border lines; pick the extremes per direction."""
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    e = cv2.dilate(cv2.Canny(g, 40, 120), np.ones((2, 2), np.uint8))
    lines = cv2.HoughLinesP(e, 1, np.pi / 720, threshold=70,
                            minLineLength=300, maxLineGap=30)
    for l in lines if lines is not None else []:
        x1, y1, x2, y2 = [int(v) for v in np.array(l).ravel()[:4]]
        ang = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        ln = float(np.hypot(x2 - x1, y2 - y1))
        kind = 'H' if abs(ang) < 20 else ('V' if abs(abs(ang) - 90) < 20 else '?')
        if kind != '?':
            print(f'{kind} len={ln:6.0f} ang={ang:6.1f}  ({x1},{y1})-({x2},{y2})')


img = cv2.imread(PATH)
if FLIP:
    img = cv2.flip(img, FLIP)
if not any(CORNERS[0]):
    detect_lines(img)
    raise SystemExit('set CORNERS from the printed candidates, then rerun')

src = np.float32(CORNERS)
dst = np.float32([[MX, MY], [MX + WT - 1, MY],
                  [MX + WT - 1, MY + HT - 1], [MX, MY + HT - 1]])
M = cv2.getPerspectiveTransform(src, dst)
warp = cv2.warpPerspective(img, M, (WT + 2 * MX, HT + 2 * MY),
                           flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

# illumination flatten -> local contrast -> denoise -> unsharp -> white point
g = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY).astype(np.float32)
bg = cv2.GaussianBlur(g, (0, 0), 50)
flat = np.clip(g / (bg + 1e-6) * 205, 0, 255).astype(np.uint8)
clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(14, 10)).apply(flat)
den = cv2.fastNlMeansDenoising(clahe, None, 6, 7, 21)
bl = cv2.GaussianBlur(den, (0, 0), 1.2)
sh = cv2.addWeighted(den, 1.8, bl, -0.8, 0)
gray = np.clip((sh.astype(np.float32) - 5) / (240 - 5) * 255, 0, 255).astype(np.uint8)

# crop to ink, fade the outer ring to white (ink protected), add scan margin
ink = (gray < 110).astype(np.uint8) * 255
ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
cols = np.where(ink.sum(0) > 510)[0]
rows = np.where(ink.sum(1) > 510)[0]
pad = 26
x0, x1 = max(0, int(cols.min()) - pad), min(gray.shape[1] - 1, int(cols.max()) + pad)
y0, y1 = max(0, int(rows.min()) - pad), min(gray.shape[0] - 1, int(rows.max()) + pad)
crop = gray[y0:y1 + 1, x0:x1 + 1].astype(np.float32)

h, w = crop.shape
yy, xx = np.mgrid[0:h, 0:w]
edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)).astype(np.float32)
band = 26.0
wgt = np.clip((band - edge) / band, 0, 1) ** 1.5
inkprot = np.clip((crop - 120.0) / 60.0, 0, 1)      # 0 on ink, 1 on paper
out = crop * (1 - wgt * inkprot) + 255.0 * (wgt * inkprot)
out = np.clip(out, 0, 255).astype(np.uint8)

fin = cv2.copyMakeBorder(out, 55, 55, 55, 55, cv2.BORDER_CONSTANT, value=255)
cv2.imwrite('label_scan.png', fin)
Image.fromarray(fin).save('label_scan.pdf', 'PDF', resolution=300.0)
print('wrote label_scan.png / label_scan.pdf', fin.shape)

# Deliver both. Before shipping, check the result: every separator level, both
# side borders vertical, top row not narrower than the bottom one.
