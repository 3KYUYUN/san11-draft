# -*- coding: utf-8 -*-
"""
s11_engine.py — 三國志11 (繁中PK) PVP 進度產生引擎
以「空白地圖模版」為底，依設定寫入勢力、武將、城市與資源，輸出可直接遊玩的劇本檔。

全部偏移量皆由差分分析（樣本01/02/03）與 Scen008 交叉驗證取得，詳見 格式偏移表.md
"""
import csv
import json
import os
import struct

from s11lib import (
    OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT,
    load_scenario, parse_officers,
)

# ── 勢力區 ──────────────────────────────────────────────
FORCE_BASE   = 0x25454   # 勢力0 記錄起點
FORCE_STRIDE = 0x48      # 72 bytes / 勢力
FORCE_MAX    = 42        # 一般勢力槽位數（42 之後為異民族/賊）
F_LORD   = 0x00          # 君主武將編號 u16（無=FFFF）
F_RANK   = 0x33          # 爵位（00=皇帝…09=無，預設 09）
F_COLOR  = 0x34          # 旗色（FF=依勢力編號自動；引擎預設=勢力編號以確保區別）
F_TITLE  = 0x35          # 國號索引（實際劇本均=勢力編號；相同會造成勢力連動！）
F_TECHP  = 0x3E          # 技巧P u16【實驗性：偏移待遊戲內驗證】
F_TECH   = 0x40          # 技巧遮罩 5 bytes：bit = 列*4+(級-1)
# 列順序：槍兵 戟兵 弩兵 騎兵 鍊兵 發明 防衛 火攻 內政（以公孫瓚三騎科技等錨點證實）
TECH_ROWS = [
    ('槍兵', ['鍛鍊槍兵', '襲擊兵糧', '奇襲', '精銳槍兵']),
    ('戟兵', ['鍛鍊戟兵', '箭盾', '大盾', '精銳戟兵']),
    ('弩兵', ['鍛鍊弩兵', '還射', '強弩', '精銳弩兵']),
    ('騎兵', ['鍛鍊騎兵', '出產良馬', '騎射', '精銳騎兵']),
    ('鍊兵', ['熟鍊兵', '難所行軍', '軍制改革', '雲梯']),
    ('發明', ['強化車軸', '石造建築', '開發投石', '霹靂']),
    ('防衛', ['培訓工兵', '強化設施', '強化城牆', '強化防衛']),
    ('火攻', ['開發木獸', '神火計', '鍊成火藥', '鍊成炸藥']),
    ('內政', ['木牛流馬', '擴展港關', '整備政令', '掌握人心']),
]
TECH_BITS = {name: r*4+l for r, (_, names) in enumerate(TECH_ROWS) for l, name in enumerate(names)}
PVP_BAN = ('霹靂', '鍊成火藥', '鍊成炸藥')

# ── 軍團區 ──────────────────────────────────────────────
ARMY_BASE   = 0x2618C    # 軍團0 記錄起點
ARMY_STRIDE = 8
A_FORCE = 0x00           # 所屬勢力 u8
A_LORD  = 0x02           # 軍團長 u16（設為君主）

# ── 都市區 ──────────────────────────────────────────────
CITY_ANCHOR0 = 0x26305   # 城市0 的「士兵上限」u32 位置
CITY_STRIDE  = 81
CITY_COUNT   = 42
C_OWNER  = -1            # 所屬勢力 u8（FF=空白地）
C_CAP    = 0             # 士兵上限 u32（模版全城 150000 = 大都市）
C_TROOP  = 4             # 士兵 u32
C_GOLD   = 8             # 金 u32
C_FOOD   = 12            # 糧 u32
C_SPEAR, C_HALBERD, C_BOW, C_HORSE = 20, 24, 28, 32          # 槍/戟/弩/軍馬 u32
C_RAM, C_TOWER, C_CATAPULT, C_BEAST = 36, 40, 44, 48         # 衝車/井闌/投石/木獸 u32
C_BOAT, C_JUNK, C_WARSHIP = 52, 56, 60                       # 走舸/樓船/鬥艦 u32

# ── 武將記錄欄位 ────────────────────────────────────────
O_FORCE   = 0x5F         # 所屬勢力 u8（FF=無）
O_CITY    = 0x60         # 所在都市 u16
O_WORK    = 0x62         # 勤務地 u16（與所在相同）
O_IDENT   = 0x64         # 身分：0=君主 1=都督 3=一般 4/6=在野 FF=未登場
O_LOYALTY = 0x68         # 忠誠 u8

IDENT_LORD, IDENT_GENERAL = 0x00, 0x03

# ── 武將能力/屬性欄位（由 761 筆真值機械探勘，吻合率 97~100%）──
O_FEMALE  = 0x37         # 女=1 男=0
O_DEBUT   = 0x38         # 登場年 u16
O_BIRTH   = 0x3A         # 生年 u16
O_DEATH   = 0x3C         # 歿年 u16
O_BLOOD   = 0x3F         # 血緣 u16（=自身編號）
O_AFFI    = 0x4A         # 相性
O_APT     = 0x6B         # 適性 槍戟弩騎兵水 u8×6（0=C 1=B 2=A 3=S）
O_STATS   = 0x71         # 統武智政魅 u8×5
O_SKILL   = 0x7C         # 特技編號（FF=無）
RESERVED_SLOTS = list(range(832, 850))   # 空白保留欄位「古代３３～５０」
CLEAN_SLOT = 832                          # 純淨記錄底板

# 複姓表（姓名拆分用）
COMPOUND_SURNAMES = ('歐陽','司馬','諸葛','夏侯','公孫','皇甫','長孫','公輸',
                     '東方','西門','上官','尉遲','令狐','太史','淳于','鍾離',
                     '南宮','申屠','呼延','徐周')

def split_name(fullname):
    """姓名 → (姓, 名)，姓/名各最多 2 個 Big5 字（欄位 5 bytes）。"""
    if len(fullname) >= 4:
        return fullname[:2], fullname[2:4]
    if len(fullname) == 3:
        if fullname[:2] in COMPOUND_SURNAMES:
            return fullname[:2], fullname[2:]
        return fullname[:1], fullname[1:]
    if len(fullname) == 2:
        return fullname[:1], fullname[1:]
    return fullname, ''

# ── 檔頭：劇本名稱／介紹／年月 ──────────────────────────
H_TITLE, H_TITLE_LEN = 0x5F, 17     # 劇本名 Big5（最多8字）
H_INTRO, H_INTRO_LEN = 0x70, 363    # 劇本介紹 Big5
H_YEAR  = 0x5B                      # 年 u16
H_MONTH = 0x5D                      # 月 u8
F_DESC, F_DESC_LEN = 0x2AE, 0x171   # 勢力解說 Big5：base + 勢力編號×369
# （以 SCEN001~007 驗證：反董卓190/1、官渡200/1、英雄集結251/1 全數吻合）

# ── 檔頭：劇本選擇畫面預覽陣列 ──────────────────────────
# 0x1DB 起共 42 bytes，每 byte = 該城所屬勢力的「國號索引」(勢力+0x35)，FF=空白地
# （Scen008 驗證：襄平=公孫度國號0x0C、晉陽=張楊國號0x1E 全數吻合）
PREVIEW_BASE = 0x1DB

# ── 城市編號對照（依 11 個錨點推導；※=待遊戲內驗證）────
CITY_IDS = {
    '襄平': 0, '北平': 1, '薊': 2, '南皮': 3, '平原': 4, '晉陽': 5, '鄴': 6,
    '北海': 7, '下邳': 8, '小沛': 9, '壽春': 10, '濮陽': 11, '陳留': 12,
    '許昌': 13, '汝南': 14, '洛陽': 15, '宛': 16, '長安': 17, '上庸': 18,
    '安定': 19, '天水': 20, '武威': 21, '建業': 22, '吳': 23, '會稽': 24,
    '廬江': 25, '柴桑': 26, '江夏': 27, '新野': 28, '襄陽': 29, '江陵': 30,
    '長沙': 31, '武陵': 32, '桂陽': 33, '零陵': 34, '永安': 35, '漢中': 36,
    '梓潼': 37, '江州': 38, '成都': 39, '建寧': 40, '雲南': 41,
}
CITY_NAMES = {v: k for k, v in CITY_IDS.items()}
# 錨點驗證等級：硬錨點（樣本檔直接證實）
CITY_CONFIRMED = set(CITY_IDS)  # 已由遊戲全域檔 Scenario.s11 機械驗證全表

# 資源範圍（依需求規格）
LIMITS = {
    '士兵': (0, 150000), '金': (0, 99999), '糧': (0, 999999),
    '槍': (0, 100000), '戟': (0, 100000), '弩': (0, 100000), '軍馬': (0, 100000),
    '衝車': (0, 100), '井闌': (0, 100), '投石': (0, 100), '木獸': (0, 100),
    '走舸': (0, 100), '樓船': (0, 100), '鬥艦': (0, 100),
    '忠誠': (0, 255),
}
RESOURCE_FIELDS = {
    '士兵': C_TROOP, '金': C_GOLD, '糧': C_FOOD,
    '槍': C_SPEAR, '戟': C_HALBERD, '弩': C_BOW, '軍馬': C_HORSE,
    '衝車': C_RAM, '井闌': C_TOWER, '投石': C_CATAPULT, '木獸': C_BEAST,
    '走舸': C_BOAT, '樓船': C_JUNK, '鬥艦': C_WARSHIP,
}


class BuildError(Exception):
    pass


def tech_mask(spec):
    """'全滿' | 'PVP' | '無' | 科技名列表 → 5-byte 遮罩（None=不寫）"""
    if spec is None:
        return None
    names = None
    if isinstance(spec, str):
        s = spec.strip()
        if s in ('', '無', '不設定'):
            return None
        if s == '全滿':
            names = list(TECH_BITS)
        elif s in ('PVP', 'PVP慣例'):
            names = [n for n in TECH_BITS if n not in PVP_BAN]
        else:
            import re as _re
            names = [t for t in _re.split(r'[\s、,，;；]+', s) if t]
    else:
        names = list(spec)
    mask = bytearray(5)
    for n in names:
        if n not in TECH_BITS:
            raise BuildError('科技表中找不到: %s' % n)
        b = TECH_BITS[n]
        mask[b >> 3] |= 1 << (b & 7)
    return bytes(mask)


class CustomRoster:
    """自訂武將庫（自訂武將.csv + 特技表.json）。"""

    def __init__(self, csv_path='自訂武將.csv', skill_path='特技表.json'):
        self.by_name = {}
        self.skills = {}
        if os.path.exists(skill_path):
            with open(skill_path, encoding='utf-8') as f:
                self.skills = json.load(f)
        if os.path.exists(csv_path):
            with open(csv_path, encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    self.by_name[row['姓名'].strip()] = row

    def get(self, name):
        return self.by_name.get(name.strip())

    @staticmethod
    def parse_token(token):
        """「瑜瑜[火神]」→ ('瑜瑜', '火神')；「關羽」→ ('關羽', None)"""
        token = token.strip()
        if token.endswith(']') and '[' in token:
            name, skill = token[:-1].split('[', 1)
            return name.strip(), skill.strip()
        return token, None

    def skill_id(self, name):
        if not name:
            return 0xFF
        if name not in self.skills:
            raise BuildError('特技表中找不到特技: %s' % name)
        return self.skills[name]


class NameIndex:
    """武將名 → 編號。同名武將須用「名字(字)」或 #編號 指名。"""

    def __init__(self, officers):
        self.officers = officers
        self.by_name = {}
        for o in officers:
            if o.fullname and not o.fullname.startswith('古代'):
                self.by_name.setdefault(o.fullname, []).append(o)

    def resolve(self, token):
        token = token.strip()
        if token.endswith(']') and '[' in token:
            token = token[:token.index('[')].strip()
        if not token:
            return None
        if token.startswith('#'):                      # 直接指定編號
            oid = int(token[1:])
            if not 0 <= oid < OFFICER_COUNT:
                raise BuildError('武將編號超出範圍: %s' % token)
            return self.officers[oid]
        name, courtesy = token, None
        if '(' in token and token.endswith(')'):        # 名字(字) 消歧義
            name, courtesy = token[:-1].split('(', 1)
        cands = self.by_name.get(name.strip())
        if not cands:
            raise BuildError('找不到武將: %s' % token)
        if courtesy is not None:
            cands = [o for o in cands if o.courtesy == courtesy.strip()]
            if not cands:
                raise BuildError('找不到 %s（字不符）' % token)
        if len(cands) > 1:
            opts = '、'.join('%s(%s)#%d' % (o.fullname, o.courtesy or '無字', o.oid) for o in cands)
            raise BuildError('同名武將請指名: %s → %s' % (name, opts))
        return cands[0]


def resolve_city(token):
    token = str(token).strip()
    if token.isdigit():
        cid = int(token)
        if not 0 <= cid < CITY_COUNT:
            raise BuildError('城市編號超出範圍: %s' % token)
        return cid
    if token not in CITY_IDS:
        raise BuildError('找不到城市: %s（可用城市: %s）' % (token, '、'.join(CITY_IDS)))
    return CITY_IDS[token]


def check_range(key, value):
    lo, hi = LIMITS[key]
    if not lo <= value <= hi:
        raise BuildError('%s=%d 超出範圍 %d~%d' % (key, value, lo, hi))
    return value


class ScenarioBuilder:
    def __init__(self, template_path):
        self.data = bytearray(load_scenario(template_path))
        self.officers = parse_officers(bytes(self.data))
        self.names = NameIndex(self.officers)
        self.roster = CustomRoster()
        # 清空模版殘留的全部勢力解說（42 格）
        self.data[F_DESC:F_DESC + 42 * F_DESC_LEN] = bytes(42 * F_DESC_LEN)
        self.assigned = {}          # oid -> 勢力編號（重複指派檢查）
        self.city_owner = {}        # cid -> 勢力編號
        self.forces = []            # (force_id, lord_officer, [(city, [officers])])

    # ---- 寫入原語 ----
    def _off_officer(self, oid):
        return OFFICER_BASE + oid * OFFICER_STRIDE

    def _off_city(self, cid):
        return CITY_ANCHOR0 + cid * CITY_STRIDE

    def write_custom(self, rec, slot, skill_override=None):
        """把自訂武將寫入指定欄位。以 #832 純淨記錄為底板。"""
        base = self._off_officer(slot)
        clean = bytes(self.data[self._off_officer(CLEAN_SLOT):
                                self._off_officer(CLEAN_SLOT) + OFFICER_STRIDE])
        self.data[base:base + OFFICER_STRIDE] = clean
        surname, given = split_name(rec['姓名'])
        sb = surname.encode('big5')[:5]
        gb = given.encode('big5')[:5]
        self.data[base:base+5] = sb + b'\x00' * (5 - len(sb))
        self.data[base+5:base+10] = gb + b'\x00' * (5 - len(gb))
        self.data[base+10:base+16] = b'\x00' * 6          # 字：留空
        self.data[base + O_FEMALE] = int(rec.get('女') or 0)
        struct.pack_into('<H', self.data, base + O_DEBUT, 221)   # 登場 221
        struct.pack_into('<H', self.data, base + O_BIRTH, 205)   # 生 205
        struct.pack_into('<H', self.data, base + O_DEATH, 299)   # 歿 299（確保 251 開局存活）
        struct.pack_into('<H', self.data, base + O_BLOOD, slot)  # 血緣=自身
        self.data[base + O_AFFI] = min(150, int(rec.get('相性') or 100))
        for i, key in enumerate(('槍', '戟', '弩', '騎', '兵', '水')):
            self.data[base + O_APT + i] = max(0, min(3, int(rec.get(key) or 0)))
        for i, key in enumerate(('統率', '武力', '智力', '政治', '魅力')):
            self.data[base + O_STATS + i] = max(1, min(120, int(rec.get(key) or 50)))
        self.data[base + O_SKILL] = self.roster.skill_id(
            skill_override if skill_override else rec.get('特技', ''))
        # 更新解析快取與名稱索引
        self.officers = parse_officers(bytes(self.data))
        self.names = NameIndex(self.officers)
        return self.officers[slot]

    def allocate_customs(self, custom_specs, referenced_oids):
        """為自訂武將分配欄位：優先保留欄位 832~849，不足則回收
        「沒被任何勢力選用」且能力總和最低的一般武將欄位。"""
        free = [s for s in RESERVED_SLOTS]
        if len(custom_specs) > len(free):
            pool = []
            for o in self.officers:
                if o.oid in referenced_oids or o.oid >= 800:
                    continue
                if not o.fullname:
                    continue
                pool.append((sum(o.raw[O_STATS:O_STATS+5]), o.oid))
            pool.sort()
            free += [oid for _, oid in pool]
        if len(custom_specs) > len(free):
            raise BuildError('自訂武將 %d 名，可用欄位不足' % len(custom_specs))
        placed = {}
        for i, (name, skill) in enumerate(custom_specs):
            rec = self.roster.get(name)
            if rec is None:
                raise BuildError('找不到武將: %s（也不在自訂武將.csv 中）' % name)
            slot = free[i]
            self.write_custom(rec, slot, skill)
            placed[name] = (slot, skill)
        if placed:
            print('自訂武將已寫入: ' + '、'.join(
                '%s→#%d%s%s' % (n, s, '(%s)' % sk if sk else '',
                                '(回收欄位)' if s not in RESERVED_SLOTS else '')
                for n, (s, sk) in placed.items()))
        return placed

    def set_officer(self, officer, force_id, city_id, ident, loyalty=None):
        if officer.oid in self.assigned:
            raise BuildError('%s(#%d) 被重複指派（勢力%d 與 勢力%d）'
                             % (officer.fullname, officer.oid,
                                self.assigned[officer.oid], force_id))
        self.assigned[officer.oid] = force_id
        base = self._off_officer(officer.oid)
        self.data[base + O_FORCE] = force_id
        struct.pack_into('<H', self.data, base + O_CITY, city_id)
        struct.pack_into('<H', self.data, base + O_WORK, city_id)
        self.data[base + O_IDENT] = ident
        if loyalty is not None:
            self.data[base + O_LOYALTY] = check_range('忠誠', loyalty)

    def create_force(self, force_id, lord, home_city, color=None, title=None,
                     techs=None, tech_p=0, desc=None):
        if not 0 <= force_id < FORCE_MAX:
            raise BuildError('勢力編號 %d 超出 0~%d' % (force_id, FORCE_MAX - 1))
        base = FORCE_BASE + force_id * FORCE_STRIDE
        struct.pack_into('<H', self.data, base + F_LORD, lord.oid)
        self.data[base + F_RANK] = 0x09
        # 旗色與國號預設=勢力編號：確保每個勢力獨立配色、避免國號共用造成框選連動
        self.data[base + F_COLOR] = force_id if color is None else int(color)
        self.data[base + F_TITLE] = force_id if title is None else int(title)
        # 勢力介紹（含清除模版殘留文字）
        if desc is not None:
            b = desc.encode('big5')
            if len(b) > F_DESC_LEN - 1:
                raise BuildError('勢力介紹過長（最多約 184 個中文字）')
            off = F_DESC + force_id * F_DESC_LEN
            self.data[off:off + F_DESC_LEN] = b + b'\x00' * (F_DESC_LEN - len(b))
        if techs:
            self.data[base + F_TECH:base + F_TECH + 5] = techs
        if tech_p:
            struct.pack_into('<H', self.data, base + F_TECHP,
                             max(0, min(65535, int(tech_p))))
        # 軍團：每個勢力建立第一軍團，軍團長=君主（San11Editor 相同行為）
        abase = ARMY_BASE + force_id * ARMY_STRIDE
        self.data[abase + A_FORCE] = force_id
        struct.pack_into('<H', self.data, abase + A_LORD, lord.oid)

    def set_city(self, city_id, force_id, resources):
        if city_id in self.city_owner:
            raise BuildError('城市 %s 被重複指派（勢力%d 與 勢力%d）'
                             % (CITY_NAMES.get(city_id, city_id),
                                self.city_owner[city_id], force_id))
        self.city_owner[city_id] = force_id
        base = self._off_city(city_id)
        self.data[base + C_OWNER] = force_id
        # 劇本選擇畫面預覽：寫入該勢力的國號索引
        fbase = FORCE_BASE + force_id * FORCE_STRIDE
        self.data[PREVIEW_BASE + city_id] = self.data[fbase + F_TITLE]
        cap = struct.unpack_from('<I', self.data, base + C_CAP)[0]
        for key, value in resources.items():
            value = check_range(key, int(value))
            if key == '士兵' and value > cap:
                raise BuildError('%s 士兵 %d 超過該城上限 %d'
                                 % (CITY_NAMES.get(city_id, city_id), value, cap))
            struct.pack_into('<I', self.data, base + RESOURCE_FIELDS[key], value)

    # ---- 高階流程 ----
    def add_force(self, force_id, lord_token, city_groups, loyalty, resources,
                  color=None, title=None, techs=None, tech_p=0, desc=None):
        """city_groups = [(城市token, [武將token, ...]), ...]，第一組為本據。"""
        lord = self.names.resolve(lord_token)
        cities = [(resolve_city(c), members) for c, members in city_groups]
        home_city = cities[0][0]
        self.create_force(force_id, lord, home_city, color, title, techs, tech_p, desc)
        self.set_officer(lord, force_id, home_city, IDENT_LORD, loyalty)
        roster = []
        for cid, members in cities:
            self.set_city(cid, force_id, resources)
            placed = []
            for token in members:
                o = self.names.resolve(token)
                if o is None:
                    continue
                if o.oid == lord.oid:
                    continue  # 君主已放在本據
                self.set_officer(o, force_id, cid, IDENT_GENERAL, loyalty)
                placed.append(o)
            roster.append((cid, placed))
        self.forces.append((force_id, lord, roster))

    def summary(self):
        lines = []
        for fid, lord, roster in self.forces:
            total = sum(len(p) for _, p in roster) + 1
            lines.append('勢力%d 君主:%s(#%d) 共%d人' % (fid, lord.fullname, lord.oid, total))
            for cid, placed in roster:
                mark = '' if CITY_NAMES.get(cid, '?') in CITY_CONFIRMED else '※'
                lines.append('  %s%s(城%d): %s' % (
                    CITY_NAMES.get(cid, '城%d' % cid), mark, cid,
                    '、'.join(o.fullname for o in placed) or '(僅君主)'))
        return '\n'.join(lines)

    def restore_vanilla_cities(self, json_path='原版城市資料.json'):
        """城市規模=遊戲預設：回填原版每城靜態區與士兵上限（含 8 大都市與城市特色）"""
        import json as _json
        with open(json_path) as f:
            vanilla = _json.load(f)
        for c, (hexs, cap) in enumerate(vanilla):
            a = CITY_ANCHOR0 + c * CITY_STRIDE
            self.data[a - 17:a - 1] = bytes.fromhex(hexs)
            struct.pack_into('<I', self.data, a, cap)

    def set_title(self, name=None, intro=None, year=None, month=None):
        if name is not None:
            b = name.encode('big5')
            if len(b) > H_TITLE_LEN - 1:
                raise BuildError('劇本名過長（最多 8 個中文字）: %s' % name)
            self.data[H_TITLE:H_TITLE + H_TITLE_LEN] = b + b'\x00' * (H_TITLE_LEN - len(b))
        if intro is not None:
            b = intro.encode('big5')
            if len(b) > H_INTRO_LEN - 1:
                raise BuildError('劇本介紹過長（最多約 180 個中文字）')
            self.data[H_INTRO:H_INTRO + H_INTRO_LEN] = b + b'\x00' * (H_INTRO_LEN - len(b))
        if year is not None:
            struct.pack_into('<H', self.data, H_YEAR, int(year))
        if month is not None:
            self.data[H_MONTH] = max(1, min(12, int(month)))

    def save(self, path):
        with open(path, 'wb') as f:
            f.write(bytes(self.data))
