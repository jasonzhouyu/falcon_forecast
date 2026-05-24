# ============================================================
# 中国完整猛禽名录 - 按迁徙行为分类
# ============================================================

# 1. 鹰形目 Accipitriformes

# 鹗科 Pandionidae
RAPTORS_PANDIONIDAE = {
    '鹗': {'thermal_req': 0.4, 'v_max': 48, 'behavior': '沿水域飞行，热力需求低', 'migration': '中距离迁徙'},
}

# 鹰科 - 蜂鹰/鸢/海雕类
RAPTORS_KITE_EAGLE = {
    '凤头蜂鹰': {'thermal_req': 0.9, 'v_max': 30, 'behavior': '集群形成热力柱，高空滑翔', 'migration': '长距离迁徙'},
    '栗鸢': {'thermal_req': 0.6, 'v_max': 35, 'behavior': '湿地活动，沿海迁徙', 'migration': '中距离迁徙'},
    '黑鸢': {'thermal_req': 0.5, 'v_max': 40, 'behavior': '利用热力盘旋，沿海分布', 'migration': '留鸟/漂泊'},
    '黑翅鸢': {'thermal_req': 0.5, 'v_max': 35, 'behavior': '开旷地低飞', 'migration': '留鸟'},
    '白尾海雕': {'thermal_req': 0.4, 'v_max': 50, 'behavior': '大型海雕，沿海岸线飞行', 'migration': '冬候鸟'},
    '虎头海雕': {'thermal_req': 0.4, 'v_max': 48, 'behavior': '大型海雕，沿海越冬', 'migration': '冬候鸟'},
    '玉带海雕': {'thermal_req': 0.4, 'v_max': 45, 'behavior': '内河沿海活动', 'migration': '冬候鸟'},
}

# 鹰科 - 秃鹫/兀鹫类
RAPTORS_VULTURE = {
    '胡兀鹫': {'thermal_req': 0.3, 'v_max': 50, 'behavior': '利用上升气流，长时间滑翔', 'migration': '垂直迁徙'},
    '白背兀鹫': {'thermal_req': 0.3, 'v_max': 45, 'behavior': '高山分布', 'migration': '留鸟'},
    '高山兀鹫': {'thermal_req': 0.2, 'v_max': 45, 'behavior': '高原食腐', 'migration': '留鸟'},
    '秃鹫': {'thermal_req': 0.3, 'v_max': 50, 'behavior': '利用上升气流，长时间滑翔', 'migration': '留鸟/漂泊'},
}

# 鹰科 - 鹞类 Circus
RAPTORS_HARRIER = {
    '白尾鹞': {'thermal_req': 0.5, 'v_max': 40, 'behavior': '开阔地低空飞行，偏好湿地', 'migration': '中距离迁徙'},
    '白头鹞': {'thermal_req': 0.5, 'v_max': 38, 'behavior': '草地/湿地低飞', 'migration': '迁徙'},
    '鹊鹞': {'thermal_req': 0.6, 'v_max': 38, 'behavior': '湿地生境，低空飞行觅食', 'migration': '迁徙'},
    '草原鹞': {'thermal_req': 0.5, 'v_max': 40, 'behavior': '开阔草原活动', 'migration': '迁徙'},
    '苍腹鹞': {'thermal_req': 0.5, 'v_max': 38, 'behavior': '亚洲东部特有', 'migration': '迁徙'},
    '灰鹞': {'thermal_req': 0.5, 'v_max': 38, 'behavior': '草原分布', 'migration': '迁徙'},
}

# 鹰科 - 鹰类 Accipiter
RAPTORS_HAWK = {
    '苍鹰': {'thermal_req': 0.6, 'v_max': 40, 'behavior': '森林边缘，高速穿梭', 'migration': '中距离迁徙'},
    '雀鹰': {'thermal_req': 0.6, 'v_max': 35, 'behavior': '快速穿插，灵活飞行', 'migration': '迁徙'},
    '松雀鹰': {'thermal_req': 0.7, 'v_max': 32, 'behavior': '快速穿插飞行，喜开阔地带', 'migration': '迁徙'},
    '赤腹鹰': {'thermal_req': 0.7, 'v_max': 35, 'behavior': '中等高度，松散集群', 'migration': '长距离迁徙'},
    '日本松雀鹰': {'thermal_req': 0.6, 'v_max': 38, 'behavior': '快速飞行，中等热力需求', 'migration': '迁徙'},
    '凤头苍鹰': {'thermal_req': 0.7, 'v_max': 35, 'behavior': '森林边缘活动', 'migration': '留鸟'},
}

# 鹰科 - 鵟类 Buteo
RAPTORS_BUTEO = {
    '普通鵟': {'thermal_req': 0.5, 'v_max': 42, 'behavior': '低空穿梭，利用地形升力', 'migration': '迁徙/漂泊'},
    '大鵟': {'thermal_req': 0.5, 'v_max': 44, 'behavior': '开阔地巡航，中等热力需求', 'migration': '冬候鸟'},
    '毛脚鵟': {'thermal_req': 0.5, 'v_max': 40, 'behavior': '北方繁殖，南下越冬', 'migration': '长距离迁徙'},
    '灰脸鵟鹰': {'thermal_req': 0.8, 'v_max': 40, 'behavior': '集群飞行，偏爱山脊线', 'migration': '迁徙高峰'},
    '栗翅鹰': {'thermal_req': 0.7, 'v_max': 35, 'behavior': '美洲传入，偶见', 'migration': '偶见'},
}

# 鹰科 - 雕类 Aquila
RAPTORS_EAGLE = {
    '金雕': {'thermal_req': 0.4, 'v_max': 50, 'behavior': '高空盘旋，利用热力柱', 'migration': '留鸟/漂泊'},
    '白肩雕': {'thermal_req': 0.4, 'v_max': 48, 'behavior': '草原分布，高空翱翔', 'migration': '迁徙'},
    '草原雕': {'thermal_req': 0.4, 'v_max': 45, 'behavior': '草原活动', 'migration': '迁徙'},
    '乌雕': {'thermal_req': 0.4, 'v_max': 45, 'behavior': '森林开阔地', 'migration': '迁徙'},
    '小雕': {'thermal_req': 0.4, 'v_max': 40, 'behavior': '小型雕类', 'migration': '留鸟'},
    '林雕': {'thermal_req': 0.7, 'v_max': 38, 'behavior': '高山飞行，利用地形波升力', 'migration': '留鸟'},
    '靴隼雕': {'thermal_req': 0.6, 'v_max': 35, 'behavior': '森林边缘', 'migration': '留鸟'},
    '蛇雕': {'thermal_req': 0.6, 'v_max': 45, 'behavior': '利用山脊动力，巡航高度较高', 'migration': '留鸟'},
    '褐冠鹃隼': {'thermal_req': 0.9, 'v_max': 28, 'behavior': '集群快速通过，不喜强风', 'migration': '迁徙'},
    '黑冠鹃隼': {'thermal_req': 1.0, 'v_max': 25, 'behavior': '集群快速通过，不喜强风', 'migration': '迁徙高峰'},
}

# 2. 隼形目 Falconiformes
RAPTORS_FALCON = {
    # 小型隼类
    '红隼': {'thermal_req': 0.4, 'v_max': 45, 'behavior': '振翅飞行，常见', 'migration': '留鸟/迁徙'},
    '红脚隼': {'thermal_req': 0.3, 'v_max': 48, 'behavior': '集群高速飞行，沿海岸线迁徙', 'migration': '迁徙量极大'},
    '阿穆尔隼': {'thermal_req': 0.4, 'v_max': 52, 'behavior': '集群高速飞行', 'migration': '迁徙高峰'},
    '燕隼': {'thermal_req': 0.3, 'v_max': 55, 'behavior': '高速直线飞行，少用热力', 'migration': '迁徙'},
    '灰背隼': {'thermal_req': 0.3, 'v_max': 50, 'behavior': '快速飞行', 'migration': '迁徙'},
    '黄爪隼': {'thermal_req': 0.3, 'v_max': 45, 'behavior': '干旱区分布', 'migration': '迁徙'},
    # 大型隼类
    '游隼': {'thermal_req': 0.2, 'v_max': 60, 'behavior': '高速俯冲捕食，沿海岸线飞行', 'migration': '迁徙'},
    '猎隼': {'thermal_req': 0.3, 'v_max': 55, 'behavior': '高速飞行，草原活动', 'migration': '冬候鸟'},
    '矛隼': {'thermal_req': 0.2, 'v_max': 50, 'behavior': '北方繁殖', 'migration': '冬候鸟'},
    '拟游隼': {'thermal_req': 0.2, 'v_max': 55, 'behavior': '近似游隼', 'migration': '偶见'},
}

# 3. 鸮形目 Strigiformes
RAPTORS_OWL = {
    # 草鸮科
    '草鸮': {'thermal_req': 0.2, 'v_max': 25, 'behavior': '夜间活动，草地生境', 'migration': '留鸟'},
    '栗鸮': {'thermal_req': 0.2, 'v_max': 25, 'behavior': '密林活动', 'migration': '留鸟'},
    # 鸱鸮科 - 大型
    '雕鸮': {'thermal_req': 0.2, 'v_max': 30, 'behavior': '夜间活动，大型', 'migration': '留鸟'},
    '雪鸮': {'thermal_req': 0.1, 'v_max': 30, 'behavior': '北极繁殖，冬候鸟', 'migration': '冬候鸟'},
    '林雕鸮': {'thermal_req': 0.2, 'v_max': 28, 'behavior': '森林夜行', 'migration': '留鸟'},
    '灰林鸮': {'thermal_req': 0.2, 'v_max': 25, 'behavior': '林地夜行', 'migration': '留鸟'},
    # 鸱鸮科 - 中小型
    '长耳鸮': {'thermal_req': 0.2, 'v_max': 25, 'behavior': '夜间迁徙，黄昏活动', 'migration': '迁徙'},
    '短耳鸮': {'thermal_req': 0.3, 'v_max': 30, 'behavior': '典型迁徙种，夜间', 'migration': '迁徙'},
    '领角鸮': {'thermal_req': 0.2, 'v_max': 22, 'behavior': '夜行，留鸟', 'migration': '留鸟'},
    '红角鸮': {'thermal_req': 0.2, 'v_max': 22, 'behavior': '夜行，夏季迁徙', 'migration': '夏候鸟'},
    '东方角鸮': {'thermal_req': 0.2, 'v_max': 22, 'behavior': '夜行', 'migration': '迁徙'},
    '纵纹腹小鸮': {'thermal_req': 0.2, 'v_max': 20, 'behavior': '小型夜行', 'migration': '留鸟'},
    '鹰鸮': {'thermal_req': 0.2, 'v_max': 28, 'behavior': '大型夜行', 'migration': '留鸟'},
    '斑头鸺鹠': {'thermal_req': 0.2, 'v_max': 20, 'behavior': '小型夜行', 'migration': '留鸟'},
    '领鸺鹠': {'thermal_req': 0.2, 'v_max': 18, 'behavior': '最小鸮类', 'migration': '留鸟'},
}

# ============================================================
# 合并所有猛禽
# ============================================================
ALL_RAPTORS = {}
ALL_RAPTORS.update(RAPTORS_PANDIONIDAE)
ALL_RAPTORS.update(RAPTORS_KITE_EAGLE)
ALL_RAPTORS.update(RAPTORS_VULTURE)
ALL_RAPTORS.update(RAPTORS_HARRIER)
ALL_RAPTORS.update(RAPTORS_HAWK)
ALL_RAPTORS.update(RAPTORS_BUTEO)
ALL_RAPTORS.update(RAPTORS_EAGLE)
ALL_RAPTORS.update(RAPTORS_FALCON)
ALL_RAPTORS.update(RAPTORS_OWL)

# 按迁徙权重分类
MIGRATION_WEIGHTS = {
    '高 (0.9-1.0)': ['凤头蜂鹰', '黑冠鹃隼', '阿穆尔隼', '灰脸鵟鹰'],
    '中 (0.6-0.8)': ['普通鵟', '赤腹鹰', '林雕', '日本松雀鹰', '灰脸鵟鹰'],
    '低 (0.2-0.4)': ['金雕', '秃鹫', '胡兀鹫', '游隼', '短耳鸮'],
}

print(f"共收录 {len(ALL_RAPTORS)} 种猛禽")
for cat, species_list in MIGRATION_WEIGHTS.items():
    print(f"  {cat}: {len(species_list)} 种")
