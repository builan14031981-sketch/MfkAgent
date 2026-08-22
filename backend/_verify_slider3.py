import re
s = open(r'E:\智慧项目\portfolio-mfkagent\index.html', encoding='utf-8').read()
print('bytes:', len(s.encode('utf-8')), '| html closed:', s.strip().endswith('</html>'))
starts = [m.start() for m in re.finditer(r'<script>', s)]
seg = '\n'.join(s[a:s.find('</script>', a)] for a in starts)
print('JS:', len(seg))
print('--- slider ---')
for kw in ['translate3d(${', 'px', '- 15', 'pointerdown', 'setPointerCapture', 'pointermove', 'pointerup',
           'trackRect.width', 'trackRect', 'getBoundingClientRect', 'resize', 'Math.round', 'arrow', 'keydown']:
    print('  ', kw, ':', seg.count(kw))
print('--- motion ---')
for kw in ['parallax', 'lerp', 'magnet', 'perspective', 'rotateX', 'rotateY', 'requestAnimationFrame',
           'prefers-reduced-motion', 'cursor']:
    print('  ', kw, ':', seg.count(kw))
print('--- CSS motion ---')
for kw in ['prefers-reduced-motion', '.parallax', 'perspective']:
    print('  ', kw, ':', s.count(kw))