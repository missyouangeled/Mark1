export type Game = {
  slug: string;
  title: string;
  subtitle: string;
  category: string;
  rating: number;
  downloads: string;
  tag: string;
  hero: string;
  accentClass: string;
  summary: string;
  description: string;
  bullets: string[];
  update: string;
  studio: string;
  price: string;
  platforms: string[];
};

export const games: Game[] = [
  {
    slug: 'starfall-zero',
    title: 'Starfall Zero',
    subtitle: '在遗失轨道上重启文明火种',
    category: '动作冒险',
    rating: 9.5,
    downloads: '128 万预约',
    tag: '编辑精选',
    hero: '沉浸式星际探索 + 高强度战斗循环',
    accentClass: 'cover-art',
    summary: '一款以坠毁空间站为舞台的科幻动作冒险，强调流畅位移、轻 Roguelite 掉落和章节式叙事。',
    description: '你将扮演轨道回收员「Mira」，在漂移的空间残骸中寻找文明黑匣子。关卡围绕高低差、失重移动与短兵器连击设计，整体节奏偏爽快，剧情则通过环境演出和语音日志拼起来。',
    bullets: ['失重穿梭 + 钩索位移', '章节 Boss 演出完整', '支持 120Hz 高帧模式'],
    update: '今天 09:30 更新',
    studio: 'North Ember Studio',
    price: '免费试玩',
    platforms: ['iOS', 'Android', 'PC 串流']
  },
  {
    slug: 'echo-drifters',
    title: 'Echo Drifters',
    subtitle: '组队穿越被噪音吞没的城市',
    category: '多人共斗',
    rating: 9.2,
    downloads: '87 万关注',
    tag: '热门新作',
    hero: '近未来美术 + 四人异能协作',
    accentClass: 'cover-art alt-1',
    summary: '强调角色技能联动与潮流视觉包装的组队动作游戏。',
    description: '当整个城市被「噪音风暴」覆盖，只剩少数人还能听见彼此。玩家需要在街区战场中彼此搭配技能，争夺讯号塔，逐步夺回城市的听觉版图。',
    bullets: ['四职业异能互补', '街区 Boss 周常轮换', '时装与战斗动画风格统一'],
    update: '昨日 18:20 更新',
    studio: 'Velvet Current',
    price: '免费游玩',
    platforms: ['iOS', 'Android']
  },
  {
    slug: 'mech-haven',
    title: 'Mech Haven',
    subtitle: '把废土据点焊成你的钢铁王国',
    category: '策略经营',
    rating: 8.9,
    downloads: '46 万下载',
    tag: '社区高分',
    hero: '机甲拼装 + 基地经营 + PvE 远征',
    accentClass: 'cover-art alt-2',
    summary: '围绕机甲零件组合和据点经营展开的中重度策略作品。',
    description: '你可以从报废战场回收零件，重新焊接为探索机甲，并让不同模块影响战斗流派。游戏用较轻的生存压力提供持续经营驱动力，适合长线沉浸。',
    bullets: ['模块化机甲装配', '沙暴天气影响战局', '地图事件文本质量高'],
    update: '3 天前更新',
    studio: 'Forge Motel',
    price: '买断制 ¥30',
    platforms: ['PC', 'Steam Deck']
  },
  {
    slug: 'petal-blitz',
    title: 'Petal Blitz',
    subtitle: '霓虹花店白天营业，夜晚参加街头竞速',
    category: '叙事竞速',
    rating: 8.7,
    downloads: '31 万想玩',
    tag: '独立佳作',
    hero: '生活模拟外壳下的轻竞速叙事',
    accentClass: 'cover-art alt-3',
    summary: '用花店经营和街头竞速讲成长故事的轻叙事作品。',
    description: '白天是整理花束、和熟客聊天的小店主，夜晚则在高架桥和旧城区穿梭，靠赢下比赛支付店租。美术轻盈，故事有生活感，适合想找点节奏感又不想太肝的人。',
    bullets: ['昼夜玩法反差鲜明', '配乐完成度高', '剧情选项影响结局氛围'],
    update: '本周更新',
    studio: 'Moon Alley',
    price: '首发折扣 ¥18',
    platforms: ['PC', 'Nintendo Switch']
  }
];

export const featured = games[0];
export const trending = games.slice(1);
export const ranked = [...games].sort((a, b) => b.rating - a.rating);
