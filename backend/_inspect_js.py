import re
s = open(r'E:\智慧项目\portfolio-mfkagent\index.html', encoding='utf-8').read()
for m in re.finditer(r'<script[^>]*>', s):
    print(m.start(), m.group(0))
print('last script end:', s.rfind('</script>'))
starts = [m.start() for m in re.finditer(r'<script>', s)]
seg = "\n".join(s[a:s.find('</script>', a)] for a in starts)
print('total inline JS chars:', len(seg))
for kw in ['cursor', 'parallax', 'requestAnimationFrame', 'lerp', 'trait', 'mousemove',
           "addEventListener('mousemove'", 'pointermove', 'snap', 'prefers-reduced-motion']:
    print(kw, ':', seg.count(kw))