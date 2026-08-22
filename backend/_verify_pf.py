s = open(r'E:\智慧项目\portfolio-mfkagent\index.html', encoding='utf-8').read()
print('bytes:', len(s.encode('utf-8')), '| html closed:', s.strip().endswith('</html>'))
print('--- anonymous ---')
for bad in ['严志辉', '辉', '求职', '简历', '联系我', '姓名', '作者：']:
    print('  BAD', bad, ':', bad in s)
print('--- gallery ---')
for kw in ['作品 0', '作品0', 'masonry', 'grid', 'gallery', '瀑布', 'placeholder', '作品']:
    print('  ', kw, ':', s.count(kw))
print('--- case-study ---')
for kw in ['解决问题', '案例', '问题', '拆解', '方案', '结果', 'Case']:
    print('  ', kw, ':', s.count(kw))
print('--- slider P0/P1 ---')
for kw in ['translate3d', 'translateX(', 'getBoundingClientRect', 'pointerdown', 'PointerEvent', 'aria-valuenow',
           'role="slider"', 'scaleX', 'ArrowLeft', 'ArrowRight', 'resize']:
    print('  ', kw, ':', s.count(kw))
print('--- fonts/colors ---')
for kw in ['Inter', 'fonts.googleapis.com', '@import', '#12141C', '#EDE8E0', '#C0392B', 'prefers-reduced-motion']:
    print('  ', kw, ':', s.count(kw))
print('--- motion ---')
for kw in ['requestAnimationFrame', 'lerp', 'cursor', 'parallax', 'magnet', 'tilt', 'perspective']:
    print('  ', kw, ':', s.count(kw))