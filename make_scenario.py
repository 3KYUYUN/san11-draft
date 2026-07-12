# -*- coding: utf-8 -*-
"""
make_scenario.py — 三國志11 PVP 進度產生器（命令列）

用法：
    python3 make_scenario.py 設定檔.txt

設定檔為 INI 格式（見 設定檔範例.txt）：
    [全域]     模版 / 輸出 / 資源預設值（士兵 金 糧 槍 戟 弩 軍馬 衝車 井闌
               投石 木獸 走舸 樓船 鬥艦）/ 忠誠
    [勢力N]    君主 / 城市 / 武將 / 城市2 / 武將2 ... / 旗色 / 國號
               另可覆寫任何全域資源值（例如該勢力士兵較多）

武將名單以空白、頓號、逗號或換行分隔。
同名武將用「馬忠(德信)」或「#514」指名。城市可用名稱或編號（0~41）。
"""
import configparser
import re
import sys

from s11_engine import ScenarioBuilder, BuildError, RESOURCE_FIELDS, check_range, tech_mask

SPLIT = re.compile(r'[\s、,，;；]+')


def parse_members(raw):
    return [t for t in SPLIT.split(raw or '') if t]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cfg = configparser.ConfigParser()
    with open(sys.argv[1], encoding='utf-8-sig') as f:
        cfg.read_file(f)

    if '全域' not in cfg:
        raise BuildError('設定檔缺少 [全域] 區段')
    g = cfg['全域']
    template = g.get('模版', 'Scen015 - 空白地圖模版.s11')
    output = g.get('輸出', '輸出劇本.s11')
    loyalty_default = int(g.get('忠誠', 100))
    check_range('忠誠', loyalty_default)

    res_default = {}
    for key in RESOURCE_FIELDS:
        if key in g:
            res_default[key] = check_range(key, int(g[key]))

    builder = ScenarioBuilder(template)
    if g.get('城市規模', '').strip() in ('遊戲預設', '有城市特色', '預設'):
        builder.restore_vanilla_cities()
    techs = tech_mask(g.get('科技'))
    tech_p = int(g.get('技巧P', 0))
    builder.set_title(
        name=g.get('劇本名'), intro=g.get('劇本介紹'),
        year=g.get('年'), month=g.get('月'))

    force_sections = [s for s in cfg.sections() if s.startswith('勢力')]

    # ── 第一遍：掃描全部武將名單，找出自訂武將並分配欄位 ──
    all_tokens = []
    for sec in force_sections:
        s = cfg[sec]
        if '君主' in s:
            all_tokens.append(s['君主'].strip())
        all_tokens += parse_members(s.get('武將', ''))
        n = 2
        while ('武將%d' % n) in s:
            all_tokens += parse_members(s['武將%d' % n])
            n += 1
    referenced, customs, seen = set(), [], set()
    for tok in all_tokens:
        name, skill = builder.roster.parse_token(tok)
        try:
            o = builder.names.resolve(name)
            if o is not None:
                referenced.add(o.oid)
                continue
        except BuildError:
            pass
        if builder.roster.get(name):
            if name not in seen:
                seen.add(name)
                customs.append((name, skill))
        else:
            raise BuildError('找不到武將: %s' % tok)
    if customs:
        builder.allocate_customs(customs, referenced)
    if not force_sections:
        raise BuildError('設定檔中沒有任何 [勢力N] 區段')
    if len(force_sections) > 15:
        raise BuildError('勢力數 %d 超過上限 15' % len(force_sections))

    for idx, sec in enumerate(force_sections):
        s = cfg[sec]
        if '君主' not in s:
            raise BuildError('[%s] 缺少 君主' % sec)
        if '城市' not in s:
            raise BuildError('[%s] 缺少 城市' % sec)

        resources = dict(res_default)
        for key in RESOURCE_FIELDS:
            if key in s:
                resources[key] = check_range(key, int(s[key]))
        loyalty = int(s.get('忠誠', loyalty_default))

        # 城市 / 武將、城市2 / 武將2、城市3 / 武將3 ...
        groups = [(s['城市'], parse_members(s.get('武將', '')))]
        n = 2
        while ('城市%d' % n) in s:
            groups.append((s['城市%d' % n], parse_members(s.get('武將%d' % n, ''))))
            n += 1

        builder.add_force(
            force_id=idx,
            lord_token=s['君主'],
            city_groups=groups,
            loyalty=loyalty,
            resources=resources,
            color=s.get('旗色'),
            title=s.get('國號'),
            techs=tech_mask(s['科技']) if '科技' in s else techs,
            tech_p=int(s.get('技巧P', tech_p)),
            desc=s.get('介紹'),
        )

    builder.save(output)
    print('已輸出：%s\n' % output)
    print(builder.summary())


if __name__ == '__main__':
    try:
        main()
    except BuildError as e:
        print('設定錯誤：%s' % e)
        sys.exit(2)
