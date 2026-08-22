import re
s = open(r'E:\智慧项目\portfolio-mfkagent\index.html', encoding='utf-8').read()
for pat in ['作品墙', '作品集', 'img', '<figure', '<picture', 'slider', 'track', 'thumb', '解决', 'demo', '<canvas']:
    print(pat, '->', len(re.findall(re.escape(pat), s)))
print()
# find section headers
for m in re.finditer(r'<(h1|h2|h3)[^>]*>', s):
    print(m.group(0), '|', s[m.end():m.end()+60].split('<')[0][:60])