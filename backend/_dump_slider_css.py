import re
s = open(r'E:\智慧项目\portfolio-mfkagent\index.html', encoding='utf-8').read()
i = s.find('.slider')
seg = s[i:i+2200]
print(seg)