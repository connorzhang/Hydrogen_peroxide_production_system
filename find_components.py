# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image
from collections import deque

pure = np.array(Image.open('PNG_1280/pure_machine_network.png'))[:,:,3]
pipes = np.array(Image.open('PNG_1280/管道流露.png'))[:,:,3]

mask = (pure > 0) & (pipes == 0)
h, w = mask.shape
visited = np.zeros((h, w), dtype=bool)

components = []

for r in range(h):
    for c in range(w):
        if mask[r, c] and not visited[r, c]:
            q = deque([(r, c)])
            visited[r, c] = True
            min_r, max_r = r, r
            min_c, max_c = c, c
            area = 0
            
            while q:
                cr, cc = q.popleft()
                area += 1
                min_r = min(min_r, cr)
                max_r = max(max_r, cr)
                min_c = min(min_c, cc)
                max_c = max(max_c, cc)
                
                for dr, dc in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
                    nr, nc = cr+dr, cc+dc
                    if 0 <= nr < h and 0 <= nc < w:
                        if mask[nr, nc] and not visited[nr, nc]:
                            visited[nr, nc] = True
                            q.append((nr, nc))
            if area > 100:
                components.append({'area': area, 'box': (min_c, max_c, min_r, max_r)})

components.sort(key=lambda x: x['area'], reverse=True)
for i, comp in enumerate(components):
    print(f"Comp {i}: area={comp['area']}, box={comp['box']}")
