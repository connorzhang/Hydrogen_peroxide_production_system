import numpy as np
from PIL import Image

orig = np.array(Image.open('PNG_1280/整体效果.png').convert('RGBA'))

boxes = {
    '电解槽': (479, 807, 277, 541),
    '纯水机': (593, 692, 636, 788),
    '阳极泵': (1002, 1138, 673, 766),
    '阴极泵': (139, 275, 672, 766),
    '压缩机': (1032, 1152, 289, 382),
    '高压罐压力': (907, 975, 280, 364),
    '阳极压力': (910, 975, 406, 490),
    '阴极压力高压罐压力': (252, 367, 280, 364),
    '阳极阀': (914, 956, 702, 746),
    '阴极阀': (320, 363, 703, 746),
    '阳极补水阀': (725, 768, 703, 746),
    '阴极补水阀': (514, 556, 703, 746),
    '阴极液位': (400, 485, 618, 807),
    '阳极液位': (798, 883, 618, 807),
    '阳极流量': (1007, 1173, 519, 595),
    '阴极流量': (218, 270, 517, 595)
}

for name, (x1, x2, y1, y2) in boxes.items():
    # Expand box by 3 pixels to ensure we don't cut edges
    x1, x2 = max(0, x1-3), min(orig.shape[1], x2+3)
    y1, y2 = max(0, y1-3), min(orig.shape[0], y2+3)
    
    img = np.zeros_like(orig)
    img[y1:y2, x1:x2] = orig[y1:y2, x1:x2]
    Image.fromarray(img).save(f'PNG_1280/{name}.png', optimize=True)
    print(f'Saved {name}.png')
