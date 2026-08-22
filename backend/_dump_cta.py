import re
s = open(r'E:\智慧项目\portfolio-mfkagent\index.html', encoding='utf-8').read()
# cta mousemove
i = s.find('ctaButton.addEventListener(')
if i < 0:
    i = s.find('ctaButton')
print('--- cta ---')
print(s[max(0, i-200):i+700] if i >= 0 else 'no cta')
print()
# reduced-motion CSS
j = s.find('prefers-reduced-motion')
print('--- reduced-motion ---')
print(s[max(0, j-200):j+400] if j >= 0 else 'none')