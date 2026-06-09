__author__ = " Lao "

import cv2
import numpy as np

img = cv2.imread("test.png")

# 1) Crop sky region (tune this!)
h, w = img.shape[:2]
sky = img[: int(h * 0.55), :]   # keep top ~55%

# 2) Convert to HSV (birds are dark -> low V)
hsv = cv2.cvtColor(sky, cv2.COLOR_BGR2HSV)
H, S, V = cv2.split(hsv)

# 3) Threshold dark pixels (tune threshold!)
mask = (V < 80).astype(np.uint8) * 255

# 4) Morphology: remove specks + connect wings
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

# Optional: remove very large dark regions (if any)
# mask = cv2.bitwise_and(mask, mask, mask=cv2.inRange(V, 0, 120))

# 5) Contours
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

boxes = []
for c in contours:
    x, y, bw, bh = cv2.boundingRect(c)
    area = bw * bh
    if area < 30 or area > 20000:
        continue

    # 6) Shape filters
    cnt_area = cv2.contourArea(c)
    if cnt_area <= 1:
        continue
    solidity = cnt_area / float(area)  # rough solidity proxy
    aspect = bw / float(bh + 1e-6)

    if solidity < 0.05:     # too skinny/noisy
        continue
    if aspect < 0.2 or aspect > 6.0:
        continue

    boxes.append((x, y, x+bw, y+bh))

# 7) Draw results
out = sky.copy()
for (x1,y1,x2,y2) in boxes:
    cv2.rectangle(out, (x1,y1), (x2,y2), (0,255,0), 2)

print("Bird candidates:", len(boxes))
cv2.imwrite("birds_detected.png", out)
cv2.imwrite("mask.png", mask)
