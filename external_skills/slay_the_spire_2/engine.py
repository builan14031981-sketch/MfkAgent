"""
STS2 Knowledge Engine: 提供闪电级检索、卡组协同分析与精准算杀数据
"""
import os
import json
import re

class STS2KnowledgeBase:
    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(__file__), 'knowledge')
        self.base_dir = base_dir
        
        self.cards = self._load_json('cards.json')
        self.powers = self._load_json('powers.json')
        self.relics = self._load_json('relics.json')
        self.potions = self._load_json('potions.json')
        self.monsters = self._load_json('monsters.json')
        
        # Build search index
        self.name_map = {}
        for db in [self.cards, self.powers, self.relics, self.potions]:
            for eid, item in db.items():
                name = item.get('name', '')
                clean_name = re.sub(r'[\s\-_+]', '', name).lower()
                self.name_map[eid.upper()] = item
                if name:
                    self.name_map[name] = item
                if clean_name:
                    self.name_map[clean_name] = item
        # Index monsters by id (class name) and loc_key
        for mid, item in self.monsters.items():
            self.name_map[mid.upper()] = item
            lk = item.get('loc_key', '')
            if lk:
                self.name_map[lk.upper()] = item
            self.name_map[mid] = item
            nzh = item.get('name_zh', '')
            if nzh:
                self.name_map[nzh] = item
                self.name_map[re.sub(r'[\s\-_+]', '', nzh).lower()] = item

    def _load_json(self, filename):
        path = os.path.join(self.base_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_monster(self, query):
        """查找怪物实体（支持 id / loc_key / 模糊名）"""
        q = re.sub(r'[\s\-_+]', '', query.strip()).lower()
        for key in (query.upper(), q.upper(), query, q):
            item = self.name_map.get(key)
            if isinstance(item, dict) and 'hp' in item:
                return item
        for key, item in self.name_map.items():
            if isinstance(item, dict) and 'hp' in item:
                if q in key.lower() or q in str(item.get('id', '')).lower():
                    return item
        return None

    def format_monster(self, m):
        """把怪物结构转成可读文本（含招式意图/伤害/格挡/状态）"""
        lines = []
        head = f"【{m.get('id')}】"
        if m.get('name_zh'):
            head += f" {m['name_zh']}"
        head += f"  类型:{m.get('type','normal')}"
        if m.get('loc_key'):
            head += f"  loc:{m['loc_key']}"
        lines.append(head)
        hp = m.get('hp', {})
        if hp:
            hpt = f"HP {hp.get('base')}"
            if hp.get('ascension_tough'):
                hpt += f" (强化难度 {hp.get('ascension_tough')})"
            lines.append("  " + hpt)
        moves = m.get('moves', [])
        cycle = m.get('move_cycle', [])
        for i, mv in enumerate(moves):
            tag = ""
            if mv.get('cycle_order') is not None:
                tag = f"[循环#{mv['cycle_order']}] "
            mname = f" {mv['name_zh']}" if mv.get('name_zh') else ""
            desc = []
            for it in mv.get('intents', []):
                t = it.get('type', '')
                a = it.get('args', [])
                if t == 'SingleAttackIntent':
                    desc.append(f"攻击{a[0] if a else '?'}")
                elif t == 'MultiAttackIntent':
                    dmg = a[0] if a else '?'; hits = a[1] if len(a) > 1 else '?'
                    desc.append(f"多段{a[0] if a else '?'}x{hits}")
                elif t == 'DefendIntent':
                    desc.append(f"防御(格挡{mv.get('block','?')})")
                elif t == 'BuffIntent':
                    desc.append("强化")
                elif t == 'DebuffIntent':
                    desc.append("减益")
                elif t == 'SleepIntent':
                    desc.append("休眠")
                else:
                    desc.append(t)
            extra = ""
            if mv.get('block') is not None:
                extra += f" 格挡{mv['block']}"
            if mv.get('statuses'):
                extra += " 施加:" + ",".join(f"{s['status']}({s['amount']})" for s in mv['statuses'])
            lines.append(f"  {tag}{mv.get('id')}{mname}: " + "/".join(desc) + extra)
        return "\n".join(lines)

    def monster_threat(self, m, turns=3, vulnerable=False):
        """计算怪物未来 N 回合的承伤威胁（用于算杀）"""
        moves_order = m.get('move_cycle') or [mv.get('id') for mv in m.get('moves', [])]
        mv_map = {mv['id']: mv for mv in m.get('moves', [])}
        vuln = 1.5 if vulnerable else 1.0
        per_turn = []
        total = 0
        n = len(moves_order)
        for t in range(turns):
            mid = moves_order[t % n] if n else None
            mv = mv_map.get(mid) if mid else None
            dmg = 0
            if mv:
                for it in mv.get('intents', []):
                    if it['type'] == 'SingleAttackIntent' and it.get('args'):
                        dmg += it['args'][0]
                    elif it['type'] == 'MultiAttackIntent' and it.get('args'):
                        dmg += it['args'][0] * (it['args'][1] if len(it['args']) > 1 else 1)
                dmg = int(dmg * vuln) if dmg else 0
            per_turn.append((mid, dmg, mv))
            total += dmg
        return per_turn, total

    def search(self, query, role=None, db_types=None):
        """全文检索（搜索名称、ID和描述，支持按角色筛选）"""
        q = query.strip().lower()
        role_key = self._parse_role(role) if role else None
        
        results = []
        dbs = []
        if not db_types:
            dbs = [('card', self.cards), ('relic', self.relics), ('potion', self.potions), ('power', self.powers)]
        else:
            for dt in db_types:
                if dt == 'card': dbs.append(('card', self.cards))
                elif dt == 'relic': dbs.append(('relic', self.relics))
                elif dt == 'potion': dbs.append(('potion', self.potions))
                elif dt == 'power': dbs.append(('power', self.powers))

        for category, db in dbs:
            for eid, item in db.items():
                if role_key and not self._match_role(eid, item, role_key):
                    continue
                name = item.get('name', '')
                desc = item.get('description', '')
                if q in name.lower() or q in eid.lower() or q in desc.lower():
                    results.append((category, item))
        return results

    def _parse_role(self, role):
        if not role: return None
        r = role.strip().lower()
        if r in ('ironclad', '铁甲战士', '战士', '红王'): return 'IRONCLAD'
        if r in ('silent', '静默猎手', '猎手', '绿娃'): return 'SILENT'
        if r in ('necrobinder', '骨王', '死灵法师', '死灵'): return 'NECROBINDER'
        if r in ('regent', '摄政王', '摄政'): return 'REGENT'
        if r in ('defect', '故障机器人', '机器人', '蓝罐'): return 'DEFECT'
        if r in ('watcher', '观者', '紫花'): return 'WATCHER'
        return r.upper()

    def _match_role(self, eid, item, role_key):
        eid_u = eid.upper()
        if role_key in eid_u:
            return True
        desc = item.get('description', '')
        if role_key in desc.upper():
            return True
        return False

    def list_items(self, category='card', role=None, limit=30):
        """按类别与角色列表呈现项"""
        role_key = self._parse_role(role) if role else None
        db_map = {'card': self.cards, 'relic': self.relics, 'potion': self.potions, 'power': self.powers}
        db = db_map.get(category, self.cards)
        
        items = []
        for eid, item in db.items():
            if role_key and not self._match_role(eid, item, role_key):
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return items

    def get_info(self, query):
        """精准查找单个卡牌/遗物/机制"""
        q = re.sub(r'[\s\-_+]', '', query.strip()).lower()
        if query.upper() in self.name_map:
            return self.name_map[query.upper()]
        if query in self.name_map:
            return self.name_map[query]
        if q in self.name_map:
            return self.name_map[q]
            
        # 模糊子串查找
        matches = []
        for key, item in self.name_map.items():
            name = item.get('name', '')
            if q in name.lower() or q in item.get('id', '').lower():
                if item not in matches:
                    matches.append(item)
        return matches

if __name__ == '__main__':
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    kb = STS2KnowledgeBase()
    if len(sys.argv) < 2:
        print("用法:")
        print("  python engine.py <card|relic|potion|monster> <名称>")
        print("  python engine.py search <关键词> [角色名]")
        print("  python engine.py list <card|relic|potion> [角色名]")
        print("  python engine.py sim <怪物> <回合> [vuln]")
        sys.exit(1)
    cmd = sys.argv[1].lower()
    q = sys.argv[2] if len(sys.argv) > 2 else ""
    role = sys.argv[3] if len(sys.argv) > 3 else None

    if cmd == 'search':
        if not q:
            print("请输入搜索关键词")
            sys.exit(1)
        res = kb.search(q, role=role)
        if not res:
            print("未找到包含 '%s' 的数据" % q)
        else:
            print("🔍 检索到 %d 条包含 '%s' 的结果%s:" % (len(res), q, (" (角色: %s)" % role) if role else ""))
            for cat, item in res[:20]:
                print("  [%s] 【%s】(%s): %s" % (cat.upper(), item.get('name', '未命名'), item.get('id', ''), str(item.get('description', '')).replace('\n', ' ')))
    elif cmd == 'list':
        cat = q if q in ('card', 'relic', 'potion', 'power') else 'card'
        role = sys.argv[2] if len(sys.argv) > 2 and q not in ('card', 'relic', 'potion', 'power') else role
        items = kb.list_items(category=cat, role=role, limit=30)
        print("📋 分类列表 [%s]%s (共 %d 条):" % (cat.upper(), (" 角色:" + role) if role else "", len(items)))
        for item in items:
            print("  【%s】(%s): %s" % (item.get('name', '未命名'), item.get('id', ''), str(item.get('description', '')).replace('\n', ' ')))
    elif cmd == 'monster':
        m = kb.get_monster(q)
        print(kb.format_monster(m) if m else "未匹配到怪物: " + q)
    elif cmd in ('card', 'relic', 'potion'):
        r = kb.get_info(q)
        if isinstance(r, dict):
            print("【%s】(%s)\n%s" % (r.get('name'), r.get('id'), r.get('description', '')))
        elif isinstance(r, list) and r:
            for it in r[:5]:
                print("【%s】: %s" % (it.get('name'), str(it.get('description', ''))[:60]))
        else:
            print("未匹配: " + q)
    elif cmd == 'sim':
        turns = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 3
        vuln = ('vuln' in sys.argv[3:]) or ('易伤' in sys.argv[3:])
        m = kb.get_monster(q)
        if not m:
            print("未匹配到怪物: " + q)
            sys.exit(1)
        per, total = kb.monster_threat(m, turns=turns, vulnerable=vuln)
        print("【%s】未来 %d 回合威胁推演%s" % (m.get('id'), turns, "（易伤×1.5）" if vuln else ""))
        for t, (mid, dmg, mv) in enumerate(per, 1):
            note = ""
            if mv and mv.get('block') is not None:
                note += " 敌格挡%d" % mv['block']
            if mv and mv.get('statuses'):
                note += " 施加:" + ",".join("%s(%s)" % (s['status'], s['amount']) for s in mv['statuses'])
            print("  回合%d: %s → 承伤%d%s" % (t, mid, dmg, note))
        print("  📊 累计承伤:%d  →  建议保留格挡 ≥ %d 以零损过关" % (total, total))
    else:
        print("未知命令: " + cmd)
