import re
s = open(r'E:\智慧项目\portfolio-mfkagent\index.html', encoding='utf-8').read()
# slider CSS block
i = s.find('.slider {')
j = s.find('</style>', i) if i >= 0 else -1
print("--- CSS ---")
print(s[i:min(i+2600, j)] if i >= 0 else "no .slider CSS")
# slider HTML
k = s.find('id="personalitySlider"')
if k < 0:
    k = s.find('class="slider"')
print("--- HTML ---")
print(s[k-200:k+1400] if k >= 0 else "no slider html")