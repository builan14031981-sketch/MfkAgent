import re
s = open(r'E:\智慧项目\portfolio-mfkagent\index.html', encoding='utf-8').read()
starts = [m.start() for m in re.finditer(r'<script>', s)]
seg = '\n'.join(s[a:s.find('</script>', a)] for a in starts)
i = seg.find('updateUI')
print('--- updateUI ---')
print(seg[i:i+900])
print('--- tilt ---')
j = seg.find('rotate')
print(seg[max(0, j-500):j+700])