import numpy as np
from PIL import Image

img = np.array(Image.open('PNG_1280/整体效果.png').convert('RGBA'))
bg = np.array(Image.open('PNG_1280/双氧水软件界面底板.png').convert('RGBA'))

diff = np.abs(img.astype(int) - bg.astype(int)).sum(axis=2)
mask = diff > 20

# Create a foreground image
fg = np.zeros_like(img)
fg[mask] = img[mask]

# Let's save it to see how many pixels
print(f'Foreground pixels: {mask.sum()}')
